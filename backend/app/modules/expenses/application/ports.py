"""Ports of the expenses application layer (23 §1)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.domain.categories import ExpenseCategoryTemplate


class ExpenseCategoryStore(Protocol):
    async def insert_system_categories(
        self, session: AsyncSession, tenant_id: UUID, categories: Iterable[ExpenseCategoryTemplate]
    ) -> None: ...
