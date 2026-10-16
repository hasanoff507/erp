"""``/api/v1/admin/users`` (14 §18.2, BO-11). Bosqich 0: block/unblock only (QT-OAUTH-07)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import PermissionGrant, require_permission
from app.modules.auth.api.deps import auth_module
from app.modules.auth.application.gateway import request_meta

router = APIRouter(prefix="/admin/users", tags=["auth"])


class MembershipStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "blocked"]


class MembershipStatusOut(BaseModel):
    user_id: UUID
    status: Literal["active", "blocked"]
    sessions_revoked: int


@router.patch("/{user_id}", operation_id="admin_users_update", response_model=MembershipStatusOut)
async def update_user(
    request: Request,
    user_id: UUID,
    body: MembershipStatusUpdate,
    _: Annotated[PermissionGrant, Depends(require_permission("settings.users"))],
    principal: Annotated[Principal, Depends(require_subscription_ok)],
) -> MembershipStatusOut:
    result = await auth_module(request).admin_users.set_status(
        principal, user_id, body.status, request_meta(request).ip
    )
    return MembershipStatusOut(
        user_id=result.user_id, status=result.status, sessions_revoked=result.sessions_revoked
    )
