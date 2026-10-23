"""Stock counts — ``stock_counts`` / ``count_lines`` (19 §14, 13 §2.11, X-02, qaror #53).

``counting`` (lines pre-filled with ``snapshot_qty`` = balance at ``started_at``) → ``review`` →
``posted``; ``cancelled`` from any state (``posted`` → storno).

``post`` (only from ``review``; ``409 DOC_INVALID_STATE`` otherwise, QT-M05-04): uncounted lines →
``422 COUNT_LINES_INCOMPLETE`` unless ``treat_uncounted_as_zero`` (then ``counted = 0`` at the post
instant). Per line ``expected = snapshot_qty + Σ stock_moves.qty (started_at < moved_at ≤
counted_at)`` — this count's own moves excluded — and ``diff = counted − expected``:

* shortage → ``txn.issue(−diff)`` with the cost line ``Dt 4730`` (``responsible_user_id``, analytics
  ``employee_id``) or ``Dt 5910`` / ``Kt inv_acct`` (balance cost, FIFO/AVECO);
* surplus → a lot (``source_doc_type='stock_counts'``) at ``last_purchase_cost`` (latest goods-receipt
  lot, else ``avg_cost``, else the register average) and ``Dt inv_acct / Kt 9390``.

All ledger lines are dated ``doc_date`` (``409 PERIOD_CLOSED`` in a closed period); number ``I-…``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
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
from app.core.money import money, qty
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.inventory.application.doc_support import (
    check_doc_date,
    decode_cursor,
    encode_cursor,
    invalid,
    invalid_state,
    m2,
    q3,
    require_scope,
    scoped_branches,
    ts,
)
from app.modules.inventory.application.ports import StockRepository, Warehouse
from app.modules.inventory.application.stock import CostPosting, StockService, StockTxn
from app.modules.inventory.domain.counts import expected_count_qty
from app.modules.inventory.domain.stock_counts import SURPLUS_ACCOUNT, shortage_account, surplus_unit_cost

DOC_TYPE = "stock_counts"
MAX_LINES = 5000
ZERO_QTY = Decimal("0.000")


@dataclass(frozen=True, slots=True)
class CountLineInput:
    product_id: UUID | None
    barcode: str | None
    counted: Decimal


@dataclass(frozen=True, slots=True)
class CountLine:
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    snapshot_qty: Decimal
    expected: Decimal
    counted: Decimal | None
    counted_at: datetime | None


@dataclass(frozen=True, slots=True)
class StockCount:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    warehouse_id: UUID
    started_at: datetime
    responsible_user_id: UUID | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    comment: str | None
    lines: tuple[CountLine, ...] = field(default=())


class CountRepository(Protocol):
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> StockCount | None: ...
    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[StockCount]: ...
    async def snapshot(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID] | None, at: datetime
    ) -> dict[UUID, Decimal]: ...
    async def moves_since(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        product_ids: Sequence[UUID],
        since: datetime,
        exclude_doc: UUID,
    ) -> dict[UUID, list[tuple[datetime, Decimal]]]: ...
    async def set_counted(self, s: AsyncSession, line_id: UUID, counted: Decimal, at: datetime) -> None: ...
    async def add_line(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def set_status(self, s: AsyncSession, doc_id: UUID, status: str) -> None: ...
    async def mark_posted(
        self, s: AsyncSession, doc_id: UUID, number: str, at: datetime, lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None: ...
    async def active_member(self, s: AsyncSession, user_id: UUID) -> bool: ...
    async def balances(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[Decimal, Decimal]]: ...


# --- JSON --------------------------------------------------------------------------------------------
def _diff(counted: Decimal | None, expected: Decimal) -> Decimal | None:
    return None if counted is None else qty(counted - expected)


def count_json(
    doc: StockCount,
    *,
    expected: Mapping[UUID, Decimal] | None = None,
    amounts: Mapping[UUID, Decimal] | None = None,
    with_lines: bool = True,
) -> dict[str, Any]:
    """``expected`` overrides the stored one (live preview while counting/in review)."""
    counted = sum(1 for ln in doc.lines if ln.counted is not None)
    body: dict[str, Any] = {
        "id": str(doc.id),
        "number": doc.number,
        "status": doc.status,
        "doc_date": doc.doc_date.isoformat(),
        "branch_id": str(doc.branch_id),
        "warehouse_id": str(doc.warehouse_id),
        "started_at": ts(doc.started_at),
        "responsible_user_id": str(doc.responsible_user_id) if doc.responsible_user_id else None,
        "comment": doc.comment,
        "line_count": len(doc.lines),
        "counted_count": counted,
        "uncounted_count": len(doc.lines) - counted,
        "created_by": str(doc.created_by),
        "created_at": ts(doc.created_at),
        "posted_at": ts(doc.posted_at),
        "cancelled_at": ts(doc.cancelled_at),
        "cancel_reason": doc.cancel_reason,
    }
    if with_lines:
        lines = []
        for ln in doc.lines:
            exp = (expected or {}).get(ln.id, ln.expected)
            lines.append(
                {
                    "id": str(ln.id),
                    "line_no": ln.line_no,
                    "product_id": str(ln.product_id),
                    "product_name": ln.product_name,
                    "snapshot_qty": q3(ln.snapshot_qty),
                    "expected": q3(exp),
                    "counted": q3(ln.counted),
                    "counted_at": ts(ln.counted_at),
                    "diff": q3(_diff(ln.counted, exp)),
                    "amount": m2((amounts or {}).get(ln.id)),
                }
            )
        body["lines"] = lines
    return body


@dataclass(frozen=True, slots=True)
class _Posted:
    line_id: UUID
    product_id: UUID
    expected: Decimal
    counted: Decimal
    amount: Decimal

    def as_json(self) -> dict[str, Any]:
        return {
            "line_id": str(self.line_id),
            "product_id": str(self.product_id),
            "expected": q3(self.expected),
            "counted": q3(self.counted),
            "diff": q3(self.counted - self.expected),
            "amount": m2(self.amount),
        }


class StockCountService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        docs: CountRepository,
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
        *,
        warehouse_id: UUID,
        doc_date: date,
        product_ids: Sequence[UUID],
        responsible_user_id: UUID | None,
        comment: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        if len(product_ids) > MAX_LINES:
            raise invalid("product_ids", "validation.max_items")
        check_doc_date(doc_date)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            wh = await self._warehouse(s, scope, warehouse_id)
            if responsible_user_id is not None and not await self._docs.active_member(s, responsible_user_id):
                raise invalid("responsible_user_id", "validation.member_not_active")
            wanted = list(dict.fromkeys(product_ids))
            if wanted:
                await self._check_products(s, wanted, "product_ids")
            started_at = datetime.now(UTC)  # the same clock as stock_moves.moved_at (StockTxn.at)
            snap = await self._docs.snapshot(s, wh.id, wanted or None, started_at)
            ordered = wanted or list(snap)
            doc_id = uuid7()
            await self._docs.insert(
                s,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": wh.branch_id,
                    "warehouse_id": wh.id,
                    "doc_date": doc_date,
                    "started_at": started_at,
                    "responsible_user_id": responsible_user_id,
                    "created_by": actor.user_id,
                    "comment": comment,
                },
                [
                    {
                        "id": uuid7(),
                        "tenant_id": actor.tenant_id,
                        "count_id": doc_id,
                        "line_no": n,
                        "product_id": pid,
                        "snapshot_qty": snap.get(pid, ZERO_QTY),
                        "expected": snap.get(pid, ZERO_QTY),
                    }
                    for n, pid in enumerate(ordered, start=1)
                ],
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="stock_count.created",
                entity=DOC_TYPE,
                entity_id=doc_id,
                ip=ip,
                after={"lines": len(ordered), "warehouse_id": str(wh.id)},
            )
            body = await self._detail(s, await self._load(s, doc_id))
            stage_response(body, 201)
        return body

    # --- lines --------------------------------------------------------------------------------------
    async def record_lines(
        self,
        actor: Principal,
        scope: BranchScope,
        doc_id: UUID,
        lines: Sequence[CountLineInput],
        ip: str | None,
    ) -> dict[str, Any]:
        if not lines:
            raise invalid("lines", "validation.required")
        if len(lines) > MAX_LINES:
            raise invalid("lines", "validation.max_items")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status != "counting":
                raise invalid_state("counting", doc.status)
            await self.record_lines_in(s, actor.tenant_id, doc, lines, datetime.now(UTC))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="stock_count.lines_recorded",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={"lines": len(lines)},
            )
            body = await self._detail(s, await self._load(s, doc.id))
            stage_response(body, 200)
        return body

    async def record_lines_in(
        self, s: AsyncSession, tenant_id: UUID, doc: StockCount, lines: Sequence[CountLineInput], at: datetime
    ) -> None:
        """Upsert counted quantities (REST: ``at`` = server now; Bosqich 3 offline: the device time)."""
        barcodes = [ln.barcode for ln in lines if ln.barcode]
        by_code = await self._repo.products_by_barcode(s, barcodes) if barcodes else {}
        resolved: list[tuple[UUID, Decimal]] = []
        for index, ln in enumerate(lines):
            if ln.barcode and ln.barcode not in by_code:
                raise AppError(
                    ErrorCode.BARCODE_NOT_IN_CATALOG,
                    params={"barcode": ln.barcode},
                    details=[
                        ErrorDetail(
                            field=f"lines[{index}].barcode", message_key="errors.barcode_not_in_catalog"
                        )
                    ],
                )
            pid = ln.product_id or (by_code[ln.barcode] if ln.barcode else None)
            if pid is None:
                raise invalid(f"lines[{index}].product_id", "validation.required")
            if ln.product_id and ln.barcode and by_code[ln.barcode] != ln.product_id:
                raise invalid(f"lines[{index}].barcode", "validation.barcode_product_mismatch")
            if qty(ln.counted) < 0:
                raise invalid(f"lines[{index}].counted", "validation.non_negative")
            resolved.append((pid, qty(ln.counted)))
        existing = {ln.product_id: ln for ln in doc.lines}
        new_ids = [pid for pid, _ in resolved if pid not in existing]
        snap: dict[UUID, Decimal] = {}
        if new_ids:
            await self._check_products(s, list(dict.fromkeys(new_ids)), "lines")
            snap = await self._docs.snapshot(s, doc.warehouse_id, new_ids, doc.started_at)
        line_no = max((ln.line_no for ln in doc.lines), default=0)
        added: dict[UUID, UUID] = {}
        for pid, counted in resolved:
            line = existing.get(pid)
            if line is not None:
                await self._docs.set_counted(s, line.id, counted, at)
            elif pid in added:
                await self._docs.set_counted(s, added[pid], counted, at)
            else:
                line_no += 1
                added[pid] = uuid7()
                base = snap.get(pid, ZERO_QTY)
                await self._docs.add_line(
                    s,
                    {
                        "id": added[pid],
                        "tenant_id": tenant_id,
                        "count_id": doc.id,
                        "line_no": line_no,
                        "product_id": pid,
                        "snapshot_qty": base,
                        "expected": base,
                        "counted": counted,
                        "counted_at": at,
                    },
                )

    async def update_line(
        self,
        actor: Principal,
        scope: BranchScope,
        doc_id: UUID,
        line_id: UUID,
        counted: Decimal,
        ip: str | None,
    ) -> dict[str, Any]:
        if qty(counted) < 0:
            raise invalid("counted", "validation.non_negative")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status != "counting":
                raise invalid_state("counting", doc.status)
            line = next((ln for ln in doc.lines if ln.id == line_id), None)
            if line is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "count_line"})
            await self._docs.set_counted(s, line.id, qty(counted), datetime.now(UTC))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="stock_count.line_updated",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                before={"counted": q3(line.counted)},
                after={"line_id": str(line.id), "counted": q3(counted)},
            )
            body = await self._detail(s, await self._load(s, doc.id))
            stage_response(body, 200)
        return body

    async def submit(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status != "counting":
                raise invalid_state("counting", doc.status)
            await self._docs.set_status(s, doc.id, "review")
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="stock_count.submitted",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
            )
            body = await self._detail(s, await self._load(s, doc.id))
            stage_response(body, 200)
        return body

    # --- post -------------------------------------------------------------------------------------
    async def post(
        self,
        actor: Principal,
        scope: BranchScope,
        doc_id: UUID,
        treat_uncounted_as_zero: bool,
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._doc(s, scope, doc_id, lock=True)
            if doc.status != "review":
                raise invalid_state("review", doc.status)
            uncounted = sum(1 for ln in doc.lines if ln.counted is None)
            if uncounted and not treat_uncounted_as_zero:
                raise AppError(ErrorCode.COUNT_LINES_INCOMPLETE, params={"uncounted_count": uncounted})
            check_doc_date(doc.doc_date)
            await self._poster.assert_period_open(s, doc.doc_date)
            txn = await self._stock.lock(
                s, actor.tenant_id, [(doc.warehouse_id, ln.product_id) for ln in doc.lines]
            )
            shortages, surpluses, expected = await self._post_lines(s, actor.tenant_id, doc, txn)
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=doc.branch_id, table=DOC_TYPE, year=doc.doc_date.year
            )
            await self._docs.mark_posted(
                s,
                doc.id,
                number,
                txn.at,
                [
                    {
                        "id": ln.id,
                        "expected": expected[ln.id],
                        "counted": ln.counted if ln.counted is not None else ZERO_QTY,
                        "counted_at": ln.counted_at or txn.at,
                    }
                    for ln in doc.lines
                ],
            )
            body = {
                "id": str(doc.id),
                "number": number,
                "status": "posted",
                "shortage_lines": [p.as_json() for p in shortages],
                "surplus_lines": [p.as_json() for p in surpluses],
            }
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="stock_count.posted",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={
                    "number": number,
                    "shortage_lines": len(shortages),
                    "surplus_lines": len(surpluses),
                    "treat_uncounted_as_zero": treat_uncounted_as_zero,
                    "uncounted": uncounted,
                },
            )
            stage_response(body, 200)
        await self._stock.after_commit(txn)
        return body

    async def _post_lines(
        self, s: AsyncSession, tenant_id: UUID, doc: StockCount, txn: StockTxn
    ) -> tuple[list[_Posted], list[_Posted], dict[UUID, Decimal]]:
        moves = await self._docs.moves_since(
            s, doc.warehouse_id, [ln.product_id for ln in doc.lines], doc.started_at, doc.id
        )
        inv_acct = await txn.inv_acct(doc.warehouse_id)
        account = shortage_account(doc.responsible_user_id)
        extra = {"employee_id": str(doc.responsible_user_id)} if doc.responsible_user_id else {}
        shortages: list[_Posted] = []
        surpluses: list[_Posted] = []
        ledger: list[LedgerLine] = []
        expected_by_line: dict[UUID, Decimal] = {}
        for ln in doc.lines:
            counted = ln.counted if ln.counted is not None else ZERO_QTY
            counted_at = ln.counted_at or txn.at
            expected = qty(
                expected_count_qty(
                    ln.snapshot_qty,
                    moves.get(ln.product_id, []),
                    started_at=doc.started_at,
                    counted_at=counted_at,
                )
            )
            expected_by_line[ln.id] = expected
            diff = qty(counted - expected)
            if diff < 0:
                res = await txn.issue(
                    doc.warehouse_id,
                    ln.product_id,
                    -diff,
                    doc_type=DOC_TYPE,
                    doc_id=doc.id,
                    line_id=ln.id,
                    cost=CostPosting(account, doc.doc_date, doc.branch_id, extra),
                )
                shortages.append(_Posted(ln.id, ln.product_id, expected, counted, res.cost))
            elif diff > 0:
                key = (doc.warehouse_id, ln.product_id)
                bal = txn.balance(key)
                unit = surplus_unit_cost(await txn.last_purchase_cost(*key), bal.qty, bal.value)
                amount = money(diff * unit)
                rec = await txn.receive(
                    doc.warehouse_id,
                    ln.product_id,
                    diff,
                    amount,
                    source_doc_type=DOC_TYPE,
                    source_doc_id=doc.id,
                    source_line_id=ln.id,
                )
                ledger.append(
                    LedgerLine(
                        doc.doc_date,
                        doc.branch_id,
                        inv_acct,
                        SURPLUS_ACCOUNT,
                        amount,
                        {
                            "product_id": str(ln.product_id),
                            "warehouse_id": str(doc.warehouse_id),
                            "line_id": str(ln.id),
                            "lot_ids": [str(rec.lot_id)],
                        },
                    )
                )
                surpluses.append(_Posted(ln.id, ln.product_id, expected, counted, amount))
        await self._poster.post(s, tenant_id, DOC_TYPE, doc.id, ledger)
        return shortages, surpluses, expected_by_line

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
                diffs = {ln.id: (ln.counted or ZERO_QTY) - ln.expected for ln in doc.lines}
                shortage = {lid for lid, d in diffs.items() if d < 0}
                surplus = {lid for lid, d in diffs.items() if d > 0}
                if surplus:
                    await txn.reverse_receipt(DOC_TYPE, doc.id, line_ids=surplus)
                if shortage:
                    await txn.reverse_issue(DOC_TYPE, doc.id, line_ids=shortage)
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, doc.id)
            await self._docs.mark_cancelled(s, doc.id, actor.user_id, reason)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="stock_count.cancelled",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                before={"status": doc.status},
                after={"reason": reason},
            )
            body = await self._detail(s, await self._load(s, doc.id))
            stage_response(body, 200)
        if txn is not None:
            await self._stock.after_commit(txn)
        return body

    # --- read -------------------------------------------------------------------------------------
    async def get(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return await self._detail(s, await self._doc(s, scope, doc_id))

    async def _detail(self, s: AsyncSession, doc: StockCount) -> dict[str, Any]:
        """The document with the live ``expected`` preview (counting/review) and amount estimates."""
        expected: dict[UUID, Decimal] = {}
        if doc.status in ("counting", "review"):
            moves = await self._docs.moves_since(
                s, doc.warehouse_id, [ln.product_id for ln in doc.lines], doc.started_at, doc.id
            )
            now = datetime.now(UTC)
            for ln in doc.lines:
                expected[ln.id] = qty(
                    expected_count_qty(
                        ln.snapshot_qty,
                        moves.get(ln.product_id, []),
                        started_at=doc.started_at,
                        counted_at=ln.counted_at or now,
                    )
                )
        amounts = await self._amount_estimates(s, doc, expected)
        return count_json(doc, expected=expected or None, amounts=amounts)

    async def _amount_estimates(
        self, s: AsyncSession, doc: StockCount, expected: Mapping[UUID, Decimal]
    ) -> dict[UUID, Decimal]:
        """BO-03 "summa": ``|diff| × unit`` — shortage at the register average, surplus at the surplus
        cost (13 §2.11); posted lines are the posted amounts' estimate too (the ledger holds the truth)."""
        diffs = {
            ln.id: (ln.product_id, qty(ln.counted - expected.get(ln.id, ln.expected)))
            for ln in doc.lines
            if ln.counted is not None
        }
        live = {lid: d for lid, d in diffs.items() if d[1] != 0}
        if not live:
            return {}
        bals = await self._docs.balances(s, doc.warehouse_id, list({p for p, _ in live.values()}))
        out: dict[UUID, Decimal] = {}
        for lid, (pid, diff) in live.items():
            bq, bv = bals.get(pid, (ZERO_QTY, Decimal("0.00")))
            if diff < 0 and bq > 0:
                unit = bv / bq
            else:
                unit = surplus_unit_cost(
                    await self._repo.last_purchase_cost(s, pid, doc.warehouse_id), bq, bv
                )
            out[lid] = money(diff * unit)
        return out

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
            "items": [count_json(d, with_lines=False) for d in page],
            "next_cursor": encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
        }

    # --- helpers ----------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> StockCount:
        doc = await self._docs.get(s, doc_id, lock=lock)
        if doc is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "stock_count"})
        return doc

    async def _doc(
        self, s: AsyncSession, scope: BranchScope, doc_id: UUID, *, lock: bool = False
    ) -> StockCount:
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

    async def _check_products(self, s: AsyncSession, product_ids: Sequence[UUID], field_name: str) -> None:
        flags = await self._repo.product_ids(s, product_ids)
        for index, pid in enumerate(product_ids):
            if pid not in flags:
                raise invalid(f"{field_name}[{index}]", "validation.product_not_found")
