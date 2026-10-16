"""Branch services."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.infrastructure import repositories

SettlementCategory = Literal["city_100k_plus", "other", "remote_mountain"]


async def ensure_default_branch(
    session: AsyncSession, tenant_id: UUID, name: str, settlement_category: SettlementCategory
) -> UUID:
    """Default branch ``01`` with its store-room warehouse (2920), 12 §5.2; idempotent."""
    existing = await repositories.default_branch_id(session, tenant_id)
    if existing is not None:
        return existing
    return await repositories.insert_default_branch(session, tenant_id, name, settlement_category)
