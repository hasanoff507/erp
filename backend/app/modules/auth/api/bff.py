"""BFF endpoints for the web SPA (14 §2.1, §16.1.4, §20; 15 §1.3).

``/auth/*`` live at the root (17 §1); the CSRF token is ``GET /api/v1/auth/csrf`` (qaror #4).
The password never reaches these endpoints — it is typed on the AS page
(``/oauth/authorize``) that ``/auth/login/start`` redirects to.
"""

from __future__ import annotations

import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from starlette.responses import RedirectResponse, Response

from app.core.auth.dependencies import current_principal, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.auth.api.deps import auth_module
from app.modules.auth.application.bff import LOGIN_STATE_TTL_S, BffError
from app.modules.auth.application.device_cookie import DEVICE_COOKIE
from app.modules.auth.application.gateway import request_meta
from app.modules.auth.domain.constants import LOGIN_COOKIE, SID_COOKIE

router = APIRouter(tags=["auth"])
api_router = APIRouter(tags=["auth"])  # mounted under /api/v1

_NO_STORE = {"Cache-Control": "no-store"}


class SessionUser(BaseModel):
    id: UUID
    full_name: str
    phone_masked: str


class SessionTenant(BaseModel):
    id: UUID
    name: str


class SessionBranch(BaseModel):
    id: UUID
    name: str


class SessionDevice(BaseModel):
    """The registered device this session is bound to (14 §7.2); ``null`` — an unbound session."""

    id: UUID
    cash_register_id: UUID | None
    branch_id: UUID | None


class SessionInfo(BaseModel):
    """``GET /auth/session`` (14 §20): SPA shell data + heartbeat."""

    user: SessionUser
    tenant: SessionTenant
    branches: list[SessionBranch]  # the membership's branch_ids; empty branch_ids = every branch
    roles: list[str]  # system_code, or the role id for a custom role (14 §5)
    permissions: list[str]  # UI hints only — the server re-checks every request
    scope: list[str]
    client_id: str
    sub_status: str | None
    access_expires_at: int
    device: SessionDevice | None = None


class CsrfToken(BaseModel):
    csrf_token: str


class RevokeAllResult(BaseModel):
    sessions_revoked: int


class SwitchTenantIn(BaseModel):
    """``POST /bff/switch-tenant`` (14 §9): the tenant to make active in this browser."""

    tenant_id: UUID


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    # __Host- prefix: Secure, Path=/, no Domain (14 §2.1 "Qo'shimcha himoya" 3)
    response.set_cookie(name, value, max_age=max_age, path="/", secure=True, httponly=True, samesite="lax")


def _clear_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/", secure=True, httponly=True, samesite="lax")


def _require_cookie_session(principal: Principal) -> UUID:
    if not principal.via_cookie or principal.sid is None:
        raise AppError(ErrorCode.UNAUTHORIZED, params={"reason": "bff_session_required"})
    return principal.sid


def _refuse_device_session(principal: Principal) -> None:
    """SEC-01: a device-bound session cannot switch tenant or end the user's other sessions (14 §7.2).

    The POS keeps ``/auth/logout``; switching would escape the device binding into an unbound session.
    """
    if principal.device_id is not None:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_session"})


async def _retire_previous_session(request: Request, new_sid: UUID) -> None:
    """A re-login in the same browser ends the session its old ``__Host-sid`` pointed to (14 §2.1, §9).

    Otherwise the overwritten cookie leaves a live server-side session (row, refresh family,
    ``bff:sess:*``) behind until its absolute expiry. Revoked through the normal logout path.
    """
    module = auth_module(request)
    old_sid = module.cookies.unsign(request.cookies.get(SID_COOKIE))
    if old_sid is None or old_sid == new_sid:
        return
    old = await module.bff.session(old_sid)
    if old is None:
        return
    await module.bff.logout(old_sid, UUID(old.user_id), UUID(old.tenant_id), request_meta(request))


@router.get(
    "/auth/login/start", operation_id="auth_login_start", status_code=302, response_class=RedirectResponse
)
async def login_start(
    request: Request,
    return_to: Annotated[str | None, Query(max_length=2048)] = None,
    tenant_id: UUID | None = None,
) -> RedirectResponse:
    """Start Authorization Code + PKCE: state/verifier stay server-side, the browser goes to the AS page.

    A registered web device (signed ``__Host-erp_device`` cookie) gets a device-bound login (14 §7.2).
    """
    module = auth_module(request)
    device = module.device_cookies.unsign(request.cookies.get(DEVICE_COOKIE))
    start = await module.bff.start_login(return_to, tenant_id, device.device_id if device else None)
    response = RedirectResponse(start.authorize_url, status_code=302, headers=_NO_STORE)
    _set_cookie(response, LOGIN_COOKIE, start.login_id, LOGIN_STATE_TTL_S)
    return response


@router.get("/auth/callback", operation_id="auth_callback", status_code=302, response_class=RedirectResponse)
async def callback(
    request: Request,
    code: Annotated[str | None, Query(max_length=512)] = None,
    state: Annotated[str | None, Query(max_length=512)] = None,
    error: Annotated[str | None, Query(max_length=128)] = None,
) -> RedirectResponse:
    module = auth_module(request)
    login_id = request.cookies.get(LOGIN_COOKIE)
    try:
        if error:
            raise BffError(ErrorCode.UNAUTHORIZED, "authorization_denied")
        session, return_to = await module.bff.complete_login(login_id, code, state, request_meta(request))
    except BffError as exc:
        failed = RedirectResponse(f"/login?error={exc.reason}", status_code=302, headers=_NO_STORE)
        _clear_cookie(failed, LOGIN_COOKIE)
        return failed
    await _retire_previous_session(request, UUID(session.sid))
    response = RedirectResponse(return_to, status_code=302, headers=_NO_STORE)
    _clear_cookie(response, LOGIN_COOKIE)
    # a fresh sid on every login (session fixation, 14 §2.1)
    _set_cookie(
        response,
        SID_COOKIE,
        module.cookies.sign(UUID(session.sid)),
        max(1, session.absolute_exp - int(time.time())),
    )
    return response


