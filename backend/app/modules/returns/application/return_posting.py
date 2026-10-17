"""``return.created`` — the POS return posting (18 §7.1, 13 §2.5, §3.2a, §4.1; US-M02-01…03; qaror #48).

One per-event transaction (sync handler contract): ``returns`` + ``return_lines``, stock back to the
**original lots at the original unit cost** (``StockTxn.return_to_lots``, FIFO and AVECO), ``Dt inv_acct /
Kt 9120``, revenue reversal ``Dt 9040 / Kt acct`` + ``Dt 6410 / Kt acct`` split into the debt part (``Kt
4010`` — the sale's open debt shrinks first, no receipt) and the money part (``refund_method``; the only
part with a ``kind='return'`` fiscal receipt), negative ``vat_moves(kind='output')``, ``cash_moves`` (−),
``debt_moves`` (−). The original sale's ledger is never touched (QT-M02-05).

Approvals (``ApprovalGate``, one call): no receipt → ``return_no_receipt`` always (QT-PERM-04); an
expired item (``expiry_date < today`` of the original lot, qaror #48) → ``return_over_limit`` that only an
unlimited ``returns.approve`` holder covers (``APPROVAL_REQUIRED``), the line is forced ``restock=false``
and a ``write_offs`` draft (``expired_return``) is created; otherwise the amount against the requester's
``returns.approve`` limit (``RETURN_LIMIT_EXCEEDED``). A return without the original receipt goes back to
the newest lots of the product that have sold room, at their unit cost.

Marked lines are accepted online only (``MARKING_RETURN_REQUIRES_ONLINE``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.money import line_total, money, money_str, percent, price, qty, qty_str, vat_from_gross
from app.modules.accounting.domain.calendar import business_date, business_today, period_label
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.integrations.fiscal.application.contracts import FiscalReceiptRef
from app.modules.integrations.fiscal.domain.rules import payment_form
from app.modules.inventory.domain.analytics import cost_analytics
from app.modules.inventory.domain.costing import Allocation, return_pieces
from app.modules.returns.application.payloads import (
    RefundCardPayload,
    ReturnCreatedPayload,
    ReturnLinePayload,
)
from app.modules.returns.application.ports import ReturnsRepository, SoldDoc, SoldLine
from app.modules.returns.domain.refund import UNLIMITED_ONLY, refund_line, split_refund
from app.modules.sales.application.payloads import parse
from app.modules.sales.application.ports import ProductInfo
from app.modules.sales.application.sale_posting import (
    LOCAL_PROVIDERS,
    Deps,
    approval_in,
    fiscal_json,
    flag_unverified,
    invalid,
    parse_ts,
)
from app.modules.sales.domain.calc import ZERO, fiscal_shares, marking_code_valid
from app.modules.sales.domain.posting import COGS, LineAmounts, Part, document_ledger
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncExceptionRow

DOC_TYPE: Final = "returns"
CARD_DERIVED: Final = (
    "card_type", "card_type_source", "card_mask", "rrn", "approval_code", "card_scheme", "terminal_ref",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class ReturnLine:
    index: int
    src: ReturnLinePayload
    product: ProductInfo
    sold: SoldLine | None
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal
    total: Decimal
    vat: Decimal
    pieces: list[Allocation]
    expired: bool
    restock: bool


@dataclass
class _Out:
    warnings: list[str] = field(default_factory=list)
    exceptions: list[SyncExceptionRow] = field(default_factory=list)
    after: list[Callable[[], Awaitable[None]]] = field(default_factory=list)
    doc_type: str = DOC_TYPE

    def flag(self, kind: str, doc_id: UUID, **details: Any) -> None:
        self.exceptions.append(SyncExceptionRow(kind=kind, details=details, doc_type=DOC_TYPE, doc_id=doc_id))


class ReturnPostingHandler:
    def __init__(self, deps: Deps, repo: ReturnsRepository) -> None:
        self._d = deps
        self._r = repo

    async def __call__(self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]) -> HandlerResult:
        p = parse(ReturnCreatedPayload, payload)
        d, out, at = self._d, _Out(), ctx.created_at
        if p.branch_id != ctx.branch_id:
            raise invalid("branch_id", "validation.branch_mismatch")
        if ctx.cash_register_id is None or p.cash_register_id != ctx.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_mismatch")
        if await self._r.return_exists(s, p.id):
            raise invalid("id", "validation.duplicate_id")
        if p.temp_number and await d.repo.temp_number_taken(s, DOC_TYPE, ctx.device_id, p.temp_number):
            raise invalid("temp_number", "validation.duplicate_temp_number")
        shift = await d.shifts.require_open(s, shift_id=p.shift_id, device_id=ctx.device_id, at=at)
        if shift.cash_register_id != p.cash_register_id:
            raise invalid("shift_id", "validation.shift_register_mismatch")
        offline_since = parse_ts(p.offline_since, "offline_since") if p.offline_since else None
        self._check_refund_card(p)
        sale = await self._sale(s, p)
        warehouse_id = await d.repo.sale_warehouse(s, p.branch_id)
        if warehouse_id is None:
            raise invalid("branch_id", "validation.no_sale_warehouse")
        lines = await self._lines(s, p, sale, warehouse_id)
        return_amount = money(sum((ln.total for ln in lines), ZERO))
        counterparty_id = await self._counterparty(s, p, sale)
        if p.refund_method == "debt_adjustment" and counterparty_id is None:
            raise invalid("counterparty_id", "validation.required")
        approved_by, approved_at = await self._approve(
            s, ctx, p, return_amount, any(ln.expired for ln in lines), out
        )

        # --- registers -----------------------------------------------------------------------------
        doc_date = business_date(at)
        policy = await d.repo.tenant_policy(s, doc_date)
        entry_date = await d.poster.first_open_date(s, doc_date)
        late = entry_date != doc_date
        if late:
            out.flag(
                "late_in_closed_period", p.id, period=period_label(doc_date), doc_date=doc_date.isoformat()
            )
        txn = await d.stock.lock(s, ctx.tenant_id, [(warehouse_id, ln.product.id) for ln in lines])
        # SYNC-01 (23 §2.1: stock → debt): the sale's open debt, the split and the fiscal room are read under
        # the customer's debt_balances lock, so a concurrent payment/write-off cannot be counted twice
        if counterparty_id is not None:
            await d.debts.lock(s, ctx.tenant_id, [(counterparty_id, "receivable")])
        open_debt = await self._r.open_debt_of_sale(s, sale.id) if sale else ZERO
        # ACC-04 (13 §2.5, §2.15): a written-off part of the sale is not on 4010 any more — the return may
        # only shrink the still-open part; the Owner cancels the write-off first (FOUNDER F2)
        if (
            sale is not None
            and return_amount > open_debt
            and await self._r.written_off_of_sale(s, sale.id) > 0
        ):
            raise invalid("sale_id", "validation.sale_debt_written_off")
        split = split_refund(return_amount, open_debt, p.refund_method)
        if split.debt_part > 0 and counterparty_id is None:
            raise invalid("counterparty_id", "validation.required")
        issues_receipt = split.money_part > 0
        self._check_receipt_fields(p, issues_receipt)
        if issues_receipt and sale is not None and split.money_part > await self._r.fiscal_room(s, sale.id):
            raise invalid("lines", "validation.fiscal_refund_exceeds_sale")
        if issues_receipt:
            await d.fiscal.assert_can_issue(s, cash_register_id=p.cash_register_id, at=at)
        number = await next_doc_number(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, table=DOC_TYPE, year=doc_date.year
        )
        card = await self._refund_card(s, ctx, p, split.money_part, out)
        await self._r.insert_return(
            s,
            {
                "id": p.id, "tenant_id": ctx.tenant_id, "branch_id": p.branch_id, "number": number,
                "temp_number": p.temp_number, "doc_date": doc_date, "sale_id": p.sale_id,
                "shift_id": p.shift_id,
                "cash_register_id": p.cash_register_id, "counterparty_id": counterparty_id,
                "reason": p.reason,
                "refund_method": p.refund_method, "is_offline": p.is_offline, "approved_by": approved_by,
                "approved_at": approved_at, "created_by": ctx.actor_user_id, "posted_at": txn.at,
                "client_event_id": ctx.client_event_id, "device_id": ctx.device_id, "comment": p.comment,
                **card,
            },
        )  # fmt: skip
        inv_acct = await txn.inv_acct(warehouse_id)
        line_rows: list[dict[str, Any]] = []
        cost_lines: list[LedgerLine] = []
        write_off: list[dict[str, Any]] = []
        for ln in lines:
            line_id = uuid7()
            amount, _ = await txn.return_to_lots(
                warehouse_id, ln.product.id, ln.pieces, doc_type=DOC_TYPE, doc_id=p.id, line_id=line_id,
                block=not ln.restock, moved_at=at,
            )  # fmt: skip
            cost = money(amount)
            if cost > 0:
                cost_lines.append(
                    LedgerLine(
                        entry_date, p.branch_id, inv_acct, COGS, cost,
                        cost_analytics(product_id=ln.product.id, warehouse_id=warehouse_id, line_id=line_id,
                                       lot_ids=[pc.lot_id for pc in ln.pieces], extra={"return_cost": True}),
                    )
                )  # fmt: skip
            if ln.expired:
                for pc in ln.pieces:
                    write_off.append({"product_id": ln.product.id, "lot_id": pc.lot_id, "qty": pc.qty,
                                      "cost_amount": money(pc.qty * pc.unit_cost)})  # fmt: skip
            line_rows.append(
                {
                    "id": line_id, "tenant_id": ctx.tenant_id, "return_id": p.id, "line_no": ln.index + 1,
                    "sale_line_id": ln.src.sale_line_id, "product_id": ln.product.id, "qty": ln.quantity,
                    "price": ln.unit_price, "vat_rate": ln.vat_rate,
                    "vat_exemption_code": ln.src.vat_exemption_code,
                    "marking_code": ln.src.marking_code, "vat_amount": ln.vat, "cost_amount": cost,
                    "line_total": ln.total, "restock": ln.restock,
                }
            )  # fmt: skip
        await self._r.insert_lines(s, line_rows)
        codes = [ln.src.marking_code for ln in lines if ln.src.marking_code]
        if codes:
            await self._r.mark_codes_returned(s, codes, p.id)
        write_off_id: UUID | None = None
        if write_off:
            write_off_id = uuid7()
            await self._r.insert_write_off(
                s,
                {"id": write_off_id, "tenant_id": ctx.tenant_id, "branch_id": p.branch_id,
                "doc_date": doc_date,
                 "warehouse_id": warehouse_id, "source_return_id": p.id, "created_by": ctx.actor_user_id,
                 "comment": f"{number}: muddati o'tgan tovar qaytarildi"},
                [{"id": uuid7(), "tenant_id": ctx.tenant_id, "write_off_id": write_off_id, "line_no": i + 1,
                  "reason": "expired_return", **row} for i, row in enumerate(write_off)],
            )  # fmt: skip
        parts: list[Part] = []
        if split.debt_part > 0:
            parts.append(Part("debt_adjustment", split.debt_part, {"counterparty_id": str(counterparty_id)}))
        if split.money_part > 0:
            parts.append(Part(p.refund_method, split.money_part, _analytics(p, card)))
        base = {"return_id": str(p.id)}
        if p.sale_id:
            base["sale_id"] = str(p.sale_id)
        if late:
            base["correction_of_period"] = period_label(doc_date)
        ledger, vat = document_ledger(
            kind="return", entry_date=entry_date, branch_id=p.branch_id, parts=parts,
            lines=[LineAmounts(ln.product.id, ln.total, ln.vat, ln.vat_rate) for ln in lines],
            vat_payer=policy.vat_payer, analytics=base,
        )  # fmt: skip
        await d.poster.post(s, ctx.tenant_id, DOC_TYPE, p.id, [*ledger, *cost_lines], vat)
        if split.debt_part > 0:
            assert counterparty_id is not None
            await d.debts.post(
                s,
                ctx.tenant_id,
                [DebtMoveInput(counterparty_id, "receivable", -split.debt_part, DOC_TYPE, p.id)],
            )
        if split.money_part > 0:
            await d.repo.insert_cash_moves(
                s,
                [{"id": uuid7(), "tenant_id": ctx.tenant_id, "cash_register_id": p.cash_register_id,
                  "shift_id": p.shift_id, "amount": -split.money_part, "method": p.refund_method,
                  "doc_type": DOC_TYPE, "doc_id": p.id}],
            )  # fmt: skip
            late_row = await d.shifts.settle_late(
                s, tenant_id=ctx.tenant_id, shift=shift, doc_type=DOC_TYPE, doc_id=p.id
            )
            if late_row is not None:  # ACC-01 (18 §3.2, 13 X-01)
                out.exceptions.append(late_row)

        receipt: FiscalReceiptRef | None = None
        if issues_receipt:
            assert p.receipt_seq is not None
            shares = fiscal_shares(
                [ln.total for ln in lines], [ln.quantity for ln in lines], [ln.vat_rate for ln in lines],
                split.money_part,
            )  # fmt: skip
            receipt = await d.fiscal.record(
                s, kind="return", doc_id=p.id, cash_register_id=p.cash_register_id, shift_id=p.shift_id,
                receipt_seq=p.receipt_seq, payment_form=payment_form([p.refund_method]),
                payload=_receipt_payload(p, number, lines, shares, card, split.money_part),
                fiscal_result=p.fiscal_result, is_offline=p.is_offline, offline_since=offline_since,
                created_at=at,
            )  # fmt: skip
            if receipt.renumbered_from is not None:
                out.flag("receipt_seq_conflict", p.id, device_receipt_seq=receipt.renumbered_from,
                         receipt_seq=receipt.receipt_seq)  # fmt: skip
        tenant_id, stock, fiscal = ctx.tenant_id, d.stock, d.fiscal
        receipt_ids = [receipt.id] if receipt else []

        async def _after() -> None:
            await stock.after_commit(txn)
            await fiscal.enqueue(tenant_id, receipt_ids)

        out.after.append(_after)
        server = {
            "id": str(p.id), "number": number,
            "fiscal_receipt_seq": receipt.receipt_seq if receipt else None,
            "fiscal": fiscal_json(receipt, deferred=receipt is None),
            "write_off_id": str(write_off_id) if write_off_id else None,
            "return_amount": money_str(return_amount), "debt_part": money_str(split.debt_part),
            "money_part": money_str(split.money_part), "warnings": list(out.warnings),
        }  # fmt: skip
        return HandlerResult(
            server=server, warnings=tuple(out.warnings), sync_exceptions=tuple(out.exceptions),
            after_commit=tuple(out.after),
        )  # fmt: skip

    # --- validation ---------------------------------------------------------------------------------
    async def _sale(self, s: AsyncSession, p: ReturnCreatedPayload) -> SoldDoc | None:
        if p.sale_id is None:
            return None
        sale = await self._r.sale_for_return(s, p.sale_id)
        if sale is None:
            raise AppError(ErrorCode.SALE_NOT_FOUND, params={"sale_id": str(p.sale_id)})
        if sale.status != "posted":
            raise invalid("sale_id", "validation.sale_not_posted")
        return sale

    async def _lines(
        self, s: AsyncSession, p: ReturnCreatedPayload, sale: SoldDoc | None, warehouse_id: UUID
    ) -> list[ReturnLine]:
        d = self._d
        products = await d.repo.products(s, list(dict.fromkeys(ln.product_id for ln in p.lines)))
        today = business_today()
        taken: dict[UUID, Decimal] = {}
        out: list[ReturnLine] = []
        for i, src in enumerate(p.lines):
            f = f"lines[{i}]"
            product = products.get(src.product_id)
            if product is None:
                raise invalid(f"{f}.product_id", "validation.not_found")
            quantity = qty(src.qty)
            if quantity <= 0:
                raise invalid(f"{f}.qty", "validation.greater_than")
            if not product.is_fractional and quantity != quantity.to_integral_value():
                raise invalid(f"{f}.qty", "validation.qty_not_whole")
            self._check_marking(f, p, src, product, quantity)
            sold: SoldLine | None = None
            pieces: list[Allocation]
            expired = False
            if sale is not None:
                if src.sale_line_id is None:
                    raise invalid(f"{f}.sale_line_id", "validation.required")
                sold = sale.lines.get(src.sale_line_id)
                if sold is None or sold.product_id != product.id:
                    raise invalid(f"{f}.sale_line_id", "validation.not_found")
                if src.marking_code is not None and src.marking_code != sold.marking_code:
                    raise invalid(f"{f}.marking_code", "validation.marking_code_not_sold")
                before = sold.returned_qty + taken.get(sold.id, ZERO)
                if before + quantity > sold.qty:
                    raise AppError(
                        ErrorCode.RETURN_QTY_EXCEEDED,
                        params={"sale_line_id": str(sold.id), "sold": qty_str(sold.qty),
                                "returned": qty_str(before), "requested": qty_str(quantity)},
                    )  # fmt: skip
                refunded = sold.refunded + sum(
                    (r.total for r in out if r.sold is not None and r.sold.id == sold.id), ZERO
                )
                total = refund_line(sold.line_total, sold.qty, quantity, before, refunded)
                vat = vat_from_gross(total, sold.vat_rate)
                if before + quantity == sold.qty:  # the line's last return takes the VAT rest too (13 §2.5)
                    earlier_vat = sold.refunded_vat + sum(
                        (r.vat for r in out if r.sold is not None and r.sold.id == sold.id), ZERO
                    )
                    vat = money(sold.vat_amount - earlier_vat)
                taken[sold.id] = taken.get(sold.id, ZERO) + quantity
                unit_price, rate = price(sold.price), percent(sold.vat_rate)
                pieces = await self._original_pieces(s, sale.id, sold, before, quantity, warehouse_id)
                expiry = await self._r.lot_expiry(s, [pc.lot_id for pc in pieces if pc.lot_id is not None])
                expired = any(e is not None and e < today for e in expiry.values())
            else:
                if src.sale_line_id is not None:
                    raise invalid(f"{f}.sale_line_id", "validation.sale_line_without_sale")
                unit_price, rate = price(src.price), percent(src.vat_rate)
                total = line_total(quantity, unit_price)
                vat = vat_from_gross(total, rate)
                pieces = await self._newest_pieces(s, warehouse_id, product.id, quantity, f)
            restock = src.restock and not expired
            out.append(
                ReturnLine(i, src, product, sold, quantity, unit_price, rate, total, vat, pieces, expired,
                           restock)
            )  # fmt: skip
        return out

    async def _counterparty(
        self, s: AsyncSession, p: ReturnCreatedPayload, sale: SoldDoc | None
    ) -> UUID | None:
        """13 §2.5: the debt part belongs to the sale's customer — a return never re-targets it (ACC-02)."""
        if sale is not None:
            if p.counterparty_id is not None and p.counterparty_id != sale.counterparty_id:
                raise invalid("counterparty_id", "validation.counterparty_mismatch")
            return sale.counterparty_id
        if p.counterparty_id is None:
            return None
        if await self._d.repo.customer(s, p.counterparty_id) is None:  # RLS: this tenant only
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED,
                params={"entity": "counterparties", "id": str(p.counterparty_id)},
            )
        return p.counterparty_id

    async def _original_pieces(
        self,
        s: AsyncSession,
        sale_id: UUID,
        sold: SoldLine,
        before: Decimal,
        quantity: Decimal,
        warehouse_id: UUID,
    ) -> list[Allocation]:
        """13 §3.2a: the original line's live allocations, reverse order, skipping earlier returns."""
        issued = await self._live_allocations(s, sale_id, sold.id)
        pieces = return_pieces(issued, before, quantity)
        if any(pc.lot_id is None for pc in pieces):  # oversold, not settled by a receipt yet (13 §3.1)
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED,
                params={
                    "entity": "stock_lots",
                    "sale_line_id": str(sold.id),
                    "warehouse_id": str(warehouse_id),
                },
            )
        return pieces

    async def _live_allocations(self, s: AsyncSession, sale_id: UUID, line_id: UUID) -> list[Allocation]:
        rows = await self._d.stock.repo.doc_moves(s, "sales", sale_id, live_only=True)
        out: list[Allocation] = []
        for m in rows:
            if m.line_id != line_id or m.qty >= 0:
                continue
            q = -m.qty
            out.append(Allocation(m.lot_id, q, price(-m.cost_amount / q), pending=m.lot_id is None))
        return out

    async def _newest_pieces(
        self, s: AsyncSession, warehouse_id: UUID, product_id: UUID, quantity: Decimal, f: str
    ) -> list[Allocation]:
        """No original receipt: the newest lots with sold room take the units back at their unit cost."""
        need = quantity
        out: list[Allocation] = []
        for lot in await self._r.free_lots(s, warehouse_id, product_id):
            take = min(need, lot.room)
            if take > 0:
                out.append(Allocation(lot.lot_id, take, lot.unit_cost))
                need -= take
            if need == 0:
                break
        if need > 0:
            raise invalid(f"{f}.qty", "validation.return_exceeds_sold_stock")
        return out

    @staticmethod
    def _check_marking(
        f: str, p: ReturnCreatedPayload, src: ReturnLinePayload, product: ProductInfo, quantity: Decimal
    ) -> None:
        if product.is_marked and src.marking_code is None:
            raise invalid(f"{f}.marking_code", "validation.marking_code_required")
        if not product.is_marked and src.marking_code is not None:
            raise invalid(f"{f}.marking_code", "validation.marking_code_unexpected")
        if src.marking_code is None:
            return
        if p.is_offline:
            raise AppError(ErrorCode.MARKING_RETURN_REQUIRES_ONLINE, params={"line": f})
        if quantity != Decimal("1.000"):
            raise invalid(f"{f}.qty", "validation.marking_qty_single")
        if not marking_code_valid(src.marking_code):
            raise AppError(ErrorCode.MARKING_CODE_INVALID, params={"line": f})

    def _check_receipt_fields(self, p: ReturnCreatedPayload, issues_receipt: bool) -> None:
        if issues_receipt and p.receipt_seq is None:
            raise invalid("receipt_seq", "validation.required")
        if not issues_receipt and p.receipt_seq is not None:
            raise invalid("receipt_seq", "validation.receipt_seq_no_money_part")
        if not issues_receipt and p.fiscal_result is not None:
            raise invalid("fiscal_result", "validation.fiscal_result_unexpected")
        if issues_receipt and p.fiscal_result is None and self._d.fiscal_provider in LOCAL_PROVIDERS:
            raise invalid("fiscal_result", "validation.required")
        if p.refund_method == "uzqr" and p.is_offline:
            raise invalid("refund_method", "validation.uzqr_online_only")
        if p.refund_method == "card" and issues_receipt and p.refund_card is None:
            raise invalid("refund_card", "validation.required")
        if p.refund_card is not None and (p.refund_method != "card" or not issues_receipt):
            raise invalid("refund_card", "validation.refund_card_unexpected")

    @staticmethod
    def _check_refund_card(p: ReturnCreatedPayload) -> None:
        """18 §7.1, QT-M01-15: no card requisites from the device (integrated → card_result)."""
        rc = p.refund_card
        if rc is None:
            return
        for name in CARD_DERIVED:
            if getattr(rc, name) is not None:
                key = ("validation.card_manual_details_forbidden" if rc.card_entry_mode == "manual"
                       else "validation.card_details_from_terminal")  # fmt: skip
                raise invalid(f"refund_card.{name}", key)
        if rc.card_entry_mode == "integrated":
            if rc.card_result is None:
                raise invalid("refund_card.card_result", "validation.card_result_required")
            if rc.manual_reason is not None:
                raise invalid("refund_card.manual_reason", "validation.card_manual_reason_unexpected")
        else:
            if rc.card_result is not None:
                raise invalid("refund_card.card_result", "validation.card_manual_details_forbidden")
            if rc.manual_reason is None:
                raise invalid("refund_card.manual_reason", "validation.card_manual_reason_required")

    async def _approve(
        self,
        s: AsyncSession,
        ctx: EventContext,
        p: ReturnCreatedPayload,
        amount: Decimal,
        expired: bool,
        out: _Out,
    ) -> tuple[UUID | None, datetime | None]:
        no_receipt = p.sale_id is None
        missing: str | None = None
        if expired and not no_receipt:
            missing = ErrorCode.APPROVAL_REQUIRED.value
        outcome = await self._d.approvals.require(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id,
            kind="return_no_receipt" if no_receipt else "return_over_limit", permission="returns.approve",
            requested_by=ctx.actor_user_id, value=UNLIMITED_ONLY if expired else amount,
            approval=approval_in(p.approval), doc_type=DOC_TYPE, doc_id=p.id, offline=p.is_offline,
            always_required=no_receipt, missing_code=missing, approver_bound=ctx.actor_bound,
        )  # fmt: skip
        flag_unverified(out, ctx, outcome, p.id)
        if outcome.offline_limit_exceeded:
            out.flag("approval_limit_exceeded_offline", p.id, approval_kind="return", **dict(outcome.details))
        if not outcome.required:
            return (ctx.actor_user_id, ctx.created_at) if no_receipt else (None, None)
        approver = await self._r.approver_of(s, outcome.doc_approval_id) if outcome.doc_approval_id else None
        return approver or (p.approval.approved_by if p.approval else None), ctx.created_at

    async def _refund_card(
        self, s: AsyncSession, ctx: EventContext, p: ReturnCreatedPayload, money_part: Decimal, out: _Out
    ) -> dict[str, Any]:
        cols: dict[str, Any] = dict.fromkeys(
            ("card_entry_mode", "card_terminal_transaction_id", "card_type", "card_mask", "rrn",
            "approval_code",
             "card_scheme", "manual_reason"),
        )  # fmt: skip
        rc: RefundCardPayload | None = p.refund_card
        if p.refund_method != "card" or rc is None or money_part <= 0:
            return cols
        cols["card_entry_mode"] = rc.card_entry_mode
        if rc.card_entry_mode == "integrated":
            assert rc.card_result is not None
            kind: Literal["refund", "void"] = (
                "void" if str(rc.card_result.get("kind")) == "void" else "refund"
            )
            rec = await self._d.cards.link_result(
                s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, cash_register_id=p.cash_register_id,
                shift_id=p.shift_id, card_result=rc.card_result, expected_amount=money_part, kind=kind,
                doc_type=DOC_TYPE, doc_id=p.id, client_event_id=ctx.client_event_id,
                actor_user_id=ctx.actor_user_id, device_id=ctx.device_id,
            )  # fmt: skip
            cols.update(
                card_terminal_transaction_id=rec.id, card_type=rec.card_type, card_mask=rec.card_mask,
                rrn=rec.rrn,
                approval_code=rec.approval_code, card_scheme=rec.card_scheme,
            )  # fmt: skip
            if rec.mismatch is not None:
                if ErrorCode.CARD_TRANSACTION_MISMATCH.value not in out.warnings:
                    out.warnings.append(ErrorCode.CARD_TRANSACTION_MISMATCH.value)
                out.flag("card_result_mismatch", p.id, **dict(rec.mismatch))
            return cols
        assert rc.manual_reason is not None
        cols["manual_reason"] = rc.manual_reason
        auth = await self._d.cards.authorize_manual(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, cash_register_id=p.cash_register_id,
            manual_reason=rc.manual_reason, amount=money_part, approval=approval_in(rc.card_manual_approval),
            requested_by=ctx.actor_user_id, doc_type=DOC_TYPE, doc_id=p.id,
            client_event_id=ctx.client_event_id,
            device_id=ctx.device_id, offline=p.is_offline, approver_bound=ctx.actor_bound,
            session_user_id=ctx.session_user_id,
        )  # fmt: skip
        if auth.approver_unverified:  # SEC-02
            out.exceptions.append(
                SyncExceptionRow("actor_unverified", dict(auth.unverified_details), DOC_TYPE, p.id)
            )
        if auth.offline_violation:
            out.flag(
                "approval_limit_exceeded_offline",
                p.id,
                approval_kind="card_manual_entry",
                **dict(auth.details),
            )
        return cols


