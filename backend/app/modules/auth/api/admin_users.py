"""``/api/v1/admin/users`` — BO-11 staff administration (14 §18.2, US-M13-01…07).

All routes need ``settings.users`` (15 §2.2: owner only). Writes carry an Idempotency-Key (17 §6);
the response is staged in the service's transaction (23 §3).
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Final, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import PermissionGrant, require_permission
from app.modules.auth.api.deps import auth_module
from app.modules.auth.application.admin_users import (
    CredentialResetResult,
    SessionsRevoked,
    SessionView,
    StaffView,
)
from app.modules.auth.application.gateway import request_meta

router = APIRouter(prefix="/admin/users", tags=["auth"])

_UZ_PHONE: Final = re.compile(r"^\+998\d{9}$")

Owner = Annotated[PermissionGrant, Depends(require_permission("settings.users"))]
Caller = Annotated[Principal, Depends(require_subscription_ok)]


# --- request models ------------------------------------------------------------------------------------
class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(max_length=17)
    name: str = Field(min_length=2, max_length=100)
    role_ids: list[UUID] = Field(min_length=1)
    branch_ids: list[UUID] = Field(min_length=1)

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, value: object) -> object:
        if isinstance(value, str):
            value = re.sub(r"[\s\-()]", "", value)
            if not _UZ_PHONE.match(value):
                raise ValueError("phone must be +998XXXXXXXXX")
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("name too short")
        return value


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "blocked"] | None = None
    role_ids: list[UUID] | None = Field(default=None, min_length=1)
    branch_ids: list[UUID] | None = Field(default=None, min_length=1)


# --- response models -----------------------------------------------------------------------------------
class StaffOut(BaseModel):
    user_id: UUID
    name: str
    phone: str
    role_ids: list[UUID]
    branch_ids: list[UUID]
    # invited — an existing account that has not redeemed the invite yet (14 §18.2): no access, and
    # ``name`` is what the inviter typed, never the account's own name
    status: Literal["active", "blocked", "invited"]
    last_login_at: datetime | None

    @classmethod
    def of(cls, view: StaffView) -> StaffOut:
        return cls.model_validate(
            {
                "user_id": view.user_id, "name": view.name, "phone": view.phone,
                "role_ids": list(view.role_ids), "branch_ids": list(view.branch_ids), "status": view.status,
                "last_login_at": view.last_login_at,
            }
        )  # fmt: skip


class StaffPageOut(BaseModel):
    items: list[StaffOut]
    next_cursor: str | None


class StaffCreatedOut(StaffOut):
    channel_used: Literal["telegram", "sms"]


class MembershipStatusOut(BaseModel):
    user_id: UUID
    status: Literal["active", "blocked", "invited"]  # unblocking an unaccepted invite → invited
    sessions_revoked: int


class CredentialResetOut(BaseModel):
    user_id: UUID
    sessions_revoked: int
    channel_used: Literal["telegram", "sms"]

    @classmethod
    def of(cls, r: CredentialResetResult) -> CredentialResetOut:
        return cls.model_validate(
            {"user_id": r.user_id, "sessions_revoked": r.sessions_revoked, "channel_used": r.channel_used}
        )


class SessionOut(BaseModel):
    session_id: UUID
    client_id: str
    device_id: UUID | None
    device_kind: str | None
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool

    @classmethod
    def of(cls, v: SessionView) -> SessionOut:
        return cls(
            session_id=v.session_id, client_id=v.client_id, device_id=v.device_id, device_kind=v.device_kind,
            created_at=v.created_at, last_seen_at=v.last_seen_at, ip=v.ip, user_agent=v.user_agent,
            current=v.current,
        )  # fmt: skip


class SessionListOut(BaseModel):
    items: list[SessionOut]


class SessionsRevokedOut(BaseModel):
    user_id: UUID
    sessions_revoked: int

    @classmethod
    def of(cls, r: SessionsRevoked) -> SessionsRevokedOut:
        return cls(user_id=r.user_id, sessions_revoked=r.sessions_revoked)


class DeviceOut(BaseModel):
    id: UUID
    kind: Literal["web", "android", "onec_agent"]
    app_version: str | None
    cash_register_id: UUID | None
    cash_register_name: str | None
    branch_id: UUID | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    revoked_at: datetime | None


class DeviceListOut(BaseModel):
    items: list[DeviceOut]


# --- routes --------------------------------------------------------------------------------------------
@router.get("", operation_id="admin_users_list", response_model=StaffPageOut)
async def list_users(
    request: Request,
    _: Owner,
    principal: Caller,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> StaffPageOut:
    page = await auth_module(request).admin_users.list_users(principal, cursor=cursor, limit=limit)
    return StaffPageOut(items=[StaffOut.of(v) for v in page.items], next_cursor=page.next_cursor)


@router.post("", operation_id="admin_users_create", response_model=StaffCreatedOut, status_code=201)
async def create_user(request: Request, body: StaffCreate, _: Owner, principal: Caller) -> StaffCreatedOut:
    result = await auth_module(request).admin_users.create(
        principal, phone=body.phone, name=body.name, role_ids=body.role_ids, branch_ids=body.branch_ids,
        ip=request_meta(request).ip,
    )  # fmt: skip
    out = StaffOut.of(result.user)
    return StaffCreatedOut.model_validate({**out.model_dump(), "channel_used": result.channel_used})


@router.patch("/{user_id}", operation_id="admin_users_update", response_model=MembershipStatusOut)
async def update_user(
    request: Request, user_id: UUID, body: StaffUpdate, _: Owner, principal: Caller
) -> MembershipStatusOut:
    result = await auth_module(request).admin_users.update(
        principal, user_id, status=body.status, role_ids=body.role_ids, branch_ids=body.branch_ids,
        ip=request_meta(request).ip,
    )  # fmt: skip
    return MembershipStatusOut(
        user_id=result.user_id, status=result.status, sessions_revoked=result.sessions_revoked
    )


@router.post(
    "/{user_id}/reset-password", operation_id="admin_users_reset_password", response_model=CredentialResetOut
)
async def reset_password(request: Request, user_id: UUID, _: Owner, principal: Caller) -> CredentialResetOut:
    result = await auth_module(request).admin_users.reset_password(
        principal, user_id, request_meta(request).ip
    )
    return CredentialResetOut.of(result)


@router.post("/{user_id}/reset-pin", operation_id="admin_users_reset_pin", response_model=CredentialResetOut)
async def reset_pin(request: Request, user_id: UUID, _: Owner, principal: Caller) -> CredentialResetOut:
    result = await auth_module(request).admin_users.reset_pin(principal, user_id, request_meta(request).ip)
    return CredentialResetOut.of(result)


@router.get("/{user_id}/sessions", operation_id="admin_users_sessions_list", response_model=SessionListOut)
async def list_sessions(request: Request, user_id: UUID, _: Owner, principal: Caller) -> SessionListOut:
    views = await auth_module(request).admin_users.sessions(principal, user_id)
    return SessionListOut(items=[SessionOut.of(v) for v in views])


@router.post(
    "/{user_id}/revoke-sessions",
    operation_id="admin_users_revoke_sessions",
    response_model=SessionsRevokedOut,
)
async def revoke_sessions(request: Request, user_id: UUID, _: Owner, principal: Caller) -> SessionsRevokedOut:
    result = await auth_module(request).admin_users.revoke_sessions(
        principal, user_id, request_meta(request).ip
    )
    return SessionsRevokedOut.of(result)


@router.post(
    "/{user_id}/sessions/{session_id}/revoke",
    operation_id="admin_users_revoke_session",
    response_model=SessionsRevokedOut,
)
async def revoke_session(
    request: Request, user_id: UUID, session_id: UUID, _: Owner, principal: Caller
) -> SessionsRevokedOut:
    result = await auth_module(request).admin_users.revoke_session(
        principal, user_id, session_id, request_meta(request).ip
    )
    return SessionsRevokedOut.of(result)


@router.get("/{user_id}/devices", operation_id="admin_users_devices_list", response_model=DeviceListOut)
async def list_devices(request: Request, user_id: UUID, _: Owner, principal: Caller) -> DeviceListOut:
    rows = await auth_module(request).admin_users.devices(principal, user_id)
    return DeviceListOut.model_validate({"items": [asdict(r) for r in rows]})
