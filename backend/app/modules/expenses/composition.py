"""Composition of the expenses services (heavy imports: access, accounting, cash, notifications).

Kept apart from :mod:`app.modules.expenses.wiring` because ``auth.wiring`` (signup provisioning) imports
``expenses.wiring`` and ``cash.wiring`` imports ``auth.wiring`` — importing the cash/access composition from
``expenses.wiring`` would close an import cycle. ``expenses.wiring`` exposes thin entry points that load
this module on first use.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db.session import Database, session_tenant_id
from app.modules.access.wiring import approval_gate, permission_grants
from app.modules.accounting.wiring import ledger_poster
from app.modules.cash.wiring import shift_guard
from app.modules.expenses.application.categories import CategoryService
from app.modules.expenses.application.expenses import ExpenseService
from app.modules.expenses.application.module import ExpensesModule
from app.modules.expenses.application.recurring import RecurringService
from app.modules.expenses.application.sync_events import ExpenseSyncHandlers
from app.modules.expenses.infrastructure.repositories import SqlExpenseRepository
from app.modules.notifications.wiring import event_recorder


def _repo() -> SqlExpenseRepository:
    return SqlExpenseRepository(permission_grants())


def _expense_service(settings: Settings | None, db: Database) -> ExpenseService:
    ttl = getattr(settings, "approval_ttl_minutes", None)
    kwargs: dict[str, Any] = {} if ttl is None else {"approval_ttl_minutes": ttl}
    return ExpenseService(
        db.session_factory,
        _repo(),
        ledger_poster(),
        approval_gate(),
        shift_guard(),
        event_recorder(),
        **kwargs,
    )


def build_expenses_module(settings: Settings, db: Database) -> ExpensesModule:
    repo = _repo()
    expenses = _expense_service(settings, db)
    return ExpensesModule(
        expenses=expenses,
        categories=CategoryService(db.session_factory, repo),
        recurring=RecurringService(db.session_factory, repo, expenses, event_recorder()),
    )


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, Any]:
    handlers = ExpenseSyncHandlers(_expense_service(settings, db))
    return {"expense.created": handlers.expense_created}


def approval_hook(
    settings: Settings, db: Database
) -> Callable[[AsyncSession, Any, str, UUID], Awaitable[None]]:
    expenses = _expense_service(settings, db)

    async def hook(s: AsyncSession, row: Any, decision: str, user_id: UUID) -> None:
        tenant_id = session_tenant_id(s)
        if decision == "approved" and row.linked_doc_id is not None and tenant_id is not None:
            await expenses.post_approved(s, tenant_id, row.linked_doc_id, row.id, user_id)

    return hook


async def remind_recurring(db: Database, tenant_id: UUID) -> int:
    expenses = _expense_service(None, db)
    recurring = RecurringService(db.session_factory, _repo(), expenses, event_recorder())
    return await recurring.remind_due(tenant_id)