def _analytics(p: ReturnCreatedPayload, card: Mapping[str, Any]) -> dict[str, Any]:
    if p.refund_method == "cash":
        return {"cash_register_id": str(p.cash_register_id), "shift_id": str(p.shift_id)}
    if p.refund_method == "debt_adjustment":
        return {"counterparty_id": str(p.counterparty_id)}
    out: dict[str, Any] = {"payment_method": p.refund_method}
    if card.get("rrn"):
        out["rrn"] = card["rrn"]
    return out


def _receipt_payload(
    p: ReturnCreatedPayload,
    number: str,
    lines: list[ReturnLine],
    shares: list[Any],
    card: Mapping[str, Any],
    total: Decimal,
) -> dict[str, Any]:
    items = []
    for ln, share in zip(lines, shares, strict=True):
        name = ln.product.name if not ln.product.name_ru else f"{ln.product.name} / {ln.product.name_ru}"
        items.append(
            {
                "line_no": ln.index + 1,
                "sale_line_id": str(ln.src.sale_line_id) if ln.src.sale_line_id else None,
                "product_id": str(ln.product.id), "name": name, "mxik": ln.product.mxik_code,
                "package_code": ln.product.package_code, "unit_code": ln.product.unit_code,
                "qty": qty_str(share.qty), "price": format(ln.unit_price, "f"),
                "vat_rate": format(ln.vat_rate, "f"),
                "vat_amount": money_str(share.vat), "amount": money_str(share.amount),
                "marking_codes": [ln.src.marking_code] if ln.src.marking_code else [],
            }
        )  # fmt: skip
    payment: dict[str, Any] = {"method": p.refund_method, "amount": money_str(total)}
    if p.refund_method == "card":
        payment["card_entry_mode"] = card.get("card_entry_mode")
        if card.get("card_entry_mode") == "integrated":
            payment.update(
                card_type=card.get("card_type"), card_mask=card.get("card_mask"), rrn=card.get("rrn")
            )
    return {
        "kind": "return", "return_id": str(p.id), "sale_id": str(p.sale_id) if p.sale_id else None,
        "number": number, "receipt_seq": p.receipt_seq, "items": items, "total": money_str(total),
        "vat_total": money_str(sum((sh.vat for sh in shares), ZERO)), "payments": [payment],
        "is_offline": p.is_offline,
    }  # fmt: skip
