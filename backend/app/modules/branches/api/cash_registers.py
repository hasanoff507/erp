"""``/cash-registers`` (20 #38–#40, #40i; BO-12)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.permissions import PermissionGrant, require_permission
from app.modules.branches.api.deps import Actor, Scope, branches_module, client_ip, has_permission
from app.modules.branches.application.cash_registers import CashRegisterPatch
from app.modules.branches.domain.model import CashRegisterKind

router = APIRouter(tags=["branches"])

ManageRegisters = Annotated[PermissionGrant, Depends(require_permission("cash_register.manage"))]
RegisterName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LocalDeviceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
OfdStatus = Literal["pending", "registered", "active", "suspended", "deregistered"]
FmState = Literal["ok", "locked", "ack_overdue", "memory_full", "unknown"]


class CashRegisterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    name: RegisterName
    kind: CashRegisterKind


class CashRegisterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RegisterName | None = None
    fiscal_agent_id: UUID | None = None
    fiscal_local_device_id: LocalDeviceId | None = None
    version: int


class CashRegisterArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CashRegisterOut(BaseModel):
    id: UUID
    branch_id: UUID
    name: str
    kind: CashRegisterKind
    fiscal_module_id: str | None
    txkm_contract_ref: str | None
    fiscal_agent_id: UUID | None
    fiscal_local_device_id: str | None
    ofd_status: OfdStatus
    fm_state: FmState
    last_unacked_receipt_at: datetime | None
    fm_receipts_pending: int | None
    tax_registered_at: datetime | None
    archived_at: datetime | None
    version: int


class CashRegisterListOut(BaseModel):
    items: list[CashRegisterOut]


class CashRegisterCreatedOut(BaseModel):
    id: UUID
    branch_id: UUID
    name: str
    kind: CashRegisterKind
    ofd_status: OfdStatus
    version: int


class CashRegisterUpdatedOut(BaseModel):
    id: UUID
    name: str
    fiscal_agent_id: UUID | None
    fiscal_local_device_id: str | None
    version: int


class CashRegisterArchivedOut(BaseModel):
    id: UUID
    archived_at: datetime | None


@router.get("/cash-registers", operation_id="cash_registers_list", response_model=CashRegisterListOut)
async def list_cash_registers(
    request: Request,
    actor: Actor,
    scope: Scope,
    branch_id: UUID | None = None,
    include_archived: bool = False,
) -> CashRegisterListOut:
    items = await branches_module(request).cash_registers.list_registers(
        actor, scope.allowed, branch_id, include_archived
    )
    return CashRegisterListOut(items=[CashRegisterOut.model_validate(asdict(i)) for i in items])


@router.post(
    "/cash-registers",
    operation_id="cash_registers_create",
    status_code=201,
    response_model=CashRegisterCreatedOut,
)
async def create_cash_register(
    request: Request,
    response: Response,
    body: CashRegisterCreate,
    _: ManageRegisters,
    actor: Actor,
    scope: Scope,
) -> CashRegisterCreatedOut:
    result = await branches_module(request).cash_registers.create(
        actor, scope.allowed, body.branch_id, body.name, body.kind, client_ip(request)
    )
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{result.id}"
    return CashRegisterCreatedOut.model_validate(asdict(result))


@router.patch(
    "/cash-registers/{register_id}",
    operation_id="cash_registers_update",
    response_model=CashRegisterUpdatedOut,
)
async def update_cash_register(
    request: Request,
    register_id: UUID,
    body: CashRegisterUpdate,
    _: ManageRegisters,
    actor: Actor,
    scope: Scope,
) -> CashRegisterUpdatedOut:
    fiscal_set = bool({"fiscal_agent_id", "fiscal_local_device_id"} & body.model_fields_set)
    patch = CashRegisterPatch(
        version=body.version,
        name=body.name,
        fiscal_fields_set=fiscal_set,
        fiscal_agent_id=body.fiscal_agent_id,
        fiscal_local_device_id=body.fiscal_local_device_id,
    )
    may_bind = fiscal_set and await has_permission(request, actor, "settings.branches")
    result = await branches_module(request).cash_registers.update(
        actor, scope.allowed, register_id, patch, may_bind_fiscal_agent=may_bind, ip=client_ip(request)
    )
    return CashRegisterUpdatedOut.model_validate(asdict(result))


@router.post(
    "/cash-registers/{register_id}/archive",
    operation_id="cash_registers_archive",
    response_model=CashRegisterArchivedOut,
)
async def archive_cash_register(
    request: Request,
    register_id: UUID,
    body: CashRegisterArchive,
    _: ManageRegisters,
    actor: Actor,
    scope: Scope,
) -> CashRegisterArchivedOut:
    result = await branches_module(request).cash_registers.archive(
        actor, scope.allowed, register_id, client_ip(request)
    )
    return CashRegisterArchivedOut.model_validate(asdict(result))
