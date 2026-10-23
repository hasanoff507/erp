"""Google sign-in (14 §2.2, qaror #34, 07 BO-01/BO-21 ①-Google).

Web (BFF): ``/auth/google/start`` keeps state + PKCE verifier + nonce server-side (Redis, bound to a
random ``__Host-erp_google_login`` cookie, 10 min), Google redirects back to ``/auth/google/callback``:

1. state must match (login-CSRF), the code is exchanged and the ID token fully verified (adapter);
2. ``email_verified=false`` → ``GOOGLE_EMAIL_NOT_VERIFIED``; any Google failure → ``GOOGLE_AUTH_FAILED``;
3. account resolution: the ``user_identities`` row of (google, sub); otherwise a user whose *other*
   verified Google identity has the same e-mail (``users`` has no e-mail column, so this is the only
   e-mail linking the schema allows; ambiguous matches never link) — a new link is written;
4. a known user is logged in through the normal BFF code exchange (``BffService.login_direct``);
5. an unknown Google account starts the signup path: the verified identity is parked server-side
   (Redis, 30 min, ``__Host-erp_google`` cookie) and the SPA continues on ``/onboarding`` — the phone
   is still verified by a ``purpose=signup`` OTP (it is the login/recovery identifier and must not
   be claimable unverified), but no password is required; ``/auth/signup`` links the identity in
   its transaction.

Both entry points are rate-limited per IP (``GOOGLE_PER_IP_WINDOW``: 30 / IP / 10 min, 14 §12) →
``429 RATE_LIMITED``.

Android (``POST /auth/google/token``): the native ID token is verified (``aud`` = our web or
Android client id) and an ``android-pos`` authorization code is returned for the app's own PKCE
challenge — tokens still come only from ``/oauth/token``.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

import structlog
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from redis.asyncio import Redis

from app.core.audit import AuditLog
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.modules.auth.application.bff import BffError, BffService, BffSession, safe_return_to
from app.modules.auth.application.ports import (
    AuthStore,
    GoogleAuthError,
    GoogleIdentity,
    GoogleOidcPort,
    IdentityStore,
    MembershipRow,
)
from app.modules.auth.application.tokens import RequestMeta, TokenService
from app.modules.auth.domain.models import AuthenticatedUser

log = structlog.get_logger(__name__)

GOOGLE_LOGIN_TTL_S: Final = 600
GOOGLE_PENDING_TTL_S: Final = 1800
GOOGLE_PER_IP_LIMIT: Final = 30
GOOGLE_PER_IP_WINDOW_S: Final = 600
PROVIDER: Final = "google"
ANDROID_CLIENT_ID: Final = "android-pos"


@dataclass(frozen=True, slots=True)
class GoogleStart:
    login_id: str
    url: str


@dataclass(frozen=True, slots=True)
class GoogleLoggedIn:
    session: BffSession
    return_to: str


@dataclass(frozen=True, slots=True)
class GoogleSignupPending:
    pending_token: str


class GoogleFlowError(Exception):
    """Ends the browser flow with a ``/login?error=<reason>`` redirect."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _choose_tenant(memberships: list[MembershipRow], tenant_id: UUID | None) -> MembershipRow:
    if not memberships:
        raise GoogleFlowError("no_active_membership")
    if tenant_id is not None:
        for m in memberships:
            if m.tenant_id == tenant_id:
                return m
        raise GoogleFlowError("not_a_member")
    if len(memberships) == 1:
        return memberships[0]
    raise GoogleFlowError("tenant_required")  # pick a shop: /auth/google/start?tenant_id=…


