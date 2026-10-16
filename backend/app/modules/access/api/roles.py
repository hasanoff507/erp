"""``/roles``, ``/roles/{id}/permissions``, ``/permissions-catalog`` (20 #24–#29, BO-11 "Rollar")."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import PermissionGrant, require_permission
from app.modules.access.api.deps import access_module, client_ip
from app.modules.access.application.roles import permission_catalog
from app.modules.access.domain.roles import ROLE_NAME_MAX, ROLE_NAME_MIN, PermissionEntry

router = APIRouter(tags=["access"])

SettingsUsers = Annotated[PermissionGrant, Depends(require_permission("settings.users"))]
Actor = Annotated[Principal, Depends(require_subscription_ok)]
RoleName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=ROLE_NAME_MIN, max_length=ROLE_NAME_MAX)
]
# limit_value: non-negative decimal string, ≤ 4 decimals (17 §3, NUMERIC(18,4))
LimitValue = Annotated[str, StringConstraints(pattern=r"^\d{1,14}(\.\d{1,4})?$")]


class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleName


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleName
    version: int


SystemRoleCode = Literal["owner", "manager", "cashier", "storekeeper", "accountant"]


class RoleOut(BaseModel):
    id: UUID
    name: str
    is_system: bool
    # 20 #24: identify system roles by code, never by their (renamable-in-future) Uzbek name
    system_code: SystemRoleCode | None = None
    version: int


class RoleNameOut(BaseModel):
    id: UUID
    name: str
    version: int


class RolePageOut(BaseModel):
    items: list[RoleOut]
    total: int
    page: int
    size: int


class PermissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    limit_value: LimitValue | None = None


class RolePermissionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: list[PermissionIn] = Field(max_length=200)


class PermissionOut(BaseModel):
    code: str
    limit_value: str | None


class RolePermissionsOut(BaseModel):
    role_id: UUID
    permissions: list[PermissionOut]


class CatalogItemOut(BaseModel):
    code: str
    module: str
    description: str
    requires_limit: bool


class CatalogOut(BaseModel):
    items: list[CatalogItemOut]


@router.get("/roles", operation_id="roles_list", response_model=RolePageOut)
async def list_roles(
    request: Request,
    _: SettingsUsers,
    actor: Actor,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RolePageOut:
    result = await access_module(request).roles.list_roles(actor, page, size)
    return RolePageOut.model_validate(asdict(result))


@router.post("/roles", operation_id="roles_create", status_code=201, response_model=RoleOut)
async def create_role(
    request: Request, response: Response, body: RoleCreate, _: SettingsUsers, actor: Actor
) -> RoleOut:
    view = await access_module(request).roles.create(actor, body.name, client_ip(request))
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{view.id}"
    return RoleOut.model_validate(asdict(view))


@router.patch("/roles/{role_id}", operation_id="roles_update", response_model=RoleNameOut)
async def update_role(
    request: Request, role_id: UUID, body: RoleUpdate, _: SettingsUsers, actor: Actor
) -> RoleNameOut:
    view = await access_module(request).roles.rename(
        actor, role_id, body.name, body.version, client_ip(request)
    )
    return RoleNameOut.model_validate(asdict(view))


@router.get(
    "/roles/{role_id}/permissions", operation_id="roles_permissions_get", response_model=RolePermissionsOut
)
async def get_role_permissions(
    request: Request, role_id: UUID, _: SettingsUsers, actor: Actor
) -> RolePermissionsOut:
    view = await access_module(request).roles.permissions(actor, role_id)
    return RolePermissionsOut.model_validate(asdict(view))


@router.put(
    "/roles/{role_id}/permissions",
    operation_id="roles_permissions_replace",
    response_model=RolePermissionsOut,
)
async def replace_role_permissions(
    request: Request, role_id: UUID, body: RolePermissionsIn, _: SettingsUsers, actor: Actor
) -> RolePermissionsOut:
    entries = [
        PermissionEntry(p.code, None if p.limit_value is None else Decimal(p.limit_value))
        for p in body.permissions
    ]
    view = await access_module(request).roles.replace_permissions(actor, role_id, entries, client_ip(request))
    return RolePermissionsOut.model_validate(asdict(view))


@router.get("/permissions-catalog", operation_id="permissions_catalog_list", response_model=CatalogOut)
async def get_permissions_catalog(_: SettingsUsers) -> CatalogOut:
    return CatalogOut(items=[CatalogItemOut.model_validate(asdict(item)) for item in permission_catalog()])
