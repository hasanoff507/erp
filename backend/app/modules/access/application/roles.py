"""Roles and their permission/limit sets (20 #24–#29, US-M13-01/02/03, 15 §2, §6.1).

Changes take effect immediately: ``require_permission`` reads the live
``role_permissions`` rows of the caller's active membership on every request
(app/core/permissions.py) — nothing here is cached.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.access.application.ports import RoleRepository, RoleRow
from app.modules.access.domain.descriptions import PERMISSION_DESCRIPTIONS
from app.modules.access.domain.permissions import PERMISSIONS, LimitUnit, SystemRole
from app.modules.access.domain.roles import PermissionEntry, normalize_limit, validate_permission_set


@dataclass(frozen=True, slots=True)
class RoleView:
    id: UUID
    name: str
    is_system: bool
    version: int
    system_code: str | None = None


@dataclass(frozen=True, slots=True)
class RoleNameView:
    id: UUID
    name: str
    version: int


@dataclass(frozen=True, slots=True)
class RolePage:
    items: list[RoleView]
    total: int
    page: int
    size: int


@dataclass(frozen=True, slots=True)
class PermissionGrantView:
    code: str
    limit_value: str | None  # 4 decimals (17 §3: limit_value)


@dataclass(frozen=True, slots=True)
class RolePermissionsView:
    role_id: UUID
    permissions: list[PermissionGrantView]


@dataclass(frozen=True, slots=True)
class CatalogItem:
    code: str
    module: str
    description: str
    requires_limit: bool


def limit_str(value: Decimal | None) -> str | None:
    normalized = normalize_limit(value)
    return None if normalized is None else format(normalized, "f")


def permission_catalog() -> list[CatalogItem]:
    """15 §2.1 tenant catalog (``platform.admin`` is not a tenant permission)."""
    return [
        CatalogItem(
            code=p.code,
            module=p.modules,
            description=PERMISSION_DESCRIPTIONS.get(p.code, p.code),
            requires_limit=p.limit_unit is not LimitUnit.NONE,
        )
        for p in PERMISSIONS
        if not p.platform_only
    ]


def _view(row: RoleRow) -> RoleView:
    return RoleView(
        id=row.id, name=row.name, is_system=row.is_system, version=row.version, system_code=row.system_code
    )


def _grants(perms: dict[str, Decimal | None]) -> list[PermissionGrantView]:
    return [PermissionGrantView(code, limit_str(limit)) for code, limit in sorted(perms.items())]


def _audit_map(perms: dict[str, Decimal | None]) -> dict[str, str | None]:
    return {code: limit_str(limit) for code, limit in sorted(perms.items())}


def _not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "roles"})


class RolesService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: RoleRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def list_roles(self, actor: Principal, page: int, size: int) -> RolePage:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, total = await self._repo.list_roles(
                s, actor.tenant_id, offset=(page - 1) * size, limit=size
            )
        return RolePage([_view(r) for r in rows], total, page, size)

    async def create(self, actor: Principal, name: str, ip: str | None) -> RoleView:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._ensure_name_free(s, actor.tenant_id, name)
            role_id = uuid7()
            await self._repo.insert_role(s, actor.tenant_id, role_id, name)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="role_created",
                entity="roles",
                entity_id=role_id,
                after={"name": name},
                ip=ip,
            )
            view = RoleView(id=role_id, name=name, is_system=False, version=1)
            stage_response(asdict(view), 201)
        return view

    async def rename(
        self, actor: Principal, role_id: UUID, name: str, version: int, ip: str | None
    ) -> RoleNameView:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._live_role(s, actor.tenant_id, role_id)
            if row.is_system:
                raise AppError(ErrorCode.SYSTEM_ROLE_READONLY, params={"role_id": str(role_id)})
            if row.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": row.version})
            new_version = row.version
            if name != row.name:
                await self._ensure_name_free(s, actor.tenant_id, name, exclude_id=role_id)
                new_version = await self._repo.rename_role(s, role_id, name)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="role_updated",
                    entity="roles",
                    entity_id=role_id,
                    before={"name": row.name},
                    after={"name": name},
                    ip=ip,
                )
            view = RoleNameView(id=role_id, name=name, version=new_version)
            stage_response(asdict(view))
        return view

    async def permissions(self, actor: Principal, role_id: UUID) -> RolePermissionsView:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_role(s, actor.tenant_id, role_id)
            if row is None or row.archived_at is not None:
                raise _not_found()
            perms = await self._repo.role_permissions(s, role_id)
        return RolePermissionsView(role_id, _grants(perms))

    async def replace_permissions(
        self, actor: Principal, role_id: UUID, entries: list[PermissionEntry], ip: str | None
    ) -> RolePermissionsView:
        problems = validate_permission_set(entries)
        if problems:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field=p.field, message_key=p.message_key) for p in problems],
            )
        wanted = {e.code: normalize_limit(e.limit_value) for e in entries}
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._live_role(s, actor.tenant_id, role_id)
            if row.system_code == SystemRole.OWNER.value:
                # qaror #28: the owner is the superset of all tenant permissions, without limits
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    details=[ErrorDetail(field="permissions", message_key="validation.owner_role_readonly")],
                )
            before = await self._repo.role_permissions(s, role_id)
            if before != wanted:
                await self._repo.replace_permissions(s, actor.tenant_id, role_id, wanted)
                await self._repo.bump_version(s, role_id)
                # 15 §6.1: every permission/limit change is audited (before → after)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="role_permissions_changed",
                    entity="roles",
                    entity_id=role_id,
                    before={"permissions": _audit_map(before)},
                    after={"permissions": _audit_map(wanted)},
                    ip=ip,
                )
            view = RolePermissionsView(role_id, _grants(wanted))
            stage_response(asdict(view))
        return view

    async def _live_role(self, s: AsyncSession, tenant_id: UUID, role_id: UUID) -> RoleRow:
        row = await self._repo.get_role(s, tenant_id, role_id, for_update=True)
        if row is None:
            raise _not_found()
        if row.archived_at is not None:
            raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "roles"})
        return row

    async def _ensure_name_free(
        self, s: AsyncSession, tenant_id: UUID, name: str, *, exclude_id: UUID | None = None
    ) -> None:
        if await self._repo.name_taken(s, tenant_id, name, exclude_id=exclude_id):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="name", message_key="validation.duplicate")],
            )
