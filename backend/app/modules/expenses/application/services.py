"""Expense category services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.application.ports import ExpenseCategoryStore
from app.modules.expenses.domain.categories import DEFAULT_EXPENSE_CATEGORIES


async def create_default_categories(
    store: ExpenseCategoryStore, session: AsyncSession, tenant_id: UUID
) -> None:
    """The 21 standard categories (13 §2.17); idempotent."""
    await store.insert_system_categories(session, tenant_id, DEFAULT_EXPENSE_CATEGORIES)
