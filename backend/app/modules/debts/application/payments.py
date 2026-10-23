"""Debt payments — ``DebtPaymentPostingService`` (18 §12.2–§12.3, 13 §2.14; qaror #30, #45, #67).

Both entry points land here: the POS event ``debt_payment.created`` (:class:`DebtPaymentHandler`, offline too
—
cash/card/uzqr/click/payme/uzum with register, shift and a ``debt_settlement`` receipt) and the back-office
REST
``POST /debt-payments`` → ``/post`` (``method='bank'`` only, no register, no receipt).

Posting (inside the caller's tenant transaction; lock order 23 §2.1 — shift ``FOR SHARE`` →
``debt_balances``):

1. lock ``debt_balances(counterparty, receivable)`` — two payments of one customer serialise;
2. rebuild the customer's open documents from the DB (sales + openings + written-off debt) and run the shared
   allocation (``app.shared.debt_allocation``) — the registers follow the SERVER result (16 §5);
3. online/REST: ``amount > Σ open`` (sales/openings reconciled to the balance, ACC-02) →
   ``422 VALIDATION_ERROR`` ``errors.debt_payment_exceeds_balance`` (qaror #45);
   offline: accepted — the rest is ``unallocated_amount`` (``Kt 6310``) +
   ``sync_exceptions(debt_overpayment_offline)``
   + M18 to the Owner (qaror #67);
4. ``debt_payment_allocations``; ``debt_moves(receivable, −a)`` per sales/opening allocation (a written-off
part
   does not reopen the debt); ledger ``Dt 5010/5710/5110 / Kt 4010 | 9390 | 6310``;
   ``sale_lines.settled_amount``
   += the server's receipt lines; ``counterparties.debt_due_date`` = ``promise_date`` while debt remains.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money, money_str, qty_str, to_decimal, vat_from_gross
from app.modules.access.application.approval_gate import ApprovalRefIn
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_date, period_label
from app.modules.cash.application.contracts import ShiftGuard
from app.modules.debts.application.counterparties import CounterpartyDirectory
from app.modules.debts.application.doc_ports import DebtDocsRepository, SaleLineRow, TargetDoc
from app.modules.debts.application.open_docs import reconciled_targets
from app.modules.debts.application.payloads import (
    ApprovalRefPayload,
    DebtPaymentCreatedPayload,
    FiscalLinePayload,
    parse,
)
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.documents import CHECKOUT_METHODS, PaymentPosting, payment_ledger
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.integrations.card_terminal.application.contracts import CardPayments
from app.modules.integrations.fiscal.application.contracts import FiscalReceiptRef, FiscalService
from app.modules.integrations.fiscal.domain.rules import payment_form
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncExceptionRow
from app.shared.debt_allocation import (
    AllocationResult,
    FiscalLine,
    OpenDoc,
    OpenLine,
    allocate,
    allocation_json,
    fiscal_line_json,
)

DOC_TYPE: Final = "debt_payments"
ZERO: Final = Decimal("0.00")
LOCAL_PROVIDERS: Final = frozenset({"multikassa_local", "fiscaldrive_local"})
DEVICE_ONLY_FORBIDDEN: Final = (
    "card_type",
    "card_type_source",
    "card_mask",
    "rrn",
    "approval_code",
    "card_scheme",
    "card_terminal_transaction_id",
)
GENERAL_LINE_NAME: Final = "Qarz to'lovi (boshlang'ich qoldiq) / Погашение долга (начальный остаток)"
OVERPAY_NOTIFY_KIND: Final = "over_limit_action"  # 20 #69 has no own kind; the payload says why


class EventRecorderPort(Protocol):
    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def exceeds_balance(balance: Decimal, requested: Decimal) -> AppError:
    """qaror #45 — online/REST overpayment; the cashier gives the change in cash."""
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        message_key="errors.debt_payment_exceeds_balance",
        params={"balance": money_str(balance), "requested": money_str(requested), "field": "amount"},
        details=[ErrorDetail(field="amount", message_key="errors.debt_payment_exceeds_balance")],
    )


