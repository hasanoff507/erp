"""SQL for ``app.branches`` / ``app.warehouses`` (12 §2.3)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7

_DEFAULT_BRANCH = text("SELECT id FROM app.branches WHERE tenant_id = :tenant_id AND code = '01'")
_INSERT_BRANCH = text(
    "INSERT INTO app.branches (id, tenant_id, code, name, is_default, settlement_category, activity_type) "
    "VALUES (:id, :tenant_id, '01', :name, true, :settlement_category, 'retail')"
)
_INSERT_WAREHOUSE = text(
    "INSERT INTO app.warehouses (id, tenant_id, branch_id, name, type, inventory_account) "
    "VALUES (:id, :tenant_id, :branch_id, 'Asosiy ombor', 'store', '2920')"
)


async def default_branch_id(session: AsyncSession, tenant_id: UUID) -> UUID | None:
    value: UUID | None = (
        await session.execute(_DEFAULT_BRANCH, {"tenant_id": tenant_id})
    ).scalar_one_or_none()
    return value


async def insert_default_branch(
    session: AsyncSession, tenant_id: UUID, name: str, settlement_category: str
) -> UUID:
    branch_id = uuid7()
    await session.execute(
        _INSERT_BRANCH,
        {"id": branch_id, "tenant_id": tenant_id, "name": name, "settlement_category": settlement_category},
    )
    await session.execute(_INSERT_WAREHOUSE, {"id": uuid7(), "tenant_id": tenant_id, "branch_id": branch_id})
    return branch_id
