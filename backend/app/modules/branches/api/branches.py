"""``/branches``, ``/branches/{id}/tax-settings``, ``/warehouses`` (20 #30–#35, #37, #37a; BO-12)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.permissions import PermissionGrant, require_permission
from app.modules.branches.api.deps import Actor, Page, Scope, Size, branches_module, client_ip
from app.modules.branches.application.branches import BranchInput, BranchPatch
from app.modules.branches.domain.model import (
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_SETTLEMENT_CATEGORY,
    DEFAULT_WAREHOUSE_TYPE,
    ActivityType,
    InventoryAccount,
    SettlementCategory,
    WarehouseType,
)
from app.modules.branches.domain.tax import TaxSetting

router = APIRouter(tags=["branches"])

SettingsBranches = Annotated[PermissionGrant, Depends(require_permission("settings.branches"))]
BranchName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
BranchCode = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{1,4}$")]
WarehouseName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WarehouseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: WarehouseType = DEFAULT_WAREHOUSE_TYPE


class BranchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: BranchName
    address: Address | None = None
    code: BranchCode | None = None
    # US-M14-04: omitted → city_100k_plus (4%, the most conservative); the UI shows the "verify" hint
    settlement_category: SettlementCategory | None = None
    activity_type: ActivityType | None = None
    warehouse: WarehouseIn | None = None


class BranchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: BranchName | None = None
    address: Address | None = None
    settlement_category: SettlementCategory | None = None
    activity_type: ActivityType | None = None
    version: int


class TaxSettingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_from: date
    settlement_category: SettlementCategory
    activity_type: ActivityType


class WarehouseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_account: InventoryAccount | None = None
    name: WarehouseName | None = None
    version: int


class BranchListItemOut(BaseModel):
    id: UUID
    name: str
    code: str
    address: str | None
    is_default: bool
    settlement_category: SettlementCategory
    activity_type: ActivityType
    version: int


class BranchPageOut(BaseModel):
    items: list[BranchListItemOut]
    total: int
    page: int
    size: int


class WarehouseBriefOut(BaseModel):
    id: UUID
    type: WarehouseType
    inventory_account: InventoryAccount


class BranchCreatedOut(BaseModel):
    id: UUID
    name: str
    address: str | None
    code: str
    settlement_category: SettlementCategory
    activity_type: ActivityType
    version: int
    warehouse: WarehouseBriefOut


class BranchDetailOut(BaseModel):
    id: UUID
    name: str
    address: str | None
    is_default: bool
    settlement_category: SettlementCategory
    activity_type: ActivityType
    version: int
    today_sales: str = Field(description="Bugungi o'tkazilgan savdo, pul satri")
    stock_value: str = Field(description="Filial omborlaridagi qoldiq qiymati, pul satri")


class BranchUpdatedOut(BaseModel):
    id: UUID
    name: str
    address: str | None
    settlement_category: SettlementCategory
    activity_type: ActivityType
    version: int


class TaxSettingOut(BaseModel):
    valid_from: date
    settlement_category: SettlementCategory
    activity_type: ActivityType


class TaxSettingPageOut(BaseModel):
    items: list[TaxSettingOut]
    total: int
    page: int
    size: int


class TaxSettingCreatedOut(BaseModel):
    branch_id: UUID
    valid_from: date
    settlement_category: SettlementCategory
    activity_type: ActivityType


class WarehouseOut(BaseModel):
    id: UUID
    branch_id: UUID
    name: str
    type: WarehouseType
    inventory_account: InventoryAccount
    version: int


class WarehouseListOut(BaseModel):
    items: list[WarehouseOut]


class WarehouseUpdatedOut(BaseModel):
    id: UUID
    name: str
    type: WarehouseType
    inventory_account: InventoryAccount
    version: int


# --- branches ---------------------------------------------------------------------------------------


@router.get("/branches", operation_id="branches_list_branches", response_model=BranchPageOut)
async def list_branches(
    request: Request, actor: Actor, scope: Scope, page: Page = 1, size: Size = 50
) -> BranchPageOut:
    result = await branches_module(request).branches.list_branches(actor, scope.allowed, page, size)
    return BranchPageOut.model_validate(asdict(result))


@router.post(
    "/branches", operation_id="branches_create_branch", status_code=201, response_model=BranchCreatedOut
)
async def create_branch(
    request: Request, response: Response, body: BranchCreate, _: SettingsBranches, actor: Actor
) -> BranchCreatedOut:
    data = BranchInput(
        name=body.name,
        address=body.address or None,
        code=body.code,
        settlement_category=body.settlement_category or DEFAULT_SETTLEMENT_CATEGORY,
        activity_type=body.activity_type or DEFAULT_ACTIVITY_TYPE,
        warehouse_type=body.warehouse.type if body.warehouse else DEFAULT_WAREHOUSE_TYPE,
    )
    result = await branches_module(request).branches.create(actor, data, client_ip(request))
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{result.id}"
    return BranchCreatedOut.model_validate(asdict(result))


@router.get("/branches/{branch_id}", operation_id="branches_get_branch", response_model=BranchDetailOut)
async def get_branch(request: Request, branch_id: UUID, actor: Actor, scope: Scope) -> BranchDetailOut:
    result = await branches_module(request).branches.get(actor, scope.allowed, branch_id)
    return BranchDetailOut.model_validate(asdict(result))


@router.patch("/branches/{branch_id}", operation_id="branches_update_branch", response_model=BranchUpdatedOut)
async def update_branch(
    request: Request, branch_id: UUID, body: BranchUpdate, _: SettingsBranches, actor: Actor, scope: Scope
) -> BranchUpdatedOut:
    patch = BranchPatch(
        version=body.version,
        name=body.name,
        address=body.address or None,
        address_set="address" in body.model_fields_set,
        settlement_category=body.settlement_category,
        activity_type=body.activity_type,
    )
    result = await branches_module(request).branches.update(
        actor, scope.allowed, branch_id, patch, client_ip(request)
    )
    return BranchUpdatedOut.model_validate(asdict(result))


@router.get(
    "/branches/{branch_id}/tax-settings",
    operation_id="branch_tax_settings_list",
    response_model=TaxSettingPageOut,
)
async def list_tax_settings(
    request: Request, branch_id: UUID, actor: Actor, scope: Scope, page: Page = 1, size: Size = 50
) -> TaxSettingPageOut:
    result = await branches_module(request).branches.tax_settings(actor, scope.allowed, branch_id, page, size)
    return TaxSettingPageOut.model_validate(asdict(result))


@router.post(
    "/branches/{branch_id}/tax-settings",
    operation_id="branch_tax_settings_create",
    status_code=201,
    response_model=TaxSettingCreatedOut,
)
async def create_tax_setting(
    request: Request, branch_id: UUID, body: TaxSettingIn, _: SettingsBranches, actor: Actor, scope: Scope
) -> TaxSettingCreatedOut:
    setting = TaxSetting(body.valid_from, body.settlement_category, body.activity_type)
    result = await branches_module(request).branches.add_tax_setting(
        actor, scope.allowed, branch_id, setting, client_ip(request)
    )
    return TaxSettingCreatedOut.model_validate(asdict(result))


# --- warehouses -------------------------------------------------------------------------------------


@router.get("/warehouses", operation_id="warehouses_list", response_model=WarehouseListOut)
async def list_warehouses(
    request: Request, actor: Actor, scope: Scope, branch_id: UUID | None = None
) -> WarehouseListOut:
    items = await branches_module(request).branches.list_warehouses(actor, scope.allowed, branch_id)
    return WarehouseListOut(items=[WarehouseOut.model_validate(asdict(i)) for i in items])


@router.patch(
    "/warehouses/{warehouse_id}", operation_id="warehouses_update", response_model=WarehouseUpdatedOut
)
async def update_warehouse(
    request: Request,
    warehouse_id: UUID,
    body: WarehouseUpdate,
    _: SettingsBranches,
    actor: Actor,
    scope: Scope,
) -> WarehouseUpdatedOut:
    result = await branches_module(request).branches.update_warehouse(
        actor,
        scope.allowed,
        warehouse_id,
        body.version,
        body.name,
        body.inventory_account,
        client_ip(request),
    )
    return WarehouseUpdatedOut.model_validate(asdict(result))
