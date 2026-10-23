"""Public entry points of the expenses module (23 §1 ``wiring.py``).

Other modules (signup provisioning, seed, sync, approvals) import **only** from here — never
from ``expenses.infrastructure``. Signatures are a cross-module contract:

* :func:`create_default_categories` — the 21 standard categories of a new tenant (provisioning);
* :func:`build_expenses_module` → REST services on ``app.state.expenses``;
* :func:`sync_handlers` → ``expense.created`` (collected by the sync module, PLAN contract 1);
* :func:`approval_hook` → the BO-16 ``linked_doc_type='expenses'`` hook (approving an
  ``expense_over_limit`` request posts the draft in the approve transaction);
* :func:`remind_recurring` — daily reminder job of one tenant (US-M15-02).

``auth.wiring`` imports this module and ``cash.wiring`` imports ``auth.wiring``, so the service composition
(:mod:`app.modules.expenses.composition`, which needs ``cash.wiring``) is loaded by name on first use — the
same technique the sync module uses to collect handlers.
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable, Mapping
from types import ModuleType
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.expenses.application import services
from app.modules.expenses.infrastructure.repositories import ExpenseCategoryRepository

if TYPE_CHECKING:
    from app.modules.expenses.application.module import ExpensesModule

__all__ = [
    "REMIND_JOB",
    "approval_hook",
    "build_expenses_module",
    "create_default_categories",
    "remind_recurring",
    "sync_handlers",
]

_STORE = ExpenseCategoryRepository()
_COMPOSITION: Final = "app.modules.expenses.composition"
REMIND_JOB: Final = "expenses_recurring_remind"

HookFn = Callable[[AsyncSession, Any, str, UUID], Awaitable[None]]


def _composition() -> ModuleType:
    return importlib.import_module(_COMPOSITION)


async def create_default_categories(session: AsyncSession, tenant_id: UUID) -> None:
    """The 21 standard expense categories of a new tenant (13 §2.17, 12 §5.2); idempotent."""
    await services.create_default_categories(_STORE, session, tenant_id)


def build_expenses_module(settings: Settings, db: Database) -> ExpensesModule:
    module: ExpensesModule = _composition().build_expenses_module(settings, db)
    return module


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, Any]:
    handlers: Mapping[str, Any] = _composition().sync_handlers(settings, db)
    return handlers


def approval_hook(settings: Settings, db: Database) -> HookFn:
    """``hooks['expenses']`` of the BO-16 queue: ``approved`` posts the linked draft (request consumed)."""
    hook: HookFn = _composition().approval_hook(settings, db)
    return hook


async def remind_recurring(db: Database, tenant_id: UUID) -> int:
    """Daily: ``recurring_expense_due`` events for due rules of one tenant (QT-M15-02)."""
    count: int = await _composition().remind_recurring(db, tenant_id)
    return count
