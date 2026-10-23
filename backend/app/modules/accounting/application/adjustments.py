"""``/ledger-adjustments`` — manual correcting entries (20 #10/#10a/#10b, 13 §2.23, §2.14, §2.15a, §5.5).

One-step document (17 §9): ``POST`` validates, numbers (``BX-…``), writes the ledger line (+ ``debt_moves``
for
4010/6010, 13 §2.14) and returns ``201 {status:"posted"}`` in ONE transaction; ``cancel`` = storno dated today
(or the first open date — a document of a closed month may be cancelled, 13 §5.2). Postings refuse a closed
``doc_date`` (``409 PERIOD_CLOSED``); a correction of a closed month is dated in the open period and marked
``correction_of_period`` (13 §5.1). Audit ``ledger_adjustment.posted`` / ``ledger_adjustment.cancelled``.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
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
from app.modules.accounting.application.ports import (
    AdjustmentFilter,
    AdjustmentRepository,
    AdjustmentRow,
    DebtRegisterPort,
)
from app.modules.accounting.application.posting import LedgerPoster, period_closed_error
from app.modules.accounting.domain.adjustments import (
    AdjustmentDraft,
    AdjustmentInvalidError,
    Problem,
    balance_needs,
    checked_adjustment,
    debt_effects,
)
from app.modules.accounting.domain.calendar import business_today, month_start, period_label
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.debts.domain.register import DebtMoveInput

DOC_TYPE = "ledger_adjustments"
ZERO = Decimal("0.00")


def _invalid(problems: list[Problem]) -> AppError:
    params: dict[str, Any] = {}
    for p in problems:
        params.update(p.params or {})
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        params=params or None,
        details=[ErrorDetail(field=p.field, message_key=p.key) for p in problems],
    )


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def adjustment_json(row: AdjustmentRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "number": row.number,
        "status": row.status,
        "branch_id": str(row.branch_id),
        "doc_date": row.doc_date.isoformat(),
        "account_dt": row.account_dt,
        "account_kt": row.account_kt,
        "amount": format(row.amount, "f"),
        "correction_of_period": None
        if row.correction_of_period is None
        else period_label(row.correction_of_period),
        "analytics": dict(row.analytics),
        "comment": row.comment,
        "created_by": str(row.created_by),
        "created_at": _ts(row.created_at),
        "posted_at": _ts(row.posted_at),
        "cancelled_at": _ts(row.cancelled_at),
        "cancel_reason": row.cancel_reason,
    }


def _encode(day: date, row_id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([day.isoformat(), str(row_id)]).encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[date, UUID]:
    try:
        day, rid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return date.fromisoformat(day), UUID(rid)
    except (ValueError, TypeError) as exc:
        raise _invalid([Problem("cursor", "validation.cursor_invalid")]) from exc


class LedgerAdjustmentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: AdjustmentRepository,
        poster: LedgerPoster,
        debts: DebtRegisterPort,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._poster = poster
        self._debts = debts

    # --- 20 #10 ---------------------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, values: dict[str, Any], ip: str | None
    ) -> dict[str, Any]:
        branch_id: UUID = values["branch_id"]
        if not scope.unrestricted and branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if not await self._repo.branch_exists(s, branch_id):
                raise _invalid([Problem("branch_id", "validation.branch_not_found")])
            try:
                draft = checked_adjustment(
                    branch_id=branch_id,
                    doc_date=values["doc_date"],
                    account_dt=values["account_dt"],
                    account_kt=values["account_kt"],
                    amount=values["amount"],
                    comment=values.get("comment"),
                    analytics=values.get("analytics"),
                    correction_of_period=values.get("correction_of_period"),
                    today=business_today(),
                    go_live_date=await self._repo.go_live_date(s),
                )
            except AdjustmentInvalidError as exc:
                raise _invalid(exc.problems) from None
            await self._check_state(s, actor.tenant_id, draft)
            adjustment_id = uuid7()
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=branch_id, table=DOC_TYPE, year=draft.doc_date.year
            )
            await self._repo.insert(
                s,
                {
                    "id": adjustment_id, "tenant_id": actor.tenant_id, "branch_id": branch_id,
                    "number": number, "doc_date": draft.doc_date, "account_dt": draft.account_dt,
                    "account_kt": draft.account_kt,
                    "amount": draft.amount, "analytics": json.dumps(draft.analytics, ensure_ascii=False),
                    "correction_of_period": draft.correction_of_period, "created_by": actor.user_id,
                    "comment": draft.comment,
                },
            )  # fmt: skip
            await self._write_registers(s, actor.tenant_id, adjustment_id, draft)
            row = await self._repo.get(s, adjustment_id)
            assert row is not None
            body = adjustment_json(row)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="ledger_adjustment.posted",
                entity=DOC_TYPE,
                entity_id=adjustment_id,
                ip=ip,
                after={k: body[k] for k in ("number", "branch_id", "doc_date", "account_dt", "account_kt",
                                            "amount", "correction_of_period", "analytics", "comment")},
            )  # fmt: skip
            stage_response(body, 201)
        return body

    async def _check_state(self, s: AsyncSession, tenant_id: UUID, d: AdjustmentDraft) -> None:
        last_closed = await self._poster.last_closed_period(s)
        if last_closed is not None and month_start(d.doc_date) <= month_start(last_closed):
            raise period_closed_error(d.doc_date)
        if d.correction_of_period is not None and (
            last_closed is None or d.correction_of_period > last_closed
        ):
            raise _invalid([Problem("correction_of_period", "validation.correction_period_not_closed")])
        counterparty = d.analytics.get("counterparty_id")
        if counterparty is not None and not await self._repo.counterparty_exists(s, UUID(counterparty)):
            raise _invalid([Problem("analytics.counterparty_id", "validation.not_found")])
        await self._check_balances(s, tenant_id, d.account_dt, d.account_kt, d.amount, counterparty, "amount")

    async def _check_balances(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        account_dt: str,
        account_kt: str,
        amount: Decimal,
        counterparty: str | None,
        field: str,
    ) -> None:
        needs = balance_needs(account_dt, account_kt, amount)
        if not needs or counterparty is None:
            return
        cp = UUID(counterparty)
        balances = await self._debts.lock(s, tenant_id, [(cp, "receivable"), (cp, "payable")])
        for need in needs:
            if need.what == "advance_6310":
                available = await self._repo.advance_6310(s, cp)
            else:
                available = Decimal(balances.get((cp, need.what), ZERO))
            if need.amount > available:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    params={"available": format(max(available, ZERO), ".2f"), "balance": need.what},
                    details=[ErrorDetail(field=field, message_key="validation.adjustment_exceeds_balance")],
                )

    async def _write_registers(
        self, s: AsyncSession, tenant_id: UUID, adjustment_id: UUID, d: AdjustmentDraft
    ) -> None:
        analytics: dict[str, Any] = {**d.analytics}
        if d.correction_of_period is not None:
            analytics["correction_of_period"] = period_label(d.correction_of_period)
        await self._poster.post(
            s,
            tenant_id,
            DOC_TYPE,
            adjustment_id,
            [LedgerLine(d.doc_date, d.branch_id, d.account_dt, d.account_kt, d.amount, analytics)],
        )
        counterparty = d.analytics.get("counterparty_id")
        effects = debt_effects(d.account_dt, d.account_kt, d.amount)
        if effects and counterparty is not None:
            await self._debts.post(
                s,
                tenant_id,
                [
                    DebtMoveInput(UUID(counterparty), e.direction, e.amount, DOC_TYPE, adjustment_id)
                    for e in effects
                ],
            )

    # --- 20 #10a --------------------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, adjustment_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        reason = reason.strip()
        if not reason:
            raise _invalid([Problem("reason", "validation.required")])
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get(s, adjustment_id, lock=True)
            if row is None or (not scope.unrestricted and row.branch_id not in scope.allowed):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": DOC_TYPE})
            if row.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED, params={"id": str(row.id)})
            # the storno consumes the opposite balances: Dt↔Kt swapped (13 §5.2)
            await self._check_balances(
                s, actor.tenant_id, row.account_kt, row.account_dt, row.amount,
                row.analytics.get("counterparty_id"), "id",
            )  # fmt: skip
            await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, row.id)
            await self._debts.reverse(s, actor.tenant_id, DOC_TYPE, row.id)
            await self._repo.mark_cancelled(s, row.id, actor.user_id, reason)
            after = await self._repo.get(s, row.id)
            assert after is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="ledger_adjustment.cancelled",
                entity=DOC_TYPE,
                entity_id=row.id,
                ip=ip,
                before={"status": row.status},
                after={"status": "cancelled", "cancel_reason": reason, "number": row.number},
            )
            body = {"id": str(row.id), "status": "cancelled", "cancelled_at": _ts(after.cancelled_at)}
            stage_response(body, 200)
        return body

    # --- 20 #10b --------------------------------------------------------------------------------------------
    async def page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        branch_id: UUID | None,
        status: str | None,
        doc_date_gte: date | None,
        doc_date_lte: date | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if doc_date_gte and doc_date_lte and doc_date_gte > doc_date_lte:
            raise _invalid([Problem("doc_date__gte", "validation.date_range")])
        if branch_id is not None:
            if not scope.unrestricted and branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            branches: tuple[UUID, ...] | None = (branch_id,)
        else:
            branches = None if scope.unrestricted else scope.allowed
        flt = AdjustmentFilter(doc_date_gte, doc_date_lte, status, branches)
        after = _decode(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.page(s, flt, after, limit + 1)
        page = rows[:limit]
        return {
            "items": [adjustment_json(r) for r in page],
            "next_cursor": _encode(page[-1].doc_date, page[-1].id) if len(rows) > limit else None,
        }
