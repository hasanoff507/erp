"""Purchase orders (19 §10, US-M07-01, QT-M07-01, BO-04 «Xaridnomalar»).

``POST`` creates a ``draft`` (no number); ``send`` moves it to ``sent`` and assigns the ``Z-…``
number (12 §2.9) — the number is taken when the order leaves draft, like every other document gets
it on posting, so abandoned drafts never burn numbers. ``PATCH`` works only in ``draft``/``sent``;
``cancel`` in ``draft``/``sent``/``partially_received``. ``closed`` is final
(``409 PURCHASE_ORDER_CLOSED``). ``partially_received``/``closed`` are written only by goods receipts
(:class:`app.modules.purchasing.application.po_receipts.PurchaseOrderReceipts`).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money_str, price_str, qty_str
from app.core.permissions import BranchScope
from app.modules.debts.application.counterparties import CounterpartyDirectory
from app.modules.purchasing.application.ports import PoFilter, PurchaseOrderRepository
from app.modules.purchasing.domain.purchase_orders import (
    CANCELLABLE,
    EDITABLE,
    MAX_LINES,
    PurchaseOrder,
    line_amount,
    received_lines,
)

DOC_TABLE: Final = "purchase_orders"


@dataclass(frozen=True, slots=True)
class PoLineInput:
    product_id: UUID
    qty: Decimal
    price: Decimal | None


@dataclass(frozen=True, slots=True)
class PoInput:
    supplier_id: UUID
    warehouse_id: UUID
    doc_date: date
    lines: Sequence[PoLineInput]
    comment: str | None = None


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "purchase_order"})


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _money(value: Decimal | None) -> str | None:
    return None if value is None else money_str(value)


def po_header_json(po: PurchaseOrder) -> dict[str, Any]:
    return {
        "id": str(po.id),
        "number": po.number,
        "status": po.status,
        "doc_date": po.doc_date.isoformat(),
        "branch_id": str(po.branch_id),
        "warehouse_id": str(po.warehouse_id),
        "supplier_id": str(po.supplier_id),
        "supplier": {"id": str(po.supplier_id), "name": po.supplier_name, "stir": po.supplier_stir},
        "comment": po.comment,
        "total": _money(po.total),
        "line_count": po.line_count,
        "created_by": str(po.created_by),
        "created_by_name": po.created_by_name,
        "created_at": _ts(po.created_at),
        "updated_at": _ts(po.updated_at),
        "sent_at": _ts(po.sent_at),
        "cancelled_at": _ts(po.cancelled_at),
        "cancel_reason": po.cancel_reason,
    }


def po_json(po: PurchaseOrder, received: Mapping[UUID, Decimal]) -> dict[str, Any]:
    lines = []
    for line in po.lines:
        amount = line_amount(line.qty, line.price)
        lines.append(
            {
                "id": str(line.id),
                "line_no": line.line_no,
                "product_id": str(line.product_id),
                "product_name": line.product_name,
                "unit_code": line.unit_code,
                "qty": qty_str(line.qty),
                "price": None if line.price is None else price_str(line.price),
                "amount": _money(amount),
            }
        )
    return po_header_json(po) | {
        "lines": lines,
        "received_lines": [
            {
                "product_id": str(r.product_id),
                "ordered_qty": qty_str(r.ordered_qty),
                "received_qty": qty_str(r.received_qty),
            }
            for r in received_lines(po.lines, received)
        ],
    }


def _encode_cursor(created_at: datetime, po_id: UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(po_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


_CURSOR_MIN: Final = datetime(2000, 1, 1, tzinfo=UTC)
_CURSOR_MAX: Final = datetime(2100, 1, 1, tzinfo=UTC)


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """``[created_at, id]``; tz-aware and within 2000…2100 UTC, else ``validation.cursor_invalid``."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, pid = json.loads(raw)
        when = datetime.fromisoformat(at)
        if when.tzinfo is None or not _CURSOR_MIN <= when <= _CURSOR_MAX:
            raise ValueError("cursor instant out of range")
        return when.astimezone(UTC), UUID(pid)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def scope_branches(scope: BranchScope) -> tuple[UUID, ...] | None:
    """Branches a list may show: ``X-Branch-Id``, else the user's branches (``None`` = all)."""
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


