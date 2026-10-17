"""Write-offs — ``write_offs`` / ``write_off_lines`` (19 §15, 13 §2.12, §4.3, US-M04-06; qaror #54).

``post`` (``draft → posted``; number ``L-…``; ``entry_date = doc_date``):

1. the total cost is estimated read-only under the stock lock (same allocation rules —
   :func:`inventory.domain.write_offs.estimate_cost`) and compared with the poster's ``stock.writeoff``
   ``limit_value`` (most generous role, ``NULL`` = unlimited): over the limit → ``approval_requests(
   kind='write_off_over_limit')`` + telegram ``over_limit_action`` and ``202 {status:"draft",
   approval_request_id}`` — nothing moves (approval itself: BO-16, Bosqich 3; an ``approved`` request
   for the document lets the next ``post`` through and is ``consumed`` — only while the estimate is
   not above its ``requested_value``, else a new request is made and the old one stays ``approved``);
2. otherwise every line is issued (its ``lot_id`` or FIFO; blocked quantity only for
   ``expired_return`` lines, ``from_blocked``) with the 13 §2.12 cost line (``Dt 9430 | 4730 | 9410 /
   Kt inv_acct``); a ``gift``/``other`` line of a VAT-regime tenant (``tenant_tax_regimes`` on
   ``doc_date``) with ``vat_rate > 0`` also books ``Dt 9430 / Kt 6410`` = VAT of the market value
   and ``vat_moves(kind='output', base_amount=market value)``. Market value = the current retail price
   of the write-off's branch without VAT; without a price the line's cost is the base (decision —
   never a zero base).

``cancel`` — ``draft`` → ``cancelled``; ``posted`` → ``reverse_issue`` + ledger/VAT storno.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.money import money, qty
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.entries import LedgerLine, VatMove
from app.modules.inventory.application.doc_support import (
    check_doc_date,
    decode_cursor,
    encode_cursor,
    invalid,
    m2,
    q3,
    require_scope,
    scoped_branches,
    ts,
)
from app.modules.inventory.application.ports import EventRecorderPort, Key, StockRepository, Warehouse
from app.modules.inventory.application.stock import CostPosting, StockService, StockTxn
from app.modules.inventory.domain.costing import ZERO_MONEY, pending_unit_cost
from app.modules.inventory.domain.write_offs import (
    LOSS_ACCOUNT,
    MANUAL_REASONS,
    VAT_ACCOUNT,
    EstimateLine,
    GiftVat,
    KeyState,
    cost_account,
    estimate_cost,
    gift_needs_vat,
    gift_vat,
)

DOC_TYPE = "write_offs"
MAX_LINES = 1000
APPROVAL_KIND = "write_off_over_limit"
APPROVAL_PERMISSION = "stock.writeoff"
APPROVAL_TTL = timedelta(minutes=15)  # 26 #87 default


@dataclass(frozen=True, slots=True)
class WriteOffLineInput:
    product_id: UUID
    qty: Decimal
    reason: str
    gift_kind: str | None = None
    lot_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class WriteOffLine:
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    lot_id: UUID | None
    expiry_date: date | None
    qty: Decimal
    reason: str
    gift_kind: str | None
    cost_amount: Decimal


@dataclass(frozen=True, slots=True)
class WriteOff:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    warehouse_id: UUID
    responsible_user_id: UUID | None
    promo_order_ref: str | None
    source_return_id: UUID | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    comment: str | None
    lines: tuple[WriteOffLine, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Approval:
    id: UUID
    status: str
    requested_value: Decimal | None = None  # the estimate the approver saw (``approval_requests``)


@dataclass(frozen=True, slots=True)
class PostResult:
    body: dict[str, Any]
    status_code: int


class WriteOffRepository(Protocol):
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> WriteOff | None: ...
    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[WriteOff]: ...
    async def mark_posted(
        self, s: AsyncSession, doc_id: UUID, number: str, at: datetime, costs: Mapping[UUID, Decimal]
    ) -> None: ...
    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None: ...
    async def active_member(self, s: AsyncSession, user_id: UUID) -> bool: ...
    async def latest_approval(self, s: AsyncSession, doc_id: UUID) -> Approval | None: ...
    async def insert_approval(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def consume_approval(self, s: AsyncSession, approval_id: UUID) -> None: ...
    async def vat_payer(self, s: AsyncSession, on: date) -> bool: ...
    async def vat_rates(self, s: AsyncSession, product_ids: Sequence[UUID]) -> dict[UUID, Decimal]: ...


class RetailPrices(Protocol):
    """``pricing`` current retail price (VAT included) — ``pricing.wiring.current_price_reader``."""

    async def __call__(
        self, s: AsyncSession, product_ids: Sequence[UUID], scope: BranchScope
    ) -> dict[UUID, Decimal]: ...


def write_off_json(doc: WriteOff, approval: Approval | None = None) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "number": doc.number,
        "status": doc.status,
        "doc_date": doc.doc_date.isoformat(),
        "branch_id": str(doc.branch_id),
        "warehouse_id": str(doc.warehouse_id),
        "responsible_user_id": str(doc.responsible_user_id) if doc.responsible_user_id else None,
        "promo_order_ref": doc.promo_order_ref,
        "source_return_id": str(doc.source_return_id) if doc.source_return_id else None,
        "comment": doc.comment,
        "line_count": len(doc.lines),
        "total_cost": m2(sum((ln.cost_amount for ln in doc.lines), ZERO_MONEY)),
        "approval_request_id": str(approval.id) if approval else None,
        "approval_status": approval.status if approval else None,
        "created_by": str(doc.created_by),
        "created_at": ts(doc.created_at),
        "posted_at": ts(doc.posted_at),
        "cancelled_at": ts(doc.cancelled_at),
        "cancel_reason": doc.cancel_reason,
        "lines": [
            {
                "id": str(ln.id),
                "line_no": ln.line_no,
                "product_id": str(ln.product_id),
                "product_name": ln.product_name,
                "lot_id": str(ln.lot_id) if ln.lot_id else None,
                "expiry_date": ln.expiry_date.isoformat() if ln.expiry_date else None,
                "qty": q3(ln.qty),
                "reason": ln.reason,
                "gift_kind": ln.gift_kind,
                "cost_amount": m2(ln.cost_amount),
            }
            for ln in doc.lines
        ],
    }


class WriteOffService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        docs: WriteOffRepository,
        repo: StockRepository,
        stock: StockService,
        poster: LedgerPoster,
        prices: RetailPrices,
        events: EventRecorderPort,
    ) -> None:
        self._sf = session_factory
        self._docs = docs
        self._repo = repo
        self._stock = stock
        self._poster = poster
        self._prices = prices
        self._events = events

    # --- create -----------------------------------------------------------------------------------
    async def create(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        warehouse_id: UUID,
        doc_date: date,
        lines: Sequence[WriteOffLineInput],
        responsible_user_id: UUID | None,
        promo_order_ref: str | None,
        comment: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        promo = (promo_order_ref or "").strip() or None
        _check_lines(lines, promo)
        check_doc_date(doc_date)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            wh = await self._warehouse(s, scope, warehouse_id)
            if responsible_user_id is not None and not await self._docs.active_member(s, responsible_user_id):
                raise invalid("responsible_user_id", "validation.member_not_active")
            await self._check_products(s, [ln.product_id for ln in lines])
            for index, ln in enumerate(lines):
                if ln.lot_id is not None:
                    lot = await self._repo.lot(s, ln.lot_id)
                    if lot is None or (lot.warehouse_id, lot.product_id) != (wh.id, ln.product_id):
                        raise invalid(f"lines[{index}].lot_id", "validation.lot_not_of_product_warehouse")
            doc_id = uuid7()
            await self._docs.insert(
                s,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": wh.branch_id,
                    "warehouse_id": wh.id,
                    "doc_date": doc_date,
                    "responsible_user_id": responsible_user_id,
                    "promo_order_ref": promo,
                    "created_by": actor.user_id,
                    "comment": comment,
                },
                [
                    {
                        "id": uuid7(),
                        "tenant_id": actor.tenant_id,
                        "write_off_id": doc_id,
                        "line_no": n,
                        "product_id": ln.product_id,
                        "lot_id": ln.lot_id,
                        "qty": qty(ln.qty),
                        "reason": ln.reason,
                        "gift_kind": ln.gift_kind if ln.reason == "gift" else None,
                    }
                    for n, ln in enumerate(lines, start=1)
                ],
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="write_off.created",
                entity=DOC_TYPE,
                entity_id=doc_id,
                ip=ip,
                after={"lines": len(lines), "warehouse_id": str(wh.id)},
            )
            body = write_off_json(await self._load(s, doc_id))
            stage_response(body, 201)
        return body

    # --- post -------------------------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, limit_value: Decimal | None, ip: str | None
    ) -> PostResult:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": doc.status}
                )
            check_doc_date(doc.doc_date)
            await self._poster.assert_period_open(s, doc.doc_date)
            txn = await self._stock.lock(
                s, actor.tenant_id, [(doc.warehouse_id, ln.product_id) for ln in doc.lines]
            )
            estimate = await self._estimate(s, txn, doc)
            approval = await self._docs.latest_approval(s, doc.id)
            # an approval covers the estimate it was asked for, never a later, larger one (SEC-07)
            approved = (
                approval is not None
                and approval.status == "approved"
                and approval.requested_value is not None
                and money(estimate) <= approval.requested_value
            )
            if limit_value is not None and estimate > limit_value and not approved:
                return await self._request_approval(s, actor, doc, estimate, limit_value, approval, ip)
            if approved and approval is not None:
                await self._docs.consume_approval(s, approval.id)
            costs = await self._issue_lines(s, actor.tenant_id, txn, doc)
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=doc.branch_id, table=DOC_TYPE, year=doc.doc_date.year
            )
            await self._docs.mark_posted(s, doc.id, number, txn.at, costs)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="write_off.posted",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={
                    "number": number,
                    "total_cost": m2(sum(costs.values(), ZERO_MONEY)),
                    "approval_request_id": str(approval.id) if approved and approval else None,
                },
            )
            body = write_off_json(await self._load(s, doc.id), approval if approved else None)
            stage_response(body, 200)
        await self._stock.after_commit(txn)
        return PostResult(body, 200)

    async def _estimate(self, s: AsyncSession, txn: StockTxn, doc: WriteOff) -> Decimal:
        """Read-only cost estimate; also raises the stock errors the real issue would raise."""
        states: dict[Key, KeyState] = {}
        for key in {(doc.warehouse_id, ln.product_id) for ln in doc.lines}:
            rows = await self._repo.open_lots(s, key)
            avg = await self._repo.avg_state(s, key) if txn.method == "aveco" else None
            units = sum((r.qty_left for r in rows), Decimal("0"))
            avg_cost = (
                avg.avg_cost if avg is not None else (txn.balance(key).value / units if units > 0 else None)
            )
            estimate = pending_unit_cost(
                txn.method,
                avg_cost=avg_cost,
                last_lot_cost=await self._repo.last_lot_cost(s, key),
                last_purchase_cost=await self._repo.last_purchase_cost(s, key[1], key[0]),
            )
            states[key] = KeyState([r.view() for r in rows], avg_cost, estimate)
        lines = [_estimate_line(doc, ln) for ln in doc.lines]
        for est in lines:  # a named lot outside the open lots: exists here (else 404) but gives nothing
            if est.lot_id is not None and all(lot.id != est.lot_id for lot in states[est.key].lots):
                found = await self._repo.lot(s, est.lot_id)
                if found is None or (found.warehouse_id, found.product_id) != est.key:
                    raise AppError(ErrorCode.LOT_NOT_FOUND, params={"lot_id": str(est.lot_id)})
                st = states[est.key]
                states[est.key] = KeyState([*st.lots, found.view()], st.avg_cost, st.pending_unit_cost)
        result = estimate_cost(txn.method, lines, states)
        for est, covered, uncovered in zip(lines, result.covered, result.uncovered, strict=True):
            if uncovered > 0 and est.lot_id is not None:
                raise AppError(
                    ErrorCode.INSUFFICIENT_STOCK,
                    params={"lot_id": str(est.lot_id), "available": format(qty(covered), "f")},
                )
            if uncovered > 0 and txn.policy == "block":
                raise AppError(
                    ErrorCode.NEGATIVE_STOCK_NOT_ALLOWED,
                    params={
                        "warehouse_id": str(est.key[0]),
                        "product_id": str(est.key[1]),
                        "requested": q3(est.quantity),
                        "available": q3(covered),
                    },
                )
        return result.total

    async def _request_approval(
        self,
        s: AsyncSession,
        actor: Principal,
        doc: WriteOff,
        estimate: Decimal,
        limit_value: Decimal,
        current: Approval | None,
        ip: str | None,
    ) -> PostResult:
        if current is not None and current.status == "pending":
            approval = current
        else:
            approval = Approval(uuid7(), "pending")
            context = {
                "write_off_id": str(doc.id),
                "warehouse_id": str(doc.warehouse_id),
                "estimated_cost": m2(estimate),
                "limit_value": m2(limit_value),
                "lines": [
                    {"product_id": str(ln.product_id), "qty": q3(ln.qty), "reason": ln.reason}
                    for ln in doc.lines
                ],
            }
            await self._docs.insert_approval(
                s,
                {
                    "id": approval.id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": doc.branch_id,
                    "kind": APPROVAL_KIND,
                    "permission_code": APPROVAL_PERMISSION,
                    "requested_value": money(estimate),
                    "context": json.dumps(context),
                    "linked_doc_type": DOC_TYPE,
                    "linked_doc_id": doc.id,
                    "requested_by": actor.user_id,
                    "expires_at": datetime.now(UTC) + APPROVAL_TTL,
                },
            )
            await self._events.record_event(
                s,
                actor.tenant_id,
                "over_limit_action",
                {
                    "action": "write_off",
                    "doc_type": DOC_TYPE,
                    "doc_id": str(doc.id),
                    "branch_id": str(doc.branch_id),
                    "approval_request_id": str(approval.id),
                    "amount": m2(estimate),
                    "limit": m2(limit_value),
                    "user_id": str(actor.user_id),
                },
                f"over_limit_action:{DOC_TYPE}:{approval.id}",
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="write_off.approval_requested",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={
                    "approval_request_id": str(approval.id),
                    "estimated_cost": m2(estimate),
                    "limit_value": m2(limit_value),
                },
            )
        body = write_off_json(doc, approval)
        stage_response(body, 202)
        return PostResult(body, 202)

    async def _issue_lines(
        self, s: AsyncSession, tenant_id: UUID, txn: StockTxn, doc: WriteOff
    ) -> dict[UUID, Decimal]:
        vat_lines = [ln for ln in doc.lines if gift_needs_vat(ln.reason, ln.gift_kind)]
        vat_payer = bool(vat_lines) and await self._docs.vat_payer(s, doc.doc_date)
        rates = await self._docs.vat_rates(s, [ln.product_id for ln in vat_lines]) if vat_payer else {}
        prices = (
            await self._prices(s, [ln.product_id for ln in vat_lines], BranchScope((), doc.branch_id))
            if vat_payer
            else {}
        )
        costs: dict[UUID, Decimal] = {}
        ledger: list[LedgerLine] = []
        vat: list[VatMove] = []
        for ln in doc.lines:
            account = cost_account(ln.reason, ln.gift_kind, doc.responsible_user_id)
            extra: dict[str, Any] = {"reason": ln.reason}
            if ln.gift_kind:
                extra["gift_kind"] = ln.gift_kind
            if account == "4730":
                extra["employee_id"] = str(doc.responsible_user_id)
            res = await txn.issue(
                doc.warehouse_id,
                ln.product_id,
                ln.qty,
                doc_type=DOC_TYPE,
                doc_id=doc.id,
                line_id=ln.id,
                lot_id=ln.lot_id,
                from_blocked=ln.reason == "expired_return" and ln.lot_id is not None,
                cost=CostPosting(account, doc.doc_date, doc.branch_id, extra),
            )
            costs[ln.id] = res.cost
            rate = rates.get(ln.product_id, Decimal("0"))
            if vat_payer and gift_needs_vat(ln.reason, ln.gift_kind) and rate > 0:
                retail = prices.get(ln.product_id)
                if retail is not None and retail > 0:
                    gv = gift_vat(retail, rate, ln.qty)
                else:  # no retail price: the cost is the taxable base (never a zero base)
                    gv = GiftVat(res.cost, money(res.cost * rate / 100))
                if gv.vat > 0:
                    ledger.append(
                        LedgerLine(
                            doc.doc_date,
                            doc.branch_id,
                            LOSS_ACCOUNT,
                            VAT_ACCOUNT,
                            gv.vat,
                            {
                                "product_id": str(ln.product_id),
                                "line_id": str(ln.id),
                                "tax_type": "vat",
                                "vat_kind": "gift_output",
                                "market_value": m2(gv.market_value),
                                "vat_rate": str(rate),
                            },
                        )
                    )
                    vat.append(VatMove(doc.doc_date, "output", gv.market_value, gv.vat))
        await self._poster.post(s, tenant_id, DOC_TYPE, doc.id, ledger, vat=vat)
        return costs

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
                await txn.reverse_issue(
                    DOC_TYPE,
                    doc.id,
                    to_blocked_line_ids=[
                        ln.id for ln in doc.lines if ln.reason == "expired_return" and ln.lot_id is not None
                    ],
                )
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, doc.id)
            await self._docs.mark_cancelled(s, doc.id, actor.user_id, reason)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="write_off.cancelled",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                before={"status": doc.status},
                after={"reason": reason},
            )
            body = write_off_json(await self._load(s, doc.id))
            stage_response(body, 200)
        if txn is not None:
            await self._stock.after_commit(txn)
        return body

    # --- read -------------------------------------------------------------------------------------
    async def get(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id)
            approval = await self._docs.latest_approval(s, doc.id)
        return write_off_json(doc, approval)

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
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if warehouse_id is not None:
                await self._warehouse(s, scope, warehouse_id, allow_archived=True)
            rows = await self._docs.page(
                s,
                status=status,
                warehouse_id=warehouse_id,
                branch_ids=scoped_branches(scope),
                after=after,
                limit=limit + 1,
            )
        page = rows[:limit]
        return {
            "items": [write_off_json(d) for d in page],
            "next_cursor": encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
        }

    # --- helpers ----------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> WriteOff:
        doc = await self._docs.get(s, doc_id, lock=lock)
        if doc is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "write_off"})
        return doc

    async def _doc(
        self, s: AsyncSession, scope: BranchScope, doc_id: UUID, *, lock: bool = False
    ) -> WriteOff:
        doc = await self._load(s, doc_id, lock=lock)
        require_scope(scope, doc.branch_id)
        return doc

    async def _warehouse(
        self, s: AsyncSession, scope: BranchScope, warehouse_id: UUID, *, allow_archived: bool = False
    ) -> Warehouse:
        wh = await self._repo.warehouse(s, warehouse_id)
        if wh is None:
            raise invalid("warehouse_id", "validation.warehouse_not_found")
        require_scope(scope, wh.branch_id)
        if wh.archived and not allow_archived:
            raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "warehouse"})
        return wh

    async def _check_products(self, s: AsyncSession, product_ids: Sequence[UUID]) -> None:
        flags = await self._repo.product_ids(s, product_ids)
        for index, pid in enumerate(product_ids):
            if pid not in flags:
                raise invalid(f"lines[{index}].product_id", "validation.product_not_found")


def _estimate_line(doc: WriteOff, ln: WriteOffLine) -> EstimateLine:
    return EstimateLine(
        (doc.warehouse_id, ln.product_id),
        ln.qty,
        ln.lot_id,
        ln.reason == "expired_return" and ln.lot_id is not None,
    )


def _check_lines(lines: Sequence[WriteOffLineInput], promo: str | None) -> None:
    if not lines:
        raise invalid("lines", "validation.required")
    if len(lines) > MAX_LINES:
        raise invalid("lines", "validation.max_items")
    for index, ln in enumerate(lines):
        if qty(ln.qty) <= 0:
            raise invalid(f"lines[{index}].qty", "validation.positive")
        if ln.reason not in MANUAL_REASONS:  # expired_return — created only by Bosqich 3 returns (qaror #48)
            raise invalid(f"lines[{index}].reason", "validation.write_off_reason_manual")
        if ln.reason == "gift" and ln.gift_kind not in ("promo_justified", "other"):
            raise invalid(f"lines[{index}].gift_kind", "validation.required")
        if ln.reason != "gift" and ln.gift_kind is not None:
            raise invalid(f"lines[{index}].gift_kind", "validation.gift_kind_only_for_gift")
        if ln.gift_kind == "promo_justified" and promo is None:
            raise invalid("promo_order_ref", "validation.required")
