"""Backend-for-Frontend for the web SPA (14 §2.1, §7; 15 §1.3).

The browser never sees an OAuth token: it holds only the signed ``__Host-sid``
cookie. Tokens live server-side in Redis (``bff:sess:{sid}``, envelope-
encrypted). The password is typed only on the AS login page
(``/oauth/authorize``); the BFF drives a real Authorization Code + PKCE
exchange against the same in-process AS, authenticated as ``web-bff``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Final
from urllib.parse import urlencode
from uuid import UUID

import structlog
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.audit import AuditLog
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.secrets import EnvelopeCipher, SecretDecryptionError
from app.modules.auth.application.keys import AccessTokenCodec
from app.modules.auth.application.oauth_server import ErpAuthorizationServer, ErpOAuth2Request
from app.modules.auth.application.ports import AuthStore
from app.modules.auth.application.revocation import RevocationCache
from app.modules.auth.application.tokens import RequestMeta, token_hash
from app.modules.auth.domain.constants import WEB_BFF_CLIENT_ID
from app.modules.auth.domain.models import AuthenticatedUser

log = structlog.get_logger(__name__)

LOGIN_STATE_TTL_S: Final = 600
REFRESH_SKEW_S: Final = 60  # refresh a little before ``exp``


@dataclass(frozen=True, slots=True)
class BffSession:
    sid: str
    user_id: str
    tenant_id: str
    access_token: str
    access_exp: int
    refresh_token: str
    absolute_exp: int


@dataclass(frozen=True, slots=True)
class LoginStart:
    login_id: str
    authorize_url: str


class BffError(Exception):
    def __init__(self, code: ErrorCode, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def safe_return_to(value: str | None) -> str:
    """Only same-site relative paths (open-redirect guard)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class BffService:
    def __init__(
        self,
        *,
        server: ErpAuthorizationServer,
        codec: AccessTokenCodec,
        repo: AuthStore,
        revocation: RevocationCache,
        audit: AuditLog,
        cipher: EnvelopeCipher,
        redis: Callable[[], Redis],
        issuer: str,
        client_secret: str,
        session_absolute_s: int,
        refresh_lock_ttl_s: int,
    ) -> None:
        self._server = server
        self._codec = codec
        self._repo = repo
        self._revocation = revocation
        self._audit = audit
        self._cipher = cipher
        self._redis = redis
        self._issuer = issuer
        self._basic = "Basic " + base64.b64encode(f"{WEB_BFF_CLIENT_ID}:{client_secret}".encode()).decode()
        self._absolute_s = session_absolute_s
        self._lock_ttl = refresh_lock_ttl_s

    @property
    def redirect_uri(self) -> str:
        return f"{self._issuer}/auth/callback"

    # --- login -----------------------------------------------------------------------------------
    async def start_login(self, return_to: str | None, tenant_id: UUID | None) -> LoginStart:
        login_id = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        record = {"state": state, "verifier": verifier, "return_to": safe_return_to(return_to)}
        await self._redis().set(f"bff:login:{_digest(login_id)}", json.dumps(record), ex=LOGIN_STATE_TTL_S)
        params = {
            "response_type": "code",
            "client_id": WEB_BFF_CLIENT_ID,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": create_s256_code_challenge(verifier),
            "code_challenge_method": "S256",
        }
        if tenant_id is not None:
            params["tenant_id"] = str(tenant_id)
        return LoginStart(login_id, f"{self._issuer}/oauth/authorize?{urlencode(params)}")

    async def complete_login(
        self, login_id: str | None, code: str | None, state: str | None, meta: RequestMeta
    ) -> tuple[BffSession, str]:
        if not login_id:
            raise BffError(ErrorCode.UNAUTHORIZED, "login_state_missing")
        raw = await self._redis().getdel(f"bff:login:{_digest(login_id)}")
        if not raw:
            raise BffError(ErrorCode.UNAUTHORIZED, "login_state_expired")
        record: dict[str, str] = json.loads(raw)
        # login-CSRF / session fixation: the callback must carry the state we issued to this browser
        if not state or not hmac.compare_digest(state, record["state"]):
            raise BffError(ErrorCode.UNAUTHORIZED, "state_mismatch")
        if not code:
            raise BffError(ErrorCode.UNAUTHORIZED, "authorization_denied")
        body = await self._token_call(
            [
                ("grant_type", "authorization_code"),
                ("code", code),
                ("redirect_uri", self.redirect_uri),
                ("code_verifier", record["verifier"]),
            ],
            meta,
        )
        session = await self._store_tokens(body)
        return session, record["return_to"]

    async def login_direct(
        self, user_id: UUID, tenant_id: UUID, meta: RequestMeta, *, method: str
    ) -> BffSession:
        """First-party login without the password page — right after signup or a Google login.

        The identity is already proven (verified OTP + new credentials, or a verified Google ID
        token), so the BFF issues itself a one-time code with a fresh PKCE pair and runs the very
        same ``authorization_code`` exchange as ``/auth/callback`` (14 §2.1): same session row,
        same cookie, same subscription/membership checks.
        """
        session = await self._direct_exchange(user_id, tenant_id, meta)
        await self._audit.write(
            tenant_id=tenant_id, user_id=user_id, action="login_success", entity="users", entity_id=user_id,
            ip=meta.ip, after={"method": method},
        )  # fmt: skip
        return session

    async def switch_tenant(
        self, sid: UUID, user_id: UUID, from_tenant: UUID, to_tenant: UUID, meta: RequestMeta
    ) -> BffSession:
        """``POST /bff/switch-tenant`` (14 §9): a new session in ``to_tenant``, the old one dies.

        The identity is the live cookie session; the target tenant is never trusted from the
        client — the membership is checked here and again (with the subscription, 14 §16.1.2) by
        the server-side ``authorization_code`` exchange. Only after the new session exists is the
        old ``sid`` revoked together with its refresh family and that family's live access
        tokens (``sid``/``fam`` markers) — a failed switch leaves the current session untouched.
        """
        ctx = await self._repo.membership_context(to_tenant, user_id)
        if ctx is None or ctx.status != "active":
            raise BffError(ErrorCode.PERMISSION_DENIED, "membership_inactive")
        old = await self.session(sid)
        new = await self._direct_exchange(user_id, to_tenant, meta)
        family = None
        if old is not None:
            row = await self._repo.lookup_refresh(token_hash(old.refresh_token))
            family = row.family_id if row is not None else None
        await self._repo.revoke_session(sid, "tenant_switch")
        await self._revocation.mark_revoked(sids=[sid], families=[family])
        await self.drop(sid)
        await self._audit.write(
            tenant_id=from_tenant, user_id=user_id, action="session_revoked", entity="sessions",
            entity_id=sid, ip=meta.ip, after={"reason": "tenant_switch"},
        )  # fmt: skip
        await self._audit.write(
            tenant_id=to_tenant, user_id=user_id, action="tenant_switched", entity="sessions",
            entity_id=UUID(new.sid), ip=meta.ip, after={"from_tenant_id": str(from_tenant)},
        )  # fmt: skip
        return new

    async def _direct_exchange(self, user_id: UUID, tenant_id: UUID, meta: RequestMeta) -> BffSession:
        """One-time code with a fresh PKCE pair, redeemed through the in-process ``/oauth/token``."""
        await self._server.clients.refresh()
        client = self._server.clients.get(WEB_BFF_CLIENT_ID)
        if client is None:
            raise BffError(ErrorCode.UNAUTHORIZED, "client_unavailable")
        verifier = secrets.token_urlsafe(64)
        code = secrets.token_urlsafe(32)
        await self._server.tokens.save_code(
            code,
            client,
            AuthenticatedUser(user_id, tenant_id),
            create_s256_code_challenge(verifier),
            self.redirect_uri,
            client.get_allowed_scope(None),
        )
        body = await self._token_call(
            [
                ("grant_type", "authorization_code"),
                ("code", code),
                ("redirect_uri", self.redirect_uri),
                ("code_verifier", verifier),
            ],
            meta,
        )
        return await self._store_tokens(body)

    # --- per request -----------------------------------------------------------------------------
    async def session(self, sid: UUID) -> BffSession | None:
        try:
            raw = await self._redis().get(f"bff:sess:{sid}")
        except RedisError:
            log.warning("bff_session_store_unavailable")
            return None
        if not raw:
            return None
        try:
            data = json.loads(self._cipher.decrypt(str(raw), f"bff_session:{sid}".encode()))
        except (SecretDecryptionError, ValueError):
            return None
        return BffSession(**data)

    async def fresh_session(self, sid: UUID, meta: RequestMeta, *, force: bool = False) -> BffSession | None:
        """Session with a usable access token; one refresh per sid at a time (single-flight).

        ``force=True`` refreshes even a still-valid access token — "claims stale" (14 §5): the
        new token carries the current roles/branches.
        """
        current = await self.session(sid)
        if current is None:
            return None
        if not force and current.access_exp - REFRESH_SKEW_S > time.time():
            return current
        seen = current.access_token
        lock_key = f"bff:refresh_lock:{sid}"
        token = secrets.token_hex(8)
        if await self._redis().set(lock_key, token, nx=True, ex=self._lock_ttl):
            try:
                current = await self.session(sid)
                if current is None or current.access_token != seen:
                    return current  # refreshed by someone else meanwhile
                return await self._refresh(current, meta)
            finally:
                if await self._redis().get(lock_key) == token:
                    await self._redis().delete(lock_key)
        # another request is refreshing: wait for its result instead of presenting the same RT
        deadline = time.monotonic() + self._lock_ttl
        while time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            current = await self.session(sid)
            if current is None:
                return None
            if current.access_token != seen or not await self._redis().exists(lock_key):
                return current if current.access_exp > time.time() else None
        return None

    async def _refresh(self, current: BffSession, meta: RequestMeta) -> BffSession | None:
        try:
            body = await self._token_call(
                [("grant_type", "refresh_token"), ("refresh_token", current.refresh_token)], meta
            )
        except BffError as exc:
            if exc.code is ErrorCode.SUBSCRIPTION_RESTRICTED:
                raise AppError(
                    ErrorCode.SUBSCRIPTION_RESTRICTED, params={"tenant_id": current.tenant_id}
                ) from exc
            await self.drop(UUID(current.sid))
            return None
        return await self._store_tokens(body)

    # --- logout ----------------------------------------------------------------------------------
    async def logout(self, sid: UUID, user_id: UUID, tenant_id: UUID, meta: RequestMeta) -> None:
        await self._repo.revoke_session(sid, "logout")
        await self._revocation.mark_sessions_revoked([sid])
        await self.drop(sid)
        await self._audit.write(
            tenant_id=tenant_id, user_id=user_id, action="session_revoked", entity="sessions", entity_id=sid,
            ip=meta.ip, after={"reason": "logout"},
        )  # fmt: skip

    async def revoke_all(self, user_id: UUID, tenant_id: UUID, meta: RequestMeta) -> int:
        """``/auth/sessions/revoke-all`` — every session of the user in every tenant."""
        sids = await self._repo.list_user_sessions(user_id, None)
        count = await self._repo.revoke_user(user_id, None, "user_revoke_all")
        await self._revocation.mark_sessions_revoked(sids)
        await self._revocation.mark_user_revoked(user_id, None)
        for sid in sids:
            await self.drop(sid)
        await self._audit.write(
            tenant_id=tenant_id, user_id=user_id, action="all_sessions_revoked", entity="users",
            entity_id=user_id, ip=meta.ip, after={"sessions": count, "initiator": "self"},
        )  # fmt: skip
        return count

    async def drop(self, sid: UUID) -> None:
        try:
            await self._redis().delete(f"bff:sess:{sid}")
        except RedisError:
            log.warning("bff_session_store_unavailable")

    # --- internals -------------------------------------------------------------------------------
    async def _token_call(self, form: list[tuple[str, str]], meta: RequestMeta) -> dict[str, Any]:
        request = ErpOAuth2Request(
            "POST",
            f"{self._issuer}/oauth/token",
            {"Authorization": self._basic, "Content-Type": "application/x-www-form-urlencoded"},
            form=form,
            meta=meta,
        )
        status, body, _ = await self._server.token(request)
        if status != 200 or not isinstance(body, dict):
            error = body.get("error") if isinstance(body, dict) else "server_error"
            reason = body.get("error_description") if isinstance(body, dict) else None
            code = (
                ErrorCode.SUBSCRIPTION_RESTRICTED
                if reason == "subscription_restricted"
                else ErrorCode.TOKEN_REVOKED
                if error == "invalid_grant"
                else ErrorCode.UNAUTHORIZED
            )
            raise BffError(code, str(reason or error))
        return body

    async def _store_tokens(self, body: dict[str, Any]) -> BffSession:
        claims = await self._codec.verify(str(body["access_token"]))
        sid = str(claims["sid"])
        existing = await self.session(UUID(sid))
        absolute = existing.absolute_exp if existing else int(time.time()) + self._absolute_s
        session = BffSession(
            sid=sid,
            user_id=str(claims["sub"]),
            tenant_id=str(claims["tenant_id"]),
            access_token=str(body["access_token"]),
            access_exp=int(claims["exp"]),
            refresh_token=str(body["refresh_token"]),
            absolute_exp=absolute,
        )
        sealed = self._cipher.encrypt(json.dumps(asdict(session)).encode(), f"bff_session:{sid}".encode())
        await self._redis().set(f"bff:sess:{sid}", sealed, ex=max(1, absolute - int(time.time())))
        return session
