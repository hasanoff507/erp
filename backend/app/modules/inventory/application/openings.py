"""Opening stock — ``stock_openings`` (19 §16, 13 §2.21, US-M04-04, QT-M04-04).

``post``: a new lot per line (``source_doc_type='stock_openings'``) + balance, and per line
``Dt inv_acct / Kt 0000`` = ``ROUND_HALF_UP(qty × unit_cost, 2)``; no VAT. ``entry_date`` =
``tenants.go_live_date − 1 day`` (``422 VALIDATION_ERROR`` ``validation.go_live_date_missing`` while
onboarding has not set it). The lots get ``received_at`` = the last instant of ``go_live_date − 1``
in Tashkent, so FIFO takes them before any receipt of the go-live period. Number ``OO-…``.

``cancel``: a draft just becomes ``cancelled``; a posted document is reversed — ``409
LOT_ALREADY_CONSUMED`` when any of its lots was touched, else storno of the lots' moves and of the
ledger (dated today, or the first open date).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
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
from app.core.money import money, price, qty
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_today, day_end
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.inventory.application.ports import StockRepository, Warehouse
from app.modules.inventory.application.stock import StockService, StockTxn

DOC_TYPE = "stock_openings"
OPENING_ACCOUNT = "0000"
MAX_LINES = 5000


@dataclass(frozen=True, slots=True)
class OpeningLineInput:
    product_id: UUID
    qty: Decimal
    unit_cost: Decimal
    expiry_date: date | None = None


@dataclass(frozen=True, slots=True)
class OpeningLine:
    id: UUID
    line_no: int
    product_id: UUID
    qty: Decimal
    unit_cost: Decimal
    expiry_date: date | None

    @property
    def amount(self) -> Decimal:
        return money(self.qty * self.unit_cost)


@dataclass(frozen=True, slots=True)
class Opening:
    id: UUID
    branch_id: UUID
    warehouse_id: UUID
    number: str | None
    doc_date: date
    status: str
    comment: str | None
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    lines: tuple[OpeningLine, ...]


class OpeningRepository(Protocol):
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Opening | None: ...
    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[Opening]: ...
    async def mark_posted(self, s: AsyncSession, doc_id: UUID, number: str, posted_at: datetime) -> None: ...
    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None: ...


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def opening_json(doc: Opening, *, with_lines: bool = True) -> dict[str, Any]:
    total = sum((ln.amount for ln in doc.lines), Decimal("0.00"))
    body: dict[str, Any] = {
        "id": str(doc.id),
        "number": doc.number,
        "status": doc.status,
        "doc_date": doc.doc_date.isoformat(),
        "branch_id": str(doc.branch_id),
        "warehouse_id": str(doc.warehouse_id),
        "comment": doc.comment,
        "line_count": len(doc.lines),
        "total_amount": format(money(total), "f"),
        "created_at": _ts(doc.created_at),
        "posted_at": _ts(doc.posted_at),
        "cancelled_at": _ts(doc.cancelled_at),
        "cancel_reason": doc.cancel_reason,
    }
    if with_lines:
        body["lines"] = [
            {
                "id": str(ln.id),
                "line_no": ln.line_no,
                "product_id": str(ln.product_id),
                "qty": format(qty(ln.qty), "f"),
                "unit_cost": format(price(ln.unit_cost), "f"),
                "amount": format(ln.amount, "f"),
                "expiry_date": ln.expiry_date.isoformat() if ln.expiry_date else None,
            }
            for ln in doc.lines
        ]
    return body


def _cursor(doc: Opening) -> str:
    raw = json.dumps([doc.created_at.isoformat(), str(doc.id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


_CURSOR_MIN = datetime(2000, 1, 1, tzinfo=UTC)
_CURSOR_MAX = datetime(2100, 1, 1, tzinfo=UTC)


def _decode(cursor: str) -> tuple[datetime, UUID]:
    """A page cursor: a tz-aware instant within 2000-01-01..2100-01-01 UTC and a document id, else 422."""
    try:
        at, oid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        when = datetime.fromisoformat(at)
        if when.tzinfo is None or not _CURSOR_MIN <= when <= _CURSOR_MAX:
            raise ValueError("cursor instant out of range")
        return when, UUID(oid)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


class StockOpeningService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        docs: OpeningRepository,
        repo: StockRepository,
        stock: StockService,
        poster: LedgerPoster,
    ) -> None:
        self._sf = session_factory
        self._docs = docs
        self._repo = repo
        self._stock = stock
        self._poster = poster

    # --- create -----------------------------------------------------------------------------------
    async def create(
        self,
        actor: Principal,
        scope: BranchScope,
        warehouse_id: UUID,
        doc_date: date,
        lines: Sequence[OpeningLineInput],
        comment: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        _check_lines(lines)
        if doc_date > business_today():  # 13 §5.2, 19 §0
            raise _invalid("doc_date", "validation.doc_date_in_future")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            wh = await self._warehouse(s, scope, warehouse_id)
            await self._check_products(s, [ln.product_id for ln in lines])
            doc_id = await self.insert_draft(s, actor.tenant_id, actor.user_id, wh, doc_date, lines, comment)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="stock_opening.created",
                entity=DOC_TYPE, entity_id=doc_id, ip=ip,
                after={"lines": len(lines), "warehouse_id": str(wh.id)},
            )  # fmt: skip
            body = opening_json(await self._load(s, doc_id))
            stage_response(body, 201)
        return body

    async def insert_draft(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        wh: Warehouse,
        doc_date: date,
        lines: Sequence[OpeningLineInput],
        comment: str | None,
    ) -> UUID:
        doc_id = uuid7()
        await self._docs.insert(
            s,
            {"id": doc_id, "tenant_id": tenant_id, "branch_id": wh.branch_id, "warehouse_id": wh.id,
             "doc_date": doc_date, "created_by": user_id, "comment": comment},
            [
                {"id": uuid7(), "tenant_id": tenant_id, "opening_id": doc_id, "line_no": n,
                 "product_id": ln.product_id, "qty": qty(ln.qty), "unit_cost": price(ln.unit_cost),
                 "expiry_date": ln.expiry_date}
                for n, ln in enumerate(lines, start=1)
            ],
        )  # fmt: skip
        return doc_id

    # --- read -------------------------------------------------------------------------------------
    async def get(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id)
        return opening_json(doc)

    async def page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        after = _decode(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if warehouse_id is not None:
                await self._warehouse(s, scope, warehouse_id, allow_archived=True)
            rows = await self._docs.page(
                s,
                status=status,
                warehouse_id=warehouse_id,
                branch_ids=None if scope.unrestricted else scope.allowed,
                after=after,
                limit=limit + 1,
            )
        page = rows[:limit]
        return {
            "items": [opening_json(d, with_lines=False) for d in page],
            "next_cursor": _cursor(page[-1]) if len(rows) > limit else None,
        }

    # --- post -------------------------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": doc.status}
                )
            txn = await self.post_in(s, actor.tenant_id, doc)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="stock_opening.posted",
                entity=DOC_TYPE, entity_id=doc.id, after={"lines": len(doc.lines)}, ip=ip,
            )  # fmt: skip
            body = opening_json(await self._load(s, doc.id))
            stage_response(body, 200)
        await self._stock.after_commit(txn)
        return body

    async def post_in(self, s: AsyncSession, tenant_id: UUID, doc: Opening) -> StockTxn:
        """Post a draft inside the caller's transaction (API post and the ``opening_stock`` import)."""
        go_live = (await self._repo.tenant_stock(s)).go_live_date
        if go_live is None:
            raise _invalid("go_live_date", "validation.go_live_date_missing")
        entry_date = go_live - timedelta(days=1)
        await self._poster.assert_period_open(s, entry_date)
        txn = await self._stock.lock(s, tenant_id, [(doc.warehouse_id, ln.product_id) for ln in doc.lines])
        inv_acct = await txn.inv_acct(doc.warehouse_id)
        received_at = day_end(entry_date)
        ledger: list[LedgerLine] = []
        for ln in doc.lines:
            res = await txn.receive(
                doc.warehouse_id, ln.product_id, ln.qty, ln.amount,
                source_doc_type=DOC_TYPE, source_doc_id=doc.id, source_line_id=ln.id,
                expiry_date=ln.expiry_date, received_at=received_at,
            )  # fmt: skip
            ledger.append(
                LedgerLine(
                    entry_date, doc.branch_id, inv_acct, OPENING_ACCOUNT, ln.amount,
                    {"product_id": str(ln.product_id), "warehouse_id": str(doc.warehouse_id),
                     "line_id": str(ln.id), "lot_ids": [str(res.lot_id)]},
                )
            )  # fmt: skip
        await self._poster.post(s, tenant_id, DOC_TYPE, doc.id, ledger)
        number = await next_doc_number(
            s, tenant_id=tenant_id, branch_id=doc.branch_id, table=DOC_TYPE, year=doc.doc_date.year
        )
        await self._docs.mark_posted(s, doc.id, number, txn.at)
        return txn

    # --- cancel -----------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        txn: StockTxn | None = None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED)
            if doc.status == "posted":
                txn = await self._stock.lock(
                    s, actor.tenant_id, [(doc.warehouse_id, ln.product_id) for ln in doc.lines]
                )
                await txn.reverse_receipt(DOC_TYPE, doc.id)
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, doc.id)
            await self._docs.mark_cancelled(s, doc.id, actor.user_id, reason)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="stock_opening.cancelled",
                entity=DOC_TYPE, entity_id=doc.id, ip=ip,
                before={"status": doc.status}, after={"reason": reason},
            )  # fmt: skip
            body = opening_json(await self._load(s, doc.id))
            stage_response(body, 200)
        if txn is not None:
            await self._stock.after_commit(txn)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, doc_id: UUID) -> Opening:
        doc = await self._docs.get(s, doc_id)
        assert doc is not None
        return doc

    async def load(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Opening:
        doc = await self._docs.get(s, doc_id, lock=lock)
        if doc is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "stock_opening"})
        return doc

    async def _doc(self, s: AsyncSession, scope: BranchScope, doc_id: UUID, *, lock: bool = False) -> Opening:
        doc = await self.load(s, doc_id, lock=lock)
        if not scope.unrestricted and doc.branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return doc

    async def _warehouse(
        self, s: AsyncSession, scope: BranchScope, warehouse_id: UUID, *, allow_archived: bool = False
    ) -> Warehouse:
        wh = await self._repo.warehouse(s, warehouse_id)
        if wh is None:
            raise _invalid("warehouse_id", "validation.warehouse_not_found")
        if not scope.unrestricted and wh.branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        if wh.archived and not allow_archived:
            raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "warehouse"})
        return wh

    async def warehouse_of(self, s: AsyncSession, scope: BranchScope, warehouse_id: UUID) -> Warehouse:
        return await self._warehouse(s, scope, warehouse_id)

    async def _check_products(self, s: AsyncSession, product_ids: Sequence[UUID]) -> None:
        flags = await self._repo.product_ids(s, product_ids)
        for index, pid in enumerate(product_ids):
            if pid not in flags:
                raise _invalid(f"lines[{index}].product_id", "validation.product_not_found")
            if flags[pid]:
                raise AppError(
                    ErrorCode.RESOURCE_ARCHIVED,
                    params={"resource": "product"},
                    details=[
                        ErrorDetail(field=f"lines[{index}].product_id", message_key="validation.archived")
                    ],
                )