def check_read_scope(scope: BranchScope, branch_id: UUID) -> None:
    if not scope.unrestricted and branch_id not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def _audit_lines(lines: Sequence[PoLineInput]) -> list[dict[str, str | None]]:
    return [
        {
            "product_id": str(ln.product_id),
            "qty": qty_str(ln.qty),
            "price": None if ln.price is None else str(ln.price),
        }
        for ln in lines
    ]


class PurchaseOrderService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: PurchaseOrderRepository,
        directory: CounterpartyDirectory,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._directory = directory

    # --- reads ------------------------------------------------------------------------------------
    async def list_page(
        self, actor: Principal, flt: PoFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = _decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_page(s, flt, after, limit + 1)
        page = rows[:limit]
        next_cursor = _encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return {"items": [po_header_json(po) for po in page], "next_cursor": next_cursor}

    async def get(self, actor: Principal, scope: BranchScope, po_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            po = await self._repo.get(s, po_id)
            if po is None:
                raise not_found()
            check_read_scope(scope, po.branch_id)
            received = await self._repo.received_qty(s, po_id)
        return po_json(po, received)

    # --- writes -----------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, data: PoInput, ip: str | None
    ) -> dict[str, Any]:
        self._check_lines(data.lines)
        po_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch_id = await self._check_refs(s, scope, data.supplier_id, data.warehouse_id, data.lines)
            await self._repo.insert(
                s,
                {
                    "id": po_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "doc_date": data.doc_date,
                    "supplier_id": data.supplier_id,
                    "warehouse_id": data.warehouse_id,
                    "created_by": actor.user_id,
                    "comment": data.comment,
                },
            )
            await self._repo.replace_lines(
                s, actor.tenant_id, po_id, self._line_rows(actor.tenant_id, po_id, data)
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="purchase_order.created",
                entity=DOC_TABLE,
                entity_id=po_id,
                after={
                    "supplier_id": str(data.supplier_id),
                    "warehouse_id": str(data.warehouse_id),
                    "doc_date": data.doc_date.isoformat(),
                    "lines": _audit_lines(data.lines),
                },
                ip=ip,
            )
            body = await self._body(s, po_id)
            stage_response(body, 201)
        return body

    async def update(
        self,
        actor: Principal,
        scope: BranchScope,
        po_id: UUID,
        changes: Mapping[str, Any],
        lines: Sequence[PoLineInput] | None,
        ip: str | None,
    ) -> dict[str, Any]:
        """19 §10 PATCH: given fields replace the stored ones; ``lines`` (when given) replace all lines."""
        if lines is not None:
            self._check_lines(lines)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            po = await self._locked(s, scope, po_id)
            if po.status == "closed":
                raise AppError(ErrorCode.PURCHASE_ORDER_CLOSED, params={"actual_status": po.status})
            if po.status not in EDITABLE:
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "draft|sent", "actual_status": po.status},
                )
            supplier_id = changes.get("supplier_id", po.supplier_id)
            warehouse_id = changes.get("warehouse_id", po.warehouse_id)
            check_lines = lines if lines is not None else []
            if "supplier_id" in changes or "warehouse_id" in changes or lines is not None:
                branch_id = await self._check_refs(s, scope, supplier_id, warehouse_id, check_lines)
                if po.number is not None and branch_id != po.branch_id:
                    # the Z-… number carries the branch code: a numbered order cannot change branch
                    raise _invalid("warehouse_id", "validation.branch_change_after_send")
            else:
                branch_id = po.branch_id
            values: dict[str, Any] = {k: v for k, v in changes.items() if k in ("doc_date", "comment")}
            if "supplier_id" in changes:
                values["supplier_id"] = supplier_id
            if "warehouse_id" in changes:
                values["warehouse_id"] = warehouse_id
                values["branch_id"] = branch_id
            if values:
                await self._repo.update(s, po_id, values)
            if lines is not None:
                data = PoInput(supplier_id, warehouse_id, values.get("doc_date", po.doc_date), lines)
                await self._repo.replace_lines(
                    s, actor.tenant_id, po_id, self._line_rows(actor.tenant_id, po_id, data)
                )
            before: dict[str, Any] = {k: _str(getattr(po, k)) for k in values}
            after: dict[str, Any] = {k: _str(v) for k, v in values.items()}
            if lines is not None:
                before["lines"] = len(po.lines)
                after["lines"] = _audit_lines(lines)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="purchase_order.updated",
                entity=DOC_TABLE,
                entity_id=po_id,
                before=before,
                after=after,
                ip=ip,
            )
            body = await self._body(s, po_id)
            stage_response(body)
        return body

    async def send(self, actor: Principal, scope: BranchScope, po_id: UUID, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            po = await self._locked(s, scope, po_id)
            if po.status != "draft":
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "draft", "actual_status": po.status},
                )
            # the supplier may have been archived since the draft was saved
            await self._directory.require_supplier(s, po.supplier_id)
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=po.branch_id, table=DOC_TABLE, year=po.doc_date.year
            )
            await self._repo.update(
                s, po_id, {"status": "sent", "number": number, "posted_at": datetime.now(UTC)}
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="purchase_order.sent",
                entity=DOC_TABLE,
                entity_id=po_id,
                before={"status": po.status},
                after={"status": "sent", "number": number},
                ip=ip,
            )
            body = await self._body(s, po_id)
            stage_response(body)
        return body

    async def cancel(
        self, actor: Principal, scope: BranchScope, po_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            po = await self._locked(s, scope, po_id)
            if po.status == "closed":
                raise AppError(ErrorCode.PURCHASE_ORDER_CLOSED, params={"actual_status": po.status})
            if po.status not in CANCELLABLE:
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "draft|sent|partially_received", "actual_status": po.status},
                )
            await self._repo.update(
                s,
                po_id,
                {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(UTC),
                    "cancelled_by": actor.user_id,
                    "cancel_reason": reason,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="purchase_order.cancelled",
                entity=DOC_TABLE,
                entity_id=po_id,
                before={"status": po.status},
                after={"status": "cancelled", "reason": reason},
                ip=ip,
            )
            body = await self._body(s, po_id)
            stage_response(body)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _locked(self, s: AsyncSession, scope: BranchScope, po_id: UUID) -> PurchaseOrder:
        po = await self._repo.get(s, po_id, lock=True)
        if po is None:
            raise not_found()
        check_read_scope(scope, po.branch_id)
        return po

    async def _body(self, s: AsyncSession, po_id: UUID) -> dict[str, Any]:
        po = await self._repo.get(s, po_id)
        assert po is not None
        return po_json(po, await self._repo.received_qty(s, po_id))

    @staticmethod
    def _check_lines(lines: Sequence[PoLineInput]) -> None:
        if not lines:
            raise _invalid("lines", "validation.required")
        if len(lines) > MAX_LINES:
            raise _invalid("lines", "validation.max_items")
        seen: set[UUID] = set()
        for index, line in enumerate(lines):
            if line.qty <= 0:
                raise _invalid(f"lines[{index}].qty", "validation.positive")
            if line.price is not None and line.price < 0:
                raise _invalid(f"lines[{index}].price", "validation.min_value")
            if line.product_id in seen:
                raise _invalid(f"lines[{index}].product_id", "validation.duplicate")
            seen.add(line.product_id)

    async def _check_refs(
        self,
        s: AsyncSession,
        scope: BranchScope,
        supplier_id: UUID,
        warehouse_id: UUID,
        lines: Sequence[PoLineInput],
    ) -> UUID:
        """Supplier active, warehouse in the caller's branch, products present; returns the PO branch."""
        await self._directory.require_supplier(s, supplier_id)
        warehouse = await self._repo.warehouse(s, warehouse_id)
        if warehouse is None or warehouse.archived:
            raise _invalid("warehouse_id", "validation.warehouse_not_found")
        if not scope.unrestricted and warehouse.branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        if scope.current is not None and warehouse.branch_id != scope.current:
            raise _invalid("warehouse_id", "validation.warehouse_not_in_branch")
        flags = await self._repo.product_archived_flags(s, [line.product_id for line in lines])
        for index, line in enumerate(lines):
            if line.product_id not in flags:
                raise _invalid(f"lines[{index}].product_id", "validation.product_not_found")
            if flags[line.product_id]:
                raise AppError(
                    ErrorCode.RESOURCE_ARCHIVED,
                    params={"resource": "product"},
                    details=[
                        ErrorDetail(field=f"lines[{index}].product_id", message_key="validation.archived")
                    ],
                )
        return warehouse.branch_id

    @staticmethod
    def _line_rows(tenant_id: UUID, po_id: UUID, data: PoInput) -> list[dict[str, Any]]:
        return [
            {
                "id": uuid7(),
                "tenant_id": tenant_id,
                "po_id": po_id,
                "line_no": n,
                "product_id": line.product_id,
                "qty": line.qty,
                "price": line.price,
            }
            for n, line in enumerate(data.lines, start=1)
        ]