class GoogleSignInService:
    def __init__(
        self,
        oidc: GoogleOidcPort | None,
        identities: IdentityStore,
        store: AuthStore,
        bff: BffService,
        tokens: TokenService,
        audit: AuditLog,
        redis: Callable[[], Redis],
        *,
        issuer: str,
    ) -> None:
        self._oidc = oidc
        self._identities = identities
        self._store = store
        self._bff = bff
        self._tokens = tokens
        self._audit = audit
        self._redis = redis
        self._issuer = issuer

    @property
    def redirect_uri(self) -> str:
        return f"{self._issuer}/auth/google/callback"

    def _port(self) -> GoogleOidcPort:
        if self._oidc is None:  # ERP_GOOGLE_CLIENT_ID not configured
            raise AppError(ErrorCode.GOOGLE_AUTH_FAILED, params={"reason": "google_not_configured"})
        return self._oidc

    # --- web -----------------------------------------------------------------------------------------
    async def start(self, return_to: str | None, tenant_id: UUID | None, *, ip: str | None) -> GoogleStart:
        await self._ip_limit("start", ip)
        port = self._port()
        login_id, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier, nonce = secrets.token_urlsafe(64), secrets.token_urlsafe(24)
        record = {
            "state": state, "verifier": verifier, "nonce": nonce, "return_to": safe_return_to(return_to),
            "tenant_id": str(tenant_id) if tenant_id else None,
        }  # fmt: skip
        await self._redis().set(
            f"auth:google:login:{_digest(login_id)}", json.dumps(record), ex=GOOGLE_LOGIN_TTL_S
        )
        url = port.build_auth_url(
            state=state,
            code_challenge=create_s256_code_challenge(verifier),
            nonce=nonce,
            redirect_uri=self.redirect_uri,
        )
        return GoogleStart(login_id, url)

    async def callback(
        self,
        login_id: str | None,
        code: str | None,
        state: str | None,
        error: str | None,
        meta: RequestMeta,
    ) -> GoogleLoggedIn | GoogleSignupPending:
        if not login_id:
            raise GoogleFlowError("login_state_missing")
        raw = await self._redis().getdel(f"auth:google:login:{_digest(login_id)}")
        if not raw:
            raise GoogleFlowError("login_state_expired")
        record = json.loads(raw)
        if not state or not secrets.compare_digest(state, str(record["state"])):
            raise GoogleFlowError("state_mismatch")
        if error or not code:
            raise GoogleFlowError("google_auth_failed")
        try:
            identity = await self._port().exchange_code(
                code=code,
                code_verifier=str(record["verifier"]),
                redirect_uri=self.redirect_uri,
                nonce=str(record["nonce"]),
            )
        except GoogleAuthError as exc:
            log.warning("google_auth_failed", reason=str(exc))
            raise GoogleFlowError("google_auth_failed") from exc
        if not identity.email_verified:
            raise GoogleFlowError("google_email_not_verified")
        user_id = await self._resolve(identity)
        if user_id is None:
            return GoogleSignupPending(await self._park(identity))
        tenant_id = UUID(record["tenant_id"]) if record.get("tenant_id") else None
        chosen = _choose_tenant(await self._store.list_memberships(user_id), tenant_id)
        try:
            session = await self._bff.login_direct(user_id, chosen.tenant_id, meta, method="google")
        except BffError as exc:
            raise GoogleFlowError(
                "subscription_restricted" if exc.code is ErrorCode.SUBSCRIPTION_RESTRICTED else exc.reason
            ) from exc
        return GoogleLoggedIn(session, str(record["return_to"]))

    async def pending_identity(self, pending_token: str | None) -> GoogleIdentity | None:
        if not pending_token:
            return None
        raw = await self._redis().get(f"auth:google:pending:{_digest(pending_token)}")
        if not raw:
            return None
        data = json.loads(raw)
        return GoogleIdentity(data["sub"], data.get("email"), bool(data["email_verified"]), data.get("name"))

    async def drop_pending(self, pending_token: str) -> None:
        await self._redis().delete(f"auth:google:pending:{_digest(pending_token)}")

    # --- android -------------------------------------------------------------------------------------
    async def android_code(
        self, id_token: str, *, code_challenge: str, redirect_uri: str, tenant_id: UUID | None, ip: str | None
    ) -> str:
        """``POST /auth/google/token``: a one-time ``android-pos`` code for the app's PKCE challenge."""
        await self._ip_limit("token", ip)
        port = self._port()
        try:
            identity = await port.verify_id_token(id_token)
        except GoogleAuthError as exc:
            log.warning("google_auth_failed", reason=str(exc), client="android")
            raise AppError(ErrorCode.GOOGLE_AUTH_FAILED) from exc
        if not identity.email_verified:
            raise AppError(ErrorCode.GOOGLE_EMAIL_NOT_VERIFIED)
        user_id = await self._resolve(identity)
        if user_id is None:  # Android has no onboarding: sign up on the web first (BO-21)
            raise AppError(ErrorCode.GOOGLE_AUTH_FAILED, params={"reason": "account_not_found"})
        try:
            chosen = _choose_tenant(await self._store.list_memberships(user_id), tenant_id)
        except GoogleFlowError as exc:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": exc.reason}) from exc
        await self._tokens.clients.refresh()
        client = self._tokens.clients.get(ANDROID_CLIENT_ID)
        if client is None or not client.check_redirect_uri(redirect_uri):
            raise AppError(ErrorCode.VALIDATION_ERROR, params={"reason": "invalid_redirect_uri"})
        code = secrets.token_urlsafe(32)
        await self._tokens.save_code(
            code,
            client,
            AuthenticatedUser(user_id, chosen.tenant_id),
            code_challenge,
            redirect_uri,
            client.get_allowed_scope(None),
        )
        await self._audit.write(
            tenant_id=chosen.tenant_id, user_id=user_id, action="login_success", entity="users",
            entity_id=user_id, ip=ip, after={"method": "google", "client_id": ANDROID_CLIENT_ID},
        )  # fmt: skip
        return code

    # --- helpers -------------------------------------------------------------------------------------
    async def _ip_limit(self, entry: str, ip: str | None) -> None:
        state = await hit(self._redis(), f"auth:google:{entry}:ip:{ip or '-'}", GOOGLE_PER_IP_WINDOW_S)
        if state.count > GOOGLE_PER_IP_LIMIT:
            raise AppError(
                ErrorCode.RATE_LIMITED,
                params={"retry_after_s": state.retry_after_s},
                headers={"Retry-After": str(state.retry_after_s)},
            )

    async def _resolve(self, identity: GoogleIdentity) -> UUID | None:
        user_id = await self._identities.user_by_identity(PROVIDER, identity.sub)
        if user_id is not None:
            return user_id
        if identity.email and identity.email_verified:
            user_id = await self._identities.user_by_verified_email(PROVIDER, identity.email)
            if user_id is not None:
                await self._identities.link_identity(user_id, identity.sub, identity.email, True)
                log.info("google_identity_linked", user_id=str(user_id))
        return user_id

    async def _park(self, identity: GoogleIdentity) -> str:
        token = secrets.token_urlsafe(32)
        data = {
            "sub": identity.sub, "email": identity.email, "email_verified": identity.email_verified,
            "name": identity.name,
        }  # fmt: skip
        await self._redis().set(
            f"auth:google:pending:{_digest(token)}", json.dumps(data), ex=GOOGLE_PENDING_TTL_S
        )
        return token