def _check_lines(lines: Sequence[OpeningLineInput]) -> None:
    if not lines:
        raise _invalid("lines", "validation.required")
    if len(lines) > MAX_LINES:
        raise _invalid("lines", "validation.max_items")
    for index, ln in enumerate(lines):
        if qty(ln.qty) <= 0:
            raise _invalid(f"lines[{index}].qty", "validation.positive")
        if price(ln.unit_cost) < 0:
            raise _invalid(f"lines[{index}].unit_cost", "validation.non_negative")


class OpeningImportAdapter:
    """``imports`` → inventory port of the ``opening_stock`` import (19 §6): barcode lookup and one
    ``stock_openings`` document created and posted in the import's commit transaction, in the
    default branch's warehouse. Recost jobs it might queue are picked up by the cron sweeper."""

    def __init__(self, openings: StockOpeningService, repo: StockRepository) -> None:
        self._openings = openings
        self._repo = repo

    async def barcode_products(self, s: AsyncSession, barcodes: Sequence[str]) -> dict[str, UUID]:
        return await self._repo.products_by_barcode(s, barcodes)

    async def check_scope(self, s: AsyncSession, scope: BranchScope) -> UUID | None:
        """The default branch the import posts to; ``403 BRANCH_SCOPE_DENIED`` when a restricted
        ``scope`` does not cover it."""
        branch = await self._repo.default_branch_id(s)
        if not scope.unrestricted and (branch is None or branch not in scope.allowed):
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return branch

    async def post_opening(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        lines: Sequence[tuple[UUID, Decimal, Decimal, date | None]],
        comment: str,
        scope: BranchScope,
    ) -> UUID:
        branch = await self.check_scope(s, scope)
        wh = await self._repo.branch_warehouse(s, branch) if branch is not None else None
        if wh is None:
            raise _invalid("warehouse_id", "validation.warehouse_not_found")
        inputs = [OpeningLineInput(pid, q, cost, expiry) for pid, q, cost, expiry in lines]
        _check_lines(inputs)
        today = datetime.now(UTC).date()
        doc_id = await self._openings.insert_draft(s, tenant_id, user_id, wh, today, inputs, comment)
        doc = await self._openings.load(s, doc_id, lock=True)
        await self._openings.post_in(s, tenant_id, doc)
        await record_audit(
            s, tenant_id=tenant_id, user_id=user_id, action="stock_opening.posted", entity=DOC_TYPE,
            entity_id=doc_id, after={"lines": len(inputs), "source": "import"},
        )  # fmt: skip
        return doc_id
