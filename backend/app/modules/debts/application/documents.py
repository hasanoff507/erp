"""Back-office debt documents (18 §12.3–§12.6; 13 §2.13–§2.15a).

* ``debt-payments`` — ``method='bank'`` only (qaror #67): draft → ``post`` (``Dt 5110 / Kt 4010``, allocation
  as on
  the POS, no receipt) → ``cancel`` (storno). A POS payment (cash/card/QR — fiscal ``debt_settlement`` receipt
  issued) is never cancelled here: ``409 DOC_INVALID_STATE`` ``params.reason='pos_fiscal_receipt'`` — the
  money
  goes back through a cash movement (18 §12.5a).
* ``debt-openings`` — receivable ``Dt 4010 / Kt 0000`` / payable ``Dt 0000 / Kt 6010`` dated
  ``go_live_date − 1`` (13 §2.13), ``debt_moves`` +amount with ``due_date``; no goods, no receipt.
* ``debt-writeoffs`` — Owner only (``debts.forgive``): ``Dt 9430 | 4910 / Kt 4010`` per written-off document
  (oldest first, ``debt_writeoff_allocations``), ``debt_moves`` −amount; 4910 needs a reserve ≥ amount
  (13 §2.15); nothing open → ``409 DEBT_ALREADY_PAID``.
* ``debt-doubtful-flags`` — Owner only, a mark without any posting (13 §2.15a, 18 §12.6).

A document with live allocations (a payment or a write-off took part of it) cannot be cancelled:
``409 DOC_INVALID_STATE`` ``params.reason='has_allocations'`` (a supplier payment on a payable opening:
``'supplier_payment_allocated'``) — cancel the later document first.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
from app.modules.debts.application.counterparties import (
    COUNTERPARTY_FIELDS,
    CounterpartyDirectory,
    validate_row,
)
from app.modules.debts.application.doc_ports import DebtDocsRepository, Row
from app.modules.debts.application.payments import (
    DebtPaymentPostingService,
    PaymentWrite,
    allocations_out,
    to_open_docs,
)
from app.modules.debts.application.ports import CounterpartyRepository
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.documents import opening_ledger, writeoff_ledger
from app.modules.debts.domain.register import DebtMoveInput
from app.shared.debt_allocation import allocate

ZERO: Final = Decimal("0.00")
PAYMENTS: Final = "debt_payments"
OPENINGS: Final = "debt_openings"
WRITEOFFS: Final = "debt_writeoffs"
FLAGS: Final = "debt_doubtful_flags"


def _invalid(field_name: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR, params=params, details=[ErrorDetail(field=field_name, message_key=key)]
    )


def _state(actual: str, expected: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.DOC_INVALID_STATE, params={"expected_status": expected, "actual_status": actual, **params}
    )


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _d(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _u(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def encode_cursor(doc_date: date, doc_id: UUID) -> str:
    raw = json.dumps([doc_date.isoformat(), str(doc_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[date, UUID]:
    try:
        day, oid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return date.fromisoformat(day), UUID(oid)
    except (ValueError, TypeError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def _base_json(row: Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "number": row["number"],
        "status": row["status"],
        "doc_date": _d(row["doc_date"]),
        "branch_id": str(row["branch_id"]),
        "counterparty_id": str(row["counterparty_id"]),
        "counterparty_name": row.get("counterparty_name"),
        "amount": money_str(row["amount"]),
        "comment": row["comment"],
        "created_by": str(row["created_by"]),
        "created_at": _ts(row["created_at"]),
        "posted_at": _ts(row["posted_at"]),
        "cancelled_at": _ts(row["cancelled_at"]),
        "cancelled_by": _u(row["cancelled_by"]),
        "cancel_reason": row["cancel_reason"],
    }


def _alloc_json(rows: Sequence[Row]) -> list[dict[str, Any]]:
    return [
        {
            "target_doc_type": a["target_doc_type"],
            "target_doc_id": str(a["target_doc_id"]),
            "target_number": a.get("target_number"),
            "target_doc_date": _d(a.get("target_doc_date")),
            "amount": money_str(a["amount"]),
        }
        for a in rows
    ]


def payment_json(row: Row, allocations: Sequence[Row], receipt: Row | None) -> dict[str, Any]:
    return _base_json(row) | {
        "method": row["method"],
        "unallocated_amount": money_str(row["unallocated_amount"]),
        "cash_register_id": _u(row["cash_register_id"]),
        "shift_id": _u(row["shift_id"]),
        "receipt_seq": row["receipt_seq"],
        "terminal_ref": row["terminal_ref"],
        "provider_tx_id": row["provider_tx_id"],
        "qr_type": row["qr_type"],
        "card_entry_mode": row["card_entry_mode"],
        "card_type": row["card_type"],
        "card_mask": row["card_mask"],
        "rrn": row["rrn"],
        "promise_date": _d(row["promise_date"]),
        "device_id": _u(row["device_id"]),
        "allocations": _alloc_json(allocations),
        "fiscal_receipt": None
        if receipt is None
        else {
            "id": str(receipt["id"]),
            "status": receipt["status"],
            "receipt_seq": receipt["receipt_seq"],
            "fm_receipt_seq": receipt["fm_receipt_seq"],
            "ofd_acked_at": _ts(receipt["ofd_acked_at"]),
        },
    }


def opening_json(row: Row) -> dict[str, Any]:
    return _base_json(row) | {"direction": row["direction"], "due_date": _d(row["due_date"])}


def writeoff_json(row: Row, allocations: Sequence[Row]) -> dict[str, Any]:
    return _base_json(row) | {
        "reason": row["reason"],
        "account_choice": row["account_choice"],
        "tax_writeoff_basis": row["tax_writeoff_basis"],
        "approved_by": _u(row["approved_by"]),
        "allocations": _alloc_json(allocations),
    }


def flag_json(row: Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "counterparty_id": str(row["counterparty_id"]),
        "reason": row["reason"],
        "flagged_by": str(row["flagged_by"]),
        "flagged_at": _ts(row["flagged_at"]),
        "unflagged_at": _ts(row.get("unflagged_at")),
        "active": row.get("unflagged_at") is None,
    }


@dataclass(frozen=True, slots=True)
class PaymentCreate:
    counterparty_id: UUID
    branch_id: UUID
    amount: Decimal
    method: str
    doc_date: date
    promise_date: date | None = None
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class OpeningCreate:
    amount: Decimal
    direction: str
    counterparty_id: UUID | None = None
    new_counterparty: Mapping[str, Any] | None = None  # {name, phone, kind?}
    due_date: date | None = None
    doc_date: date | None = None
    branch_id: UUID | None = None
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class WriteoffCreate:
    counterparty_id: UUID
    amount: Decimal
    reason: str
    account_choice: str = "9430"
    tax_writeoff_basis: str | None = None
    doc_date: date | None = None
    branch_id: UUID | None = None
    comment: str | None = None


@dataclass(frozen=True, slots=True)
class DocFilter:
    counterparty_id: UUID | None = None
    branch_id: UUID | None = None
    status: str | None = None
    doc_date__gte: date | None = None
    doc_date__lte: date | None = None
    method: str | None = None
    direction: str | None = None


class DebtDocumentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: DebtDocsRepository,
        counterparties: CounterpartyRepository,
        directory: CounterpartyDirectory,
        register: DebtRegister,
        poster: LedgerPoster,
        posting: DebtPaymentPostingService,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._cps = counterparties
        self._dir = directory
        self._register = register
        self._poster = poster
        self._posting = posting

    # === debt payments (18 §12.3, §12.5a) ==========================================================
    async def create_payment(
        self, actor: Principal, scope: BranchScope, body: PaymentCreate, ip: str | None
    ) -> dict[str, Any]:
        if body.method != "bank":  # qaror #67 — cash/card/QR only at the POS (debt_payment.created)
            raise _invalid("method", "validation.debt_payment_backoffice_bank_only", field="method")
        amount = self._positive(body.amount)
        self._not_future(body.doc_date)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._branch(s, scope, body.branch_id)
            await self._dir.require_customer(s, body.counterparty_id)
            await self._poster.assert_period_open(s, body.doc_date)
            await self._posting.plan(
                s, actor.tenant_id, body.counterparty_id, amount, online=True, fiscal=False
            )
            doc_id = uuid7()
            await self._repo.insert_doc(
                s,
                PAYMENTS,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": body.branch_id,
                    "doc_date": body.doc_date,
                    "status": "draft",
                    "counterparty_id": body.counterparty_id,
                    "method": "bank",
                    "amount": amount,
                    "promise_date": body.promise_date,
                    "created_by": actor.user_id,
                    "comment": body.comment,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_payment.created",
                entity=PAYMENTS,
                entity_id=doc_id,
                ip=ip,
                after={
                    "amount": money_str(amount),
                    "method": "bank",
                    "counterparty_id": str(body.counterparty_id),
                },
            )
            body_json = await self._payment(s, doc_id)
            stage_response(body_json, 201)
        return body_json

    async def post_payment(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._doc(s, scope, PAYMENTS, doc_id, lock=True)
            if row["status"] != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT,
                    params={"expected_status": "draft", "actual_status": row["status"]},
                )
            self._not_future(row["doc_date"])
            amount = money(row["amount"])
            plan = await self._posting.plan(
                s, actor.tenant_id, row["counterparty_id"], amount, online=True, fiscal=False
            )
            number = await next_doc_number(
                s,
                tenant_id=actor.tenant_id,
                branch_id=row["branch_id"],
                table=PAYMENTS,
                year=row["doc_date"].year,
            )
            await self._repo.update_doc(
                s,
                PAYMENTS,
                doc_id,
                {
                    "status": "posted",
                    "number": number,
                    "posted_at": datetime.now(UTC),
                    "unallocated_amount": plan.result.unallocated_amount,
                },
            )
            await self._posting.write(
                s,
                plan,
                PaymentWrite(
                    actor.tenant_id,
                    doc_id,
                    row["branch_id"],
                    "bank",
                    row["doc_date"],
                    {},
                    {},
                    row["promise_date"],
                ),
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_payment.posted",
                entity=PAYMENTS,
                entity_id=doc_id,
                ip=ip,
                after={"number": number, "allocations": allocations_out(plan.result)},
            )
            body = await self._payment(s, doc_id)
            stage_response(body, 200)
        return body

    async def cancel_payment(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._doc(s, scope, PAYMENTS, doc_id, lock=True)
            if row["status"] == "cancelled":
                raise _state("cancelled", "draft|posted")
            if row["status"] == "posted":
                if row["method"] != "bank":
                    raise _state("posted", "draft", reason="pos_fiscal_receipt")
                await self._register.lock(s, actor.tenant_id, [(row["counterparty_id"], "receivable")])
                await self._register.reverse(s, actor.tenant_id, PAYMENTS, doc_id)
                await self._poster.reverse_document(s, actor.tenant_id, PAYMENTS, doc_id)
                await self._repo.touch_balance(s, row["counterparty_id"])
            await self._cancelled(s, actor, PAYMENTS, row, reason, ip, "debt_payment.cancelled")
            body = await self._payment(s, doc_id)
            stage_response(body, 200)
        return body

    async def get_payment(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._doc(s, scope, PAYMENTS, doc_id)
            return await self._payment(s, doc_id)

    async def page_payments(
        self, actor: Principal, scope: BranchScope, flt: DocFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, next_cursor = await self._page(s, scope, PAYMENTS, flt, cursor, limit)
            ids = [r["id"] for r in rows]
            allocs = await self._repo.allocations_of(s, "debt_payment_allocations", ids)
            receipts = await self._repo.payment_receipts(s, ids)
        return {
            "items": [payment_json(r, allocs.get(r["id"], []), receipts.get(r["id"])) for r in rows],
            "next_cursor": next_cursor,
        }

    async def _payment(self, s: AsyncSession, doc_id: UUID) -> dict[str, Any]:
        row = await self._repo.get_doc(s, PAYMENTS, doc_id)
        assert row is not None
        allocs = await self._repo.allocations_of(s, "debt_payment_allocations", [doc_id])
        receipts = await self._repo.payment_receipts(s, [doc_id])
        return payment_json(row, allocs[doc_id], receipts.get(doc_id))

    # === debt openings (18 §12.4, 13 §2.13) ========================================================
    async def create_opening(
        self, actor: Principal, scope: BranchScope, body: OpeningCreate, ip: str | None
    ) -> dict[str, Any]:
        if body.direction not in ("receivable", "payable"):
            raise _invalid("direction", "validation.enum")
        amount = self._positive(body.amount)
        doc_date = body.doc_date or business_today()
        self._not_future(doc_date)
        if (body.counterparty_id is None) == (body.new_counterparty is None):
            raise _invalid("counterparty_id", "validation.required")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch_id = await self._branch(s, scope, body.branch_id)
            if body.counterparty_id is not None:
                cp_id = body.counterparty_id
                if body.direction == "receivable":
                    await self._dir.require_customer(s, cp_id)
                else:
                    await self._dir.require_supplier(s, cp_id, field="counterparty_id")
            else:
                assert body.new_counterparty is not None
                cp_id = await self._new_counterparty(s, actor, body.new_counterparty, body.direction, ip)
            doc_id = uuid7()
            await self._repo.insert_doc(
                s,
                OPENINGS,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "doc_date": doc_date,
                    "status": "draft",
                    "counterparty_id": cp_id,
                    "amount": amount,
                    "direction": body.direction,
                    "due_date": body.due_date,
                    "created_by": actor.user_id,
                    "comment": body.comment,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_opening.created",
                entity=OPENINGS,
                entity_id=doc_id,
                ip=ip,
                after={
                    "amount": money_str(amount),
                    "direction": body.direction,
                    "counterparty_id": str(cp_id),
                },
            )
            result = opening_json(await self._load(s, OPENINGS, doc_id))
            stage_response(result, 201)
        return result

    async def post_opening(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._doc(s, scope, OPENINGS, doc_id, lock=True)
            if row["status"] != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT,
                    params={"expected_status": "draft", "actual_status": row["status"]},
                )
            go_live = await self._repo.go_live_date(s)
            if go_live is None:
                raise _invalid("go_live_date", "validation.go_live_date_missing")
            entry_date = go_live - timedelta(days=1)
            await self._poster.assert_period_open(s, entry_date)
            cp_id, direction, amount = row["counterparty_id"], row["direction"], money(row["amount"])
            await self._register.post(
                s,
                actor.tenant_id,
                [DebtMoveInput(cp_id, direction, amount, OPENINGS, doc_id, row["due_date"])],
            )
            await self._poster.post(
                s,
                actor.tenant_id,
                OPENINGS,
                doc_id,
                opening_ledger(entry_date, row["branch_id"], direction, amount, cp_id, doc_id),
            )
            number = await next_doc_number(
                s,
                tenant_id=actor.tenant_id,
                branch_id=row["branch_id"],
                table=OPENINGS,
                year=row["doc_date"].year,
            )
            await self._repo.update_doc(
                s, OPENINGS, doc_id, {"status": "posted", "number": number, "posted_at": datetime.now(UTC)}
            )
            if direction == "receivable" and row["due_date"] is not None:
                current = await self._cps.get(s, cp_id)
                if current is not None and current.archived_at is None:
                    await self._repo.set_due_date(s, cp_id, row["due_date"])
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_opening.posted",
                entity=OPENINGS,
                entity_id=doc_id,
                ip=ip,
                after={"number": number, "entry_date": entry_date.isoformat()},
            )
            result = opening_json(await self._load(s, OPENINGS, doc_id))
            stage_response(result, 200)
        return result

    async def cancel_opening(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._doc(s, scope, OPENINGS, doc_id, lock=True)
            if row["status"] == "cancelled":
                raise _state("cancelled", "draft|posted")
            if row["status"] == "posted":
                await self._register.lock(s, actor.tenant_id, [(row["counterparty_id"], row["direction"])])
                blocked = await self._repo.live_allocation_reason(s, OPENINGS, doc_id)
                if blocked is not None:
                    raise _state("posted", "posted", reason=blocked)
                await self._register.reverse(s, actor.tenant_id, OPENINGS, doc_id)
                await self._poster.reverse_document(s, actor.tenant_id, OPENINGS, doc_id)
            await self._cancelled(s, actor, OPENINGS, row, reason, ip, "debt_opening.cancelled")
            result = opening_json(await self._load(s, OPENINGS, doc_id))
            stage_response(result, 200)
        return result

    async def get_opening(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return opening_json(await self._doc(s, scope, OPENINGS, doc_id))

    async def page_openings(
        self, actor: Principal, scope: BranchScope, flt: DocFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, next_cursor = await self._page(s, scope, OPENINGS, flt, cursor, limit)
        return {"items": [opening_json(r) for r in rows], "next_cursor": next_cursor}

    async def _new_counterparty(
        self, s: AsyncSession, actor: Principal, raw: Mapping[str, Any], direction: str, ip: str | None
    ) -> UUID:
        """US-M08-07: «ism, telefon» row of the paper book — a quick customer (or a supplier for payable)."""
        row: dict[str, Any] = dict.fromkeys(COUNTERPARTY_FIELDS)
        supplier = direction == "payable"
        row.update(
            kind=raw.get("kind") or "person",
            name=raw.get("name"),
            phone=raw.get("phone"),
            is_customer=not supplier,
            is_supplier=supplier,
            notify_consent=False,
        )
        validate_row(row)
        cp_id = uuid7()
        await self._cps.insert(
            s, {**row, "id": cp_id, "tenant_id": actor.tenant_id, "notify_consent_at": None}
        )
        await record_audit(
            s,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            action="counterparty.created",
            entity="counterparties",
            entity_id=cp_id,
            ip=ip,
            after={"kind": row["kind"], "name": row["name"], "phone": row["phone"], "source": "debt_opening"},
        )
        return cp_id

    # === debt write-offs (18 §12.5, 13 §2.15) ======================================================
    async def create_writeoff(
        self, actor: Principal, scope: BranchScope, body: WriteoffCreate, ip: str | None
    ) -> dict[str, Any]:
        amount = self._positive(body.amount)
        if not body.reason.strip():
            raise _invalid("reason", "validation.required")
        if body.account_choice not in ("9430", "4910"):
            raise _invalid("account_choice", "validation.enum")
        doc_date = body.doc_date or business_today()
        self._not_future(doc_date)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch_id = await self._branch(s, scope, body.branch_id)
            await self._dir.require_customer(s, body.counterparty_id)
            await self._writeoff_limits(s, actor.tenant_id, body.counterparty_id, amount, body.account_choice)
            doc_id = uuid7()
            await self._repo.insert_doc(
                s,
                WRITEOFFS,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "doc_date": doc_date,
                    "status": "draft",
                    "counterparty_id": body.counterparty_id,
                    "amount": amount,
                    "reason": body.reason.strip(),
                    "account_choice": body.account_choice,
                    "tax_writeoff_basis": body.tax_writeoff_basis,
                    "created_by": actor.user_id,
                    "comment": body.comment,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_writeoff.created",
                entity=WRITEOFFS,
                entity_id=doc_id,
                ip=ip,
                after={
                    "amount": money_str(amount),
                    "reason": body.reason.strip(),
                    "account_choice": body.account_choice,
                    "counterparty_id": str(body.counterparty_id),
                },
            )
            result = await self._writeoff(s, doc_id)
            stage_response(result, 201)
        return result

    async def post_writeoff(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._doc(s, scope, WRITEOFFS, doc_id, lock=True)
            if row["status"] != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT,
                    params={"expected_status": "draft", "actual_status": row["status"]},
                )
            self._not_future(row["doc_date"])
            await self._poster.assert_period_open(s, row["doc_date"])
            cp_id, amount = row["counterparty_id"], money(row["amount"])
            docs = await self._writeoff_limits(s, actor.tenant_id, cp_id, amount, row["account_choice"])
            result = allocate(amount, docs, fiscal=False)
            targets = [(a.target_doc_type, UUID(a.target_doc_id), a.amount) for a in result.allocations]
            await self._repo.insert_allocations(
                s,
                "debt_writeoff_allocations",
                [
                    {
                        "id": uuid7(),
                        "tenant_id": actor.tenant_id,
                        "debt_writeoff_id": doc_id,
                        "target_doc_type": t,
                        "target_doc_id": i,
                        "amount": a,
                    }
                    for t, i, a in targets
                ],
            )
            await self._register.post(
                s,
                actor.tenant_id,
                [DebtMoveInput(cp_id, "receivable", -a, WRITEOFFS, doc_id) for _, _, a in targets],
            )
            await self._poster.post(
                s,
                actor.tenant_id,
                WRITEOFFS,
                doc_id,
                writeoff_ledger(
                    row["doc_date"], row["branch_id"], row["account_choice"], cp_id, doc_id, targets
                ),
            )
            number = await next_doc_number(
                s,
                tenant_id=actor.tenant_id,
                branch_id=row["branch_id"],
                table=WRITEOFFS,
                year=row["doc_date"].year,
            )
            await self._repo.update_doc(
                s,
                WRITEOFFS,
                doc_id,
                {
                    "status": "posted",
                    "number": number,
                    "posted_at": datetime.now(UTC),
                    "approved_by": actor.user_id,
                },
            )
            await self._repo.touch_balance(s, cp_id)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_writeoff.posted",
                entity=WRITEOFFS,
                entity_id=doc_id,
                ip=ip,
                after={
                    "number": number,
                    "amount": money_str(amount),
                    "reason": row["reason"],
                    "account_choice": row["account_choice"],
                    "approved_by": str(actor.user_id),
                    "allocations": allocations_out(result),
                },
            )
            body = await self._writeoff(s, doc_id)
            stage_response(body, 200)
        return body

    async def cancel_writeoff(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._doc(s, scope, WRITEOFFS, doc_id, lock=True)
            if row["status"] == "cancelled":
                raise _state("cancelled", "draft|posted")
            if row["status"] == "posted":
                await self._register.lock(s, actor.tenant_id, [(row["counterparty_id"], "receivable")])
                blocked = await self._repo.live_allocation_reason(s, WRITEOFFS, doc_id)
                if blocked is not None:
                    raise _state("posted", "posted", reason=blocked)
                await self._register.reverse(s, actor.tenant_id, WRITEOFFS, doc_id)
                await self._poster.reverse_document(s, actor.tenant_id, WRITEOFFS, doc_id)
                await self._repo.touch_balance(s, row["counterparty_id"])
            await self._cancelled(s, actor, WRITEOFFS, row, reason, ip, "debt_writeoff.cancelled")
            body = await self._writeoff(s, doc_id)
            stage_response(body, 200)
        return body

    async def get_writeoff(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._doc(s, scope, WRITEOFFS, doc_id)
            return await self._writeoff(s, doc_id)

    async def page_writeoffs(
        self, actor: Principal, scope: BranchScope, flt: DocFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, next_cursor = await self._page(s, scope, WRITEOFFS, flt, cursor, limit)
            allocs = await self._repo.allocations_of(s, "debt_writeoff_allocations", [r["id"] for r in rows])
        return {
            "items": [writeoff_json(r, allocs.get(r["id"], [])) for r in rows],
            "next_cursor": next_cursor,
        }

    async def _writeoff(self, s: AsyncSession, doc_id: UUID) -> dict[str, Any]:
        row = await self._load(s, WRITEOFFS, doc_id)
        allocs = await self._repo.allocations_of(s, "debt_writeoff_allocations", [doc_id])
        return writeoff_json(row, allocs[doc_id])

    async def _writeoff_limits(
        self, s: AsyncSession, tenant_id: UUID, counterparty_id: UUID, amount: Decimal, account: str
    ) -> list[Any]:
        """Open debt (sales + openings) of the customer; 409 when nothing is open, 422 above it / above
        4910."""
        locked = await self._register.lock(s, tenant_id, [(counterparty_id, "receivable")])
        balance = money(locked.get((counterparty_id, "receivable"), ZERO))
        targets, lines = await self._posting.open_docs(s, counterparty_id, balance)
        docs = [d for d in to_open_docs(targets, lines) if d.doc_type != "debt_writeoffs"]
        open_total = money(sum((d.open_amount for d in docs), ZERO))
        if open_total <= 0:
            raise AppError(ErrorCode.DEBT_ALREADY_PAID, params={"counterparty_id": str(counterparty_id)})
        if amount > open_total:
            raise _invalid(
                "amount", "validation.debt_writeoff_exceeds_balance", balance=money_str(open_total)
            )
        if account == "4910":
            reserve = money(await self._repo.reserve_4910(s, counterparty_id))
            if reserve < amount:
                raise _invalid(
                    "account_choice", "validation.reserve_4910_insufficient", reserve=money_str(reserve)
                )
        return docs

    # === doubtful flags (18 §12.6) =================================================================
    async def flag(
        self, actor: Principal, counterparty_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        if not reason.strip():
            raise _invalid("reason", "validation.required")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            cp = await self._cps.get(s, counterparty_id, lock=True)
            if cp is None:
                raise AppError(
                    ErrorCode.NOT_FOUND,
                    params={"resource": "counterparty"},
                    details=[ErrorDetail(field="counterparty_id", message_key="validation.not_found")],
                )
            if (await self._repo.active_flags(s, [counterparty_id])).get(counterparty_id) is not None:
                raise _state("flagged", "unflagged", reason="already_flagged")
            flag_id = uuid7()
            await self._repo.insert_flag(
                s,
                {
                    "id": flag_id,
                    "tenant_id": actor.tenant_id,
                    "counterparty_id": counterparty_id,
                    "flagged_by": actor.user_id,
                    "reason": reason.strip(),
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_doubtful_flagged",
                entity=FLAGS,
                entity_id=flag_id,
                ip=ip,
                after={"counterparty_id": str(counterparty_id), "reason": reason.strip()},
            )
            row = await self._repo.get_flag(s, flag_id)
            assert row is not None
            body = flag_json(row)
            stage_response(body, 201)
        return body

    async def unflag(self, actor: Principal, flag_id: UUID, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_flag(s, flag_id, lock=True)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "debt_doubtful_flag"})
            if row["unflagged_at"] is not None:
                raise _state("unflagged", "flagged")
            await self._repo.unflag(s, flag_id)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="debt_doubtful_unflagged",
                entity=FLAGS,
                entity_id=flag_id,
                ip=ip,
                before={"reason": row["reason"]},
                after={"counterparty_id": str(row["counterparty_id"])},
            )
            updated = await self._repo.get_flag(s, flag_id)
            assert updated is not None
            body = flag_json(updated)
            stage_response(body, 200)
        return body

    # === helpers ===================================================================================
    @staticmethod
    def _positive(amount: Decimal) -> Decimal:
        value = money(amount)
        if value <= 0:
            raise _invalid("amount", "validation.positive")
        return value

    @staticmethod
    def _not_future(day: date) -> None:
        if day > business_today():  # 13 §5.2
            raise _invalid("doc_date", "validation.doc_date_in_future")

    async def _branch(self, s: AsyncSession, scope: BranchScope, branch_id: UUID | None) -> UUID:
        chosen = branch_id or scope.current or await self._repo.default_branch(s)
        if chosen is None:
            raise _invalid("branch_id", "validation.required")
        if not scope.unrestricted and chosen not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        if not await self._repo.branch_exists(s, chosen):
            raise _invalid("branch_id", "validation.not_found")
        return chosen

    async def _load(self, s: AsyncSession, table: str, doc_id: UUID) -> Row:
        row = await self._repo.get_doc(s, table, doc_id)
        assert row is not None
        return row

    async def _doc(
        self, s: AsyncSession, scope: BranchScope, table: str, doc_id: UUID, *, lock: bool = False
    ) -> Row:
        row = await self._repo.get_doc(s, table, doc_id, lock=lock)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": table.removesuffix("s")})
        if not scope.unrestricted and row["branch_id"] not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return row

    async def _page(
        self, s: AsyncSession, scope: BranchScope, table: str, flt: DocFilter, cursor: str | None, limit: int
    ) -> tuple[list[Row], str | None]:
        after = decode_cursor(cursor) if cursor else None
        if flt.branch_id is not None and not scope.unrestricted and flt.branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        filters = {k: getattr(flt, k) for k in DocFilter.__dataclass_fields__}
        rows = await self._repo.docs_page(
            s,
            table,
            filters=filters,
            branch_ids=None if scope.unrestricted else scope.allowed,
            after=after,
            limit=limit + 1,
        )
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1]["doc_date"], page[-1]["id"]) if len(rows) > limit else None
        return page, next_cursor

    async def _cancelled(
        self,
        s: AsyncSession,
        actor: Principal,
        table: str,
        row: Row,
        reason: str,
        ip: str | None,
        action: str,
    ) -> None:
        if not reason.strip():
            raise _invalid("reason", "validation.required")
        await self._repo.update_doc(
            s,
            table,
            row["id"],
            {
                "status": "cancelled",
                "cancelled_at": datetime.now(UTC),
                "cancelled_by": actor.user_id,
                "cancel_reason": reason.strip(),
            },
        )
        await record_audit(
            s,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            action=action,
            entity=table,
            entity_id=row["id"],
            ip=ip,
            before={"status": row["status"]},
            after={"reason": reason.strip()},
        )
