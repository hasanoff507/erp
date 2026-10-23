"""Expenses (M15): ``draft → post → cancel`` REST (20 #41–#44), POS ``expense.created`` (18 §13.2).

Posting (``ExpensePostingService`` of 13 §2.17, one transaction — 23 §2.1): one ledger line
``Dt <category.default_account> / Kt 5010 | 5110`` (analytics ``expense_category_id``, ``source``,
``tax_type``, ``cash_register_id``), for ``source='cash'`` also ``cash_moves(−amount, method='cash',
doc_type='expenses')`` in the shift (no ``cash_movements`` document), number ``E-…``.
A ``6410`` category (``tax_payment``) is a payment to the budget, not an expense — ``tax_type`` mandatory
(13 §2.26, QT-M15-06).

Limits:

* back-office ``post`` — the poster's ``expenses.approve`` ``limit_value`` (15 §2.1; Owner unlimited,
  a role without the code always needs approval). Over it: ``approval_requests(kind='expense_over_limit')``
  + ``over_limit_action`` event, ``202 {status:"draft", approval_request_id}`` (17 §9) — the document stays
  ``draft``. Approving in BO-16 posts it through :meth:`ExpenseService.post_approved` (approval hook), or the
  next ``post`` consumes the approved request (``doc_approvals``, single use);
* POS ``expense.created`` — the actor's ``cash.withdraw`` limit (cashier default 50 000 so'm); over it an
  ``ApprovalRef`` is required (kind ``cash_withdrawal_over_limit``; ``local_pin`` offline too) exactly like
  ``cash_movement.created``; posted immediately.

``cancel`` — ``draft`` → ``cancelled``; ``posted`` → ledger storno (13 §5.2) and, for cash, a reversing
``cash_moves`` row — only while the shift is still open (a closed shift's expected cash is final, as for
cash movements, 20 #54), else ``409 DOC_INVALID_STATE``. The record is never deleted (QT-M15-04).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
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
from app.core.permissions import BranchScope
from app.modules.access.application.approval_gate import ApprovalGate, ApprovalRefIn
from app.modules.access.domain.approvals import APPROVAL_TTL_MINUTES
from app.modules.accounting.wiring import LedgerLine, LedgerPoster, business_today, period_label
from app.modules.cash.application.contracts import ShiftGuard
from app.modules.expenses.application.ports import ExpenseFilter, ExpenseRow, ExpenseStore
from app.modules.expenses.domain.expenses import (
    Violation,
    cash_refs_violations,
    credit_account,
    tax_type_violation,
)
from app.modules.sync.application.handlers import EventContext, SyncExceptionRow

DOC_TYPE = "expenses"
_OFFLINE_AFTER = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class ExpenseInput:
    doc_date: date
    category_id: UUID
    amount: Decimal
    source: str
    branch_id: UUID | None = None
    cash_register_id: UUID | None = None
    shift_id: UUID | None = None
    attachment_id: UUID | None = None
    comment: str | None = None
    recurring_rule_id: UUID | None = None
    tax_type: str | None = None


@dataclass(frozen=True, slots=True)
class PostOutcome:
    body: dict[str, Any]
    status: int


@dataclass(frozen=True, slots=True)
class Posted:
    body: dict[str, Any]
    sync_exceptions: tuple[SyncExceptionRow, ...] = ()


# --- small helpers ------------------------------------------------------------------------------------
def m2(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(Decimal("0.01")), "f")


def ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sid(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def violations_error(violations: list[Violation]) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        details=[ErrorDetail(field=v.field, message_key=v.message_key) for v in violations],
    )


def encode_cursor(day: date, row_id: UUID) -> str:
    raw = json.dumps([day.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[date, UUID] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        day, row_id = json.loads(raw)
        return date.fromisoformat(day), UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise invalid("cursor", "validation.cursor_invalid") from exc


def scope_branches(scope: BranchScope) -> tuple[UUID, ...] | None:
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


def check_branch(scope: BranchScope, branch_id: UUID, resource: str) -> None:
    if not scope.unrestricted and branch_id not in scope.allowed:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": resource})


def default_branch(scope: BranchScope, explicit: UUID | None) -> UUID:
    """Body ``branch_id``, else ``X-Branch-Id``, else the member's only branch (20 #42)."""
    branch = explicit or scope.current
    if branch is None and len(scope.allowed) == 1:
        branch = scope.allowed[0]
    if branch is None:
        raise invalid("branch_id", "validation.required")
    if not scope.unrestricted and branch not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
    return branch


