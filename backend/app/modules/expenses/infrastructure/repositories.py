"""SQL for ``app.expense_categories`` (12 §2.6)."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.expenses.domain.categories import ExpenseCategoryTemplate

_INSERT = text(
    "INSERT INTO app.expense_categories (id, tenant_id, code, name, default_account, source_ref, is_system) "
    "VALUES (:id, :tenant_id, :code, :name, :default_account, :source_ref, true) "
    "ON CONFLICT DO NOTHING"
)


async def insert_system_categories(
    session: AsyncSession, tenant_id: UUID, categories: Iterable[ExpenseCategoryTemplate]
) -> None:
    rows = [
        {
            "id": uuid7(),
            "tenant_id": tenant_id,
            "code": c.code,
            "name": c.name,
            "default_account": c.default_account,
            "source_ref": c.source_ref,
        }
        for c in categories
    ]
    if rows:
        await session.execute(_INSERT, rows)
