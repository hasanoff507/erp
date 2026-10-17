"""Cash movements (M16): ``cash_movement.created`` + back-office REST (18 §13, 20 #52–#54, 13 §2.18).

One-step document: created ``posted`` (number ``CM-…``) with its ``cash_moves`` row and one ledger line
in the same transaction. Rights: ``in`` — ``cash.deposit``; ``out`` — ``cash.withdraw`` whose
``limit_value`` (default 50 000 so'm for a cashier) is enforced through the
:class:`~app.modules.access.application.approval_gate.ApprovalGate` (kind ``cash_withdrawal_over_limit``):

* POS event — over the limit needs ``approval`` (``local_pin`` offline too, ``remote_request`` online);
  missing → ``CASH_WITHDRAW_LIMIT_EXCEEDED``;
* back-office ``POST`` — over the limit the movement is stored as ``draft`` with an
  ``approval_requests(kind='cash_withdrawal_over_limit', linked_doc_type='cash_movements')`` and the
  response is ``202 {status:"draft", approval_request_id}``; approving the request (BO-16) posts the
  draft (``post_approved`` — the request is consumed through the gate; the shift must still be open).

``cancel`` (back-office, online): ``draft`` → ``cancelled``; ``posted`` → storno of the ledger line and a
reversing ``cash_moves`` row (``reversal_of_id``) — only while the shift is open (a closed shift's
expected cash is final), else ``409 DOC_INVALID_STATE``; ``cancelled`` → ``409 DOC_ALREADY_CANCELLED``.
"""

from __future__ import annotations

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
from app.modules.accounting.wiring import LedgerLine, LedgerPoster, business_date, business_today
from app.modules.cash.application.common import (
    check_branch,
    decode_cursor,
    encode_cursor,
    invalid,
    m2,
    register_date,
    scope_branches,
    ts,
)
from app.modules.cash.application.ports import CashRepository, MovementFilter, MovementRow, ShiftRow
from app.modules.cash.application.shift_guard import ShiftGuardService
from app.modules.cash.domain.movements import (
    MovementInput,
    effective_account,
    ledger_entry,
    owner_account,
    signed,
    validate,
)
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.sync.application.handlers import EventContext, SyncExceptionRow

DOC_TYPE = "cash_movements"


@dataclass(frozen=True, slots=True)
class Posted:
    body: dict[str, Any]
    sync_exceptions: tuple[SyncExceptionRow, ...] = ()


def movement_json(row: MovementRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "number": row.number,
        "status": row.status,
        "doc_date": row.doc_date.isoformat(),
        "branch_id": str(row.branch_id),
        "cash_register_id": str(row.cash_register_id),
        "shift_id": str(row.shift_id),
        "direction": row.direction,
        "amount": m2(row.amount),
        "reason": row.reason,
        "account": row.account,
        "counterparty_id": None if row.counterparty_id is None else str(row.counterparty_id),
        "employee_id": None if row.employee_id is None else str(row.employee_id),
        "comment": row.comment,
        "created_by": str(row.created_by),
        "created_at": ts(row.created_at),
        "posted_at": ts(row.posted_at),
        "cancelled_at": ts(row.cancelled_at),
        "cancel_reason": row.cancel_reason,
        "device_id": None if row.device_id is None else str(row.device_id),
    }


def _right(direction: str) -> str:
    return "cash.deposit" if direction == "in" else "cash.withdraw"


RECEIVABLE = "4010"


