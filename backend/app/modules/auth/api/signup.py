"""Signup, OTP, credential-set and Google endpoints (14 §2.2, §4.2, §20; 07 BO-01/BO-21; US-M17-01).

All live at the root like the other BFF endpoints (17 §1). There is no session yet, so the BFF CSRF
token does not exist: the browser POSTs are guarded like the AS login form — same-origin
``Origin`` / ``Sec-Fetch-Site`` (14 §2.1 "Qo'shimcha himoya" 1) — and they never return OAuth
tokens: signup and Google login end with the ``__Host-sid`` cookie of a normal BFF login.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from redis.exceptions import RedisError
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.core.error_codes import ERROR_SPECS, ErrorCode
from app.core.errors import AppError
from app.modules.auth.api.bff import _clear_cookie, _retire_previous_session, _set_cookie
from app.modules.auth.api.deps import auth_module
from app.modules.auth.api.oauth import same_origin
from app.modules.auth.application.gateway import request_meta
from app.modules.auth.application.google import (
    GOOGLE_LOGIN_TTL_S,
    GOOGLE_PENDING_TTL_S,
    GoogleFlowError,
    GoogleLoggedIn,
)
from app.modules.auth.application.otp import OtpChannel, OtpPurpose
from app.modules.auth.application.signup import BusinessType, LegalForm, SignupCommand
from app.modules.auth.domain.constants import GOOGLE_LOGIN_COOKIE, GOOGLE_PENDING_COOKIE, SID_COOKIE

router = APIRouter(tags=["auth"])

_NO_STORE = {"Cache-Control": "no-store"}


def _require_same_origin(request: Request) -> None:
    if not same_origin(request):
        raise AppError(ErrorCode.CSRF_INVALID, params={"reason": "cross_origin"})


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- OTP -----------------------------------------------------------------------------------------------
class OtpRequestIn(_Request):
    phone: str = Field(min_length=9, max_length=17)
    purpose: Literal["signup", "recovery"]


class ApiWarning(BaseModel):
    code: str
    message_key: str


class OtpRequestOut(BaseModel):
    challenge_id: UUID
    channel_used: OtpChannel
    expires_at: datetime
    warnings: list[ApiWarning] = Field(default_factory=list)


StaffCodePurpose = Literal["invite", "admin_reset", "pin_reset"]


class OtpVerifyIn(_Request):
    """Either ``challenge_id`` (from ``/auth/otp/request``) or ``phone`` + ``purpose`` (BO-11 codes)."""

    challenge_id: UUID | None = None
    phone: str | None = Field(default=None, max_length=20)
    purpose: StaffCodePurpose | None = None
    code: str = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def _one_way(self) -> OtpVerifyIn:
        by_id = self.challenge_id is not None
        by_phone = self.phone is not None or self.purpose is not None
        if by_id == by_phone or (by_phone and (self.phone is None or self.purpose is None)):
            raise ValueError("send either challenge_id, or phone and purpose")
        return self


class OtpVerifyOut(BaseModel):
    challenge_id: UUID
    purpose: OtpPurpose
    verified: bool
    # recovery / invite / admin_reset / pin_reset: the credential-set session (14 §4.2) — not a token
    credential_token: str | None = None
    credential_token_expires_in: int | None = None
    credential_kinds: list[Literal["password", "pin"]] | None = None
    # invite only: the inviting tenant's membership is active now (14 §18.2). An account that already
    # has a password/PIN gets no credential_token — it logs in with its existing credentials
    invite_accepted: bool | None = None


@router.post("/auth/otp/request", operation_id="auth_otp_request", response_model=OtpRequestOut)
async def otp_request(request: Request, body: OtpRequestIn) -> Response:
    """Telegram bot first, SMS fallback (14 §4.2); ``channel_used`` + ``TELEGRAM_NOT_LINKED`` warning."""
    _require_same_origin(request)
    purpose: OtpPurpose = body.purpose
    issued = await auth_module(request).otp.request(body.phone, purpose, ip=request_meta(request).ip)
    warnings = []
    if issued.channel_used == "sms":
        spec = ERROR_SPECS[ErrorCode.TELEGRAM_NOT_LINKED]
        warnings.append(ApiWarning(code=ErrorCode.TELEGRAM_NOT_LINKED.value, message_key=spec.message_key))
    result = OtpRequestOut(
        challenge_id=issued.challenge_id,
        channel_used=issued.channel_used,
        expires_at=issued.expires_at,
        warnings=warnings,
    )
    return Response(result.model_dump_json(), media_type="application/json", headers=_NO_STORE)


@router.post("/auth/otp/verify", operation_id="auth_otp_verify", response_model=OtpVerifyOut)
async def otp_verify(request: Request, body: OtpVerifyIn) -> Response:
    """``OTP_INVALID`` / ``OTP_EXPIRED`` / ``OTP_MAX_ATTEMPTS`` (5 attempts per challenge).

    ``429 RATE_LIMITED`` — per-IP attempt limit or the per-phone daily cap of wrong codes (14 §12).
    """
    _require_same_origin(request)
    module = auth_module(request)
    ip = request_meta(request).ip
    if body.challenge_id is not None:
        verified = await module.otp.verify(body.challenge_id, body.code, ip=ip)
    else:
        phone, purpose = body.phone or "", body.purpose or "invite"  # both set (_one_way)
        verified = await module.otp.verify_by_phone(phone, purpose, body.code, ip=ip)
    result = OtpVerifyOut(challenge_id=verified.challenge_id, purpose=verified.purpose, verified=True)
    if verified.purpose not in ("signup", "data_export"):
        redeemed = await module.credentials.redeem(verified, ip=ip)
        result.invite_accepted = redeemed.invite_accepted
        cred = redeemed.session
        if cred is not None:
            result.credential_token = cred.token
            result.credential_token_expires_in = cred.expires_in
            result.credential_kinds = [k for k in ("password", "pin") if k in cred.allowed]
    return Response(result.model_dump_json(), media_type="application/json", headers=_NO_STORE)


# --- credential set (invite / admin_reset / pin_reset / recovery) -----------------------------------
class CredentialsIn(_Request):
    credential_token: str = Field(min_length=16, max_length=128)
    password: str | None = Field(default=None, max_length=128)
    pin: str | None = Field(default=None, max_length=6)


@router.post("/auth/credentials", operation_id="auth_credentials_set", status_code=204)
async def credentials_set(request: Request, body: CredentialsIn) -> Response:
    """New password and/or PIN after a verified code; ``204`` — then a normal login (no tokens here)."""
    _require_same_origin(request)
    await auth_module(request).credentials.set_credentials(
        body.credential_token, password=body.password, pin=body.pin, ip=request_meta(request).ip
    )
    return Response(status_code=204, headers=_NO_STORE)


# --- signup ----------------------------------------------------------------------------------------
class SignupIn(_Request):
    otp_challenge_id: UUID  # a verified purpose=signup challenge — proves the phone (14 §20)
    password: str | None = Field(default=None, min_length=8, max_length=128)  # optional on the Google path
    owner_name: str = Field(min_length=2, max_length=100)
    store_name: str = Field(min_length=2, max_length=100)
    business_type: BusinessType
    legal_form: LegalForm
    accepted_terms_version: str = Field(min_length=1, max_length=32)
    ai_cross_border_consent: bool = False


class SignupOut(BaseModel):
    tenant_id: UUID
    user_id: UUID
    sub_status: Literal["trial"]
    trial_ends_at: datetime


@router.post("/auth/signup", operation_id="auth_signup", status_code=201, response_model=SignupOut)
async def signup(request: Request, body: SignupIn) -> Response:
    """15 §1.5 provisioning in one transaction, then the owner is logged in (``__Host-sid``)."""
    _require_same_origin(request)
    module = auth_module(request)
    meta = request_meta(request)
    pending_token = request.cookies.get(GOOGLE_PENDING_COOKIE)
    google = await module.google.pending_identity(pending_token)
    result = await module.signup.signup(
        SignupCommand(
            otp_challenge_id=body.otp_challenge_id,
            password=body.password,
            owner_name=body.owner_name,
            store_name=body.store_name,
            business_type=body.business_type,
            legal_form=body.legal_form,
            accepted_terms_version=body.accepted_terms_version,
            ai_cross_border_consent=body.ai_cross_border_consent,
            ip=meta.ip,
            google=google,
        )
    )
    if pending_token and google is not None:
        await module.google.drop_pending(pending_token)
    session = await module.bff.login_direct(result.user_id, result.tenant_id, meta, method="signup")
    await _retire_previous_session(request, UUID(session.sid))
    payload = SignupOut(
        tenant_id=result.tenant_id,
        user_id=result.user_id,
        sub_status="trial",
        trial_ends_at=result.trial_ends_at,
    )
    response = Response(
        payload.model_dump_json(), status_code=201, media_type="application/json", headers=_NO_STORE
    )
    _set_cookie(
        response,
        SID_COOKIE,
        module.cookies.sign(UUID(session.sid)),
        max(1, session.absolute_exp - int(time.time())),
    )
    _clear_cookie(response, GOOGLE_PENDING_COOKIE)
    return response


# --- Google (14 §2.2) ------------------------------------------------------------------------------
@router.get(
    "/auth/google/start", operation_id="auth_google_start", status_code=302, response_class=RedirectResponse
)
async def google_start(
    request: Request,
    return_to: Annotated[str | None, Query(max_length=2048)] = None,
    tenant_id: UUID | None = None,
) -> RedirectResponse:
    """302 to Google; Google not configured / unavailable → 302 ``/login?error=google_auth_failed``.

    ``429 RATE_LIMITED`` past 30 starts / IP / 10 min (14 §12).
    """
    try:
        start = await auth_module(request).google.start(return_to, tenant_id, ip=request_meta(request).ip)
    except AppError as exc:
        if exc.code is ErrorCode.RATE_LIMITED:
            raise
        return RedirectResponse("/login?error=google_auth_failed", status_code=302, headers=_NO_STORE)
    except RedisError:
        return RedirectResponse("/login?error=google_auth_failed", status_code=302, headers=_NO_STORE)
    response = RedirectResponse(start.url, status_code=302, headers=_NO_STORE)
    _set_cookie(response, GOOGLE_LOGIN_COOKIE, start.login_id, GOOGLE_LOGIN_TTL_S)
    return response


@router.get(
    "/auth/google/callback",
    operation_id="auth_google_callback",
    status_code=302,
    response_class=RedirectResponse,
)
async def google_callback(
    request: Request,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=512)] = None,
    error: Annotated[str | None, Query(max_length=128)] = None,
) -> RedirectResponse:
    """Known account → BFF login cookie; new account → ``/onboarding?method=google`` (BO-21 ①-Google)."""
    module = auth_module(request)
    try:
        outcome = await module.google.callback(
            request.cookies.get(GOOGLE_LOGIN_COOKIE), code, state, error, request_meta(request)
        )
    except GoogleFlowError as exc:
        failed = RedirectResponse(f"/login?error={exc.reason}", status_code=302, headers=_NO_STORE)
        _clear_cookie(failed, GOOGLE_LOGIN_COOKIE)
        return failed
    if isinstance(outcome, GoogleLoggedIn):
        session = outcome.session
        await _retire_previous_session(request, UUID(session.sid))
        response = RedirectResponse(outcome.return_to, status_code=302, headers=_NO_STORE)
        _set_cookie(
            response,
            SID_COOKIE,
            module.cookies.sign(UUID(session.sid)),
            max(1, session.absolute_exp - int(time.time())),
        )
    else:
        response = RedirectResponse("/onboarding?method=google", status_code=302, headers=_NO_STORE)
        _set_cookie(response, GOOGLE_PENDING_COOKIE, outcome.pending_token, GOOGLE_PENDING_TTL_S)
    _clear_cookie(response, GOOGLE_LOGIN_COOKIE)
    return response


class GoogleTokenIn(_Request):
    id_token: str = Field(min_length=20, max_length=8192)
    code_challenge: str = Field(min_length=43, max_length=128)
    code_challenge_method: Literal["S256"] = "S256"
    redirect_uri: str = Field(max_length=2048)
    tenant_id: UUID | None = None


class GoogleTokenOut(BaseModel):
    code: str
    redirect_uri: str


@router.post("/auth/google/token", operation_id="auth_google_token", response_model=GoogleTokenOut)
async def google_token(request: Request, body: GoogleTokenIn) -> JSONResponse:
    """Android native Google Sign-In: verified ID token → one-time ``android-pos`` code.

    The app redeems it at ``/oauth/token`` (``authorization_code`` + its ``code_verifier``).
    """
    code = await auth_module(request).google.android_code(
        body.id_token,
        code_challenge=body.code_challenge,
        redirect_uri=body.redirect_uri,
        tenant_id=body.tenant_id,
        ip=request_meta(request).ip,
    )
    return JSONResponse(
        GoogleTokenOut(code=code, redirect_uri=body.redirect_uri).model_dump(), headers=_NO_STORE
    )
