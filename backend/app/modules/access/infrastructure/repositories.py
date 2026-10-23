"""SQL for roles / role_permissions (12 §2.3). Runs inside the caller's tenant transaction."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.access.application.ports import RoleRow

_INSERT_SYSTEM_ROLE = text(
    "INSERT INTO app.roles (id, tenant_id, name, is_system, system_code) "
    "VALUES (:id, :tenant_id, :name, true, :system_code) "
    "ON CONFLICT (tenant_id, name) DO NOTHING"
)
_SYSTEM_ROLE_ID = text("SELECT id FROM app.roles WHERE tenant_id = :tenant_id AND system_code = :system_code")
_INSERT_PERMISSION = text(
    "INSERT INTO app.role_permissions (id, tenant_id, role_id, permission_code, limit_value) "
    "VALUES (:id, :tenant_id, :role_id, :code, :limit_value) "
    "ON CONFLICT (role_id, permission_code) DO NOTHING"
)
_UPSERT_PERMISSION = text(
    "INSERT INTO app.role_permissions (id, tenant_id, role_id, permission_code, limit_value) "
    "VALUES (:id, :tenant_id, :role_id, :code, :limit_value) "
    "ON CONFLICT (role_id, permission_code) DO UPDATE "
    "SET limit_value = EXCLUDED.limit_value, updated_at = now() "
    "WHERE app.role_permissions.limit_value IS DISTINCT FROM EXCLUDED.limit_value"
)
_DELETE_OTHER_PERMISSIONS = text(
    "DELETE FROM app.role_permissions WHERE tenant_id = :tenant_id AND role_id = :role_id "
    "AND NOT (permission_code = ANY(CAST(:codes AS text[])))"
)
_ROLE_COLUMNS = "id, name, is_system, system_code, version, archived_at"
# system roles first in 15 §2.2 order, then custom roles by name
_LIST_ROLES = text(
    f"SELECT {_ROLE_COLUMNS}, count(*) OVER () AS total FROM app.roles "  # noqa: S608
    "WHERE tenant_id = :tenant_id AND archived_at IS NULL "
    "ORDER BY is_system DESC, "
    "array_position(ARRAY['owner','manager','cashier','storekeeper','accountant'], system_code), "
    "lower(name), id OFFSET :offset LIMIT :limit"
)
_COUNT_ROLES = text("SELECT count(*) FROM app.roles WHERE tenant_id = :tenant_id AND archived_at IS NULL")
_GET_ROLE = text(f"SELECT {_ROLE_COLUMNS} FROM app.roles WHERE tenant_id = :tenant_id AND id = :id")  # noqa: S608
_GET_ROLE_FOR_UPDATE = text(
    f"SELECT {_ROLE_COLUMNS} FROM app.roles WHERE tenant_id = :tenant_id AND id = :id FOR UPDATE"  # noqa: S608
)
_NAME_TAKEN = text(
    "SELECT 1 FROM app.roles WHERE tenant_id = :tenant_id AND lower(name) = lower(:name) "
    "AND (CAST(:exclude_id AS uuid) IS NULL OR id <> CAST(:exclude_id AS uuid)) LIMIT 1"
)
_INSERT_ROLE = text(
    "INSERT INTO app.roles (id, tenant_id, name, is_system) VALUES (:id, :tenant_id, :name, false)"
)
_RENAME_ROLE = text(
    "UPDATE app.roles SET name = :name, version = version + 1, updated_at = now() WHERE id = :id "
    "RETURNING version"
)
_BUMP_ROLE = text(
    "UPDATE app.roles SET version = version + 1, updated_at = now() WHERE id = :id RETURNING version"
)
_ROLE_PERMISSIONS = text(
    "SELECT permission_code, limit_value FROM app.role_permissions WHERE role_id = :role_id"
)


def _role(row: Any) -> RoleRow:
    return RoleRow(
        id=row.id,
        name=row.name,
        is_system=row.is_system,
        system_code=row.system_code,
        version=row.version,
        archived_at=row.archived_at,
    )


def _rows(tenant_id: UUID, role_id: UUID, permissions: dict[str, Decimal | None]) -> list[dict[str, Any]]:
    return [
        {"id": uuid7(), "tenant_id": tenant_id, "role_id": role_id, "code": code, "limit_value": limit}
        for code, limit in sorted(permissions.items())
    ]


class SqlRoleRepository:
    """:class:`app.modules.access.application.ports.RoleRepository` over ``app.roles``."""

    async def upsert_system_role(
        self, session: AsyncSession, tenant_id: UUID, system_code: str, name: str
    ) -> UUID:
        await session.execute(
            _INSERT_SYSTEM_ROLE,
            {"id": uuid7(), "tenant_id": tenant_id, "name": name, "system_code": system_code},
        )
        role_id: UUID = (
            await session.execute(_SYSTEM_ROLE_ID, {"tenant_id": tenant_id, "system_code": system_code})
        ).scalar_one()
        return role_id

    async def grant_permissions(
        self, session: AsyncSession, tenant_id: UUID, role_id: UUID, permissions: dict[str, Decimal | None]
    ) -> None:
        rows = _rows(tenant_id, role_id, permissions)
        if rows:
            await session.execute(_INSERT_PERMISSION, rows)

    async def list_roles(
        self, session: AsyncSession, tenant_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[RoleRow], int]:
        rows = (
            await session.execute(_LIST_ROLES, {"tenant_id": tenant_id, "offset": offset, "limit": limit})
        ).all()
        if rows:
            return [_role(r) for r in rows], int(rows[0].total)
        total = (await session.execute(_COUNT_ROLES, {"tenant_id": tenant_id})).scalar_one()
        return [], int(total)

    async def get_role(
        self, session: AsyncSession, tenant_id: UUID, role_id: UUID, *, for_update: bool = False
    ) -> RoleRow | None:
        stmt = _GET_ROLE_FOR_UPDATE if for_update else _GET_ROLE
        row = (await session.execute(stmt, {"tenant_id": tenant_id, "id": role_id})).first()
        return None if row is None else _role(row)

    async def name_taken(
        self, session: AsyncSession, tenant_id: UUID, name: str, *, exclude_id: UUID | None = None
    ) -> bool:
        params = {"tenant_id": tenant_id, "name": name, "exclude_id": exclude_id}
        return (await session.execute(_NAME_TAKEN, params)).first() is not None

    async def insert_role(self, session: AsyncSession, tenant_id: UUID, role_id: UUID, name: str) -> None:
        await session.execute(_INSERT_ROLE, {"id": role_id, "tenant_id": tenant_id, "name": name})

    async def rename_role(self, session: AsyncSession, role_id: UUID, name: str) -> int:
        version: int = (await session.execute(_RENAME_ROLE, {"id": role_id, "name": name})).scalar_one()
        return version

    async def bump_version(self, session: AsyncSession, role_id: UUID) -> int:
        version: int = (await session.execute(_BUMP_ROLE, {"id": role_id})).scalar_one()
        return version

    async def role_permissions(self, session: AsyncSession, role_id: UUID) -> dict[str, Decimal | None]:
        rows = (await session.execute(_ROLE_PERMISSIONS, {"role_id": role_id})).all()
        return {r.permission_code: r.limit_value for r in rows}

    async def replace_permissions(
        self, session: AsyncSession, tenant_id: UUID, role_id: UUID, permissions: dict[str, Decimal | None]
    ) -> None:
        await session.execute(
            _DELETE_OTHER_PERMISSIONS,
            {"tenant_id": tenant_id, "role_id": role_id, "codes": sorted(permissions)},
        )
        rows = _rows(tenant_id, role_id, permissions)
        if rows:
            await session.execute(_UPSERT_PERMISSION, rows)
