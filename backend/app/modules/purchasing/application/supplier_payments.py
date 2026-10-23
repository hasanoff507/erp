"""Supplier payments (19 §11; 13 §2.16, §2.8; qaror #47; US-M07-04, US-M08-11; QT-M07-05).

One-step document (17 §9): ``POST /supplier-payments`` creates it ``posted`` (number ``SP-…``) and writes in
ONE transaction — ``supplier_payments`` + ``supplier_payment_allocations``, ``ledger_entries``
(``Dt 6010`` debt part / ``Dt 4310`` advance against ``Kt 5110`` bank or ``Kt 5010`` till cash),
``debt_moves(payable, −amount)``, ``cash_moves(−amount)`` for cash, and the released deferred input VAT
(``vat_moves(input)`` only — the 4410 line was written by the receipt, 13 §2.8). ``cancel`` is a storno of
every register row (13 §5.2); a cash payment is cancelled only while its shift is open (the cash goes back to
the same till, like ``cash_movements``), and a payment whose advance part was already offset by a later
receipt (4310 debit balance < advance part) is refused with ``DOC_INVALID_STATE``
``reason='advance_consumed'`` (ACC-03).

Lock order (23 §2.1): payment row → shift row (``FOR SHARE``) → ``debt_balances`` of the supplier (serialises
concurrent payments/receipts of the same supplier, so outstanding amounts are read under the lock).
"""

from __future__ import annotations

from collections.abc import Sequence
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
from app.core.money import money, money_str
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_today
from app.modules.debts.application.counterparties import CounterpartyDirectory
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.purchasing.application.purchase_orders import check_read_scope
from app.modules.purchasing.application.supplier_payments_ports import (
    PaymentFilter,
    PaymentRow,
    SupplierPaymentRepository,
)
from app.modules.purchasing.domain.supplier_payments import (
    TARGET_TYPES,
    ZERO,
    Allocation,
    OpenDoc,
    allocation_key,
    auto_allocate,
    debt_part,
    payment_posting,
    vat_release,
)

DOC_TYPE: Final = "supplier_payments"
PAYABLE: Final = "payable"


@dataclass(frozen=True, slots=True)
class AllocationInput:
    target_doc_type: str
    target_doc_id: UUID
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PaymentInput:
    supplier_id: UUID
    amount: Decimal
    method: str
    doc_date: date
    cash_register_id: UUID | None = None
    shift_id: UUID | None = None
    allocations: Sequence[AllocationInput] | None = None
    comment: str | None = None


def _invalid(field: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        params=params or None,
        details=[ErrorDetail(field=field, message_key=key)],
    )


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "supplier_payment"})


def open_doc_json(doc: OpenDoc) -> dict[str, Any]:
    return {
        "target_doc_type": doc.target_doc_type,
        "target_doc_id": str(doc.target_doc_id),
        "number": doc.number,
        "doc_date": doc.doc_date.isoformat(),
        "due_date": None if doc.due_date is None else doc.due_date.isoformat(),
        "total": money_str(doc.total),
        "outstanding": money_str(doc.outstanding),
        "einvoice_id": _str(doc.einvoice_id),
        "einvoice_risk_flag": doc.risk_flag,
        "vat_pending": money_str(doc.vat_pending),
    }