class CashMovementService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CashRepository,
        poster: LedgerPoster,
        gate: ApprovalGate,
        guard: ShiftGuardService,
        notifications: Any | None = None,
        approval_ttl_minutes: int = APPROVAL_TTL_MINUTES,
        debts: DebtRegister | None = None,
    ) -> None:
        self._ttl = approval_ttl_minutes  # settings.approval_ttl_minutes (ACC-06)
        # B4: account 4010 against a customer moves debt_balances too (debt book = 4010 ledger, 13 §2.18)
        self._debts = debts
        self._sf = session_factory
        self._repo = repo
        self._poster = poster
        self._gate = gate
        self._guard = guard
        self._notify = notifications

    # --- POS event ------------------------------------------------------------------------------------
    async def from_event(
        self,
        s: AsyncSession,
        ctx: EventContext,
        movement_id: UUID,
        m: MovementInput,
        approval: ApprovalRefIn | None,
    ) -> Posted:
        right = await self._repo.grant(s, ctx.actor_user_id, _right(m.direction))
        if not right.holds:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": _right(m.direction)})
        opened = await self._guard.require_open(
            s, shift_id=m.shift_id, device_id=ctx.device_id, at=ctx.created_at
        )
        if opened.cash_register_id != m.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_not_of_shift")
        if await self._repo.get_movement(s, movement_id) is not None:
            raise invalid("id", "validation.duplicate")
        await self._check_refs(s, m)
        doc_date = business_date(ctx.created_at)
        await self._insert(
            s,
            ctx.tenant_id,
            movement_id,
            opened.branch_id,
            doc_date,
            m,
            ctx.actor_user_id,
            ctx.client_event_id,
            ctx.device_id,
        )
        exceptions: list[SyncExceptionRow] = []
        if m.direction == "out":
            offline = ctx.received_at - ctx.created_at > timedelta(minutes=5)
            outcome = await self._gate.require(
                s,
                tenant_id=ctx.tenant_id,
                branch_id=opened.branch_id,
                kind="cash_withdrawal_over_limit",
                permission="cash.withdraw",
                requested_by=ctx.actor_user_id,
                value=m.amount,
                approval=approval,
                doc_type=DOC_TYPE,
                doc_id=movement_id,
                offline=offline,
                approver_bound=ctx.actor_bound,
            )
            if outcome.approver_unverified:
                exceptions.append(
                    SyncExceptionRow(
                        kind="actor_unverified",
                        details={**outcome.unverified_details, "session_user_id": str(ctx.session_user_id)},
                        doc_type=DOC_TYPE,
                        doc_id=movement_id,
                    )
                )
            if outcome.offline_limit_exceeded:
                exceptions.append(
                    SyncExceptionRow(
                        kind="approval_limit_exceeded_offline",
                        details=dict(outcome.details),
                        doc_type=DOC_TYPE,
                        doc_id=movement_id,
                    )
                )
        late = await self._post(
            s, ctx.tenant_id, movement_id, opened.branch_id, doc_date, m, ctx.actor_user_id
        )
        if late is not None:
            exceptions.append(late)
        late_shift = await self._guard.settle_late(
            s, tenant_id=ctx.tenant_id, shift=opened, doc_type=DOC_TYPE, doc_id=movement_id
        )
        if late_shift is not None:
            exceptions.append(late_shift)
        return Posted({"id": str(movement_id)}, tuple(exceptions))

    # --- back-office REST -----------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, m: MovementInput, doc_date: date, ip: str | None
    ) -> tuple[dict[str, Any], int]:
        if doc_date > business_today():
            raise invalid("doc_date", "validation.doc_date_in_future")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            right = await self._repo.grant(s, actor.user_id, _right(m.direction))
            if not right.holds:
                raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": _right(m.direction)})
            shift = await self._open_shift(s, m)
            check_branch(scope, shift.branch_id, "shift")
            await self._poster.assert_period_open(s, doc_date)
            await self._check_refs(s, m)
            movement_id = uuid7()
            await self._check_customer_credit(s, actor.tenant_id, m)
            await self._insert(
                s, actor.tenant_id, movement_id, shift.branch_id, doc_date, m, actor.user_id, None, None
            )
            if m.direction == "out" and not (right.owner or right.covers(m.amount)):
                request_id = await self._request_approval(s, actor, shift, movement_id, m, ip)
                body: dict[str, Any] = {
                    "id": str(movement_id),
                    "status": "draft",
                    "amount": m2(m.amount),
                    "approval_request_id": str(request_id),
                }
                stage_response(body, 202)
                return body, 202
            await self._post(s, actor.tenant_id, movement_id, shift.branch_id, doc_date, m, actor.user_id)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="cash_movement_posted",
                entity=DOC_TYPE,
                entity_id=movement_id,
                ip=ip,
                after={"direction": m.direction, "reason": m.reason, "amount": m2(m.amount)},
            )
            body = {
                "id": str(movement_id),
                "status": "posted",
                "amount": m2(m.amount),
                "approval_request_id": None,
            }
            stage_response(body, 201)
        return body, 201

    async def post_approved(
        self, s: AsyncSession, tenant_id: UUID, movement_id: UUID, request_id: UUID
    ) -> None:
        """BO-16 approved the draft's request: post it now (inside the approve transaction)."""
        row = await self._repo.get_movement(s, movement_id, lock=True)
        if row is None or row.status != "draft":
            return  # cancelled meanwhile — the approved request simply stays unused
        shift = await self._repo.get_shift(s, row.shift_id, lock="share")
        if shift is None or shift.status != "open":
            raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(row.shift_id)})
        m = _input_of(row)
        await self._gate.require(
            s,
            tenant_id=tenant_id,
            branch_id=row.branch_id,
            kind="cash_withdrawal_over_limit",
            permission="cash.withdraw",
            requested_by=row.created_by,
            value=row.amount,
            approval=ApprovalRefIn(mode="remote_request", approval_request_id=request_id),
            doc_type=DOC_TYPE,
            doc_id=row.id,
            offline=False,
        )
        await self._post(s, tenant_id, row.id, row.branch_id, row.doc_date, m, row.created_by, rest=True)

    async def cancel(
        self, actor: Principal, scope: BranchScope, movement_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_movement(s, movement_id, lock=True)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cash_movement"})
            check_branch(scope, row.branch_id, "cash_movement")
            right = await self._repo.grant(s, actor.user_id, _right(row.direction))
            if not right.holds:
                raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": _right(row.direction)})
            if row.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED, params={"id": str(row.id)})
            if row.status == "posted":
                shift = await self._repo.get_shift(s, row.shift_id, lock="share")
                if shift is None or shift.status != "open":
                    raise AppError(
                        ErrorCode.DOC_INVALID_STATE,
                        params={"reason": "shift_closed", "shift_id": str(row.shift_id)},
                    )
                if row.direction == "in":
                    # cancelling a deposit takes the cash out: cash.withdraw + limit (SEC-10, 20 #54)
                    await self._gate.require(
                        s,
                        tenant_id=actor.tenant_id,
                        branch_id=row.branch_id,
                        kind="cash_withdrawal_over_limit",
                        permission="cash.withdraw",
                        requested_by=actor.user_id,
                        value=row.amount,
                        approval=None,
                        doc_type=DOC_TYPE,
                        doc_id=row.id,
                        offline=False,
                    )
                for move_id, amount, register_id, shift_id, method in await self._repo.live_cash_moves(
                    s, DOC_TYPE, row.id
                ):
                    await self._repo.insert_cash_move(
                        s,
                        {
                            "tenant_id": actor.tenant_id,
                            "cash_register_id": register_id,
                            "shift_id": shift_id,
                            "amount": -amount,
                            "method": method,
                            "doc_type": DOC_TYPE,
                            "doc_id": row.id,
                            "reversal_of_id": move_id,
                        },
                    )
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, row.id)
                if self._debts is not None:
                    await self._debts.reverse(s, actor.tenant_id, DOC_TYPE, row.id)
            await self._repo.mark_cancelled(s, row.id, actor.user_id, reason)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="cash_movement_cancelled",
                entity=DOC_TYPE,
                entity_id=row.id,
                ip=ip,
                before={"status": row.status},
                after={
                    "status": "cancelled",
                    "reason": reason,
                    "amount": m2(row.amount),
                    "direction": row.direction,
                },
            )
            body = {"id": str(row.id), "status": "cancelled"}
            stage_response(body, 200)
        return body

    async def list_page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        cash_register_id: UUID | None,
        shift_id: UUID | None,
        direction: str | None,
        reason: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_movements(
                s,
                MovementFilter(
                    scope_branches(scope),
                    cash_register_id,
                    shift_id,
                    direction,
                    reason,
                    decode_cursor(cursor),
                    limit + 1,
                ),
            )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [movement_json(r) for r in rows],
            "next_cursor": encode_cursor(rows[-1].created_at, rows[-1].id) if more and rows else None,
        }

    # --- helpers --------------------------------------------------------------------------------------
    async def _open_shift(self, s: AsyncSession, m: MovementInput) -> ShiftRow:
        shift = await self._repo.get_shift(s, m.shift_id, lock="share")
        if shift is None or shift.status != "open":
            raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(m.shift_id)})
        if shift.cash_register_id != m.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_not_of_shift")
        return shift

    async def _check_refs(self, s: AsyncSession, m: MovementInput) -> None:
        legal_form, _ = await self._repo.tenant_legal(s)
        violations = validate(m, sole_proprietor=legal_form == "sole_proprietor")
        if violations:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field=v.field, message_key=v.message_key) for v in violations],
            )
        if m.counterparty_id is not None:
            cp = await self._repo.counterparty(s, m.counterparty_id)
            if cp is None or not cp[1]:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "counterparty"})
            if m.reason == "owner_withdrawal" and not cp[0]:
                raise invalid("counterparty_id", "validation.counterparty_not_founder")
        if m.employee_id is not None and not await self._repo.is_member(s, m.employee_id):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "employee"})

    async def _check_customer_credit(self, s: AsyncSession, tenant_id: UUID, m: MovementInput) -> None:
        """ACC-02 (13 §2.18): a 4010 ``out`` only pays back the customer's 4010 credit — under the
        ``debt_balances`` lock, ``amount ≤ max(−receivable, 0)``; never a receivable without a document."""
        if effective_account(m) != RECEIVABLE or m.direction != "out" or m.counterparty_id is None:
            return
        if self._debts is None:
            return
        balances = await self._debts.lock(s, tenant_id, [(m.counterparty_id, "receivable")])
        available = max(-balances.get((m.counterparty_id, "receivable"), Decimal(0)), Decimal(0))
        if m.amount > available:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                params={"available": m2(available)},
                details=[
                    ErrorDetail(
                        field="amount", message_key="validation.cash_movement_exceeds_customer_credit"
                    )
                ],
            )

    async def _insert(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        movement_id: UUID,
        branch_id: UUID,
        doc_date: date,
        m: MovementInput,
        user_id: UUID,
        client_event_id: UUID | None,
        device_id: UUID | None,
    ) -> None:
        await self._repo.insert_movement(
            s,
            {
                "id": movement_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "doc_date": doc_date,
                "cash_register_id": m.cash_register_id,
                "shift_id": m.shift_id,
                "direction": m.direction,
                "amount": m.amount,
                "reason": m.reason,
                "counterparty_id": m.counterparty_id,
                "account": effective_account(m),
                "employee_id": m.employee_id,
                "created_by": user_id,
                "client_event_id": client_event_id,
                "device_id": device_id,
                "comment": m.comment,
            },
        )

    async def _post(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        movement_id: UUID,
        branch_id: UUID,
        doc_date: date,
        m: MovementInput,
        user_id: UUID,
        *,
        rest: bool = False,
    ) -> SyncExceptionRow | None:
        await self._check_customer_credit(s, tenant_id, m)
        legal_form, configured = await self._repo.tenant_legal(s)
        entry = ledger_entry(m, owner_acct=owner_account(legal_form, configured), branch_id=branch_id)
        late: SyncExceptionRow | None = None
        analytics = dict(entry.analytics)
        entry_date = doc_date
        if not rest:
            entry_date, correction = await register_date(s, self._poster, doc_date)
            if correction is not None:
                analytics["correction_of_period"] = correction
                late = SyncExceptionRow(
                    kind="late_in_closed_period",
                    details={"period": correction, "doc_date": doc_date.isoformat()},
                    doc_type=DOC_TYPE,
                    doc_id=movement_id,
                )
        await self._poster.post(
            s,
            tenant_id,
            DOC_TYPE,
            movement_id,
            [LedgerLine(entry_date, branch_id, entry.account_dt, entry.account_kt, m.amount, analytics)],
        )
        if (
            self._debts is not None
            and m.counterparty_id is not None
            and RECEIVABLE
            in (
                entry.account_dt,
                entry.account_kt,
            )
        ):
            delta = m.amount if entry.account_dt == RECEIVABLE else -m.amount
            await self._debts.post(
                s, tenant_id, [DebtMoveInput(m.counterparty_id, "receivable", delta, DOC_TYPE, movement_id)]
            )
        await self._repo.insert_cash_move(
            s,
            {
                "tenant_id": tenant_id,
                "cash_register_id": m.cash_register_id,
                "shift_id": m.shift_id,
                "amount": signed(m.direction, m.amount),
                "method": "cash",
                "doc_type": DOC_TYPE,
                "doc_id": movement_id,
            },
        )
        number = await next_doc_number(
            s, tenant_id=tenant_id, branch_id=branch_id, table=DOC_TYPE, year=doc_date.year
        )
        await self._repo.mark_posted(s, movement_id, number)
        del user_id
        return late

    async def _request_approval(
        self,
        s: AsyncSession,
        actor: Principal,
        shift: ShiftRow,
        movement_id: UUID,
        m: MovementInput,
        ip: str | None,
    ) -> UUID:
        request_id = uuid7()
        now = datetime.now(UTC)
        await self._repo.insert_approval_request(
            s,
            {
                "id": request_id,
                "tenant_id": actor.tenant_id,
                "branch_id": shift.branch_id,
                "kind": "cash_withdrawal_over_limit",
                "permission_code": "cash.withdraw",
                "requested_value": m.amount,
                "context": json.dumps(
                    {
                        "amount": m2(m.amount),
                        "reason": m.reason,
                        "direction": m.direction,
                        "cash_register_id": str(m.cash_register_id),
                        "shift_id": str(m.shift_id),
                    }
                ),
                "linked_doc_type": DOC_TYPE,
                "linked_doc_id": movement_id,
                "device_id": actor.device_id,
                "requested_by": actor.user_id,
                "requested_at": now,
                "expires_at": now + timedelta(minutes=self._ttl),
            },
        )
        await record_audit(
            s,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            action="approval_requested",
            entity="approval_requests",
            entity_id=request_id,
            ip=ip,
            after={
                "kind": "cash_withdrawal_over_limit",
                "requested_value": m2(m.amount),
                "linked_doc_type": DOC_TYPE,
                "linked_doc_id": str(movement_id),
            },
        )
        if self._notify is not None:
            await self._notify.record_event(
                s,
                actor.tenant_id,
                "over_limit_action",
                {
                    "approval_request_id": str(request_id),
                    "kind": "cash_withdrawal_over_limit",
                    "branch_id": str(shift.branch_id),
                    "requested_value": m2(m.amount),
                    "requested_by": str(actor.user_id),
                },
                f"approval_requested:{request_id}",
            )
        return request_id


def _input_of(row: MovementRow) -> MovementInput:
    return MovementInput(
        cash_register_id=row.cash_register_id,
        shift_id=row.shift_id,
        direction=row.direction,
        reason=row.reason,
        amount=Decimal(row.amount),
        account=row.account,
        counterparty_id=row.counterparty_id,
        employee_id=row.employee_id,
        comment=row.comment,
    )