@router.get("/auth/session", operation_id="auth_session_get", response_model=SessionInfo)
async def session_info(
    request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
) -> Response:
    """ "Who am I" + heartbeat (14 §16.1.4, §20); ``403 SUBSCRIPTION_RESTRICTED`` when locked out.

    Cheap enough for a ~30 s heartbeat: the session and subscription state come
    from Redis and the profile part is cached for 60 s (``SessionProfileService``).
    """
    return await _session_response(request, principal)


async def _session_response(request: Request, principal: Principal) -> Response:
    module = auth_module(request)
    profile = await module.profiles.profile(principal.tenant_id, principal.user_id)
    if profile is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "membership_inactive"})
    device = None
    if principal.device_id is not None:
        binding = await module.repo.device_binding(principal.tenant_id, principal.device_id)
        if binding is not None:
            device = SessionDevice(
                id=binding.device_id, cash_register_id=binding.cash_register_id, branch_id=binding.branch_id
            )
    info = SessionInfo(
        user=SessionUser(
            id=principal.user_id, full_name=profile.full_name, phone_masked=profile.phone_masked
        ),
        tenant=SessionTenant(id=principal.tenant_id, name=profile.tenant_name),
        branches=[SessionBranch(id=UUID(b.id), name=b.name) for b in profile.branches],
        roles=list(profile.roles),
        permissions=list(profile.permissions),
        scope=sorted(principal.scopes),
        client_id=principal.client_id,
        sub_status=principal.sub_status,
        access_expires_at=principal.expires_at,
        device=device,
    )
    return Response(info.model_dump_json(), media_type="application/json", headers=_NO_STORE)


@router.post(
    "/bff/switch-tenant",
    operation_id="bff_switch_tenant",
    response_model=SessionInfo,
    responses={403: {"description": "PERMISSION_DENIED / SUBSCRIPTION_RESTRICTED / CSRF_INVALID"}},
)
async def switch_tenant(
    request: Request, body: SwitchTenantIn, principal: Annotated[Principal, Depends(current_principal)]
) -> Response:
    """Tenant switch (14 §9): a fresh server-side code exchange for ``tenant_id``, the old session dies.

    Cookie session + ``X-CSRF-Token`` only. The answer is ``GET /auth/session`` of the new
    session and ``__Host-sid`` now points to it; the CSRF token of the old ``sid`` is dead —
    fetch a new one (``GET /api/v1/auth/csrf``). The current tenant itself is a no-op (same
    session, no cookie change). ``403 PERMISSION_DENIED`` — no active membership there;
    ``403 SUBSCRIPTION_RESTRICTED`` — that tenant is locked out (14 §16.1.2); in both cases the
    current session stays as it was.
    """
    sid = _require_cookie_session(principal)
    _refuse_device_session(principal)
    if body.tenant_id == principal.tenant_id:
        return await _session_response(request, principal)
    module = auth_module(request)
    try:
        session = await module.bff.switch_tenant(
            sid, principal.user_id, principal.tenant_id, body.tenant_id, request_meta(request)
        )
    except BffError as exc:
        if exc.code is ErrorCode.SUBSCRIPTION_RESTRICTED:
            raise AppError(
                ErrorCode.SUBSCRIPTION_RESTRICTED, params={"tenant_id": str(body.tenant_id)}
            ) from exc
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "membership_inactive"}) from exc
    response = await _session_response(request, await module.gateway.session_principal(session))
    _set_cookie(
        response,
        SID_COOKIE,
        module.cookies.sign(UUID(session.sid)),
        max(1, session.absolute_exp - int(time.time())),
    )
    return response


@router.post("/auth/logout", operation_id="auth_logout", status_code=204)
async def logout(request: Request, principal: Annotated[Principal, Depends(current_principal)]) -> Response:
    sid = _require_cookie_session(principal)
    await auth_module(request).bff.logout(sid, principal.user_id, principal.tenant_id, request_meta(request))
    response = Response(status_code=204, headers=_NO_STORE)
    _clear_cookie(response, SID_COOKIE)
    return response


@router.post(
    "/auth/sessions/revoke-all", operation_id="auth_sessions_revoke_all", response_model=RevokeAllResult
)
async def revoke_all(
    request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> Response:
    _require_cookie_session(principal)
    _refuse_device_session(principal)
    count = await auth_module(request).bff.revoke_all(
        principal.user_id, principal.tenant_id, request_meta(request)
    )
    response = Response(
        RevokeAllResult(sessions_revoked=count).model_dump_json(),
        media_type="application/json",
        headers=_NO_STORE,
    )
    _clear_cookie(response, SID_COOKIE)
    return response


@api_router.get("/auth/csrf", operation_id="auth_csrf_get", response_model=CsrfToken)
async def csrf(request: Request, principal: Annotated[Principal, Depends(current_principal)]) -> CsrfToken:
    sid = _require_cookie_session(principal)
    return CsrfToken(csrf_token=auth_module(request).gateway.csrf_token(sid))