def to_open_docs(targets: Sequence[TargetDoc], lines: Mapping[UUID, Sequence[SaleLineRow]]) -> list[OpenDoc]:
    """DB targets → the input of the shared allocation (16 §1 ``open_debt_docs`` without presentation
    fields)."""
    out: list[OpenDoc] = []
    for t in targets:
        sale_lines = lines.get(t.doc_id, ()) if t.doc_type == "sales" else ()
        out.append(
            OpenDoc(
                doc_type=t.doc_type,
                doc_id=str(t.doc_id),
                doc_date=t.doc_date.isoformat(),
                due_date=t.due_date.isoformat() if t.due_date else None,
                open_amount=money(t.open_amount),
                lines=tuple(
                    OpenLine(
                        sale_line_id=str(ln.sale_line_id),
                        product_id=str(ln.product_id),
                        qty=ln.qty,
                        line_total=ln.line_total,
                        vat_rate=ln.vat_rate,
                        settled_amount=ln.settled_amount,
                        marking_code=ln.marking_code,
                        returned_qty=ln.returned_qty,
                        returned_amount=ln.returned_amount,
                    )
                    for ln in sale_lines
                ),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class PaymentPlan:
    counterparty_id: UUID
    amount: Decimal
    balance_before: Decimal  # debt_balances receivable before the payment
    open_total: Decimal  # Σ open (sales + openings + written-off debt) — the online limit
    result: AllocationResult
    lines: Mapping[UUID, Sequence[SaleLineRow]]

    @property
    def debt_part(self) -> Decimal:
        return money(self.result.amount_for("sales") + self.result.amount_for("debt_openings"))

    @property
    def remaining_balance(self) -> Decimal:
        return money(self.balance_before - self.debt_part)


@dataclass(frozen=True, slots=True)
class PaymentWrite:
    tenant_id: UUID
    payment_id: UUID
    branch_id: UUID
    method: str
    entry_date: date
    money_analytics: Mapping[str, Any]
    extra_analytics: Mapping[str, Any]
    promise_date: date | None


class DebtPaymentPostingService:
    """The one posting service of ``debt_payments`` (18 §1 band 7) — runs in the caller's transaction."""

    def __init__(self, repo: DebtDocsRepository, register: DebtRegister, poster: LedgerPoster) -> None:
        self._repo = repo
        self._register = register
        self._poster = poster

    @property
    def poster(self) -> LedgerPoster:
        return self._poster

    async def open_docs(
        self, s: AsyncSession, counterparty_id: UUID, balance: Decimal | None = None
    ) -> tuple[list[TargetDoc], dict[UUID, list[SaleLineRow]]]:
        """The customer's open documents reconciled to the receivable ``balance`` (ACC-02; read from
        ``debt_balances`` when not given — pass the locked balance inside a posting)."""
        balances = None if balance is None else {counterparty_id: balance}
        targets = (await reconciled_targets(self._repo, s, [counterparty_id], balances=balances))[
            counterparty_id
        ]
        lines = await self._repo.sale_lines(s, [t.doc_id for t in targets if t.doc_type == "sales"])
        return targets, lines

    async def plan(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        counterparty_id: UUID,
        amount: Decimal,
        *,
        online: bool,
        fiscal: bool,
    ) -> PaymentPlan:
        balances = await self._register.lock(s, tenant_id, [(counterparty_id, "receivable")])
        balance = money(balances.get((counterparty_id, "receivable"), ZERO))
        targets, lines = await self.open_docs(s, counterparty_id, balance)
        docs = to_open_docs(targets, lines)
        open_total = money(sum((d.open_amount for d in docs), ZERO))  # Σ reconciled + Σ written-off open
        if online and amount > open_total:
            raise exceeds_balance(open_total, amount)
        result = allocate(amount, docs, fiscal=fiscal)
        return PaymentPlan(counterparty_id, amount, balance, open_total, result, lines)

    async def write(self, s: AsyncSession, plan: PaymentPlan, w: PaymentWrite) -> None:
        result = plan.result
        await self._repo.insert_allocations(
            s,
            "debt_payment_allocations",
            [
                {
                    "id": uuid7(),
                    "tenant_id": w.tenant_id,
                    "debt_payment_id": w.payment_id,
                    "target_doc_type": a.target_doc_type,
                    "target_doc_id": UUID(a.target_doc_id),
                    "amount": a.amount,
                }
                for a in result.allocations
            ],
        )
        moves = [
            DebtMoveInput(plan.counterparty_id, "receivable", -a.amount, DOC_TYPE, w.payment_id)
            for a in result.allocations
            if a.target_doc_type != "debt_writeoffs"
        ]
        await self._register.post(s, w.tenant_id, moves)
        posting = PaymentPosting(
            entry_date=w.entry_date,
            branch_id=w.branch_id,
            method=w.method,
            counterparty_id=plan.counterparty_id,
            payment_id=w.payment_id,
            money_analytics=w.money_analytics,
            extra=w.extra_analytics,
        )
        await self._poster.post(s, w.tenant_id, DOC_TYPE, w.payment_id, payment_ledger(posting, result))
        settled = {UUID(k): v for k, v in result.settled_by_line().items()}
        await self._repo.add_settled(s, settled)
        await self._repo.touch_balance(s, plan.counterparty_id)
        if plan.remaining_balance <= 0:
            await self._repo.set_due_date(s, plan.counterparty_id, None)
        elif w.promise_date is not None:
            await self._repo.set_due_date(s, plan.counterparty_id, w.promise_date)


def allocations_out(result: AllocationResult) -> list[dict[str, str]]:
    return [allocation_json(a) for a in result.allocations]


def _approval(ref: ApprovalRefPayload | None) -> ApprovalRefIn | None:
    if ref is None:
        return None
    return ApprovalRefIn(ref.mode, ref.approved_by, ref.pin_verified_locally, ref.approval_request_id)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def _parse_ts(raw: str, field_name: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise invalid(field_name, "validation.datetime") from None
    if value.tzinfo is None:
        raise invalid(field_name, "validation.datetime_timezone")
    return value


def check_payment_shape(p: DebtPaymentCreatedPayload) -> None:
    """18 §12.2 = 18 §4.1 ``payments[]`` rules (qaror #64/#71): the device never sends card requisites."""
    for name in DEVICE_ONLY_FORBIDDEN:
        if getattr(p, name) is not None:
            key = (
                "validation.card_manual_details_forbidden"
                if p.method == "card" and p.card_entry_mode == "manual"
                else "validation.card_details_from_terminal"
                if p.method == "card"
                else "validation.card_fields_forbidden"
            )
            raise invalid(name, key)
    if p.method == "card":
        if p.card_entry_mode is None:
            raise invalid("card_entry_mode", "validation.card_entry_mode_required")
        if p.terminal_ref is not None:
            key = (
                "validation.card_manual_details_forbidden"
                if p.card_entry_mode == "manual"
                else "validation.card_details_from_terminal"
            )
            raise invalid("terminal_ref", key)
        if p.card_entry_mode == "integrated":
            if p.card_result is None:
                raise invalid("card_result", "validation.card_result_required")
            if p.manual_reason is not None:
                raise invalid("manual_reason", "validation.card_manual_reason_unexpected")
            if p.card_manual_approval is not None:
                raise invalid("card_manual_approval", "validation.card_manual_approval_unexpected")
        else:
            if p.card_result is not None:
                raise invalid("card_result", "validation.card_manual_details_forbidden")
            if p.manual_reason is None:
                raise invalid("manual_reason", "validation.card_manual_reason_required")
    else:
        for name in ("card_entry_mode", "card_result", "manual_reason", "card_manual_approval"):
            if getattr(p, name) is not None:
                raise invalid(name, "validation.card_fields_forbidden")
    if p.method == "uzqr":
        if p.qr_type is None:
            raise invalid("qr_type", "validation.qr_type_required")
        if p.is_offline:
            raise invalid("method", "validation.uzqr_online_only")
        if p.qr_type == "static" and p.checkout_ref is not None:
            raise invalid("checkout_ref", "validation.checkout_ref_static_qr")
        if p.qr_type == "dynamic":
            if p.checkout_ref is None:
                raise invalid("checkout_ref", "validation.required")
            if not p.provider_tx_id:
                raise invalid("provider_tx_id", "validation.required")
            if p.terminal_ref is not None:
                raise invalid("terminal_ref", "validation.terminal_ref_static_qr_only")
    else:
        if p.qr_type is not None:
            raise invalid("qr_type", "validation.qr_type_uzqr_only")
        if p.terminal_ref is not None and p.method != "card":
            raise invalid("terminal_ref", "validation.terminal_ref_static_qr_only")
    if p.method in CHECKOUT_METHODS:
        if p.is_offline:
            raise invalid("method", "validation.payment_online_only")
        if p.checkout_ref is None:
            raise invalid("checkout_ref", "validation.required")
        if not p.provider_tx_id:
            raise invalid("provider_tx_id", "validation.required")
    elif p.method != "uzqr":
        if p.checkout_ref is not None:
            raise invalid("checkout_ref", "validation.checkout_ref_unexpected")
        if p.provider_tx_id is not None:
            raise invalid("provider_tx_id", "validation.provider_tx_id_unexpected")


def check_fiscal_lines(p: DebtPaymentCreatedPayload, amount: Decimal) -> None:
    """The device receipt (18 §12.2 ``fiscal_lines[]``): Σ = the money received, VAT per qaror #26."""
    total = ZERO
    for i, ln in enumerate(p.fiscal_lines):
        line_amount = money(to_decimal(ln.amount))
        if money(to_decimal(ln.vat_amount)) != vat_from_gross(line_amount, ln.vat_rate):
            raise invalid(f"fiscal_lines[{i}].vat_amount", "validation.vat_amount_mismatch")
        if (ln.sale_line_id is None) != (ln.sale_id is None):
            raise invalid(f"fiscal_lines[{i}].sale_line_id", "validation.required")
        total += line_amount
    if money(total) != amount:
        raise invalid("fiscal_lines", "validation.fiscal_lines_total_mismatch")
    device_alloc = sum((money(to_decimal(a.amount)) for a in p.allocations), ZERO)
    if money(device_alloc) > amount:
        raise invalid("allocations", "validation.allocations_exceed_amount")


@dataclass
class _Out:
    warnings: list[str] = field(default_factory=list)
    exceptions: list[SyncExceptionRow] = field(default_factory=list)

    def warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)

    def flag(self, kind: str, doc_id: UUID, **details: Any) -> None:
        self.exceptions.append(SyncExceptionRow(kind=kind, details=details, doc_type=DOC_TYPE, doc_id=doc_id))


@dataclass(frozen=True, slots=True)
class HandlerDeps:
    repo: DebtDocsRepository
    posting: DebtPaymentPostingService
    directory: CounterpartyDirectory
    fiscal: FiscalService
    fiscal_provider: str
    shifts: ShiftGuard
    cards: CardPayments
    events: EventRecorderPort


class DebtPaymentHandler:
    """``debt_payment.created`` (18 §12.2) — the ``SyncEventHandler`` of POS debt payments."""

    def __init__(self, deps: HandlerDeps) -> None:
        self._d = deps

    async def __call__(self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]) -> HandlerResult:
        p = parse(DebtPaymentCreatedPayload, payload)
        d, out, at = self._d, _Out(), ctx.created_at
        if p.branch_id != ctx.branch_id:
            raise invalid("branch_id", "validation.branch_mismatch")
        if ctx.cash_register_id is None or p.cash_register_id != ctx.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_mismatch")
        if await d.repo.get_doc(s, DOC_TYPE, p.id) is not None:
            raise invalid("id", "validation.duplicate_id")
        shift = await d.shifts.require_open(s, shift_id=p.shift_id, device_id=ctx.device_id, at=at)
        if shift.cash_register_id != p.cash_register_id:
            raise invalid("shift_id", "validation.shift_register_mismatch")
        check_payment_shape(p)
        amount = money(to_decimal(p.amount))
        if amount <= 0:
            raise invalid("amount", "validation.positive")
        check_fiscal_lines(p, amount)
        offline_since = _parse_ts(p.offline_since, "offline_since") if p.offline_since else None
        if p.fiscal_result is None and d.fiscal_provider in LOCAL_PROVIDERS:
            raise invalid("fiscal_result", "validation.required")
        customer = await d.directory.get(s, p.counterparty_id)
        if customer is None:
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED,
                params={"entity": "counterparties", "id": str(p.counterparty_id)},
            )
        if not customer.is_customer:
            raise invalid("counterparty_id", "validation.not_a_customer")
        await d.fiscal.assert_can_issue(s, cash_register_id=p.cash_register_id, at=at)
        if p.checkout_ref is not None:
            await self._consume_checkout(s, p, amount)

        doc_date = business_date(at)
        entry_date = await d.posting.poster.first_open_date(s, doc_date)
        extra: dict[str, Any] = {}
        if entry_date != doc_date:
            extra["correction_of_period"] = period_label(doc_date)
            out.flag(
                "late_in_closed_period",
                p.id,
                period=period_label(doc_date),
                doc_date=doc_date.isoformat(),
                entry_date=entry_date.isoformat(),
            )
        plan = await d.posting.plan(
            s, ctx.tenant_id, p.counterparty_id, amount, online=not p.is_offline, fiscal=True
        )
        card = await self._card(s, ctx, p, amount, out)
        number = await next_doc_number(
            s, tenant_id=ctx.tenant_id, branch_id=p.branch_id, table=DOC_TYPE, year=doc_date.year
        )
        await d.repo.insert_doc(
            s,
            DOC_TYPE,
            {
                "id": p.id,
                "tenant_id": ctx.tenant_id,
                "branch_id": p.branch_id,
                "number": number,
                "doc_date": doc_date,
                "status": "posted",
                "counterparty_id": p.counterparty_id,
                "method": p.method,
                "amount": amount,
                "cash_register_id": p.cash_register_id,
                "shift_id": p.shift_id,
                "terminal_ref": p.terminal_ref if p.method == "uzqr" else card.get("terminal_ref"),
                "provider_tx_id": p.provider_tx_id,
                "qr_type": p.qr_type,
                "checkout_ref": p.checkout_ref,
                "card_entry_mode": p.card_entry_mode,
                "card_type": card.get("card_type"),
                "card_mask": card.get("card_mask"),
                "rrn": card.get("rrn"),
                "card_terminal_transaction_id": card.get("card_terminal_transaction_id"),
                "approval_code": card.get("approval_code"),
                "card_scheme": card.get("card_scheme"),
                "card_type_source": card.get("card_type_source"),
                "manual_reason": p.manual_reason,
                "promise_date": p.promise_date,
                "receipt_seq": p.receipt_seq,
                "unallocated_amount": plan.result.unallocated_amount,
                "created_by": ctx.actor_user_id,
                "posted_at": datetime.now(at.tzinfo),
                "client_event_id": ctx.client_event_id,
                "device_id": ctx.device_id,
                "comment": p.comment,
            },
        )
        if p.method == "cash":
            money_analytics: dict[str, Any] = {
                "cash_register_id": str(p.cash_register_id),
                "shift_id": str(p.shift_id),
            }
        else:
            money_analytics = {"payment_method": p.method}
            if p.provider_tx_id:
                money_analytics["provider_tx_id"] = p.provider_tx_id
            if card.get("rrn"):
                money_analytics["rrn"] = card["rrn"]
        await d.posting.write(
            s,
            plan,
            PaymentWrite(
                ctx.tenant_id, p.id, p.branch_id, p.method, entry_date, money_analytics, extra, p.promise_date
            ),
        )
        await d.repo.insert_cash_moves(
            s,
            [
                {
                    "id": uuid7(),
                    "tenant_id": ctx.tenant_id,
                    "cash_register_id": p.cash_register_id,
                    "shift_id": p.shift_id,
                    "amount": amount,
                    "method": p.method,
                    "doc_type": DOC_TYPE,
                    "doc_id": p.id,
                }
            ],
        )
        late_row = await d.shifts.settle_late(
            s, tenant_id=ctx.tenant_id, shift=shift, doc_type=DOC_TYPE, doc_id=p.id
        )
        if late_row is not None:
            out.exceptions.append(late_row)

        device = sorted(
            (a.target_doc_type, str(a.target_doc_id), money_str(money(to_decimal(a.amount))))
            for a in p.allocations
        )
        server = sorted(
            (a.target_doc_type, a.target_doc_id, money_str(a.amount)) for a in plan.result.allocations
        )
        known_lines = {ln.sale_line_id for rows in plan.lines.values() for ln in rows}
        foreign = sorted(
            str(ln.sale_line_id)
            for ln in p.fiscal_lines
            if ln.sale_line_id is not None and ln.sale_line_id not in known_lines
        )
        device_lines = sorted(_device_line_key(ln) for ln in p.fiscal_lines)
        server_lines = sorted(_server_line_key(ln) for ln in plan.result.fiscal_lines)
        if device != server or foreign or device_lines != server_lines:
            details: dict[str, Any] = {
                "device": [{"target_doc_type": t, "target_doc_id": i, "amount": a} for t, i, a in device],
                "server": allocations_out(plan.result),
            }
            if device_lines != server_lines:
                details["server_fiscal_lines"] = [fiscal_line_json(ln) for ln in plan.result.fiscal_lines]
            if foreign:
                details["unknown_sale_line_ids"] = foreign
            out.flag("debt_allocation_mismatch", p.id, **details)
        if plan.result.unallocated_amount > 0:
            out.flag(
                "debt_overpayment_offline",
                p.id,
                counterparty_id=str(p.counterparty_id),
                amount=money_str(amount),
                allocated=money_str(plan.result.allocated),
                unallocated_amount=money_str(plan.result.unallocated_amount),
            )
            await d.events.record_event(
                s,
                ctx.tenant_id,
                OVERPAY_NOTIFY_KIND,
                {
                    "reason": "debt_overpayment_offline",
                    "debt_payment_id": str(p.id),
                    "number": number,
                    "counterparty_id": str(p.counterparty_id),
                    "counterparty_name": customer.name,
                    "branch_id": str(p.branch_id),
                    "amount": money_str(amount),
                    "unallocated_amount": money_str(plan.result.unallocated_amount),
                },
                f"debt_overpayment_offline:{p.id}",
            )

        receipt = await d.fiscal.record(
            s,
            kind="debt_settlement",
            doc_id=p.id,
            cash_register_id=p.cash_register_id,
            shift_id=p.shift_id,
            receipt_seq=p.receipt_seq,
            payment_form=payment_form([p.method]),
            payload=await self._receipt_payload(s, p, number, amount, card, plan),
            fiscal_result=p.fiscal_result,
            is_offline=p.is_offline,
            offline_since=offline_since,
            created_at=at,
        )
        if receipt.renumbered_from is not None:
            out.flag(
                "receipt_seq_conflict",
                p.id,
                device_receipt_seq=receipt.renumbered_from,
                receipt_seq=receipt.receipt_seq,
            )
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="debt_payment.created",
            entity=DOC_TYPE,
            entity_id=p.id,
            device_id=ctx.device_id,
            after={
                "amount": money_str(amount),
                "method": p.method,
                "counterparty_id": str(p.counterparty_id),
                "unallocated_amount": money_str(plan.result.unallocated_amount),
                "client_event_id": str(ctx.client_event_id),
            },
        )
        fiscal = d.fiscal
        tenant_id = ctx.tenant_id

        async def _after() -> None:
            await fiscal.enqueue(tenant_id, [receipt.id])

        server_json = {
            "id": str(p.id),
            "number": number,
            "allocations": allocations_out(plan.result),
            "unallocated_amount": money_str(plan.result.unallocated_amount),
            "remaining_balance": money_str(plan.remaining_balance),
            "fiscal_receipt_seq": receipt.receipt_seq,
            "fiscal": _fiscal_json(receipt),
            "warnings": list(out.warnings),
        }
        return HandlerResult(
            server=server_json,
            warnings=tuple(out.warnings),
            sync_exceptions=tuple(out.exceptions),
            after_commit=(_after,),
        )

    async def _consume_checkout(self, s: AsyncSession, p: DebtPaymentCreatedPayload, amount: Decimal) -> None:
        assert p.checkout_ref is not None
        found = await self._d.repo.checkout(s, p.checkout_ref)
        ok = (
            found is not None
            and found["status"] == "confirmed"
            and found["provider"] == p.method
            and found["cash_register_id"] == p.cash_register_id
            and money(found["amount"]) == amount
            and (found["provider_tx_id"] is None or found["provider_tx_id"] == p.provider_tx_id)
        )
        if not ok:
            raise AppError(ErrorCode.PAYMENT_NOT_CONFIRMED, params={"checkout_ref": str(p.checkout_ref)})
        await self._d.repo.consume_checkout(s, p.checkout_ref)

    async def _card(
        self, s: AsyncSession, ctx: EventContext, p: DebtPaymentCreatedPayload, amount: Decimal, out: _Out
    ) -> dict[str, Any]:
        if p.method != "card":
            return {}
        if p.card_entry_mode == "integrated":
            assert p.card_result is not None
            rec = await self._d.cards.link_result(
                s,
                tenant_id=ctx.tenant_id,
                branch_id=p.branch_id,
                cash_register_id=p.cash_register_id,
                shift_id=p.shift_id,
                card_result=p.card_result,
                expected_amount=amount,
                kind="purchase",
                doc_type=DOC_TYPE,
                doc_id=p.id,
                client_event_id=ctx.client_event_id,
                actor_user_id=ctx.actor_user_id,
                device_id=ctx.device_id,
            )
            if rec.mismatch is not None:
                out.warn(ErrorCode.CARD_TRANSACTION_MISMATCH.value)
                out.flag("card_result_mismatch", p.id, **dict(rec.mismatch))
            return {
                "card_terminal_transaction_id": rec.id,
                "card_type": rec.card_type or "unknown",
                "card_type_source": rec.card_type_source or "bin_table",
                "card_mask": rec.card_mask,
                "rrn": rec.rrn,
                "approval_code": rec.approval_code,
                "card_scheme": rec.card_scheme,
                "terminal_ref": rec.tid,
            }
        assert p.manual_reason is not None
        auth = await self._d.cards.authorize_manual(
            s,
            tenant_id=ctx.tenant_id,
            branch_id=p.branch_id,
            cash_register_id=p.cash_register_id,
            manual_reason=p.manual_reason,
            amount=amount,
            approval=_approval(p.card_manual_approval),
            requested_by=ctx.actor_user_id,
            doc_type=DOC_TYPE,
            doc_id=p.id,
            client_event_id=ctx.client_event_id,
            device_id=ctx.device_id,
            offline=p.is_offline,
            approver_bound=ctx.actor_bound,
            session_user_id=ctx.session_user_id,
        )
        if auth.approver_unverified:
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
        return {}

    async def _receipt_payload(
        self,
        s: AsyncSession,
        p: DebtPaymentCreatedPayload,
        number: str,
        amount: Decimal,
        card: Mapping[str, Any],
        plan: PaymentPlan,
    ) -> dict[str, Any]:
        """``fiscal_receipts.payload`` (18 §12.2, SYNC-03), two-language names (§4.9).

        Signed by the device's FM (``fiscal_result`` present) — the DEVICE lines as signed; the server
        fiscalizes (``fiscal_result`` is None) — the SERVER allocation's lines (``plan.result.fiscal_lines``).
        Goods data is looked up only in this customer's sales."""
        known: dict[UUID, SaleLineRow] = {ln.sale_line_id: ln for rows in plan.lines.values() for ln in rows}
        source: list[FiscalLinePayload]
        if p.fiscal_result is None:
            source = [_payload_line(ln) for ln in plan.result.fiscal_lines]
        else:
            source = list(p.fiscal_lines)
        missing = [
            ln.sale_id
            for ln in source
            if ln.sale_line_id is not None and ln.sale_line_id not in known and ln.sale_id is not None
        ]
        if missing:
            found = await self._d.repo.sale_lines(s, missing, counterparty_id=p.counterparty_id)
            for rows in found.values():
                known.update({ln.sale_line_id: ln for ln in rows})
        items: list[dict[str, Any]] = []
        for n, ln in enumerate(source, start=1):
            src = known.get(ln.sale_line_id) if ln.sale_line_id is not None else None
            name = GENERAL_LINE_NAME
            if src is not None:
                name = src.name if not src.name_ru else f"{src.name} / {src.name_ru}"
            items.append(
                {
                    "line_no": n,
                    "sale_id": str(ln.sale_id) if ln.sale_id else None,
                    "sale_line_id": str(ln.sale_line_id) if ln.sale_line_id else None,
                    "product_id": str(ln.product_id) if ln.product_id else None,
                    "name": name,
                    "mxik": src.mxik_code if src else None,
                    "package_code": src.package_code if src else None,
                    "unit_code": src.unit_code if src else None,
                    "qty": qty_str(to_decimal(ln.qty)),
                    "price": format(src.price, "f") if src else money_str(to_decimal(ln.amount)),
                    "discount": "0.00",
                    "vat_rate": ln.vat_rate,
                    "vat_exemption_code": src.vat_exemption_code if src else None,
                    "vat_amount": ln.vat_amount,
                    "amount": ln.amount,
                    "marking_codes": [ln.marking_code] if ln.marking_code else [],
                }
            )
        entry: dict[str, Any] = {"method": p.method, "amount": money_str(amount)}
        if p.method == "card":
            entry["card_entry_mode"] = p.card_entry_mode
            if p.card_entry_mode == "integrated":
                entry.update(
                    card_type=card.get("card_type"), card_mask=card.get("card_mask"), rrn=card.get("rrn")
                )
        vat_total = sum((money(to_decimal(ln.vat_amount)) for ln in source), ZERO)
        return {
            "kind": "debt_settlement",
            "debt_payment_id": str(p.id),
            "number": number,
            "counterparty_id": str(p.counterparty_id),
            "receipt_seq": p.receipt_seq,
            "items": items,
            "total": money_str(amount),
            "vat_total": money_str(vat_total),
            "payments": [entry],
            "is_offline": p.is_offline,
            "delivery": "printed",
        }


def _device_line_key(ln: FiscalLinePayload) -> tuple[str, str, str, str, str]:
    return (
        str(ln.sale_line_id or ""),
        qty_str(to_decimal(ln.qty)),
        money_str(to_decimal(ln.amount)),
        money_str(to_decimal(ln.vat_amount)),
        ln.marking_code or "",
    )


def _server_line_key(ln: FiscalLine) -> tuple[str, str, str, str, str]:
    return (
        ln.sale_line_id or "",
        qty_str(ln.qty),
        money_str(ln.amount),
        money_str(ln.vat_amount),
        ln.marking_code or "",
    )


def _payload_line(ln: FiscalLine) -> FiscalLinePayload:
    """A server receipt line in the device-payload shape (the receipt builder reads one shape)."""
    raw = fiscal_line_json(ln)
    return FiscalLinePayload.model_validate({k: v for k, v in raw.items() if v is not None})


def _fiscal_json(ref: FiscalReceiptRef) -> dict[str, Any]:
    return {
        "status": ref.status,
        "ofd_acked_at": _iso(ref.ofd_acked_at),
        "fm_receipt_seq": ref.fm_receipt_seq,
        "receipt_seq": ref.receipt_seq,
    }


AfterCommit = Callable[[], Awaitable[None]]
