"""Public entry points of the expenses module (23 §1 ``wiring.py``).

Other modules (signup provisioning, seed) import **only** from here — never
from ``expenses.infrastructure``. Signatures are a cross-module contract.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.application import services
from app.modules.expenses.infrastructure.repositories import ExpenseCategoryRepository

__all__ = ["create_default_categories"]

_STORE = ExpenseCategoryRepository()


async def create_default_categories(session: AsyncSession, tenant_id: UUID) -> None:
    """The 21 standard expense categories of a new tenant (13 §2.17, 12 §5.2); idempotent."""
    await services.create_default_categories(_STORE, session, tenant_id)
