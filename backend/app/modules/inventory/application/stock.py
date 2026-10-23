"""The stock posting toolkit — every stock document posts through it (13 §2–§3, 23 §2.1–§2.3).

Usage (a posting service, inside ONE ``tenant_transaction``)::

    stock = stock_service()                                    # inventory.wiring
    txn = await stock.lock(s, tenant_id, [(doc.warehouse_id, ln.product_id) for ln in doc.lines])
    for ln in doc.lines:                                       # ALL keys locked in ONE call
        res = await txn.issue(doc.warehouse_id, ln.product_id, ln.qty,
                              doc_type="write_offs", doc_id=doc.id, line_id=ln.id,
                              cost=CostPosting(account_dt="9430", entry_date=doc.doc_date))
        ...                                                    # res.allocations / res.cost
    await poster.post(...)                                     # other (non-cost) ledger lines
    ... status = posted, posted_at = txn.at, next_doc_number(...), record_audit(...)
    stage_response(body, 200)
    # after the transaction committed:
    await stock.after_commit(txn)                              # enqueues recost jobs (if any)

Locking (23 §2.1): :meth:`StockService.lock` first takes the tenant valuation advisory lock
(shared; exclusive only to apply a FIFO↔AVECO switch), then ``INSERT … ON CONFLICT DO NOTHING`` +
``SELECT … FOR UPDATE`` of every ``stock_balances (warehouse_id, product_id)`` row of the document,
sorted ascending. Every path that touches lots / ``avg_costs`` / balances (receipts, issues,
returns, cancels, recost, valuation switch) goes through it; ``debt_balances`` (debts module) are
locked *after* it. ``txn.at`` — the instant right after the locks — is the posting time: use it as
``posted_at`` and ``stock_moves.moved_at`` (13 X-02), so the move order equals the lock order.

Negative stock (13 §3.1, 16 §5, QT-M04-11): ``tenants.settings.negative_stock_policy='allow'``
(default) turns the uncovered part of an issue into a pending piece (``lot_id = null``) costed at
an estimate (``sync_exceptions(kind='cost_unknown')`` when it is 0); ``'block'`` →
``422 NEGATIVE_STOCK_NOT_ALLOWED``. Any later credit to the same (warehouse, product) *settles* the
pending pieces at once from the arriving stock — storno of the pending move + real allocation
moves, both at the pending move's original ``moved_at`` — and queues a ``recost_jobs`` row; the job
then re-posts the issue documents' cost ledger lines to the settled cost (13 §3.3).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import unit_of_work_var
from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.money import money, price, qty
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_date
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.inventory.application.ports import (
    Balance,
    JobEnqueuer,
    Key,
    LotRow,
    MoveRow,
    RecostRepository,
    StockRepository,
    TenantStock,
    Warehouse,
)
from app.modules.inventory.application.valuation import ValuationService
from app.modules.inventory.domain.analytics import cost_analytics
from app.modules.inventory.domain.costing import (
    ZERO_MONEY,
    ZERO_QTY,
    Allocation,
    AvecoValueError,
    AvgState,
    IssuePlan,
    LotView,
    Method,
    aveco_credit,
    aveco_debit,
    aveco_issue,
    empties_all,
    fifo_piece_costs,
    lot_unit_cost,
    pending_unit_cost,
    plan_issue,
    split_amount,
)

log = structlog.get_logger(__name__)

RECOST_JOB = "inventory_recost"
_LOCKED_KEY = "inventory_stock_locked"
RECEIPT_SOURCES = frozenset({"goods_receipts", "stock_openings", "transfers", "stock_counts"})


@dataclass(frozen=True, slots=True)
class CostPosting:
    """The cost ledger line an issue writes: ``Dt account_dt / Kt inv_acct(warehouse)``.

    ``branch_id`` defaults to the warehouse's branch; ``analytics`` are extra keys (``employee_id``,
    ``expense_category_id`` …) on top of the cost-line contract (``inventory.domain.analytics``).
    """

    account_dt: str
    entry_date: date
    branch_id: UUID | None = None
    analytics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IssueResult:
    allocations: list[Allocation]
    cost: Decimal  # total cost (covered + pending estimate), 2 dp
    move_ids: list[UUID]
    pending_qty: Decimal
    ledger_ids: list[UUID]

    @property
    def unit_cost(self) -> Decimal:
        total = sum((a.qty for a in self.allocations), ZERO_QTY)
        return price(self.cost / total) if total else Decimal("0.0000")

    def allocations_json(self) -> list[dict[str, Any]]:
        return [a.as_json() for a in self.allocations]


@dataclass(frozen=True, slots=True)
class ReceiveResult:
    lot_id: UUID
    move_id: UUID
    unit_cost: Decimal
    settled_qty: Decimal  # pending quantity of earlier issues settled from this lot


def _err_negative(key: Key, requested: Decimal, available: Decimal) -> AppError:
    return AppError(
        ErrorCode.NEGATIVE_STOCK_NOT_ALLOWED,
        params={
            "warehouse_id": str(key[0]),
            "product_id": str(key[1]),
            "requested": format(qty(requested), "f"),
            "available": format(qty(max(available, ZERO_QTY)), "f"),
        },
    )


class StockService:
    def __init__(
        self,
        repo: StockRepository,
        recost: RecostRepository,
        poster: LedgerPoster,
        valuation: ValuationService,
        queue: JobEnqueuer | None,
    ) -> None:
        self._repo = repo
        self._recost = recost
        self._poster = poster
        self._valuation = valuation
        self._queue = queue

    @property
    def repo(self) -> StockRepository:
        return self._repo

    async def lock(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        keys: Iterable[Key],
        *,
        negative_stock_policy: str | None = None,
    ) -> StockTxn:
        """Lock every (warehouse, product) a document touches — call ONCE per transaction."""
        uow = unit_of_work_var.get()
        if uow is not None and s.info.get(_LOCKED_KEY) is uow:
            raise RuntimeError("StockService.lock() must be called once per transaction (23 §2.1)")
        method = await self._valuation.ensure_applied(s, tenant_id)
        ordered = sorted(set(keys), key=lambda k: (k[0].int, k[1].int))
        balances = await self._repo.lock_balances(s, tenant_id, ordered)
        s.info[_LOCKED_KEY] = uow
        tenant = await self._repo.tenant_stock(s)
        policy = negative_stock_policy or tenant.negative_stock_policy
        return StockTxn(self, s, tenant_id, method, datetime.now(UTC), policy, tenant, balances)

    async def after_commit(self, txn: StockTxn) -> None:
        """Enqueue the recost jobs the transaction created (best effort; the cron sweeper is the backstop)."""
        await self.enqueue_recost(txn.tenant_id, txn.recost_job_ids)

    async def enqueue_recost(self, tenant_id: UUID, job_ids: Iterable[UUID]) -> None:
        if self._queue is None:
            return
        for job_id in dict.fromkeys(job_ids):
            try:
                await self._queue.enqueue(RECOST_JOB, tenant_id, job_id=str(job_id), key=f"recost:{job_id}")
            except Exception:  # the sweeper re-enqueues queued jobs
                log.warning("recost_enqueue_failed", job_id=str(job_id), exc_info=True)

    async def queue_recost(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        key: Key,
        from_date: date,
        reason_doc_type: str,
        reason_doc_id: UUID,
    ) -> UUID:
        """Create (or widen to ``from_date``) the queued recost job of ``key`` — public for Bosqich 3
        late-sync triggers. Call inside the posting transaction; enqueue after commit."""
        return await self._recost.upsert_queued(s, tenant_id, key, from_date, reason_doc_type, reason_doc_id)


class StockTxn:
    """The locked stock of one transaction. Not thread-safe; one per ``tenant_transaction``."""

    def __init__(
        self,
        service: StockService,
        s: AsyncSession,
        tenant_id: UUID,
        method: Method,
        at: datetime,
        policy: str,
        tenant: TenantStock,
        balances: Mapping[Key, Balance],
    ) -> None:
        self._svc = service
        self._repo = service._repo
        self.session = s
        self.tenant_id = tenant_id
        self.method: Method = method
        self.at = at
        self.policy = policy
        self.tenant = tenant
        self._balances: dict[Key, Balance] = dict(balances)
        self._warehouses: dict[UUID, Warehouse] = {}
        self.recost_job_ids: list[UUID] = []

    # --- reference --------------------------------------------------------------------------------
    @property
    def keys(self) -> frozenset[Key]:
        return frozenset(self._balances)

    def _check(self, key: Key) -> None:
        if key not in self._balances:
            raise RuntimeError(f"(warehouse, product) {key} is not locked by this StockTxn (23 §2.1)")

    async def warehouse(self, warehouse_id: UUID) -> Warehouse:
        cached = self._warehouses.get(warehouse_id)
        if cached is None:
            found = await self._repo.warehouse(self.session, warehouse_id)
            if found is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "warehouse"})
            self._warehouses[warehouse_id] = cached = found
        return cached

    async def inv_acct(self, warehouse_id: UUID) -> str:
        """``inv_acct(warehouse)`` = ``warehouses.inventory_account`` (2910/2920, 13 §1)."""
        return (await self.warehouse(warehouse_id)).inventory_account

    def balance(self, key: Key) -> Balance:
        self._check(key)
        return self._balances[key]

    async def last_purchase_cost(self, warehouse_id: UUID, product_id: UUID) -> Decimal | None:
        """13 §2.11: unit cost of the latest not-cancelled ``goods_receipts`` lot (this warehouse, else
        any), else — AVECO only — ``avg_costs.avg_cost`` (under FIFO that row is stale; the caller
        falls back to the register average)."""
        found = await self._repo.last_purchase_cost(self.session, product_id, warehouse_id)
        if found is not None:
            return found
        if self.method != "aveco":
            return None
        avg = await self._repo.avg_state(self.session, (warehouse_id, product_id))
        return avg.avg_cost if avg is not None and avg.avg_cost > 0 else None

    # --- receive ----------------------------------------------------------------------------------
    async def receive(
        self,
        warehouse_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        amount: Decimal,
        *,
        source_doc_type: str,
        source_doc_id: UUID,
        source_line_id: UUID,
        receipt_line_id: UUID | None = None,
        expiry_date: date | None = None,
        received_at: datetime | None = None,
        moved_at: datetime | None = None,
    ) -> ReceiveResult:
        """A new lot (receipt, opening, transfer arrival, count surplus) worth ``amount`` (the line
        total, 2 dp — never recomputed from the 4 dp unit cost); then pending issues are settled."""
        key = (warehouse_id, product_id)
        self._check(key)
        if source_doc_type not in RECEIPT_SOURCES:
            raise ValueError(f"source_doc_type {source_doc_type!r} (12 stock_lots CHECK)")
        if receipt_line_id is not None and source_doc_type != "goods_receipts":
            raise ValueError("receipt_line_id is only for goods_receipts lots")
        quantity, amount = qty(quantity), money(amount)
        if quantity <= 0 or amount < 0:
            raise ValueError("receive() needs qty > 0 and amount ≥ 0")
        await self.warehouse(warehouse_id)
        lots = await self._repo.open_lots(self.session, key)
        units_before = sum((lot.qty_left for lot in lots), ZERO_QTY)
        state = await self._avg(key, lots) if self.method == "aveco" else None  # before any change
        unit_cost = lot_unit_cost(amount, quantity)
        lot_id, move_id = uuid7(), uuid7()
        await self._repo.insert_lot(
            self.session,
            {
                "id": lot_id, "tenant_id": self.tenant_id, "warehouse_id": warehouse_id,
                "product_id": product_id, "receipt_line_id": receipt_line_id,
                "source_doc_type": source_doc_type, "source_doc_id": source_doc_id,
                "source_line_id": source_line_id, "received_at": received_at or self.at, "qty_in": quantity,
                "qty_left": quantity, "unit_cost": unit_cost, "expiry_date": expiry_date,
            },
        )  # fmt: skip
        await self._moves(
            [self._move(key, move_id, lot_id, quantity, amount, source_doc_type, source_doc_id,
                        source_line_id, None, moved_at or self.at)]
        )  # fmt: skip
        await self._add_balance(key, quantity, amount)
        if state is not None:
            await self._save_avg(key, aveco_credit(state, units_before, quantity, amount))
        settled = await self.settle_pending(key, source_doc_type, source_doc_id)
        return ReceiveResult(lot_id, move_id, unit_cost, settled)

    # --- issue ------------------------------------------------------------------------------------
    async def issue(
        self,
        warehouse_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        *,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID,
        lot_id: UUID | None = None,
        from_blocked: bool = False,
        cost: CostPosting | None = None,
        moved_at: datetime | None = None,
        allow_negative: bool | None = None,
    ) -> IssueResult:
        """Take ``quantity`` out (FIFO lots, or ``lot_id``); value it by the method in force.

        ``lot_id`` given → ``422 INSUFFICIENT_STOCK {lot_id, available}`` when the lot cannot give it
        (never pending). Otherwise an uncovered rest is pending (policy 'allow') or
        ``422 NEGATIVE_STOCK_NOT_ALLOWED`` (policy 'block'; ``allow_negative`` overrides the policy).
        With ``cost`` the cost ledger line is written here (contract: ``inventory.domain.analytics``).
        """
        key = (warehouse_id, product_id)
        self._check(key)
        quantity = qty(quantity)
        if quantity <= 0:
            raise ValueError("issue() needs qty > 0")
        await self.warehouse(warehouse_id)
        rows = await self._repo.open_lots(self.session, key)
        if lot_id is not None and all(r.id != lot_id for r in rows):
            lot = await self._repo.lot(self.session, lot_id)
            if lot is None or (lot.warehouse_id, lot.product_id) != key:
                raise AppError(ErrorCode.LOT_NOT_FOUND, params={"lot_id": str(lot_id)})
            rows.append(lot)
        lots = [r.view() for r in rows]
        plan = plan_issue(lots, quantity, lot_id=lot_id, from_blocked=from_blocked)
        if plan.uncovered > 0:
            if lot_id is not None:
                avail = plan.covered
                raise AppError(
                    ErrorCode.INSUFFICIENT_STOCK,
                    params={"lot_id": str(lot_id), "available": format(qty(avail), "f")},
                )
            allowed = allow_negative if allow_negative is not None else self.policy != "block"
            if not allowed:
                raise _err_negative(key, quantity, plan.covered)
        allocations, costs = await self._value_issue(key, lots, plan, quantity)
        pending_qty = plan.uncovered
        if pending_qty > 0:
            estimate = await self._estimate(key)
            allocations.append(Allocation(None, pending_qty, estimate, pending=True))
            costs.append(money(pending_qty * estimate))
            if estimate == 0:
                await self._cost_unknown(key, doc_type, doc_id, line_id, pending_qty, cost)
        await self._apply_plan(plan, from_blocked=from_blocked)
        at = moved_at or self.at
        move_ids = [uuid7() for _ in allocations]
        await self._moves(
            [
                self._move(key, mid, a.lot_id, -a.qty, -c, doc_type, doc_id, line_id, None, at)
                for mid, a, c in zip(move_ids, allocations, costs, strict=True)
            ]
        )
        total = sum(costs, ZERO_MONEY)
        await self._add_balance(key, -quantity, -total)
        ledger_ids: list[UUID] = []
        if cost is not None:
            ledger_ids = await self._post_cost(key, doc_type, doc_id, line_id, total, allocations, cost)
        return IssueResult(allocations, total, move_ids, pending_qty, ledger_ids)

    def cost_line(
        self,
        *,
        warehouse_id: UUID,
        product_id: UUID,
        line_id: UUID,
        amount: Decimal,
        account_dt: str,
        inv_acct: str,
        entry_date: date,
        branch_id: UUID,
        allocations: Sequence[Allocation] = (),
        extra: Mapping[str, Any] | None = None,
    ) -> LedgerLine:
        """A cost ledger line that honours the analytics contract (for callers posting it themselves)."""
        return LedgerLine(
            entry_date=entry_date,
            branch_id=branch_id,
            account_dt=account_dt,
            account_kt=inv_acct,
            amount=amount,
            analytics=cost_analytics(
                product_id=product_id,
                warehouse_id=warehouse_id,
                line_id=line_id,
                lot_ids=[a.lot_id for a in allocations],
                extra=extra,
            ),
        )

    # --- returns (13 §3.2a) & blocked qty (13 §2.5) -----------------------------------------------
    async def return_to_lots(
        self,
        warehouse_id: UUID,
        product_id: UUID,
        pieces: Sequence[Allocation],
        *,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID,
        block: bool = False,
        moved_at: datetime | None = None,
    ) -> tuple[Decimal, list[UUID]]:
        """Give units back to their original lots at the ORIGINAL unit cost (13 §3.2a).

        ``pieces`` come from :func:`inventory.domain.costing.return_pieces` over the original line's
        allocations (reverse allocation order). FIFO: ``qty_left`` of those lots grows, unit cost
        unchanged; AVECO: ``total_value += Σ piece.qty × original unit cost`` (a receipt at the
        original cost, not the current ``avg_cost``). ``block=True`` (``restock=false`` return of an
        expired item, qaror #48) also blocks the returned quantity on the lot. Returns ``(amount,
        move_ids)``; pending pieces must be settled first (Bosqich 3).
        """
        key = (warehouse_id, product_id)
        self._check(key)
        if any(p.lot_id is None for p in pieces):
            raise ValueError("cannot return a pending (unsettled) allocation to a lot")
        lots_before = await self._repo.open_lots(self.session, key)
        units_before = sum((lot.qty_left for lot in lots_before), ZERO_QTY)
        state = await self._avg(key, lots_before) if self.method == "aveco" else None
        at = moved_at or self.at
        amounts = [money(p.qty * p.unit_cost) for p in pieces]
        move_ids = [uuid7() for _ in pieces]
        for p in pieces:
            assert p.lot_id is not None
            lot = await self._repo.lot(self.session, p.lot_id)
            if lot is None or (lot.warehouse_id, lot.product_id) != key:
                raise AppError(ErrorCode.LOT_NOT_FOUND, params={"lot_id": str(p.lot_id)})
            if lot.qty_left + p.qty > lot.qty_in:
                raise ValueError(f"lot {lot.id}: return would exceed qty_in")
            await self._repo.set_lot(
                self.session,
                lot.id,
                qty_left=lot.qty_left + p.qty,
                blocked_qty=lot.blocked_qty + (p.qty if block else ZERO_QTY),
            )
        await self._moves(
            [
                self._move(key, mid, p.lot_id, p.qty, a, doc_type, doc_id, line_id, None, at)
                for mid, p, a in zip(move_ids, pieces, amounts, strict=True)
            ]
        )
        total = sum(amounts, ZERO_MONEY)
        quantity = sum((p.qty for p in pieces), ZERO_QTY)
        await self._add_balance(key, quantity, total)
        if state is not None:
            await self._save_avg(key, aveco_credit(state, units_before, quantity, total))
        await self.settle_pending(key, doc_type, doc_id)
        return total, move_ids

    async def block(self, lot_id: UUID, quantity: Decimal) -> None:
        """Block ``quantity`` of a lot's free units (13 §2.5) — they stay in stock but are never issued."""
        lot = await self._repo.lot(self.session, lot_id)
        if lot is None:
            raise AppError(ErrorCode.LOT_NOT_FOUND, params={"lot_id": str(lot_id)})
        self._check((lot.warehouse_id, lot.product_id))
        if quantity <= 0 or lot.qty_left - lot.blocked_qty < quantity:
            raise AppError(
                ErrorCode.INSUFFICIENT_STOCK,
                params={"lot_id": str(lot_id), "available": format(lot.qty_left - lot.blocked_qty, "f")},
            )
        await self._repo.set_lot(
            self.session, lot_id, qty_left=lot.qty_left, blocked_qty=lot.blocked_qty + quantity
        )

    # --- cancel (23 §2.3) -------------------------------------------------------------------------
    async def reverse_receipt(
        self, doc_type: str, doc_id: UUID, *, line_ids: Collection[UUID] | None = None
    ) -> list[UUID]:
        """Cancel a receipt-type document's lots: ``409 LOT_ALREADY_CONSUMED`` when any lot it created
        was touched (``qty_left ≠ qty_in`` or ``blocked_qty > 0``) — under AVECO also when another
        document issued the same (warehouse, product) after the lot's receipt (its value is mixed into
        that COGS, 13 §3.1); else storno its moves, lots → 0.

        ``line_ids`` limits it to those document lines (a stock count has issue and receipt lines)."""
        lots = await self._repo.lots_of_source(self.session, doc_type, doc_id)
        if line_ids is not None:
            lots = [lot for lot in lots if lot.source_line_id in line_ids]
        moves = await self._repo.doc_moves(self.session, doc_type, doc_id, live_only=True)
        if line_ids is not None:
            moves = [m for m in moves if m.line_id in line_ids]
        for lot in lots:
            key = (lot.warehouse_id, lot.product_id)
            self._check(key)
            if lot.qty_left != lot.qty_in or lot.blocked_qty > 0:
                raise AppError(ErrorCode.LOT_ALREADY_CONSUMED, params={"lot_id": str(lot.id)})
            if self.method == "aveco":
                received = [m.created_at for m in moves if m.lot_id == lot.id and m.qty > 0]
                if received and await self._repo.live_issues_since(
                    self.session, key, min(received), (doc_type, doc_id)
                ):
                    raise AppError(ErrorCode.LOT_ALREADY_CONSUMED, params={"lot_id": str(lot.id)})
        lot_ids = {lot.id for lot in lots}
        out: list[UUID] = []
        for lot in lots:
            key = (lot.warehouse_id, lot.product_id)
            mine = [m for m in moves if m.lot_id == lot.id]
            open_lots = await self._repo.open_lots(self.session, key)
            units_before = sum((x.qty_left for x in open_lots), ZERO_QTY)
            amount = sum((m.cost_amount for m in mine), ZERO_MONEY)
            state = await self._avg(key, open_lots) if self.method == "aveco" else None
            await self._repo.set_lot(self.session, lot.id, qty_left=ZERO_QTY, blocked_qty=ZERO_QTY)
            out += await self._reverse_moves(mine)
            if state is not None:
                try:
                    debited = aveco_debit(state, units_before, lot.qty_in, amount)
                except AvecoValueError:
                    raise AppError(ErrorCode.LOT_ALREADY_CONSUMED, params={"lot_id": str(lot.id)}) from None
                await self._save_avg(key, debited)
        other = [m for m in moves if m.lot_id not in lot_ids]
        if other:
            raise ValueError(f"{doc_type} {doc_id} has stock moves that are not its own lots")
        return out

    async def reverse_issue(
        self,
        doc_type: str,
        doc_id: UUID,
        *,
        line_ids: Collection[UUID] | None = None,
        to_blocked_line_ids: Collection[UUID] = (),
    ) -> list[UUID]:
        """Cancel an issue-type document: storno its live moves and give the quantities back to the
        same lots (reverse order), AVECO value back at the issued cost; pending pieces just drop.

        ``line_ids`` limits it to those document lines (a stock count has issue and receipt lines).
        Lines in ``to_blocked_line_ids`` were issued ``from_blocked`` (``expired_return`` write-off,
        13 §2.5): their units go back blocked (``blocked_qty`` grows with ``qty_left``)."""
        moves = await self._repo.doc_moves(self.session, doc_type, doc_id, live_only=True)
        if line_ids is not None:
            moves = [m for m in moves if m.line_id in line_ids]
        if any(m.qty > 0 for m in moves):
            raise ValueError(f"{doc_type} {doc_id}: reverse_issue() on positive moves")
        by_key: dict[Key, list[MoveRow]] = {}
        for m in moves:
            by_key.setdefault((m.warehouse_id, m.product_id), []).append(m)
        out: list[UUID] = []
        for key, group in by_key.items():
            self._check(key)
            open_lots = await self._repo.open_lots(self.session, key)
            units_before = sum((x.qty_left for x in open_lots), ZERO_QTY)
            state = await self._avg(key, open_lots) if self.method == "aveco" else None
            lot_qty, lot_value, pending_qty = ZERO_QTY, ZERO_MONEY, ZERO_QTY
            for m in reversed(group):
                if m.lot_id is None:
                    pending_qty -= m.qty
                    continue
                lot = await self._repo.lot(self.session, m.lot_id)
                assert lot is not None
                blocked = lot.blocked_qty - m.qty if m.line_id in to_blocked_line_ids else lot.blocked_qty
                await self._repo.set_lot(
                    self.session, lot.id, qty_left=lot.qty_left - m.qty, blocked_qty=blocked
                )
                lot_qty -= m.qty
                lot_value -= m.cost_amount
            out += await self._reverse_moves(list(reversed(group)))
            if state is not None:
                # lot units come back at their issued cost (a receipt, 13 §3.2a); pending ones only in qty
                if lot_qty > 0:
                    state = aveco_credit(state, units_before, lot_qty, lot_value)
                await self._save_avg(
                    key, AvgState(state.qty + pending_qty, state.avg_cost, state.total_value)
                )
            await self.settle_pending(key, doc_type, doc_id)
        return out

    async def live_allocations(self, doc_type: str, doc_id: UUID, line_id: UUID) -> list[Allocation]:
        """Current allocations of an issued line, derived from its live moves (after any settlement)."""
        moves = await self._repo.doc_moves(self.session, doc_type, doc_id, live_only=True)
        out: list[Allocation] = []
        for m in moves:
            if m.line_id != line_id or m.qty >= 0:
                continue
            q = -m.qty
            out.append(Allocation(m.lot_id, q, price(-m.cost_amount / q), pending=m.lot_id is None))
        return out

    # --- internals --------------------------------------------------------------------------------
    async def _value_issue(
        self, key: Key, lots: Sequence[LotView], plan: IssuePlan, quantity: Decimal
    ) -> tuple[list[Allocation], list[Decimal]]:
        """Allocations + per-piece costs of the covered part (both methods)."""
        last_out = empties_all(lots, plan)
        if self.method == "fifo":
            register = await self._physical_value(key) if last_out else ZERO_MONEY
            lot_values = {
                lot.id: await self._repo.lot_value(self.session, lot.id)
                for lot, q in plan.pieces
                if lot.qty_left - q == 0
            }
            costs = fifo_piece_costs(plan, register_value=register, last_out=last_out, lot_values=lot_values)
            return [Allocation(lot.id, q, lot.unit_cost) for lot, q in plan.pieces], costs
        state = await self._avg(key, lots)
        covered_cost, new_state = aveco_issue(state, quantity, plan.covered, last_out=last_out)
        await self._save_avg(key, new_state)
        costs = split_amount(covered_cost, [q for _, q in plan.pieces], state.avg_cost)
        return [Allocation(lot.id, q, state.avg_cost) for lot, q in plan.pieces], costs

    async def _apply_plan(self, plan: IssuePlan, *, from_blocked: bool) -> None:
        for lot, q in plan.pieces:
            await self._repo.set_lot(
                self.session,
                lot.id,
                qty_left=lot.qty_left - q,
                blocked_qty=lot.blocked_qty - q if from_blocked else lot.blocked_qty,
            )

    async def settle_pending(self, key: Key, reason_doc_type: str, reason_doc_id: UUID) -> Decimal:
        """Settle pending pieces of ``key`` from the free stock now in the lots (oldest pending first).

        Per pending move: storno it and write real allocation moves (and a smaller pending move for
        any rest), all at the pending move's ``moved_at`` and with its document refs; the balance
        qty does not change. Then queue a recost job from the oldest settled pending date.
        """
        pending = await self._repo.pending_moves(self.session, key)
        if not pending:
            return ZERO_QTY
        rows = await self._repo.open_lots(self.session, key)
        lots = [r.view() for r in rows]
        free = sum((lot.available for lot in lots if lot.available > 0), ZERO_QTY)
        settled = ZERO_QTY
        oldest: datetime | None = None
        for pm in pending:
            if free <= 0:
                break
            p_qty, p_cost = -pm.qty, -pm.cost_amount
            take = min(p_qty, free)
            plan = plan_issue(lots, take)
            allocations, costs = await self._value_issue(key, lots, plan, take)
            if self.method == "aveco":  # settlement does not change the balance qty
                state = await self._avg(key, lots)
                await self._save_avg(key, AvgState(state.qty + take, state.avg_cost, state.total_value))
            await self._apply_plan(plan, from_blocked=False)
            rows_out = [self._move(key, uuid7(), pm.lot_id, p_qty, p_cost, pm.doc_type, pm.doc_id,
                                   pm.line_id, pm.id, pm.moved_at)]  # fmt: skip
            rows_out += [
                self._move(key, uuid7(), a.lot_id, -a.qty, -c, pm.doc_type, pm.doc_id, pm.line_id, None,
                           pm.moved_at)
                for a, c in zip(allocations, costs, strict=True)
            ]  # fmt: skip
            rest_cost = ZERO_MONEY
            if take < p_qty:
                estimate = price(p_cost / p_qty)
                rest_cost = money((p_qty - take) * estimate)
                rows_out.append(self._move(key, uuid7(), None, -(p_qty - take), -rest_cost, pm.doc_type,
                                           pm.doc_id, pm.line_id, None, pm.moved_at))  # fmt: skip
            await self._moves(rows_out)
            await self._add_balance(key, ZERO_QTY, p_cost - sum(costs, ZERO_MONEY) - rest_cost)
            lots = [r.view() for r in await self._repo.open_lots(self.session, key)]
            free -= take
            settled += take
            oldest = pm.moved_at if oldest is None or pm.moved_at < oldest else oldest
        if oldest is not None:
            job_id = await self._svc.queue_recost(
                self.session, self.tenant_id, key, business_date(oldest), reason_doc_type, reason_doc_id
            )
            self.recost_job_ids.append(job_id)
        return settled

    async def _estimate(self, key: Key) -> Decimal:
        avg = await self._repo.avg_state(self.session, key) if self.method == "aveco" else None
        return pending_unit_cost(
            self.method,
            avg_cost=avg.avg_cost if avg is not None else None,
            last_lot_cost=await self._repo.last_lot_cost(self.session, key),
            last_purchase_cost=await self._repo.last_purchase_cost(self.session, key[1], key[0]),
        )

    async def _cost_unknown(
        self,
        key: Key,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID,
        pending_qty: Decimal,
        cost: CostPosting | None,
    ) -> None:
        details: dict[str, Any] = {
            "warehouse_id": str(key[0]),
            "product_id": str(key[1]),
            "line_id": str(line_id),
            "qty": format(pending_qty, "f"),
        }
        if cost is not None:  # what recost needs to write the cost line later (amount 0 → not written now)
            wh = await self.warehouse(key[0])
            details["cost_line"] = {
                "account_dt": cost.account_dt,
                "account_kt": wh.inventory_account,
                "entry_date": cost.entry_date.isoformat(),
                "branch_id": str(cost.branch_id or wh.branch_id),
                "analytics": dict(cost.analytics),
            }
        await self._repo.insert_sync_exception(
            self.session,
            {"id": uuid7(), "tenant_id": self.tenant_id, "kind": "cost_unknown", "doc_type": doc_type,
             "doc_id": doc_id, "details": details},
        )  # fmt: skip

    async def _post_cost(
        self,
        key: Key,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID,
        amount: Decimal,
        allocations: Sequence[Allocation],
        cost: CostPosting,
    ) -> list[UUID]:
        wh = await self.warehouse(key[0])
        line = self.cost_line(
            warehouse_id=key[0], product_id=key[1], line_id=line_id, amount=amount,
            account_dt=cost.account_dt, inv_acct=wh.inventory_account, entry_date=cost.entry_date,
            branch_id=cost.branch_id or wh.branch_id, allocations=allocations, extra=cost.analytics,
        )  # fmt: skip
        posted = await self._svc._poster.post(self.session, self.tenant_id, doc_type, doc_id, [line])
        return posted.ledger_ids

    async def _physical_value(self, key: Key) -> Decimal:
        """Value of the units in lots = balance value + the estimates of pending pieces."""
        pending = await self._repo.pending_moves(self.session, key)
        return money(self._balances[key].value - sum((m.cost_amount for m in pending), ZERO_MONEY))

    async def _avg(self, key: Key, lots: Sequence[LotView] | Sequence[LotRow]) -> AvgState:
        state = await self._repo.avg_state(self.session, key)
        if state is not None:
            return state
        # first AVECO touch of this key (or a key created during a FIFO→AVECO switch): from the register
        units = sum((lot.qty_left for lot in lots), ZERO_QTY)
        value = await self._physical_value(key)
        avg = price(value / units) if units > 0 else Decimal("0.0000")
        return AvgState(self._balances[key].qty, avg, value)

    async def _save_avg(self, key: Key, state: AvgState) -> None:
        await self._repo.save_avg(self.session, self.tenant_id, key, state)

    async def _add_balance(self, key: Key, dq: Decimal, dv: Decimal) -> None:
        old = self._balances[key]
        self._balances[key] = Balance(old.qty + dq, money(old.value + dv))
        await self._repo.add_balance(self.session, key, dq, dv)

    async def _moves(self, rows: Sequence[Mapping[str, Any]]) -> None:
        if rows:
            await self._repo.insert_moves(self.session, rows)

    async def _reverse_moves(self, moves: Sequence[MoveRow]) -> list[UUID]:
        ids = [uuid7() for _ in moves]
        rows = [
            self._move((m.warehouse_id, m.product_id), rid, m.lot_id, -m.qty, -m.cost_amount, m.doc_type,
                       m.doc_id, m.line_id, m.id, self.at)
            for rid, m in zip(ids, moves, strict=True)
        ]  # fmt: skip
        await self._moves(rows)
        for m in moves:
            await self._add_balance((m.warehouse_id, m.product_id), -m.qty, -m.cost_amount)
        return ids

    def _move(
        self,
        key: Key,
        move_id: UUID,
        lot_id: UUID | None,
        quantity: Decimal,
        cost_amount: Decimal,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID | None,
        reversal_of_id: UUID | None,
        moved_at: datetime,
    ) -> dict[str, Any]:
        return {
            "id": move_id, "tenant_id": self.tenant_id, "warehouse_id": key[0], "product_id": key[1],
            "lot_id": lot_id, "qty": quantity, "cost_amount": cost_amount, "doc_type": doc_type,
            "doc_id": doc_id, "line_id": line_id, "reversal_of_id": reversal_of_id, "moved_at": moved_at,
        }  # fmt: skip