def payment_json(row: PaymentRow, warnings: Sequence[dict[str, Any]] | None = None) -> dict[str, Any]:
    vat_by_einvoice: dict[UUID | None, Decimal] = {}
    for einvoice_id, vat in row.vat_unlocked:
        vat_by_einvoice[einvoice_id] = vat_by_einvoice.get(einvoice_id, ZERO) + vat
    allocated = money(sum((a.amount for a in row.allocations), ZERO))
    body: dict[str, Any] = {
        "id": str(row.id),
        "number": row.number,
        "status": row.status,
        "doc_date": row.doc_date.isoformat(),
        "branch_id": str(row.branch_id),
        "supplier_id": str(row.supplier_id),
        "supplier": {"id": str(row.supplier_id), "name": row.supplier_name, "stir": row.supplier_stir},
        "method": row.method,
        "amount": money_str(row.amount),
        "cash_register_id": _str(row.cash_register_id),
        "shift_id": _str(row.shift_id),
        "allocations": [
            {
                "target_doc_type": a.target_doc_type,
                "target_doc_id": str(a.target_doc_id),
                "target_number": a.target_number,
                "target_doc_date": None if a.target_doc_date is None else a.target_doc_date.isoformat(),
                "amount": money_str(a.amount),
                "vat_credit_unlocked": money_str(
                    vat_by_einvoice.get(a.target_einvoice_id, ZERO) if a.target_einvoice_id else ZERO
                ),
            }
            for a in row.allocations
        ],
        "advance_amount": money_str(row.amount - allocated),
        "vat_credit_unlocked": [
            {"einvoice_id": _str(e), "vat_amount": money_str(v)} for e, v in vat_by_einvoice.items() if v
        ],
        "comment": row.comment,
        "created_by": str(row.created_by),
        "created_by_name": row.created_by_name,
        "created_at": _ts(row.created_at),
        "posted_at": _ts(row.posted_at),
        "cancelled_at": _ts(row.cancelled_at),
        "cancel_reason": row.cancel_reason,
    }
    if warnings is not None:
        body["warnings"] = list(warnings)
    return body


def check_input(data: PaymentInput) -> None:
    if money(data.amount) <= 0:
        raise _invalid("amount", "validation.positive")
    if data.doc_date > business_today():
        raise _invalid("doc_date", "validation.doc_date_in_future")
    if data.method == "cash":
        if data.cash_register_id is None:
            raise _invalid("cash_register_id", "validation.required")
        if data.shift_id is None:
            raise _invalid("shift_id", "validation.required")
    elif data.cash_register_id is not None or data.shift_id is not None:
        raise _invalid("cash_register_id", "validation.cash_fields_bank_payment")
    if data.allocations is not None:
        seen: set[tuple[str, UUID]] = set()
        for i, a in enumerate(data.allocations):
            if a.target_doc_type not in TARGET_TYPES:
                raise _invalid(f"allocations[{i}].target_doc_type", "validation.allocation_target_invalid")
            if money(a.amount) <= 0:
                raise _invalid(f"allocations[{i}].amount", "validation.positive")
            key = (a.target_doc_type, a.target_doc_id)
            if key in seen:
                raise _invalid(f"allocations[{i}].target_doc_id", "validation.duplicate")
            seen.add(key)


def explicit_allocations(
    wanted: Sequence[AllocationInput], docs: Sequence[OpenDoc], debt: Decimal
) -> list[Allocation]:
    """A client split (19 §11): every target an open document of the supplier, each line ≤ its outstanding,
    Σ = the debt part exactly (the rest of the payment is the 4310 advance, 13 §2.16)."""
    by_key = {(d.target_doc_type, d.target_doc_id): d for d in docs}
    out: list[Allocation] = []
    for i, a in enumerate(wanted):
        doc = by_key.get((a.target_doc_type, a.target_doc_id))
        if doc is None:
            raise _invalid(f"allocations[{i}].target_doc_id", "validation.allocation_target_invalid")
        amount = money(a.amount)
        if amount > doc.outstanding:
            raise _invalid(
                f"allocations[{i}].amount",
                "validation.allocation_exceeds_outstanding",
                outstanding=money_str(doc.outstanding),
            )
        out.append(Allocation(doc, amount))
    total = money(sum((a.amount for a in out), ZERO))
    if total != debt:
        raise _invalid("allocations", "validation.allocation_sum_mismatch", expected=money_str(debt))
    return sorted(out, key=lambda a: allocation_key(a.doc))


class SupplierPaymentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: SupplierPaymentRepository,
        directory: CounterpartyDirectory,
        poster: LedgerPoster,
        debts: DebtRegister,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._directory = directory
        self._poster = poster
        self._debts = debts

    # --- reads ------------------------------------------------------------------------------------
    async def open_documents(self, actor: Principal, supplier_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._directory.require_supplier(s, supplier_id)
            balance = (await self._debts.balances(s, supplier_id))[PAYABLE]
            docs = [d for d in await self._repo.open_docs(s, supplier_id) if d.outstanding > 0]
        return {
            "supplier_id": str(supplier_id),
            "payable_balance": money_str(balance),
            "advance_balance": money_str(max(-balance, ZERO)),
            "items": [open_doc_json(d) for d in sorted(docs, key=allocation_key)],
        }

    async def get(self, actor: Principal, scope: BranchScope, payment_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get(s, payment_id)
            if row is None:
                raise not_found()
            check_read_scope(scope, row.branch_id)
        return payment_json(row)

    async def list_page(
        self, actor: Principal, flt: PaymentFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after: UUID | None = None
        if cursor:
            try:
                after = UUID(cursor)
            except ValueError:
                raise _invalid("cursor", "validation.cursor_invalid") from None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_page(s, flt, after, limit + 1)
        page = rows[:limit]
        return {
            "items": [payment_json(r) for r in page],
            "next_cursor": str(page[-1].id) if len(rows) > limit else None,
        }

    # --- create (= post) --------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, data: PaymentInput, ip: str | None
    ) -> dict[str, Any]:
        check_input(data)
        amount = money(data.amount)
        payment_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._directory.require_supplier(s, data.supplier_id)
            branch_id = await self._branch(s, scope, data)
            await self._poster.assert_period_open(s, data.doc_date)
            locked = await self._debts.lock(s, actor.tenant_id, [(data.supplier_id, PAYABLE)])
            balance = money(locked.get((data.supplier_id, PAYABLE), ZERO))
            docs = [d for d in await self._repo.open_docs(s, data.supplier_id) if d.outstanding > 0]
            open_total = money(sum((d.outstanding for d in docs), ZERO))
            debt = min(debt_part(amount, balance), open_total)
            advance = money(amount - debt)
            if advance > 0 and await self._repo.overpay_policy(s) == "block":
                raise AppError(
                    ErrorCode.SUPPLIER_OVERPAY_BLOCKED,
                    params={"debt": money_str(debt), "amount": money_str(amount)},
                )
            if data.allocations is None:
                allocations = auto_allocate(docs, debt)
            else:
                allocations = explicit_allocations(data.allocations, docs, debt)
            releases = [r for r in (vat_release(a) for a in allocations) if r is not None]
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=branch_id, table=DOC_TYPE, year=data.doc_date.year
            )
            await self._repo.insert(
                s,
                {
                    "id": payment_id, "tenant_id": actor.tenant_id, "branch_id": branch_id, "number": number,
                    "doc_date": data.doc_date, "supplier_id": data.supplier_id, "method": data.method,
                    "amount": amount, "cash_register_id": data.cash_register_id, "shift_id": data.shift_id,
                    "created_by": actor.user_id, "comment": data.comment,
                },
                [
                    {"id": uuid7(), "tenant_id": actor.tenant_id, "supplier_payment_id": payment_id,
                     "target_doc_type": a.doc.target_doc_type, "target_doc_id": a.doc.target_doc_id,
                     "amount": a.amount}
                    for a in allocations
                ],
            )  # fmt: skip
            ledger, vat = payment_posting(
                method=data.method, allocated=debt, advance=advance, entry_date=data.doc_date,
                branch_id=branch_id, supplier_id=data.supplier_id, cash_register_id=data.cash_register_id,
                shift_id=data.shift_id, releases=releases,
            )  # fmt: skip
            await self._poster.post(s, actor.tenant_id, DOC_TYPE, payment_id, ledger, vat=vat)
            await self._debts.post(
                s, actor.tenant_id, [DebtMoveInput(data.supplier_id, PAYABLE, -amount, DOC_TYPE, payment_id)]
            )
            if data.method == "cash":
                await self._repo.insert_cash_move(
                    s,
                    {
                        "id": uuid7(), "tenant_id": actor.tenant_id,
                        "cash_register_id": data.cash_register_id, "shift_id": data.shift_id,
                        "amount": -amount, "method": "cash", "doc_type": DOC_TYPE,
                        "doc_id": payment_id, "reversal_of_id": None,
                    },
                )  # fmt: skip
            warnings: list[dict[str, Any]] = []
            if advance > 0:
                warnings.append(
                    {
                        "code": ErrorCode.SUPPLIER_OVERPAY_ADVANCE.value,
                        "params": {
                            "debt": money_str(debt),
                            "amount": money_str(amount),
                            "advance": money_str(advance),
                        },
                    }
                )
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="supplier_payment.created",
                entity=DOC_TYPE, entity_id=payment_id, ip=ip,
                after={
                    "supplier_id": str(data.supplier_id), "method": data.method, "amount": money_str(amount),
                    "advance": money_str(advance), "doc_date": data.doc_date.isoformat(), "number": number,
                    "allocations": [
                        {"target_doc_type": a.doc.target_doc_type, "target_doc_id": str(a.doc.target_doc_id),
                         "amount": money_str(a.amount)}
                        for a in allocations
                    ],
                },
            )  # fmt: skip
            body = payment_json(await self._load(s, payment_id), warnings)
            stage_response(body, 201)
        return body

    # --- cancel -----------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, payment_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get(s, payment_id, lock=True)
            if row is None:
                raise not_found()
            check_read_scope(scope, row.branch_id)
            if row.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED, params={"id": str(row.id)})
            if row.method == "cash" and row.shift_id is not None:
                shift = await self._repo.shift(s, row.shift_id)
                if shift is None or shift.status != "open":
                    raise AppError(
                        ErrorCode.DOC_INVALID_STATE,
                        params={"reason": "shift_closed", "shift_id": str(row.shift_id)},
                    )
            await self._debts.lock(s, actor.tenant_id, [(row.supplier_id, PAYABLE)])
            # ACC-03: the advance part (Dt 4310) may already be offset by a later receipt (Dt 6010 /
            # Kt 4310, 13 §2.6) — a blind storno would leave 4310 in credit with a payable and no document.
            # Partly consumed is refused too: the Owner cancels the consuming receipt first.
            advance_part = money(row.amount - sum((a.amount for a in row.allocations), ZERO))
            if advance_part > 0:
                available = money(await self._repo.advance_balance(s, row.supplier_id))
                if advance_part > available:
                    raise AppError(
                        ErrorCode.DOC_INVALID_STATE,
                        params={
                            "reason": "advance_consumed",
                            "advance": money_str(advance_part),
                            "available": money_str(max(available, ZERO)),
                        },
                    )
            await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, row.id)
            await self._debts.reverse(s, actor.tenant_id, DOC_TYPE, row.id)
            for move_id, amount, register_id, shift_id, method in await self._repo.live_cash_moves(s, row.id):
                await self._repo.insert_cash_move(
                    s,
                    {
                        "id": uuid7(), "tenant_id": actor.tenant_id, "cash_register_id": register_id,
                        "shift_id": shift_id, "amount": -amount, "method": method, "doc_type": DOC_TYPE,
                        "doc_id": row.id, "reversal_of_id": move_id,
                    },
                )  # fmt: skip
            await self._repo.mark_cancelled(s, row.id, actor.user_id, reason)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="supplier_payment.cancelled",
                entity=DOC_TYPE, entity_id=row.id, ip=ip, before={"status": row.status},
                after={"status": "cancelled", "reason": reason, "amount": money_str(row.amount),
                       "method": row.method},
            )  # fmt: skip
            body = payment_json(await self._load(s, row.id))
            stage_response(body)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, payment_id: UUID) -> PaymentRow:
        row = await self._repo.get(s, payment_id)
        assert row is not None
        return row

    async def _branch(self, s: AsyncSession, scope: BranchScope, data: PaymentInput) -> UUID:
        """Cash: the till shift's branch (open shift of that register); bank: ``X-Branch-Id``, else the
        default branch (unrestricted user) or the user's only branch."""
        if data.method == "cash":
            assert data.shift_id is not None
            shift = await self._repo.shift(s, data.shift_id)
            if shift is None or shift.status != "open":
                raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(data.shift_id)})
            if shift.cash_register_id != data.cash_register_id:
                raise _invalid("cash_register_id", "validation.cash_register_not_of_shift")
            check_read_scope(scope, shift.branch_id)
            return shift.branch_id
        if scope.current is not None:
            return scope.current
        if scope.unrestricted:
            return await self._repo.default_branch(s)
        if len(scope.allowed) == 1:
            return scope.allowed[0]
        raise _invalid("branch_id", "validation.branch_required")
