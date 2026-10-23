"""``/devices`` — BO-11 "Qurilmalar" (20 #29a/#29b, M13 → tag ``access``)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.permissions import PermissionGrant, require_permission
from app.modules.branches.api.deps import Actor, Page, Scope, Size, branches_module, client_ip
from app.modules.branches.domain.model import DeviceKind

router = APIRouter(tags=["access"])

RevokeDevices = Annotated[PermissionGrant, Depends(require_permission("devices.revoke"))]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class DeviceRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason
    confirm_pending_loss: bool = False


class DeviceOut(BaseModel):
    id: UUID
    kind: DeviceKind
    app_version: str | None
    cash_register_id: UUID | None
    cash_register_name: str | None
    branch_id: UUID | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    outbox_pending_count: int | None
    outbox_oldest_pending_at: datetime | None
    has_pending: bool
    revoked_at: datetime | None


class DevicePageOut(BaseModel):
    items: list[DeviceOut]
    total: int
    page: int
    size: int


class DeviceRevokedOut(BaseModel):
    id: UUID
    revoked_at: datetime | None
    outbox_pending_count: int | None


@router.get("/devices", operation_id="devices_list", response_model=DevicePageOut)
async def list_devices(
    request: Request,
    _: RevokeDevices,
    actor: Actor,
    scope: Scope,
    branch_id: UUID | None = None,
    kind: DeviceKind | None = None,
    include_revoked: bool = False,
    page: Page = 1,
    size: Size = 50,
) -> DevicePageOut:
    result = await branches_module(request).devices.list_devices(
        actor,
        scope.allowed,
        branch_id=branch_id,
        kind=kind,
        include_revoked=include_revoked,
        page=page,
        size=size,
    )
    return DevicePageOut.model_validate(asdict(result))


@router.post("/devices/{device_id}/revoke", operation_id="devices_revoke", response_model=DeviceRevokedOut)
async def revoke_device(
    request: Request, device_id: UUID, body: DeviceRevoke, _: RevokeDevices, actor: Actor, scope: Scope
) -> DeviceRevokedOut:
    result = await branches_module(request).devices.revoke(
        actor, scope.allowed, device_id, body.reason, body.confirm_pending_loss, client_ip(request)
    )
    return DeviceRevokedOut.model_validate(asdict(result))
