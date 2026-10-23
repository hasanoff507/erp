"""``sale.created`` — the POS sale posting (18 §4, 13 §2.1–§2.4, §3, §4.1; 16 §5–§7; 23 §2.1).

Runs inside the per-event transaction of ``/sync/push`` (sync handler contract): document + lines +
payments, stock issue (FIFO/AVECO, ``Dt 9120 / Kt inv_acct``), ``cash_moves``, ``debt_moves`` (debt part,
13 §2.3/§2.4), revenue/VAT ledger (:func:`sales.domain.posting.document_ledger`), ``vat_moves``, marking
codes (``pending_verification``) and the fiscal receipt (``FiscalService``). Any ``AppError`` rejects the
event and nothing it wrote survives.

Accepted-with-flag rules (16 §5): overselling → ``STOCK_NEGATIVE`` + ``sync_exceptions(stock_negative)``;
price differs from the server price in force at the (server-clamped) event time → the receipt price is
frozen, ``sync_exceptions(price_mismatch)`` (CORR-06, QT-M09-09); archived product → ``archived_product``;
offline credit limit / approval / manual-card policy breaches → ``debt_limit_exceeded_offline`` /
``approval_limit_exceeded_offline``; ``doc_date`` in a closed period → registers in the first open period +
``late_in_closed_period`` (qaror #69); card result ≠ server row → ``CARD_TRANSACTION_MISMATCH`` +
``card_result_mismatch``.

Lock order (23 §2.1): shift row (``ShiftGuard``, ``FOR SHARE``) → ``stock_balances`` → ``debt_balances``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money, money_str, percent, price, qty, qty_str, to_decimal
from app.modules.access.application.approval_gate import ApprovalGate, ApprovalOutcome, ApprovalRefIn
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_date, period_label
from app.modules.cash.application.contracts import ShiftGuard
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.integrations.card_terminal.application.contracts import CardPayments
from app.modules.integrations.einvoice.application.hooks import EInvoiceHooksPort
from app.modules.integrations.fiscal.application.contracts import FiscalReceiptRef, FiscalService
from app.modules.integrations.fiscal.domain.rules import payment_form
from app.modules.integrations.marking.application.hooks import MarkingHooks
from app.modules.inventory.application.stock import CostPosting, StockService
from app.modules.sales.application.payloads import (
    ApprovalRefPayload,
    SaleCreatedPayload,
    SaleLinePayload,
    SalePaymentPayload,
    parse,
)
from app.modules.sales.application.ports import CustomerInfo, ProductInfo, SalesRepository
from app.modules.sales.domain.calc import (
    ZERO,
    CalcError,
    LineMath,
    check_line,
    discount_pct,
    fiscal_shares,
    marking_code_valid,
)
from app.modules.sales.domain.posting import COGS, LineAmounts, Part, document_ledger
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncExceptionRow

DOC_TYPE: Final = "sales"
DEVICE_ONLY_FORBIDDEN: Final = (
    "card_type", "card_type_source", "card_mask", "rrn", "approval_code", "card_scheme",
    "card_terminal_transaction_id",
)  # fmt: skip
CHECKOUT_METHODS: Final = frozenset({"click", "payme", "uzum"})
LOCAL_PROVIDERS: Final = frozenset({"multikassa_local", "fiscaldrive_local"})
STANDING_TOLERANCE: Final = Decimal("0.01")
LATE_SYNC: Final = timedelta(minutes=1)
DUPLICATE_KIND: Final = "marking_code_duplicate"  # sync_exceptions kind (B3 F-5, 16 §5)


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def approval_in(ref: ApprovalRefPayload | None) -> ApprovalRefIn | None:
    if ref is None:
        return None
    return ApprovalRefIn(
        mode=ref.mode,
        approved_by=ref.approved_by,
        pin_verified_locally=ref.pin_verified_locally,
        approval_request_id=ref.approval_request_id,
    )


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def parse_ts(raw: str, field: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise invalid(field, "validation.datetime") from None
    if value.tzinfo is None:
        raise invalid(field, "validation.datetime_timezone")
    return value


def fiscal_json(ref: FiscalReceiptRef | None, deferred: bool) -> dict[str, Any]:
    if ref is None:
        return {"status": "deferred" if deferred else "pending", "ofd_acked_at": None, "fm_receipt_seq": None,
                "receipt_seq": None}  # fmt: skip
    return {
        "status": ref.status,
        "ofd_acked_at": iso(ref.ofd_acked_at),
        "fm_receipt_seq": ref.fm_receipt_seq,
        "receipt_seq": ref.receipt_seq,
    }


def flag_unverified(out: Any, ctx: EventContext, outcome: ApprovalOutcome, doc_id: UUID) -> None:
    """SEC-02 (15 §2.3a): an online `local_pin` approver not PIN-bound to the session — detect only;
    /sync/push records the M18 ``over_limit_action`` for the row."""
    if outcome.approver_unverified:
        out.exceptions.append(
            SyncExceptionRow(
                kind="actor_unverified",
                details={**dict(outcome.unverified_details), "session_user_id": str(ctx.session_user_id)},
                doc_type=out.doc_type,
                doc_id=doc_id,
            )
        )


@dataclass
class Outcome:
    """What the posting collects besides the registers (→ ``HandlerResult``)."""

    warnings: list[str] = field(default_factory=list)
    exceptions: list[SyncExceptionRow] = field(default_factory=list)
    after: list[Callable[[], Awaitable[None]]] = field(default_factory=list)
    doc_type: str = DOC_TYPE

    def warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)

    def flag(self, kind: str, doc_id: UUID | None, **details: Any) -> None:
        self.exceptions.append(SyncExceptionRow(kind=kind, details=details, doc_type=DOC_TYPE, doc_id=doc_id))


@dataclass(frozen=True, slots=True)
class CheckedLine:
    index: int
    src: SaleLinePayload
    product: ProductInfo
    math: LineMath
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal
    discount: Decimal


@dataclass(frozen=True, slots=True)
class Deps:
    repo: SalesRepository
    stock: StockService
    poster: LedgerPoster
    debts: DebtRegister
    fiscal: FiscalService
    fiscal_provider: str
    shifts: ShiftGuard
    approvals: ApprovalGate
    cards: CardPayments
    marking: MarkingHooks
    einvoices: EInvoiceHooksPort


class SalePostingHandler:
    """The ``sale.created`` sync handler (``SyncEventHandler`` protocol)."""

    def __init__(self, deps: Deps) -> None:
        self._d = deps

    async def __call__(self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]) -> HandlerResult:
        p = parse(SaleCreatedPayload, payload)
        d, out, at = self._d, Outcome(), ctx.created_at
        if p.branch_id != ctx.branch_id:
            raise invalid("branch_id", "validation.branch_mismatch")
        if ctx.cash_register_id is None or p.cash_register_id != ctx.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_mismatch")
        if await d.repo.sale_exists(s, p.id):
            raise invalid("id", "validation.duplicate_id")
        if await d.repo.temp_number_taken(s, DOC_TYPE, ctx.device_id, p.temp_number):
            raise invalid("temp_number", "validation.duplicate_temp_number")
        shift = await d.shifts.require_open(s, shift_id=p.shift_id, device_id=ctx.device_id, at=at)
        if shift.cash_register_id != p.cash_register_id:
            raise invalid("shift_id", "validation.shift_register_mismatch")
        doc_date = business_date(at)
        policy = await d.repo.tenant_policy(s, doc_date)
        offline_since = parse_ts(p.offline_since, "offline_since") if p.offline_since else None
        if p.is_offline and offline_since is None:
            raise invalid("offline_since", "validation.required")
        lines = await self._check_lines(s, p, at, out)
        total = money(sum((ln.math.total for ln in lines), ZERO))
        debt_total, non_debt = self._check_payments(p, total)
        credit_type = _credit_policy(policy.settings) == "credit_type"
        self._check_fiscal_fields(p, non_debt, debt_total, credit_type)
        customer = await self._customer(s, p, debt_total, lines)
        await self._check_discounts(s, ctx, p, lines, customer, doc_date, out)
        limit_flag = await self._check_credit(s, ctx, p, customer, debt_total, out)
        issues_receipt = non_debt > 0 or (credit_type and debt_total > 0)
        if issues_receipt:
            await d.fiscal.assert_can_issue(s, cash_register_id=p.cash_register_id, at=at)
        await self._consume_checkouts(s, p)
        codes = [(ln.src.marking_code, ln.product.id) for ln in lines if ln.src.marking_code]
        if codes:
            signed = p.fiscal_result is not None  # the FM already signed the receipt (local bridge)
            taken = await d.repo.take_marking_codes(
                s, ctx.tenant_id, [(c, pid) for c, pid in codes if c], p.id, keep_free=signed
            )
            if taken and not signed:  # no receipt with a duplicate code is ever fiscalized (18 §4.2)
                raise AppError(ErrorCode.MARKING_CODE_ALREADY_SOLD, params={"codes": sorted(taken)[:20]})
            if taken:  # signed already: the sale happened — accept, audit, flag, M18 (16 §7, B3 F-5)
                out.warn(ErrorCode.MARKING_CODE_ALREADY_SOLD.value)
                await record_audit(
                    s, tenant_id=ctx.tenant_id, user_id=ctx.actor_user_id, action="marking.verify_failed",
                    entity="sales", entity_id=p.id, device_id=ctx.device_id,
                    after={"reason": "duplicate_code", "codes": sorted(taken)[:20],
                           "client_event_id": str(ctx.client_event_id)},
                )  # fmt: skip
                out.flag(DUPLICATE_KIND, p.id, codes=sorted(taken)[:20], fiscal_signed=True)
                await d.marking.on_signed_duplicate(
                    s, ctx.tenant_id, p.id, branch_id=p.branch_id, device_id=ctx.device_id, codes=taken
                )
            sold = [c for c, _ in codes if c and c not in taken]
            if p.is_offline and sold:  # 16 §7: CRPT check once online (MARKING_PRECHECK != off) + audit
                await d.marking.on_offline_sale(
                    s, ctx.tenant_id, p.id, branch_id=p.branch_id, codes=sold,
                    precheck_mode=str(policy.settings.get("marking_precheck") or "warn"),
                )  # fmt: skip
                await record_audit(
                    s, tenant_id=ctx.tenant_id, user_id=ctx.actor_user_id, action="marking.offline_sold",
                    entity="sales", entity_id=p.id, device_id=ctx.device_id,
                    after={"codes": sold[:20], "price_source": "cache", "created_at": iso(at)},
                )  # fmt: skip

        # --- registers -----------------------------------------------------------------------------
        entry_date = await d.poster.first_open_date(s, doc_date)
        late = entry_date != doc_date
        if late:
            out.flag(
                "late_in_closed_period", p.id, period=period_label(doc_date), doc_date=doc_date.isoformat()
            )
        warehouse_id = await d.repo.sale_warehouse(s, p.branch_id)
        if warehouse_id is None:
            raise invalid("branch_id", "validation.no_sale_warehouse")
        txn = await d.stock.lock(s, ctx.tenant_id, [(warehouse_id, ln.product.id) for ln in lines])
        number = await next_doc_number(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, table=DOC_TYPE, year=doc_date.year
        )
        await d.repo.insert_sale(
            s,
            {
                "id": p.id, "tenant_id": ctx.tenant_id, "branch_id": p.branch_id, "number": number,
                "temp_number": p.temp_number, "doc_date": doc_date, "shift_id": p.shift_id,
                "cash_register_id": p.cash_register_id, "counterparty_id": p.counterparty_id,
                "total_amount": total, "is_offline": p.is_offline, "debt_limit_exceeded": limit_flag,
                "created_by": ctx.actor_user_id, "posted_at": txn.at, "client_event_id": ctx.client_event_id,
                "device_id": ctx.device_id, "comment": p.comment,
            },
        )  # fmt: skip
        shares = fiscal_shares(
            [ln.math.total for ln in lines], [ln.quantity for ln in lines], [ln.vat_rate for ln in lines],
            non_debt,
        )  # fmt: skip
        line_rows: list[dict[str, Any]] = []
        for ln, share in zip(lines, shares, strict=True):
            res = await txn.issue(
                warehouse_id, ln.product.id, ln.quantity, doc_type=DOC_TYPE, doc_id=p.id, line_id=ln.src.id,
                cost=CostPosting(account_dt=COGS, entry_date=entry_date, branch_id=p.branch_id),
                moved_at=at, allow_negative=True,
            )  # fmt: skip
            if res.pending_qty > 0:
                out.warn(ErrorCode.STOCK_NEGATIVE.value)
                out.flag(
                    "stock_negative", p.id, line_id=str(ln.src.id), product_id=str(ln.product.id),
                    warehouse_id=str(warehouse_id), qty=qty_str(res.pending_qty),
                )  # fmt: skip
            if p.is_offline and txn.at - at > LATE_SYNC:
                txn.recost_job_ids.append(
                    await d.stock.queue_recost(
                        s, ctx.tenant_id, (warehouse_id, ln.product.id), doc_date, DOC_TYPE, p.id
                    )
                )
            line_rows.append(
                _line_row(ctx.tenant_id, p.id, ln, money(res.cost), res.allocations_json(), share)
            )
        await d.repo.insert_lines(s, line_rows)
        payment_rows = await self._payment_rows(s, ctx, p, out)
        await d.repo.insert_payments(s, payment_rows)
        await d.repo.insert_cash_moves(
            s,
            [
                {"id": uuid7(), "tenant_id": ctx.tenant_id, "cash_register_id": p.cash_register_id,
                 "shift_id": p.shift_id, "amount": money(to_decimal(pay.amount)), "method": pay.method,
                 "doc_type": DOC_TYPE, "doc_id": p.id}
                for pay in p.payments
                if pay.method != "debt"
            ],
        )  # fmt: skip
        late_row = await d.shifts.settle_late(
            s, tenant_id=ctx.tenant_id, shift=shift, doc_type=DOC_TYPE, doc_id=p.id
        )
        if late_row is not None:  # ACC-01: created before the close, pushed after it (18 §3.2, 13 X-01)
            out.exceptions.append(late_row)
        if debt_total > 0:
            assert p.counterparty_id is not None
            due = next((pay.due_date for pay in p.payments if pay.method == "debt" and pay.due_date), None)
            await d.debts.post(
                s, ctx.tenant_id,
                [DebtMoveInput(p.counterparty_id, "receivable", debt_total, DOC_TYPE, p.id, due, limit_flag)],
            )  # fmt: skip
        base = {"sale_id": str(p.id)}
        if late:
            base["correction_of_period"] = period_label(doc_date)
        ledger, vat = document_ledger(
            kind="sale", entry_date=entry_date, branch_id=p.branch_id,
            parts=[_part(pay, p, row) for pay, row in zip(p.payments, payment_rows, strict=True)],
            lines=[LineAmounts(ln.product.id, ln.math.total, ln.math.vat, ln.vat_rate, ln.math.discount_net)
                   for ln in lines],
            vat_payer=policy.vat_payer, discount_posting=_discount_posting(policy.settings), analytics=base,
        )  # fmt: skip
        await d.poster.post(s, ctx.tenant_id, DOC_TYPE, p.id, ledger, vat)
        if debt_total > 0 and p.counterparty_id is not None:  # US-M01-06: B2B credit sale → e-invoice draft
            await d.einvoices.on_b2b_credit_sale_posted(s, ctx.tenant_id, p.id)

        # --- fiscal receipt(s) ----------------------------------------------------------------------
        receipts: list[FiscalReceiptRef] = []
        main: FiscalReceiptRef | None = None
        if non_debt > 0:
            assert p.receipt_seq is not None
            main = await d.fiscal.record(
                s, kind="sale", doc_id=p.id, cash_register_id=p.cash_register_id, shift_id=p.shift_id,
                receipt_seq=p.receipt_seq,
                payment_form=payment_form(pay.method for pay in p.payments),
                payload=_receipt_payload(p, number, lines, shares, payment_rows, non_debt, "sale"),
                fiscal_result=p.fiscal_result, is_offline=p.is_offline, offline_since=offline_since,
                delivery=p.delivery, delivery_reason=p.delivery_reason, created_at=at,
            )  # fmt: skip
            receipts.append(main)
            if main.renumbered_from is not None:
                out.flag("receipt_seq_conflict", p.id, device_receipt_seq=main.renumbered_from,
                         receipt_seq=main.receipt_seq)  # fmt: skip
        if credit_type and debt_total > 0:
            assert p.credit_receipt_seq is not None
            credit_shares = fiscal_shares(
                [ln.math.total for ln in lines], [ln.quantity for ln in lines], [ln.vat_rate for ln in lines],
                debt_total,
            )  # fmt: skip
            credit = await d.fiscal.record(
                s, kind="credit_sale", doc_id=p.id, cash_register_id=p.cash_register_id, shift_id=p.shift_id,
                receipt_seq=p.credit_receipt_seq, payment_form="cash",
                payload=_receipt_payload(p, number, lines, credit_shares, [], debt_total, "credit_sale"),
                fiscal_result=None, is_offline=p.is_offline, offline_since=offline_since, created_at=at,
            )  # fmt: skip
            receipts.append(credit)
        tenant_id = ctx.tenant_id
        fiscal_ids = [r.id for r in receipts]
        stock = d.stock
        fiscal = d.fiscal

        async def _after() -> None:
            await stock.after_commit(txn)
            await fiscal.enqueue(tenant_id, fiscal_ids)

        out.after.append(_after)
        server = {
            "id": str(p.id),
            "number": number,
            "fiscal_receipt_seq": main.receipt_seq if main else None,
            "fiscal": fiscal_json(main, deferred=non_debt == 0),
            "warnings": list(out.warnings),
        }
        return HandlerResult(
            server=server, warnings=tuple(out.warnings), sync_exceptions=tuple(out.exceptions),
            after_commit=tuple(out.after),
        )  # fmt: skip

    # --- validation ---------------------------------------------------------------------------------
    async def _check_lines(
        self, s: AsyncSession, p: SaleCreatedPayload, at: datetime, out: Outcome
    ) -> list[CheckedLine]:
        ids = list(dict.fromkeys(ln.product_id for ln in p.lines))
        products = await self._d.repo.products(s, ids)
        prices = await self._d.repo.prices_at(s, ids, p.branch_id, at)
        seen_ids: set[UUID] = set()
        seen_codes: set[str] = set()
        checked: list[CheckedLine] = []
        for i, src in enumerate(p.lines):
            f = f"lines[{i}]"
            product = products.get(src.product_id)
            if product is None:
                raise invalid(f"{f}.product_id", "validation.not_found")
            if src.id in seen_ids:
                raise invalid(f"{f}.id", "validation.duplicate_id")
            seen_ids.add(src.id)
            if src.unit_code != product.unit_code:
                raise invalid(f"{f}.unit_code", "validation.unit_mismatch")
            quantity, unit_price = qty(src.qty), price(src.price)
            if not product.is_fractional and quantity != quantity.to_integral_value():
                raise invalid(f"{f}.qty", "validation.qty_not_whole")
            rate = percent(src.vat_rate)
            amount = money(to_decimal(src.discount_amount)) if src.discount_amount is not None else ZERO
            if (amount > 0) != (src.discount_source is not None):
                raise invalid(f"{f}.discount_source", "validation.discount_source_mismatch")
            if src.discount_source == "rule" and src.discount_rule_id is None:
                raise invalid(f"{f}.discount_rule_id", "validation.required")
            if src.discount_source != "rule" and src.discount_rule_id is not None:
                raise invalid(f"{f}.discount_rule_id", "validation.discount_rule_unexpected")
            if src.discount_approval is not None and src.discount_source != "manual":
                raise invalid(f"{f}.discount_approval", "validation.discount_approval_unexpected")
            if src.discount_pct is not None and percent(src.discount_pct) > 100:
                raise invalid(f"{f}.discount_pct", "validation.less_than_equal")
            try:
                math = check_line(quantity, unit_price, rate, amount, to_decimal(src.line_total),
                                  to_decimal(src.vat_amount))  # fmt: skip
            except CalcError as exc:
                raise invalid(f"{f}.{exc.field}", exc.message_key) from None
            server_price = prices.get(product.id)
            self._check_marking(f, src, product, quantity, seen_codes, p.is_offline, server_price)
            if product.archived_at is not None:
                out.flag("archived_product", p.id, line_id=str(src.id), product_id=str(product.id))
            if server_price is None or price(server_price) != unit_price:
                out.flag(
                    "price_mismatch", p.id, line_id=str(src.id), product_id=str(product.id),
                    device_price=format(unit_price, "f"),
                    server_price=format(price(server_price), "f") if server_price is not None else None,
                )  # fmt: skip
            checked.append(CheckedLine(i, src, product, math, quantity, unit_price, rate, amount))
        return checked

    @staticmethod
    def _check_marking(
        f: str,
        src: SaleLinePayload,
        product: ProductInfo,
        quantity: Decimal,
        seen: set[str],
        offline: bool,
        server_price: Decimal | None,
    ) -> None:
        code = src.marking_code
        if not product.is_marked:
            if code is not None:
                raise invalid(f"{f}.marking_code", "validation.marking_code_unexpected")
            return
        if code is None:
            raise invalid(f"{f}.marking_code", "validation.marking_code_required")
        if quantity != Decimal("1.000"):
            raise invalid(f"{f}.qty", "validation.marking_qty_single")
        if not marking_code_valid(code):
            raise AppError(ErrorCode.MARKING_CODE_INVALID, params={"line": f})
        if code in seen:
            raise invalid(f"{f}.marking_code", "validation.marking_code_duplicate")
        seen.add(code)
        if offline and server_price is None:
            raise AppError(ErrorCode.MARKING_PRICE_UNKNOWN_OFFLINE, params={"product_id": str(product.id)})

    def _check_payments(self, p: SaleCreatedPayload, total: Decimal) -> tuple[Decimal, Decimal]:
        debt_total = ZERO
        for i, pay in enumerate(p.payments):
            f = f"payments[{i}]"
            _payment_shape(f, pay, p.is_offline)
            if pay.method == "debt":
                debt_total += to_decimal(pay.amount)
        amounts = money(sum((to_decimal(pay.amount) for pay in p.payments), ZERO))
        if amounts != total:
            raise invalid("payments", "validation.payments_total_mismatch")
        if debt_total > 0 and p.counterparty_id is None:
            raise invalid("counterparty_id", "validation.required")
        debt_total = money(debt_total)
        return debt_total, money(total - debt_total)

    def _check_fiscal_fields(
        self, p: SaleCreatedPayload, non_debt: Decimal, debt_total: Decimal, credit_type: bool
    ) -> None:
        if non_debt > 0 and p.receipt_seq is None:
            raise invalid("receipt_seq", "validation.required")
        if non_debt == 0 and p.receipt_seq is not None:
            raise invalid("receipt_seq", "validation.receipt_seq_debt_only")
        needs_credit = credit_type and debt_total > 0
        if needs_credit and p.credit_receipt_seq is None:
            raise invalid("credit_receipt_seq", "validation.required")
        if not needs_credit and p.credit_receipt_seq is not None:
            raise invalid("credit_receipt_seq", "validation.credit_receipt_seq_unexpected")
        if p.delivery == "electronic" and p.delivery_reason is None:
            raise invalid("delivery_reason", "validation.required")
        if p.delivery == "printed" and p.delivery_reason is not None:
            raise invalid("delivery_reason", "validation.delivery_reason_unexpected")
        if p.fiscal_result is not None and non_debt == 0:
            raise invalid("fiscal_result", "validation.fiscal_result_unexpected")
        if non_debt > 0 and p.fiscal_result is None and self._d.fiscal_provider in LOCAL_PROVIDERS:
            raise invalid("fiscal_result", "validation.required")

    async def _customer(
        self, s: AsyncSession, p: SaleCreatedPayload, debt_total: Decimal, lines: Sequence[CheckedLine]
    ) -> CustomerInfo | None:
        if p.counterparty_id is None:
            return None
        customer = await self._d.repo.customer(s, p.counterparty_id)
        if customer is None:
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED,
                params={"entity": "counterparties", "id": str(p.counterparty_id)},
            )
        return customer

    async def _check_discounts(
        self,
        s: AsyncSession,
        ctx: EventContext,
        p: SaleCreatedPayload,
        lines: Sequence[CheckedLine],
        customer: CustomerInfo | None,
        doc_date: date,
        out: Outcome,
    ) -> None:
        manual = [ln for ln in lines if ln.src.discount_source == "manual"]
        for ln in lines:
            f = f"lines[{ln.index}]"
            if ln.src.discount_source == "standing_customer":
                standing = customer.standing_discount_pct if customer else None
                if standing is None:
                    raise invalid(f"{f}.discount_source", "validation.standing_discount_missing")
                if discount_pct(ln.discount, ln.math.gross) > percent(standing) + STANDING_TOLERANCE:
                    raise invalid(f"{f}.discount_amount", "validation.discount_exceeds_standing")
            elif ln.src.discount_source == "rule":
                await self._check_rule(s, f, p, ln, doc_date, out)
        if not manual:
            return
        gross = sum((ln.math.gross for ln in manual), ZERO)
        pct = discount_pct(sum((ln.discount for ln in manual), ZERO), gross)
        ref = next((ln.src.discount_approval for ln in manual if ln.src.discount_approval), None)
        outcome = await self._d.approvals.require(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, kind="discount_over_limit",
            permission="discount.give", requested_by=ctx.actor_user_id, value=pct, approval=approval_in(ref),
            doc_type=DOC_TYPE, doc_id=p.id, offline=p.is_offline, line_id=manual[0].src.id,
            approver_bound=ctx.actor_bound,
        )  # fmt: skip
        flag_unverified(out, ctx, outcome, p.id)
        if outcome.offline_limit_exceeded:
            out.flag(
                "approval_limit_exceeded_offline",
                p.id,
                approval_kind="discount_over_limit",
                **dict(outcome.details),
            )

    async def _check_rule(
        self, s: AsyncSession, f: str, p: SaleCreatedPayload, ln: CheckedLine, doc_date: date, out: Outcome
    ) -> None:
        assert ln.src.discount_rule_id is not None
        rule = await self._d.repo.discount_rule(s, ln.src.discount_rule_id)
        if rule is None:
            raise invalid(f"{f}.discount_rule_id", "validation.not_found")
        applies = rule.scope == "all" or (rule.scope == "product" and ln.product.id in rule.target_ids)
        if rule.scope == "category":
            applies = await self._d.repo.product_category(s, ln.product.id) in rule.target_ids
        active = (
            rule.archived_at is None
            and rule.valid_from <= doc_date
            and (rule.valid_to is None or doc_date <= rule.valid_to)
            and (not rule.branch_ids or p.branch_id in rule.branch_ids)
        )
        if not (applies and active):  # frozen like a price (16 §5) — accepted, reviewed by the accountant
            out.flag(
                "price_mismatch", p.id, line_id=str(ln.src.id), product_id=str(ln.product.id),
                discount_rule_id=str(rule.id), reason="discount_rule_not_in_force",
            )  # fmt: skip

    async def _check_credit(
        self,
        s: AsyncSession,
        ctx: EventContext,
        p: SaleCreatedPayload,
        customer: CustomerInfo | None,
        debt_total: Decimal,
        out: Outcome,
    ) -> bool:
        if debt_total <= 0 or customer is None or customer.credit_limit is None:
            return False
        balances = await self._d.debts.lock(s, ctx.tenant_id, [(customer.id, "receivable")])
        requested = money(balances.get((customer.id, "receivable"), ZERO) + debt_total)
        if requested <= customer.credit_limit:
            return False
        params = {"limit": money_str(customer.credit_limit), "requested": money_str(requested)}
        if p.is_offline:  # 18 §4.3: never blocked offline — flag + M18
            out.warn(ErrorCode.DEBT_LIMIT_EXCEEDED.value)
            out.flag("debt_limit_exceeded_offline", p.id, counterparty_id=str(customer.id), **params)
            return True
        ref = next(
            (pay.debt_approval for pay in p.payments if pay.method == "debt" and pay.debt_approval), None
        )
        if ref is None:
            raise AppError(ErrorCode.DEBT_LIMIT_EXCEEDED, params=params)
        outcome = await self._d.approvals.require(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, kind="debt_over_limit",
            permission="debts.approve",
            requested_by=ctx.actor_user_id, value=requested, approval=approval_in(ref), doc_type=DOC_TYPE,
            doc_id=p.id, offline=False, always_required=True,
            missing_code=ErrorCode.DEBT_LIMIT_EXCEEDED.value, approver_bound=ctx.actor_bound,
        )  # fmt: skip
        flag_unverified(out, ctx, outcome, p.id)
        return False

    async def _consume_checkouts(self, s: AsyncSession, p: SaleCreatedPayload) -> None:
        for i, pay in enumerate(p.payments):
            if pay.checkout_ref is None:
                continue
            found = await self._d.repo.checkout(s, pay.checkout_ref)
            ok = (
                found is not None
                and found.status == "confirmed"
                and found.provider == pay.method
                and found.cash_register_id == p.cash_register_id
                and money(found.amount) == money(to_decimal(pay.amount))
                # a confirmed checkout always carries the provider transaction it was paid by (18 §16.4)
                and found.provider_tx_id is not None
                and found.provider_tx_id == pay.provider_tx_id
            )
            if not ok:
                raise AppError(
                    ErrorCode.PAYMENT_NOT_CONFIRMED,
                    params={"checkout_ref": str(pay.checkout_ref), "payment": i},
                )
            await self._d.repo.consume_checkout(s, pay.checkout_ref)

    async def _payment_rows(
        self, s: AsyncSession, ctx: EventContext, p: SaleCreatedPayload, out: Outcome
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for pay in p.payments:
            row: dict[str, Any] = {
                "id": uuid7(), "tenant_id": ctx.tenant_id, "sale_id": p.id, "method": pay.method,
                "amount": money(to_decimal(pay.amount)), "provider_tx_id": pay.provider_tx_id,
                "terminal_ref": pay.terminal_ref if pay.method == "uzqr" else None, "card_type": None,
                "card_mask": None, "rrn": None, "qr_type": pay.qr_type,
                "due_date": pay.due_date if pay.method == "debt" else None, "checkout_ref": pay.checkout_ref,
                "card_entry_mode": pay.card_entry_mode, "card_terminal_transaction_id": None,
                "approval_code": None, "card_scheme": None, "card_type_source": None,
                "manual_reason": pay.manual_reason,
            }  # fmt: skip
            if pay.method == "card" and pay.card_entry_mode == "integrated":
                assert pay.card_result is not None
                rec = await self._d.cards.link_result(
                    s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, cash_register_id=p.cash_register_id,
                    shift_id=p.shift_id, card_result=pay.card_result, expected_amount=row["amount"],
                    kind="purchase", doc_type=DOC_TYPE, doc_id=p.id, client_event_id=ctx.client_event_id,
                    actor_user_id=ctx.actor_user_id, device_id=ctx.device_id,
                )  # fmt: skip
                row.update(
                    card_terminal_transaction_id=rec.id, card_type=rec.card_type or "unknown",
                    card_type_source=rec.card_type_source or "bin_table", card_mask=rec.card_mask,
                    rrn=rec.rrn,
                    approval_code=rec.approval_code, card_scheme=rec.card_scheme, terminal_ref=rec.tid,
                )  # fmt: skip
                if rec.mismatch is not None:
                    out.warn(ErrorCode.CARD_TRANSACTION_MISMATCH.value)
                    out.flag("card_result_mismatch", p.id, **dict(rec.mismatch))
            elif pay.method == "card":
                assert pay.manual_reason is not None
                auth = await self._d.cards.authorize_manual(
                    s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, cash_register_id=p.cash_register_id,
                    manual_reason=pay.manual_reason, amount=row["amount"],
                    approval=approval_in(pay.card_manual_approval), requested_by=ctx.actor_user_id,
                    doc_type=DOC_TYPE, doc_id=p.id, client_event_id=ctx.client_event_id,
                    device_id=ctx.device_id, offline=p.is_offline, line_id=row["id"],
                    approver_bound=ctx.actor_bound, session_user_id=ctx.session_user_id,
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
            rows.append(row)
        return rows


# --- helpers ------------------------------------------------------------------------------------------
def _credit_policy(settings: Mapping[str, Any]) -> str:
    fiscal = settings.get("fiscal_policy")
    value = fiscal.get("credit_sale_receipt") if isinstance(fiscal, Mapping) else None
    return str(value or "none")


def _discount_posting(settings: Mapping[str, Any]) -> Literal["gross_9050", "net"]:
    return "net" if settings.get("discount_posting") == "net" else "gross_9050"


def _payment_shape(f: str, pay: SalePaymentPayload, offline: bool) -> None:
    """18 §4.1 payment row rules (QT-M01-15/-17/-32/-33): the device never sends card requisites."""
    for name in DEVICE_ONLY_FORBIDDEN:
        if getattr(pay, name) is not None:
            key = (
                "validation.card_manual_details_forbidden"
                if pay.method == "card" and pay.card_entry_mode == "manual"
                else "validation.card_details_from_terminal"
                if pay.method == "card"
                else "validation.card_fields_forbidden"
            )
            raise invalid(f"{f}.{name}", key)
    if pay.method == "card":
        if pay.card_entry_mode is None:
            raise invalid(f"{f}.card_entry_mode", "validation.card_entry_mode_required")
        if pay.terminal_ref is not None:
            key = (
                "validation.card_manual_details_forbidden"
                if pay.card_entry_mode == "manual"
                else ("validation.card_details_from_terminal")
            )
            raise invalid(f"{f}.terminal_ref", key)
        if pay.card_entry_mode == "integrated":
            if pay.card_result is None:
                raise invalid(f"{f}.card_result", "validation.card_result_required")
            if pay.manual_reason is not None:
                raise invalid(f"{f}.manual_reason", "validation.card_manual_reason_unexpected")
            if pay.card_manual_approval is not None:
                raise invalid(f"{f}.card_manual_approval", "validation.card_manual_approval_unexpected")
        else:
            if pay.card_result is not None:
                raise invalid(f"{f}.card_result", "validation.card_manual_details_forbidden")
            if pay.manual_reason is None:
                raise invalid(f"{f}.manual_reason", "validation.card_manual_reason_required")
    else:
        for name in ("card_entry_mode", "card_result", "manual_reason", "card_manual_approval"):
            if getattr(pay, name) is not None:
                raise invalid(f"{f}.{name}", "validation.card_fields_forbidden")
    if pay.method == "uzqr":
        if pay.qr_type is None:
            raise invalid(f"{f}.qr_type", "validation.qr_type_required")
        if offline:
            raise invalid(f"{f}.method", "validation.uzqr_online_only")
        if pay.qr_type == "static" and pay.checkout_ref is not None:
            raise invalid(f"{f}.checkout_ref", "validation.checkout_ref_static_qr")
        if pay.qr_type == "dynamic":
            if pay.checkout_ref is None:
                raise invalid(f"{f}.checkout_ref", "validation.required")
            if not pay.provider_tx_id:
                raise invalid(f"{f}.provider_tx_id", "validation.required")
            if pay.terminal_ref is not None:
                raise invalid(f"{f}.terminal_ref", "validation.terminal_ref_static_qr_only")
    else:
        if pay.qr_type is not None:
            raise invalid(f"{f}.qr_type", "validation.qr_type_uzqr_only")
        if pay.terminal_ref is not None and pay.method != "card":
            raise invalid(f"{f}.terminal_ref", "validation.terminal_ref_static_qr_only")
    if pay.method in CHECKOUT_METHODS:
        if offline:
            raise invalid(f"{f}.method", "validation.payment_online_only")
        if pay.checkout_ref is None:
            raise invalid(f"{f}.checkout_ref", "validation.required")
        if not pay.provider_tx_id:
            raise invalid(f"{f}.provider_tx_id", "validation.required")
    elif pay.method != "uzqr":
        if pay.checkout_ref is not None:
            raise invalid(f"{f}.checkout_ref", "validation.checkout_ref_unexpected")
        if pay.provider_tx_id is not None:
            raise invalid(f"{f}.provider_tx_id", "validation.provider_tx_id_unexpected")
    if pay.method != "debt":
        if pay.due_date is not None:
            raise invalid(f"{f}.due_date", "validation.due_date_debt_only")
        if pay.debt_approval is not None:
            raise invalid(f"{f}.debt_approval", "validation.debt_approval_debt_only")


def _line_row(
    tenant_id: UUID,
    sale_id: UUID,
    ln: CheckedLine,
    cost: Decimal,
    allocations: list[dict[str, Any]],
    share: Any,
) -> dict[str, Any]:
    return {
        "id": ln.src.id, "tenant_id": tenant_id, "sale_id": sale_id, "line_no": ln.index + 1,
        "product_id": ln.product.id, "qty": ln.quantity, "price": ln.unit_price,
        "discount_amount": ln.discount,
        "vat_rate": ln.vat_rate, "vat_exemption_code": ln.src.vat_exemption_code,
        "discount_pct": percent(ln.src.discount_pct) if ln.src.discount_pct is not None else (
            discount_pct(ln.discount, ln.math.gross) if ln.discount > 0 else None),
        "discount_source": ln.src.discount_source, "discount_rule_id": ln.src.discount_rule_id,
        "vat_amount": ln.math.vat, "line_total": ln.math.total, "cost_amount": cost,
        "marking_code": ln.src.marking_code, "lot_allocations": allocations,
        "settled_amount": share.amount,
    }  # fmt: skip


def _part(pay: SalePaymentPayload, p: SaleCreatedPayload, row: Mapping[str, Any]) -> Part:
    analytics: dict[str, Any]
    if pay.method == "cash":
        analytics = {"cash_register_id": str(p.cash_register_id), "shift_id": str(p.shift_id)}
    elif pay.method == "debt":
        analytics = {"counterparty_id": str(p.counterparty_id)}
    else:
        analytics = {"payment_method": pay.method}
        if pay.provider_tx_id:
            analytics["provider_tx_id"] = pay.provider_tx_id
        if row.get("rrn"):
            analytics["rrn"] = row["rrn"]
    return Part(pay.method, money(to_decimal(pay.amount)), analytics)


def _receipt_payload(
    p: SaleCreatedPayload,
    number: str,
    lines: Sequence[CheckedLine],
    shares: Sequence[Any],
    payment_rows: Sequence[Mapping[str, Any]],
    total: Decimal,
    kind: str,
) -> dict[str, Any]:
    """``fiscal_receipts.payload`` (21 §1): two-language item names, MXIK, PackageCode, marking codes (GS kept
    as is), VAT per line; card requisites only for integrated card payments (qaror #64/#71, 26 #178)."""
    items = []
    for ln, share in zip(lines, shares, strict=True):
        name = ln.product.name if not ln.product.name_ru else f"{ln.product.name} / {ln.product.name_ru}"
        items.append(
            {
                "line_no": ln.index + 1, "sale_line_id": str(ln.src.id), "product_id": str(ln.product.id),
                "name": name, "mxik": ln.product.mxik_code, "package_code": ln.product.package_code,
                "unit_code": ln.product.unit_code, "qty": qty_str(share.qty),
                "price": format(ln.unit_price, "f"),
                "discount": money_str(ln.discount) if share.amount == ln.math.total else "0.00",
                "vat_rate": format(ln.vat_rate, "f"), "vat_exemption_code": ln.src.vat_exemption_code,
                "vat_amount": money_str(share.vat), "amount": money_str(share.amount),
                "marking_codes": [ln.src.marking_code] if ln.src.marking_code else [],
            }
        )  # fmt: skip
    payments = []
    for row in payment_rows:
        if row["method"] == "debt":
            continue
        entry: dict[str, Any] = {"method": row["method"], "amount": money_str(row["amount"])}
        if row["method"] == "card":
            entry["card_entry_mode"] = row["card_entry_mode"]
            if row["card_entry_mode"] == "integrated":
                entry.update(card_type=row["card_type"], card_mask=row["card_mask"], rrn=row["rrn"])
        payments.append(entry)
    return {
        "kind": kind, "sale_id": str(p.id), "number": number, "temp_number": p.temp_number,
        "receipt_seq": p.receipt_seq if kind == "sale" else p.credit_receipt_seq,
        "items": items, "total": money_str(total),
        "vat_total": money_str(sum((sh.vat for sh in shares), ZERO)), "payments": payments,
        "is_offline": p.is_offline, "delivery": p.delivery,
    }  # fmt: skip
