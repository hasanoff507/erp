"""SQL for roles / role_permissions (12 §2.3). Runs inside the caller's tenant transaction."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7

_INSERT_ROLE = text(
    "INSERT INTO app.roles (id, tenant_id, name, is_system, system_code) "
    "VALUES (:id, :tenant_id, :name, true, :system_code) "
    "ON CONFLICT (tenant_id, name) DO NOTHING"
)
_ROLE_ID = text("SELECT id FROM app.roles WHERE tenant_id = :tenant_id AND system_code = :system_code")
_INSERT_PERMISSION = text(
    "INSERT INTO app.role_permissions (id, tenant_id, role_id, permission_code, limit_value) "
    "VALUES (:id, :tenant_id, :role_id, :code, :limit_value) "
    "ON CONFLICT (role_id, permission_code) DO NOTHING"
)


async def upsert_system_role(session: AsyncSession, tenant_id: UUID, system_code: str, name: str) -> UUID:
    await session.execute(
        _INSERT_ROLE, {"id": uuid7(), "tenant_id": tenant_id, "name": name, "system_code": system_code}
    )
    role_id: UUID = (
        await session.execute(_ROLE_ID, {"tenant_id": tenant_id, "system_code": system_code})
    ).scalar_one()
    return role_id


async def grant_permissions(
    session: AsyncSession, tenant_id: UUID, role_id: UUID, permissions: dict[str, Decimal | None]
) -> None:
    rows = [
        {"id": uuid7(), "tenant_id": tenant_id, "role_id": role_id, "code": code, "limit_value": limit}
        for code, limit in sorted(permissions.items())
    ]
    if rows:
        await session.execute(_INSERT_PERMISSION, rows)