def expense_json(row: ExpenseRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "number": row.number,
        "branch_id": str(row.branch_id),
        "doc_date": row.doc_date.isoformat(),
        "status": row.status,
        "category_id": str(row.category_id),
        "category_name": row.category_name,
        "account": row.posted_account or row.category_account,
        "amount": m2(row.amount),
        "source": row.source,
        "tax_type": row.tax_type,
        "cash_register_id": _sid(row.cash_register_id),
        "shift_id": _sid(row.shift_id),
        "attachment_id": _sid(row.attachment_id),
        "recurring_rule_id": _sid(row.recurring_rule_id),
        "comment": row.comment,
        "created_by": str(row.created_by),
        "created_at": ts(row.created_at),
        "posted_at": ts(row.posted_at),
        "cancelled_at": ts(row.cancelled_at),
        "cancel_reason": row.cancel_reason,
        "device_id": _sid(row.device_id),
        "approval_request_id": _sid(row.approval_request_id),
        "approval_status": row.approval_status,
    }


class ExpenseService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: ExpenseStore,
        poster: LedgerPoster,
        gate: ApprovalGate,
        guard: ShiftGuard,
        notifications: Any | None = None,
        approval_ttl_minutes: int = APPROVAL_TTL_MINUTES,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._poster = poster
        self._gate = gate
        self._guard = guard
        self._notify = notifications
        self._ttl = approval_ttl_minutes

    # --- back-office REST ---------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, inp: ExpenseInput, ip: str | None
    ) -> dict[str, Any]:
        branch_id = default_branch(scope, inp.branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            expense_id = await self.insert_draft(s, actor.tenant_id, actor.user_id, inp, branch_id)
            row = await self._repo.get_expense(s, expense_id)
            assert row is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="expense.created",
                entity=DOC_TYPE,
                entity_id=expense_id,
                ip=ip,
                device_id=actor.device_id,
                after={"amount": m2(inp.amount), "source": inp.source, "category_id": str(inp.category_id)},
            )
            body = expense_json(row)
            stage_response(body, 201)
        return body

    async def post(
        self, actor: Principal, scope: BranchScope, expense_id: UUID, ip: str | None
    ) -> PostOutcome:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_expense(s, expense_id, lock=True)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "expense"})
            check_branch(scope, row.branch_id, "expense")
            outcome = await self.post_draft(s, actor.tenant_id, actor.user_id, row, ip, actor.device_id)
            stage_response(outcome.body, outcome.status)
        return outcome

    async def cancel(
        self, actor: Principal, scope: BranchScope, expense_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_expense(s, expense_id, lock=True)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "expense"})
            check_branch(scope, row.branch_id, "expense")
            if row.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED, params={"id": str(row.id)})
            if row.status == "posted":
                if row.source == "cash" and row.shift_id is not None:
                    shift = await self._repo.get_shift(s, row.shift_id)
                    if shift is None or shift.status != "open":
                        raise AppError(
                            ErrorCode.DOC_INVALID_STATE,
                            params={"reason": "shift_closed", "shift_id": str(row.shift_id)},
                        )
                for move_id, amount, register_id, shift_id, _ in await self._repo.live_cash_moves(s, row.id):
                    await self._repo.insert_cash_move(
                        s,
                        {
                            "tenant_id": actor.tenant_id,
                            "cash_register_id": register_id,
                            "shift_id": shift_id,
                            "amount": -amount,
                            "doc_id": row.id,
                            "reversal_of_id": move_id,
                        },
                    )
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, row.id)
            cancelled_at = await self._repo.mark_cancelled(s, row.id, actor.user_id, reason)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="expense.cancelled",
                entity=DOC_TYPE,
                entity_id=row.id,
                ip=ip,
                device_id=actor.device_id,
                before={"status": row.status},
                after={
                    "status": "cancelled",
                    "reason": reason,
                    "amount": m2(row.amount),
                    "source": row.source,
                },
            )
            body = {"id": str(row.id), "status": "cancelled", "cancelled_at": ts(cancelled_at)}
            stage_response(body, 200)
        return body

    async def list_page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        branch_id: UUID | None,
        category_id: UUID | None,
        source: str | None,
        status: str | None,
        date_from: date | None,
        date_to: date | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        branches = scope_branches(scope)
        if branch_id is not None:
            check_branch(scope, branch_id, "branch")
            branches = () if branches is not None and branch_id not in branches else (branch_id,)
        flt = ExpenseFilter(
            branches, category_id, source, status, date_from, date_to, decode_cursor(cursor), limit + 1
        )
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_expenses(s, flt)
            totals = await self._repo.totals(s, flt)
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [expense_json(r) for r in rows],
            "next_cursor": encode_cursor(rows[-1].doc_date, rows[-1].id) if more and rows else None,
            "totals": {"posted": m2(totals["posted"]), "draft": m2(totals["draft"])},
        }

    async def post_approved(
        self, s: AsyncSession, tenant_id: UUID, expense_id: UUID, request_id: UUID, user_id: UUID
    ) -> None:
        """BO-16 approved the draft's ``expense_over_limit`` request: post it now (approve transaction)."""
        row = await self._repo.get_expense(s, expense_id, lock=True)
        if row is None or row.status != "draft" or row.approval_request_id != request_id:
            return  # cancelled / already posted meanwhile — the approved request stays unused
        await self._repo_check_post(s, row)
        await self._consume(s, tenant_id, row, request_id)
        await self._post_registers(s, tenant_id, row, row.doc_date, {})
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=user_id,
            action="expense.posted",
            entity=DOC_TYPE,
            entity_id=row.id,
            after={"amount": m2(row.amount), "approval_request_id": str(request_id)},
        )

    # --- POS event (18 §13.2) -------------------------------------------------------------------------
    async def from_event(
        self,
        s: AsyncSession,
        ctx: EventContext,
        expense_id: UUID,
        inp: ExpenseInput,
        approval: ApprovalRefIn | None,
    ) -> Posted:
        right = await self._repo.grant(s, ctx.actor_user_id, "cash.withdraw")
        if not right.holds:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": "cash.withdraw"})
        assert inp.shift_id is not None
        assert inp.cash_register_id is not None
        opened = await self._guard.require_open(
            s, shift_id=inp.shift_id, device_id=ctx.device_id, at=ctx.created_at
        )
        if opened.cash_register_id != inp.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_not_of_shift")
        if inp.branch_id is not None and opened.branch_id != inp.branch_id:
            raise invalid("branch_id", "validation.branch_mismatch")
        if await self._repo.get_expense(s, expense_id) is not None:
            raise invalid("id", "validation.duplicate")
        await self.insert_draft(
            s,
            ctx.tenant_id,
            ctx.actor_user_id,
            inp,
            opened.branch_id,
            expense_id=expense_id,
            client_event_id=ctx.client_event_id,
            device_id=ctx.device_id,
            pos=True,
        )
        exceptions: list[SyncExceptionRow] = []
        outcome = await self._gate.require(
            s,
            tenant_id=ctx.tenant_id,
            branch_id=opened.branch_id,
            kind="cash_withdrawal_over_limit",
            permission="cash.withdraw",
            requested_by=ctx.actor_user_id,
            value=inp.amount,
            approval=approval,
            doc_type=DOC_TYPE,
            doc_id=expense_id,
            offline=ctx.received_at - ctx.created_at > _OFFLINE_AFTER,
            approver_bound=ctx.actor_bound,
        )
        if outcome.approver_unverified:
            exceptions.append(
                SyncExceptionRow(
                    kind="actor_unverified",
                    details={**outcome.unverified_details, "session_user_id": str(ctx.session_user_id)},
                    doc_type=DOC_TYPE,
                    doc_id=expense_id,
                )
            )
        if outcome.offline_limit_exceeded:
            exceptions.append(
                SyncExceptionRow(
                    kind="approval_limit_exceeded_offline",
                    details=dict(outcome.details),
                    doc_type=DOC_TYPE,
                    doc_id=expense_id,
                )
            )
        row = await self._repo.get_expense(s, expense_id)
        assert row is not None
        # closed period (qaror #69): never refused — registers go to the first open date
        entry_date = await self._poster.first_open_date(s, row.doc_date)
        analytics: dict[str, Any] = {}
        if entry_date != row.doc_date:
            analytics["correction_of_period"] = period_label(row.doc_date)
            exceptions.append(
                SyncExceptionRow(
                    kind="late_in_closed_period",
                    details={
                        "period": period_label(row.doc_date),
                        "doc_date": row.doc_date.isoformat(),
                        "entry_date": entry_date.isoformat(),
                    },
                    doc_type=DOC_TYPE,
                    doc_id=expense_id,
                )
            )
        await self._post_registers(s, ctx.tenant_id, row, entry_date, analytics)
        late_shift = await self._guard.settle_late(
            s, tenant_id=ctx.tenant_id, shift=opened, doc_type=DOC_TYPE, doc_id=expense_id
        )
        if late_shift is not None:
            exceptions.append(late_shift)
        return Posted({"id": str(expense_id), "status": "posted"}, tuple(exceptions))

    # --- in-transaction building blocks (also used by recurring rules) -------------------------------
    async def insert_draft(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        inp: ExpenseInput,
        branch_id: UUID,
        *,
        expense_id: UUID | None = None,
        client_event_id: UUID | None = None,
        device_id: UUID | None = None,
        pos: bool = False,
    ) -> UUID:
        if inp.doc_date > business_today():
            raise invalid("doc_date", "validation.doc_date_in_future")
        violations = cash_refs_violations(inp.source, inp.cash_register_id, inp.shift_id)
        if violations:
            raise violations_error(violations)
        if not pos:
            if not await self._repo.branch_exists(s, branch_id):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "branch"})
            await self._poster.assert_period_open(s, inp.doc_date)
        category = await self._repo.get_category(s, inp.category_id)
        if category is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "expense_category"})
        if category.archived_at is not None:
            raise invalid("category_id", "validation.archived")
        violation = tax_type_violation(category.default_account, inp.tax_type)
        if violation is not None:
            raise violations_error([violation])
        if inp.source == "cash" and not pos:
            assert inp.shift_id is not None
            shift = await self._repo.get_shift(s, inp.shift_id)
            if shift is None or shift.status != "open":
                raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(inp.shift_id)})
            if shift.cash_register_id != inp.cash_register_id:
                raise invalid("cash_register_id", "validation.cash_register_not_of_shift")
            if shift.branch_id != branch_id:
                raise invalid("branch_id", "validation.branch_mismatch")
        if inp.attachment_id is not None:
            kind = await self._repo.attachment_kind(s, inp.attachment_id)
            if kind is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "attachment"})
            if kind != "expense_receipt":
                raise invalid("attachment_id", "validation.invalid_choice")
        if inp.recurring_rule_id is not None and await self._repo.get_rule(s, inp.recurring_rule_id) is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "recurring_expense"})
        new_id = expense_id or uuid7()
        await self._repo.insert_expense(
            s,
            {
                "id": new_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "doc_date": inp.doc_date,
                "category_id": inp.category_id,
                "amount": inp.amount,
                "source": inp.source,
                "tax_type": inp.tax_type,
                "cash_register_id": inp.cash_register_id,
                "shift_id": inp.shift_id,
                "attachment_id": inp.attachment_id,
                "recurring_rule_id": inp.recurring_rule_id,
                "created_by": user_id,
                "client_event_id": client_event_id,
                "device_id": device_id,
                "comment": inp.comment,
            },
        )
        return new_id

    async def post_draft(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        row: ExpenseRow,
        ip: str | None,
        device_id: UUID | None,
    ) -> PostOutcome:
        """``POST /expenses/{id}/post`` inside the caller's transaction (``row`` locked)."""
        if row.status != "draft":
            raise AppError(ErrorCode.DOC_NOT_DRAFT, params={"id": str(row.id), "status": row.status})
        await self._poster.assert_period_open(s, row.doc_date)
        await self._repo_check_post(s, row)
        own = await self._repo.grant(s, user_id, "expenses.approve")
        within = own.active and (own.owner or own.covers(row.amount))
        if not within:
            status = row.approval_status
            value_ok = row.approval_requested_value is not None and row.approval_requested_value >= row.amount
            if row.approval_request_id is not None and status == "approved" and value_ok:
                await self._consume(s, tenant_id, row, row.approval_request_id)
            elif row.approval_request_id is not None and status == "pending" and value_ok:
                body = {
                    "id": str(row.id),
                    "status": "draft",
                    "approval_request_id": str(row.approval_request_id),
                }
                return PostOutcome(body, 202)
            else:
                request_id = await self._request_approval(s, tenant_id, user_id, row, ip, device_id)
                return PostOutcome(
                    {"id": str(row.id), "status": "draft", "approval_request_id": str(request_id)}, 202
                )
        number, posted_at = await self._post_registers(s, tenant_id, row, row.doc_date, {})
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=user_id,
            action="expense.posted",
            entity=DOC_TYPE,
            entity_id=row.id,
            ip=ip,
            device_id=device_id,
            before={"status": "draft"},
            after={"status": "posted", "number": number, "amount": m2(row.amount), "source": row.source},
        )
        return PostOutcome(
            {"id": str(row.id), "status": "posted", "number": number, "posted_at": ts(posted_at)}, 200
        )

    # --- helpers --------------------------------------------------------------------------------------
    async def _repo_check_post(self, s: AsyncSession, row: ExpenseRow) -> None:
        """The category's *current* account decides the posting; re-check ``tax_type`` and the shift."""
        category = await self._repo.get_category(s, row.category_id)
        assert category is not None  # FK
        violation = tax_type_violation(category.default_account, row.tax_type)
        if violation is not None:
            raise violations_error([violation])
        if row.source == "cash" and row.shift_id is not None:
            shift = await self._repo.get_shift(s, row.shift_id)
            if shift is None or shift.status != "open":
                raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(row.shift_id)})

    async def _consume(self, s: AsyncSession, tenant_id: UUID, row: ExpenseRow, request_id: UUID) -> None:
        request = await self._repo.approval_requester(s, request_id)
        if request is None:
            raise AppError(ErrorCode.APPROVAL_INVALID, params={"reason": "approval_request_not_found"})
        await self._gate.require(
            s,
            tenant_id=tenant_id,
            branch_id=row.branch_id,
            kind="expense_over_limit",
            permission="expenses.approve",
            requested_by=request,
            value=row.amount,
            approval=ApprovalRefIn(mode="remote_request", approval_request_id=request_id),
            doc_type=DOC_TYPE,
            doc_id=row.id,
            offline=False,
            always_required=True,
        )

    async def _post_registers(
        self, s: AsyncSession, tenant_id: UUID, row: ExpenseRow, entry_date: date, extra: dict[str, Any]
    ) -> tuple[str, datetime]:
        category = await self._repo.get_category(s, row.category_id)
        assert category is not None
        analytics: dict[str, Any] = {
            "expense_category_id": str(row.category_id),
            "source": row.source,
            **extra,
        }
        if row.tax_type is not None:
            analytics["tax_type"] = row.tax_type
        if row.cash_register_id is not None:
            analytics["cash_register_id"] = str(row.cash_register_id)
        await self._poster.post(
            s,
            tenant_id,
            DOC_TYPE,
            row.id,
            [
                LedgerLine(
                    entry_date,
                    row.branch_id,
                    category.default_account,
                    credit_account(row.source),
                    row.amount,
                    analytics,
                )
            ],
        )
        if row.source == "cash":
            await self._repo.insert_cash_move(
                s,
                {
                    "tenant_id": tenant_id,
                    "cash_register_id": row.cash_register_id,
                    "shift_id": row.shift_id,
                    "amount": -row.amount,
                    "doc_id": row.id,
                },
            )
        number = await next_doc_number(
            s, tenant_id=tenant_id, branch_id=row.branch_id, table=DOC_TYPE, year=row.doc_date.year
        )
        posted_at = await self._repo.mark_posted(s, row.id, number)
        return number, posted_at

    async def _request_approval(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        row: ExpenseRow,
        ip: str | None,
        device_id: UUID | None,
    ) -> UUID:
        request_id = uuid7()
        now = datetime.now(UTC)
        await self._repo.insert_approval_request(
            s,
            {
                "id": request_id,
                "tenant_id": tenant_id,
                "branch_id": row.branch_id,
                "kind": "expense_over_limit",
                "permission_code": "expenses.approve",
                "requested_value": row.amount,
                "context": json.dumps(
                    {
                        "amount": m2(row.amount),
                        "category_id": str(row.category_id),
                        "category_name": row.category_name,
                        "source": row.source,
                        "doc_date": row.doc_date.isoformat(),
                    },
                    ensure_ascii=False,
                ),
                "linked_doc_type": DOC_TYPE,
                "linked_doc_id": row.id,
                "device_id": device_id,
                "requested_by": user_id,
                "requested_at": now,
                "expires_at": now + timedelta(minutes=self._ttl),
            },
        )
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=user_id,
            action="approval_requested",
            entity="approval_requests",
            entity_id=request_id,
            ip=ip,
            device_id=device_id,
            after={
                "kind": "expense_over_limit",
                "requested_value": m2(row.amount),
                "linked_doc_type": DOC_TYPE,
                "linked_doc_id": str(row.id),
            },
        )
        if self._notify is not None:
            await self._notify.record_event(
                s,
                tenant_id,
                "over_limit_action",
                {
                    "approval_request_id": str(request_id),
                    "kind": "expense_over_limit",
                    "branch_id": str(row.branch_id),
                    "requested_value": m2(row.amount),
                    "requested_by": str(user_id),
                    "doc_type": DOC_TYPE,
                    "doc_id": str(row.id),
                },
                f"approval_requested:{request_id}",
            )
        return request_id
