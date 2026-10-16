"""Token issuance, refresh rotation, revocation and introspection (14 §5, §7, §16).

Async business logic behind the Authlib grants (``oauth_server.py``). It raises
Authlib ``OAuth2Error`` subclasses so the RFC 6749 §5.2 error bodies come out
unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749 import InvalidGrantError, InvalidScopeError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.audit import AuditLog
from app.core.db.base import uuid7
from app.modules.auth.application.keys import AccessTokenCodec, InvalidAccessTokenError
from app.modules.auth.application.revocation import RevocationCache
from app.modules.auth.application.subscription import SubscriptionStatusService
from app.modules.auth.domain.constants import LOCKED_SUBSCRIPTION_STATES, SCOPE_SYNC_DRAIN
from app.modules.auth.domain.models import (
    AccessCredential,
    AuthenticatedUser,
    AuthorizationCode,
    OAuthClient,
    RefreshCredential,
)
from app.modules.auth.domain.scopes import effective_scopes, scope_to_set, scope_to_str
from app.modules.auth.infrastructure.repositories import AuthRepository, ClientRow, MembershipContext

log = structlog.get_logger(__name__)

REFRESH_GRACE_S: Final = 30  # REFRESH_REUSE_GRACE_S (14 §7) — fixed in app.auth_rotate_refresh


def token_hash(token: str) -> str:
    """SHA-256 of a high-entropy token (codes, refresh tokens — 14 §7)."""
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class TokenPolicy:
    access_ttl_s: int
    drain_ttl_s: int
    code_ttl_s: int
    session_idle_s: int
    session_absolute_s: int


class SubscriptionLockedError(OAuth2Error):  # type: ignore[misc]
    """14 §16.1.2: no token for a restricted tenant; the body tells the client why."""

    error = "access_denied"
    status_code = 403

    def __init__(self, tenant_id: UUID, status: str) -> None:
        super().__init__(description="subscription_restricted")
        self.tenant_id = tenant_id
        self.sub_status = status

    def get_body(self) -> list[tuple[str, Any]]:
        body: list[tuple[str, Any]] = super().get_body()
        return [*body, ("tenant_id", str(self.tenant_id)), ("sub_status", self.sub_status)]


class ClientRegistry:
    """``platform.oauth_clients`` in memory (5 rows), secrets decrypted with the KEK."""

    _TTL_S: Final = 60.0

    def __init__(self, repo: AuthRepository, decrypt_secret: Callable[[ClientRow], str | None]) -> None:
        self._repo = repo
        self._decrypt = decrypt_secret
        self._by_client_id: dict[str, OAuthClient] = {}
        self._by_id: dict[UUID, OAuthClient] = {}
        self._loaded_at = 0.0

    async def refresh(self, *, force: bool = False) -> None:
        if not force and self._by_client_id and time.monotonic() - self._loaded_at < self._TTL_S:
            return
        clients: list[OAuthClient] = []
        for row in await self._repo.list_clients():
            if row.status != "active":
                continue  # pending_secret / disabled clients do not exist for the AS (12 §2.1)
            secret = self._decrypt(row) if row.client_type == "confidential" else None
            if row.client_type == "confidential" and not secret:
                continue
            clients.append(
                OAuthClient(
                    row.id, row.client_id, row.client_type, row.name, secret, row.redirect_uris,
                    row.allowed_grant_types, row.allowed_scopes,
                )
            )  # fmt: skip
        self._by_client_id = {c.client_id: c for c in clients}
        self._by_id = {c.id: c for c in clients}
        self._loaded_at = time.monotonic()

    def get(self, client_id: str | None) -> OAuthClient | None:
        return self._by_client_id.get(client_id or "")

    def by_db_id(self, client_db_id: UUID) -> OAuthClient | None:
        return self._by_id.get(client_db_id)


class _GraceCache:
    """Response of the last rotation, replayed for a retried RT within 30 s (14 §7).

    Encrypted with a key derived from the presented (old) refresh token, so
    Redis alone never reveals the new token pair.
    """

    def __init__(self, redis: Callable[[], Redis]) -> None:
        self._redis = redis

    @staticmethod
    def _key(token: str) -> AESGCM:
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"erp-refresh-grace")
        return AESGCM(hkdf.derive(token.encode()))

    async def put(self, token: str, response: dict[str, Any]) -> None:
        nonce = os.urandom(12)
        sealed = self._key(token).encrypt(nonce, json.dumps(response).encode(), None)
        try:
            await self._redis().set(
                f"auth:rt_grace:{token_hash(token)}",
                base64.b64encode(nonce + sealed).decode(),
                ex=REFRESH_GRACE_S,
            )
        except RedisError:
            log.warning("refresh_grace_cache_unavailable")

    async def get(self, token: str) -> dict[str, Any] | None:
        try:
            raw = await self._redis().get(f"auth:rt_grace:{token_hash(token)}")
        except RedisError:
            return None
        if not raw:
            return None
        blob = base64.b64decode(raw)
        try:
            data: dict[str, Any] = json.loads(self._key(token).decrypt(blob[:12], blob[12:], None))
        except (InvalidTag, ValueError):
            return None
        return data


class TokenService:
    def __init__(
        self,
        repo: AuthRepository,
        clients: ClientRegistry,
        codec: AccessTokenCodec,
        revocation: RevocationCache,
        subscriptions: SubscriptionStatusService,
        audit: AuditLog,
        redis: Callable[[], Redis],
        policy: TokenPolicy,
    ) -> None:
        self._repo = repo
        self.clients = clients
        self._codec = codec
        self._revocation = revocation
        self._subs = subscriptions
        self._audit = audit
        self._grace = _GraceCache(redis)
        self._policy = policy

    # --- authorization code ------------------------------------------------------------------
    async def save_code(
        self,
        code: str,
        client: OAuthClient,
        user: AuthenticatedUser,
        code_challenge: str,
        redirect_uri: str,
        scope: str,
    ) -> None:
        await self._repo.issue_code(
            code_hash=token_hash(code), client_id=client.id, user_id=user.user_id, tenant_id=user.tenant_id,
            code_challenge=code_challenge, redirect_uri=redirect_uri, scope=scope,
            ttl_s=self._policy.code_ttl_s,
        )  # fmt: skip

    async def consume_code(self, code: str, client: OAuthClient) -> AuthorizationCode | None:
        """Single use: the code is burnt on the first exchange attempt, even a failed one."""
        row = await self._repo.consume_code(token_hash(code))
        if row is None or row.client_id != client.id or row.tenant_id is None:
            return None
        return AuthorizationCode(
            row.client_id, row.user_id, row.tenant_id, row.code_challenge, row.code_challenge_method,
            row.redirect_uri, row.scope,
        )  # fmt: skip

    async def issue_for_code(
        self, client: OAuthClient, code: AuthorizationCode, meta: RequestMeta
    ) -> dict[str, Any]:
        assert code.tenant_id is not None
        ctx = await self._active_membership(code.tenant_id, code.user_id)
        sub_status = await self._subscription_ok(code.tenant_id)
        scopes = effective_scopes(code.scope, ctx.permission_codes)
        refresh = secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        idle = now + timedelta(seconds=self._policy.session_idle_s)
        absolute = now + timedelta(seconds=self._policy.session_absolute_s)
        issued = await self._repo.issue_tokens(
            user_id=code.user_id, tenant_id=code.tenant_id, client_id=client.id, device_id=None,
            refresh_hash=token_hash(refresh), refresh_expires_at=min(idle, absolute), scope=code.scope,
            with_session=client.is_bff, idle_expires_at=idle if client.is_bff else None,
            absolute_expires_at=absolute if client.is_bff else None, ip=meta.ip, user_agent=meta.user_agent,
        )  # fmt: skip
        access, ttl = await self._mint(
            client, code.user_id, code.tenant_id, scopes, ctx, issued.session_id, None, sub_status,
            family_id=issued.family_id,
        )  # fmt: skip
        return self._response(access, ttl, refresh, scopes)

    # --- refresh token -------------------------------------------------------------------------
    async def lookup_refresh(self, token: str) -> RefreshCredential | None:
        row = await self._repo.lookup_refresh(token_hash(token))
        if row is None:
            return None
        return RefreshCredential(
            token=token, token_hash=token_hash(token), client_db_id=row.client_id, user_id=row.user_id,
            tenant_id=row.tenant_id, scope=row.scope, expires_at=row.expires_at,
            revoked=row.revoked_at is not None or row.used_at is not None,
            family_issued_at=row.family_issued_at, session_id=row.session_id,
        )  # fmt: skip

    async def refresh(
        self,
        client: OAuthClient,
        credential: RefreshCredential,
        requested_scope: str | None,
        meta: RequestMeta,
    ) -> dict[str, Any]:
        row = await self._repo.lookup_refresh(credential.token_hash)
        if row is None or row.tenant_id is None or row.client_id != client.id:
            raise InvalidGrantError()
        tenant_id = row.tenant_id
        fresh = row.used_at is None and row.revoked_at is None
        ctx: MembershipContext | None = None
        sub_status: str | None = None
        if fresh:
            # checks that must not burn the token: membership and subscription (14 §7 "Obuna tekshiruvi")
            ctx = await self._active_membership(tenant_id, row.user_id)
            if row.suspended_at is None:
                sub_status = await self._subscription_ok(tenant_id)
            elif requested_scope and scope_to_set(requested_scope) != {SCOPE_SYNC_DRAIN}:
                # 14 §16.4(2): a suspended family yields sync.drain only; anything else is refused
                # before rotation so the token is not burnt
                raise InvalidScopeError(description="suspended_sync_drain_only")
        now = datetime.now(UTC)
        new_expires = min(
            now + timedelta(seconds=self._policy.session_idle_s),
            row.family_issued_at + timedelta(seconds=self._policy.session_absolute_s),
        )
        if new_expires <= now:
            raise InvalidGrantError(description="refresh_token_expired")
        new_refresh = secrets.token_urlsafe(48)
        result = await self._repo.rotate_refresh(credential.token_hash, token_hash(new_refresh), new_expires)

        if result.outcome == "grace_replay":
            cached = await self._grace.get(credential.token)
            if cached is None:
                raise InvalidGrantError()
            return cached
        if result.outcome == "reuse_revoked":
            await self._on_reuse(row.user_id, tenant_id, row.session_id, row.family_id, meta)
            raise InvalidGrantError(description="refresh_token_reused")
        if result.outcome != "rotated" or ctx is None:
            raise InvalidGrantError()

        if result.suspended:
            # 14 §16.4: a suspended family only yields a short sync.drain token
            scopes: frozenset[str] = frozenset({SCOPE_SYNC_DRAIN})
            ttl = self._policy.drain_ttl_s
            sub_status = "restricted"
        else:
            ceiling = requested_scope or row.scope
            scopes = effective_scopes(ceiling, ctx.permission_codes)
            ttl = self._policy.access_ttl_s
        access, ttl = await self._mint(
            client, row.user_id, tenant_id, scopes, ctx, row.session_id, row.device_id, sub_status,
            ttl=ttl, family_id=row.family_id,
        )  # fmt: skip
        if row.session_id is not None:
            await self._repo.touch_session(
                row.session_id, now + timedelta(seconds=self._policy.session_idle_s)
            )
        response = self._response(access, ttl, new_refresh, scopes)
        await self._grace.put(credential.token, response)
        return response

    async def _on_reuse(
        self, user_id: UUID, tenant_id: UUID, sid: UUID | None, family_id: UUID | None, meta: RequestMeta
    ) -> None:
        # app.auth_rotate_refresh already revoked the family and its sessions (14 §7, QT-OAUTH-03):
        # only the reused family's access tokens die — the user's other sessions/devices survive
        if sid is not None:
            await self._revocation.mark_sessions_revoked([sid])
        elif family_id is not None:
            await self._revocation.mark_family_revoked(family_id)  # sid-less tokens carry ``fam``
        else:
            await self._revocation.mark_user_revoked(user_id, tenant_id)  # last-resort fallback
        await self._audit.write(
            tenant_id=tenant_id, user_id=user_id, action="refresh_token_reuse_detected", entity="sessions",
            entity_id=sid, ip=meta.ip,
        )  # fmt: skip
        log.warning("refresh_token_reuse_detected", user_id=str(user_id), tenant_id=str(tenant_id))

    # --- revocation / introspection ------------------------------------------------------------
    async def query_token(self, token: str, hint: str | None) -> AccessCredential | RefreshCredential | None:
        looks_like_jwt = token.count(".") == 2
        if looks_like_jwt and hint != "refresh_token":
            try:
                claims = await self._codec.verify(token, verify_exp=False)
            except InvalidAccessTokenError:
                return None
            client = self.clients.get(str(claims.get("client_id")))
            revoked = await self._revocation.is_revoked(claims)
            return AccessCredential(token, claims, client.id if client else None, revoked)
        if not looks_like_jwt:
            return await self.lookup_refresh(token)
        return None

    async def revoke(self, credential: AccessCredential | RefreshCredential, meta: RequestMeta) -> None:
        if isinstance(credential, RefreshCredential):
            revoked = await self._repo.revoke_refresh_family(credential.token_hash, "revoked_by_client")
            if revoked is None:
                return
            sid, user_id, tenant_id = revoked.session_id, revoked.user_id, revoked.tenant_id
        else:
            claims = credential.claims
            sid = UUID(claims["sid"]) if claims.get("sid") else None
            user_id, tenant_id = UUID(claims["sub"]), UUID(claims["tenant_id"])
            if sid is not None:
                await self._repo.revoke_session(sid, "revoked_by_client")
            await self._revocation.mark_jti_revoked(str(claims["jti"]), int(claims["exp"]))
        await self._revocation.mark_sessions_revoked([sid])
        if sid is not None and tenant_id is not None:
            await self._audit.write(
                tenant_id=tenant_id, user_id=user_id, action="session_revoked", entity="sessions",
                entity_id=sid, ip=meta.ip, after={"reason": "revoked_by_client"},
            )  # fmt: skip

    def introspect(self, credential: AccessCredential | RefreshCredential) -> dict[str, Any]:
        if isinstance(credential, AccessCredential):
            c = credential.claims
            payload: dict[str, Any] = {
                k: c[k]
                for k in ("scope", "client_id", "sub", "exp", "iat", "iss", "aud", "jti", "tenant_id", "sid")
                if k in c
            }
            return {"active": True, "token_type": "Bearer", **payload}
        client = self.clients.by_db_id(credential.client_db_id)
        return {
            "active": True,
            "token_type": "refresh_token",
            "scope": credential.scope,
            "client_id": client.client_id if client else None,
            "sub": str(credential.user_id),
            "exp": int(credential.expires_at.timestamp()),
            "tenant_id": str(credential.tenant_id) if credential.tenant_id else None,
        }

    # --- helpers -------------------------------------------------------------------------------
    async def _active_membership(self, tenant_id: UUID, user_id: UUID) -> MembershipContext:
        ctx = await self._repo.membership_context(tenant_id, user_id)
        if ctx is None or ctx.status != "active":
            raise InvalidGrantError(description="membership_inactive")
        return ctx

    async def _subscription_ok(self, tenant_id: UUID) -> str:
        status = await self._subs.status(tenant_id)
        if status in LOCKED_SUBSCRIPTION_STATES:
            raise SubscriptionLockedError(tenant_id, status)
        return status

    async def _mint(
        self,
        client: OAuthClient,
        user_id: UUID,
        tenant_id: UUID,
        scopes: frozenset[str],
        ctx: MembershipContext,
        sid: UUID | None,
        device_id: UUID | None,
        sub_status: str | None,
        *,
        ttl: int | None = None,
        family_id: UUID | None = None,
    ) -> tuple[str, int]:
        ttl = ttl or self._policy.access_ttl_s
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(user_id),
            "client_id": client.client_id,
            "iat": now,
            "exp": now + ttl,
            "jti": str(uuid7()),
            "tenant_id": str(tenant_id),
            "branch_ids": [str(b) for b in ctx.branch_ids],
            "roles": list(ctx.role_codes),
            "scope": scope_to_str(scopes),
            "sub_status": sub_status,
        }
        if sid is not None:
            claims["sid"] = str(sid)
        elif family_id is not None:
            claims["fam"] = str(family_id)  # revocation key of a sid-less refresh family (14 §7)
        if device_id is not None:
            claims["device_id"] = str(device_id)
        return await self._codec.mint(claims), ttl

    @staticmethod
    def _response(access: str, ttl: int, refresh: str, scopes: frozenset[str]) -> dict[str, Any]:
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": ttl,
            "refresh_token": refresh,
            "scope": scope_to_str(scopes),
        }
