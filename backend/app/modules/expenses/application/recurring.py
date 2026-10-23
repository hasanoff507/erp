"""Recurring expenses (US-M15-02; 20 #48–#51; 12 ``recurring_expenses``).

A rule is never paid automatically: the daily cron (:meth:`RecurringService.remind_due`) records the
``recurring_expense_due`` notification once per (rule, due date) — "Ijara to'lash vaqti: 3 000 000 so'm"
(QT-M15-02) — and the owner confirms with one click (``POST /recurring-expenses/{id}/confirm``), which
creates the expense (``recurring_rule_id``) and posts it under the same limit rule as ``/expenses/{id}/post``
(``202`` + ``expense_over_limit`` request when over the confirmer's ``expenses.approve`` limit). The rule then
moves ``next_due_date`` one period ahead. Confirmation is only possible once the rule is due.

``6410`` categories (tax payments — ``tax_type`` mandatory, amounts vary) are not accepted in a rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.accounting.wiring import business_today
from app.modules.expenses.application.expenses import (
    ExpenseInput,
    ExpenseService,
    check_branch,
    default_branch,
    invalid,
    m2,
    scope_branches,
    ts,
)
from app.modules.expenses.application.ports import ExpenseStore, RuleRow
from app.modules.expenses.domain.expenses import (
    TAX_ACCOUNT,
    add_period,
    first_due_date,
    reminder_text,
    roll_forward,
)

EVENT_KIND = "recurring_expense_due"


def rule_json(row: RuleRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "branch_id": str(row.branch_id),
        "category_id": str(row.category_id),
        "amount": m2(row.amount),
        "period": row.period,
        "day_of_month": row.day_of_month,
        "source": row.source,
        "cash_register_id": None if row.cash_register_id is None else str(row.cash_register_id),
        "next_due_date": row.next_due_date.isoformat(),
        "last_triggered_at": ts(row.last_triggered_at),
        "is_active": row.is_active,
        "is_due": row.is_active and row.next_due_date <= business_today(),
        "version": row.version,
    }


class RecurringService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: ExpenseStore,
        expenses: ExpenseService,
        notifications: Any | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._expenses = expenses
        self._notify = notifications

    async def list_page(
        self, actor: Principal, scope: BranchScope, *, is_active: bool | None, page: int, size: int
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, total = await self._repo.list_rules(
                s, scope_branches(scope), is_active, (page - 1) * size, size
            )
        return {"items": [rule_json(r) for r in rows], "total": total, "page": page, "size": size}

    async def create(
        self, actor: Principal, scope: BranchScope, body: Mapping[str, Any], ip: str | None
    ) -> dict[str, Any]:
        branch_id = default_branch(scope, body.get("branch_id"))
        source = body["source"]
        register_id: UUID | None = body.get("cash_register_id")
        if source == "cash" and register_id is None:
            raise invalid("cash_register_id", "validation.required")
        if source != "cash" and register_id is not None:
            raise invalid("cash_register_id", "validation.must_be_null")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._check_category(s, body["category_id"])
            if register_id is not None:
                register_branch = await self._repo.register_branch(s, register_id)
                if register_branch is None:
                    raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cash_register"})
                if register_branch != branch_id:
                    raise invalid("cash_register_id", "validation.cash_register_not_in_branch")
            rule_id = uuid7()
            day = int(body["day_of_month"])
            await self._repo.insert_rule(
                s,
                {
                    "id": rule_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "category_id": body["category_id"],
                    "name": body.get("name"),
                    "amount": Decimal(body["amount"]),
                    "period": body["period"],
                    "day_of_month": day,
                    "source": source,
                    "cash_register_id": register_id,
                    "next_due_date": first_due_date(business_today(), day),
                    "created_by": actor.user_id,
                },
            )
            row = await self._repo.get_rule(s, rule_id)
            assert row is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="recurring_expense.created",
                entity="recurring_expenses",
                entity_id=rule_id,
                ip=ip,
                device_id=actor.device_id,
                after={"amount": m2(row.amount), "period": row.period, "day_of_month": day, "source": source},
            )
            out = rule_json(row)
            stage_response(out, 201)
        return out

    async def update(
        self,
        actor: Principal,
        scope: BranchScope,
        rule_id: UUID,
        version: int,
        changes: Mapping[str, Any],
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get_rule(s, rule_id, lock=True)
            if current is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "recurring_expense"})
            check_branch(scope, current.branch_id, "recurring_expense")
            if current.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            patch: dict[str, Any] = {}
            if "name" in changes:
                patch["name"] = changes["name"]
            if "amount" in changes:
                patch["amount"] = Decimal(changes["amount"])
            day = current.day_of_month
            due = current.next_due_date
            if "day_of_month" in changes:
                day = int(changes["day_of_month"])
                patch["day_of_month"] = day
                due = due.replace(day=day)  # same period; a due payment is never skipped
            if "is_active" in changes:
                patch["is_active"] = bool(changes["is_active"])
                if patch["is_active"] and not current.is_active:
                    # re-activated: no stale reminders for the paused periods
                    due = roll_forward(due, current.period, day, business_today())
            if due != current.next_due_date:
                patch["next_due_date"] = due
            if patch and not await self._repo.update_rule(s, rule_id, version, patch):
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            row = await self._repo.get_rule(s, rule_id)
            assert row is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="recurring_expense.updated",
                entity="recurring_expenses",
                entity_id=rule_id,
                ip=ip,
                device_id=actor.device_id,
                before={
                    "amount": m2(current.amount),
                    "day_of_month": current.day_of_month,
                    "is_active": current.is_active,
                },
                after={k: (m2(v) if isinstance(v, Decimal) else str(v)) for k, v in patch.items()},
            )
            out = rule_json(row)
            stage_response(out, 200)
        return out

    async def confirm(
        self,
        actor: Principal,
        scope: BranchScope,
        rule_id: UUID,
        amount_override: Decimal | None,
        ip: str | None,
    ) -> tuple[dict[str, Any], int]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rule = await self._repo.get_rule(s, rule_id, lock=True)
            if rule is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "recurring_expense"})
            check_branch(scope, rule.branch_id, "recurring_expense")
            if not rule.is_active:
                raise invalid("id", "validation.recurring_expense_inactive")
            today = business_today()
            if rule.next_due_date > today:
                raise invalid("id", "validation.recurring_expense_not_due")
            shift_id: UUID | None = None
            if rule.source == "cash":
                assert rule.cash_register_id is not None
                shift = await self._repo.open_shift_of_register(s, rule.cash_register_id)
                if shift is None:
                    raise AppError(
                        ErrorCode.SHIFT_NOT_OPEN, params={"cash_register_id": str(rule.cash_register_id)}
                    )
                shift_id = shift.id
            amount = amount_override if amount_override is not None else rule.amount
            expense_id = await self._expenses.insert_draft(
                s,
                actor.tenant_id,
                actor.user_id,
                ExpenseInput(
                    doc_date=today,
                    category_id=rule.category_id,
                    amount=amount,
                    source=rule.source,
                    cash_register_id=rule.cash_register_id,
                    shift_id=shift_id,
                    comment=rule.name,
                    recurring_rule_id=rule.id,
                ),
                rule.branch_id,
            )
            row = await self._repo.get_expense(s, expense_id, lock=True)
            assert row is not None
            outcome = await self._expenses.post_draft(
                s, actor.tenant_id, actor.user_id, row, ip, actor.device_id
            )
            next_due = add_period(rule.next_due_date, rule.period, rule.day_of_month)
            await self._repo.update_rule(s, rule.id, rule.version, {"next_due_date": next_due})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="recurring_expense.confirmed",
                entity="recurring_expenses",
                entity_id=rule.id,
                ip=ip,
                device_id=actor.device_id,
                after={
                    "expense_id": str(expense_id),
                    "amount": m2(amount),
                    "due_date": rule.next_due_date.isoformat(),
                    "next_due_date": next_due.isoformat(),
                },
            )
            body: dict[str, Any] = {"expense_id": str(expense_id), "status": outcome.body["status"]}
            status = 201
            if outcome.status == 202:
                body["approval_request_id"] = outcome.body["approval_request_id"]
                status = 202
            stage_response(body, status)
        return body, status

    async def remind_due(self, tenant_id: UUID) -> int:
        """Daily cron: one ``recurring_expense_due`` event per (rule, due date); returns new events."""
        if self._notify is None:
            return 0
        recorded = 0
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            for rule in await self._repo.due_rules(s, business_today()):
                category = await self._repo.get_category(s, rule.category_id)
                label = rule.name or (category.name if category is not None else "Xarajat")
                new = await self._notify.record_event(
                    s,
                    tenant_id,
                    EVENT_KIND,
                    {
                        "recurring_expense_id": str(rule.id),
                        "branch_id": str(rule.branch_id),
                        "category_id": str(rule.category_id),
                        "name": label,
                        "amount": m2(rule.amount),
                        "due_date": rule.next_due_date.isoformat(),
                        "source": rule.source,
                        "text": reminder_text(label, rule.amount),
                    },
                    f"{EVENT_KIND}:{rule.id}:{rule.next_due_date.isoformat()}",
                )
                if new:
                    await self._repo.mark_rule_triggered(s, rule.id)
                    recorded += 1
        return recorded

    async def _check_category(self, s: AsyncSession, category_id: UUID) -> None:
        category = await self._repo.get_category(s, category_id)
        if category is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "expense_category"})
        if category.archived_at is not None:
            raise invalid("category_id", "validation.archived")
        if category.default_account == TAX_ACCOUNT:
            raise invalid("category_id", "validation.not_allowed")
