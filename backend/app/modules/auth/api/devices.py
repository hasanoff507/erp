"""Web-POS device registration and the online PIN check (14 §4.3, §7.2, §20; 16 §9).

Both live at the root like every ``/auth/*`` endpoint (17 §1): no ``Idempotency-Key`` — registration is
idempotent through the signed ``__Host-erp_device`` cookie, a PIN check writes nothing but counters
and audit. Cookie-authenticated calls need ``X-CSRF-Token`` (the gateway checks it).
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, Protocol
from uuid import UUID

from fastapi import Depends, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.responses import Response

from app.core.auth.dependencies import current_principal, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.auth.api.bff import SessionInfo, _session_response, _set_cookie
from app.modules.auth.api.deps import auth_module
from app.modules.auth.application.actor import ActorBindingUnavailableError, session_key
from app.modules.auth.application.bff import BffError
from app.modules.auth.application.device_cookie import DEVICE_COOKIE
from app.modules.auth.application.gateway import request_meta
from app.modules.auth.domain.constants import SID_COOKIE

if TYPE_CHECKING:
    from app.modules.branches.application.devices import DeviceRegistration

router = APIRouter(tags=["auth"])

_NO_STORE = {"Cache-Control": "no-store"}

Actor = Annotated[Principal, Depends(require_subscription_ok)]
ManageRegisters = Annotated[PermissionGrant, Depends(require_permission("cash_register.manage"))]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Pin = Annotated[str, StringConstraints(pattern=r"^[0-9]{4,6}$")]


class DeviceRegistry(Protocol):
    """``BranchesModule.devices`` (``app.devices`` belongs to the branches module)."""

    async def register(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        cash_register_id: UUID,
        app_version: str | None,
        cookie_device_id: UUID | None,
        ip: str | None,
    ) -> DeviceRegistration: ...


def _registry(request: Request) -> DeviceRegistry:
    module = getattr(request.app.state, "branches_module", None)
    if module is None:
        raise RuntimeError("branches module is not wired (app.state.branches_module)")
    registry: DeviceRegistry = module.devices
    return registry


class DeviceRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_register_id: UUID
    app_version: Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)] | None = None


class DeviceRegisteredOut(BaseModel):
    id: UUID
    kind: str
    cash_register_id: UUID
    cash_register_name: str
    branch_id: UUID
    branch_name: str
    app_version: str | None
    created: bool
    session: SessionInfo


class PinVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    pin: Pin
    # actor — the user takes over the till (one live actor per device session, SEC-05);
    # approval — a manager/owner confirms an operation without taking over the till (no binding)
    purpose: Literal["actor", "approval"] = "actor"


class PinVerifiedOut(BaseModel):
    user_id: UUID
    full_name: str
    roles: list[str]
    permissions: list[str]
    verified_at: datetime
    pin_local_hash: str | None = Field(
        description="Offline PBKDF2 verifier `pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>` (14 §13)"
    )


@router.post(
    "/auth/devices/register",
    operation_id="auth_devices_register",
    response_model=DeviceRegisteredOut,
    status_code=201,
    responses={
        200: {"model": DeviceRegisteredOut, "description": "This browser is already that device"},
        422: {"description": "VALIDATION_ERROR (validation.device_bound_to_other_register)"},
    },
)
async def register_device(
    request: Request, body: DeviceRegisterIn, actor: Actor, _: ManageRegisters, scope: Scope
) -> Response:
    """Register this browser as the web device of a cash register (14 §7.2) — Owner/Manager.

    BFF cookie session only. The current session is replaced by a device-bound one (sliding 14 d /
    absolute 180 d): new ``__Host-sid`` and ``__Host-erp_device`` cookies; fetch a new CSRF token.
    """
    if not actor.via_cookie or actor.sid is None:
        raise AppError(ErrorCode.UNAUTHORIZED, params={"reason": "bff_session_required"})
    module = auth_module(request)
    meta = request_meta(request)
    cookie = module.device_cookies.unsign(request.cookies.get(DEVICE_COOKIE))
    cookie_device = cookie.device_id if cookie is not None and cookie.tenant_id == actor.tenant_id else None
    device = await _registry(request).register(
        actor, scope.allowed, body.cash_register_id, body.app_version, cookie_device, meta.ip
    )
    if actor.device_id == device.id:
        session_principal = actor  # already bound to this device
        new_sid = None
    else:
        try:
            session = await module.bff.bind_device(actor.sid, actor.user_id, actor.tenant_id, device.id, meta)
        except BffError as exc:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": exc.reason}) from exc
        session_principal = await module.gateway.session_principal(session)
        new_sid = session
    info = await _session_response(request, session_principal)
    out = DeviceRegisteredOut(
        id=device.id,
        kind=device.kind,
        cash_register_id=device.cash_register_id,
        cash_register_name=device.cash_register_name,
        branch_id=device.branch_id,
        branch_name=device.branch_name,
        app_version=device.app_version,
        created=device.created,
        session=SessionInfo.model_validate_json(bytes(info.body)),
    )
    response = Response(
        out.model_dump_json(),
        status_code=201 if device.created else 200,
        media_type="application/json",
        headers=_NO_STORE,
    )
    settings = module.settings
    _set_cookie(
        response,
        DEVICE_COOKIE,
        module.device_cookies.sign(device.id, actor.tenant_id),
        settings.device_cookie_max_age_s,
    )
    if new_sid is not None:
        _set_cookie(
            response,
            SID_COOKIE,
            module.cookies.sign(UUID(new_sid.sid)),
            max(1, new_sid.absolute_exp - int(time.time())),
        )
    return response


@router.post(
    "/auth/pin/verify",
    operation_id="auth_pin_verify",
    response_model=PinVerifiedOut,
    responses={
        400: {"description": "PIN_INVALID (params.reason=must_change_pin — the PIN must be set anew)"},
        423: {"description": "ACCOUNT_LOCKED (params.retry_after_s)"},
        429: {"description": "RATE_LIMITED — online check unavailable (fail-closed)"},
    },
)
async def verify_pin(request: Request, body: PinVerifyIn, actor: Actor) -> Response:
    """Online PIN check on a registered device (14 §4.3, §12): "who pressed", never a token.

    The device's session must be device-bound (``403 PERMISSION_DENIED reason=device_required``).
    """
    if actor.device_id is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_required"})
    module = auth_module(request)
    verified = await module.pin.verify(
        tenant_id=actor.tenant_id,
        user_id=body.user_id,
        pin=body.pin,
        device_id=actor.device_id,
        ip=request_meta(request).ip,
    )
    if body.purpose == "actor":
        # 14 §4.3: the verified user becomes THE actor of this device session (X-Actor-User-Id) — fail closed
        key = session_key(actor.sid, actor.family_id)
        if key is None:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_required"})
        try:
            await module.actors.bind(actor.device_id, key, verified.user_id)
        except ActorBindingUnavailableError as exc:
            raise AppError(ErrorCode.RATE_LIMITED, headers={"Retry-After": "30"}) from exc
    out = PinVerifiedOut(
        user_id=verified.user_id,
        full_name=verified.full_name,
        roles=list(verified.roles),
        permissions=list(verified.permissions),
        verified_at=verified.verified_at,
        pin_local_hash=verified.pin_local_hash,
    )
    return Response(out.model_dump_json(), media_type="application/json", headers=_NO_STORE)


@router.post(
    "/auth/pin/release",
    operation_id="auth_pin_release",
    status_code=204,
    responses={403: {"description": "PERMISSION_DENIED (reason=device_required)"}},
)
async def release_pin_actor(
    request: Request, actor: Annotated[Principal, Depends(current_principal)]
) -> Response:
    """End the PIN actor of this device session (SEC-05): cashier lock/switch, shift close, logout.

    Idempotent; afterwards every ``/api/v1`` call needs a new online ``POST /auth/pin/verify``.
    """
    key = session_key(actor.sid, actor.family_id)
    if actor.device_id is None or key is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_required"})
    try:
        await auth_module(request).actors.release(actor.device_id, key)
    except ActorBindingUnavailableError as exc:
        raise AppError(ErrorCode.RATE_LIMITED, headers={"Retry-After": "30"}) from exc
    return Response(status_code=204, headers=_NO_STORE)
