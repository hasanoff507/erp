"""Resource Server: Bearer JWT or BFF cookie → :class:`Principal` (14 §2.1, §5; 23 §3 steps 2–3).

Besides signature/expiry and the sid/jti/user revocation cache, every request passes the
:class:`AccessGuard`:

* **revoked device** (16 §9, 14 §21 "Qurilma bekor qilish") — a token whose ``device_id`` claim points
  to a device with ``app.devices.revoked_at`` set gets ``403 DEVICE_REVOKED``. Redis keeps
  ``auth:device_revoked:{device}`` (set by :func:`mark_device_revoked` — immediate) and a short
  positive cache ``auth:device_ok:{device}``; a cache miss reads the database.
* **claims stale** (14 §5) — after an owner changes a user's ``role_ids``/``branch_ids``,
  ``auth:claims_stale:{tenant}:{user}`` holds a watermark; an access token issued up to it whose
  ``roles``/``branch_ids`` differ from the live membership is re-issued: the BFF refreshes the cookie
  session server-side, a Bearer client gets ``401 TOKEN_EXPIRED`` and refreshes. Permissions and
  branch scope never trust the claims (they are read live), so this only refreshes the token claims.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.requests import Request

from app.core.auth.principal import Principal
from app.core.auth.tokens import CsrfTokens, SessionCookieSigner
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.auth.application.admin_ports import DeviceStatusReader
from app.modules.auth.application.bff import BffService, BffSession
from app.modules.auth.application.keys import AccessTokenCodec, InvalidAccessTokenError
from app.modules.auth.application.ports import AuthStore
from app.modules.auth.application.revocation import RevocationCache, TokenRevokedError
from app.modules.auth.application.subscription import SubscriptionStatusService
from app.modules.auth.application.tokens import RequestMeta
from app.modules.auth.domain.constants import CSRF_HEADER, SID_COOKIE
from app.modules.auth.domain.scopes import scope_to_set

log = structlog.get_logger(__name__)

SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})
_BEARER_CHALLENGE: Final = {"WWW-Authenticate": 'Bearer error="invalid_token"'}
DEVICE_REVOKED_MARKER_S: Final = 86400  # the database stays authoritative after the marker expires


def request_meta(request: Request) -> RequestMeta:
    ip = request.client.host if request.client else None
    return RequestMeta(ip=ip, user_agent=(request.headers.get("user-agent") or "")[:512] or None)


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _device_revoked_key(device_id: str) -> str:
    return f"auth:device_revoked:{device_id}"


def _device_ok_key(device_id: str) -> str:
    return f"auth:device_ok:{device_id}"


def _claims_stale_key(tenant_id: str, user_id: str) -> str:
    return f"auth:claims_stale:{tenant_id}:{user_id}"


async def mark_device_revoked(redis: Redis, device_id: UUID) -> None:
    """Call right after ``app.devices.revoked_at`` is committed (``POST /devices/{id}/revoke``, 20 #29b).

    Makes the rejection immediate; without it the RS notices within the positive-cache TTL
    (``session_check_cache_s``) through the database fallback.
    """
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.set(_device_revoked_key(str(device_id)), "1", ex=DEVICE_REVOKED_MARKER_S)
            pipe.delete(_device_ok_key(str(device_id)))
            await pipe.execute()
    except RedisError:
        log.warning("device_revoke_cache_unavailable", device_id=str(device_id))


class DeviceRevokedError(Exception):
    pass


GuardVerdict = Literal["ok", "stale"]


class AccessGuard:
    """Per-request revoked-device and claims-stale check — one Redis ``MGET``."""

    def __init__(
        self,
        devices: DeviceStatusReader,
        redis: Callable[[], Redis],
        *,
        access_ttl_s: int,
        device_check_cache_s: int,
    ) -> None:
        self._devices = devices
        self._redis = redis
        self._stale_ttl = access_ttl_s + 120
        self._ok_ttl = device_check_cache_s

    async def mark_claims_stale(self, tenant_id: UUID, user_id: UUID) -> None:
        # whole seconds: ``iat`` is an integer, a token issued later in the same second is current
        try:
            await self._redis().set(
                _claims_stale_key(str(tenant_id), str(user_id)), str(int(time.time())), ex=self._stale_ttl
            )
        except RedisError:
            log.warning("claims_stale_cache_unavailable", user_id=str(user_id))

    async def mark_device_revoked(self, device_id: UUID) -> None:
        await mark_device_revoked(self._redis(), device_id)

    async def check(self, claims: dict[str, Any]) -> GuardVerdict:
        """Raise :class:`DeviceRevokedError`; ``"stale"`` = re-issue the access token."""
        tenant, user = str(claims["tenant_id"]), str(claims["sub"])
        device = _uuid(claims.get("device_id"))
        keys = [_claims_stale_key(tenant, user)]
        if device is not None:
            keys += [_device_revoked_key(str(device)), _device_ok_key(str(device))]
        values: list[Any] | None
        try:
            values = await self._redis().mget(keys)
        except RedisError:
            values = None
        if device is not None:
            if values is not None and values[1]:
                raise DeviceRevokedError
            if values is None or not values[2]:
                await self._check_device_row(UUID(tenant), device, cache=values is not None)
        watermark = int(values[0]) if values is not None and values[0] else 0
        # same second counts: the gateway then compares the claims with the live membership
        return "stale" if watermark and int(claims["iat"]) <= watermark else "ok"

    async def _check_device_row(self, tenant_id: UUID, device_id: UUID, *, cache: bool) -> None:
        revoked = await self._devices.device_revoked(tenant_id, device_id)
        if cache:
            key = _device_revoked_key(str(device_id)) if revoked else _device_ok_key(str(device_id))
            with contextlib.suppress(RedisError):
                await self._redis().set(key, "1", ex=DEVICE_REVOKED_MARKER_S if revoked else self._ok_ttl)
        if revoked:
            raise DeviceRevokedError


class ErpAuthGateway:
    def __init__(
        self,
        *,
        codec: AccessTokenCodec,
        revocation: RevocationCache,
        subscriptions: SubscriptionStatusService,
        repo: AuthStore,
        bff: BffService,
        cookies: SessionCookieSigner,
        csrf: CsrfTokens,
        guard: AccessGuard | None = None,
    ) -> None:
        self._codec = codec
        self._revocation = revocation
        self._subs = subscriptions
        self._repo = repo
        self._bff = bff
        self._cookies = cookies
        self._csrf = csrf
        self._guard = guard

    async def authenticate(self, request: Request) -> Principal:
        header = request.headers.get("authorization")
        if header is not None:
            scheme, _, token = header.partition(" ")
            if scheme.lower() != "bearer" or not token.strip():
                raise AppError(ErrorCode.UNAUTHORIZED, headers=_BEARER_CHALLENGE)
            claims = await self._verify(token.strip(), bearer=True)
            if await self._guarded(claims) == "stale":
                # 14 §5 claims stale: the client refreshes and gets the current roles/branches
                raise AppError(ErrorCode.TOKEN_EXPIRED, headers=_BEARER_CHALLENGE)
            return self._principal(claims, via_cookie=False)

        sid = self._cookies.unsign(request.cookies.get(SID_COOKIE))
        if sid is None:
            raise AppError(ErrorCode.UNAUTHORIZED)
        # 15 §1.3 / 23 §3 step 2: CSRF before anything else on cookie-authenticated writes
        if request.method not in SAFE_METHODS and not self._csrf.verify(
            request.headers.get(CSRF_HEADER), sid
        ):
            raise AppError(ErrorCode.CSRF_INVALID)
        claims = await self._cookie_claims(sid, request, force=False)
        if await self._guarded(claims) == "stale":
            # 14 §5 claims stale: the BFF re-issues the access token with the current roles/branches
            claims = await self._cookie_claims(sid, request, force=True)
            await self._guarded(claims)
        return self._principal(claims, via_cookie=True)

    async def peek_tenant(self, request: Request) -> UUID | None:
        """Idempotency tenant (23 §3): a revoked token/session gets no replay — it falls through to 401."""
        try:
            header = request.headers.get("authorization")
            if header is not None:
                scheme, _, token = header.partition(" ")
                if scheme.lower() != "bearer":
                    return None
                claims = await self._codec.verify(token.strip())
                await self._revocation.check(claims)
                await self._guard_device(claims)
                return _uuid(claims.get("tenant_id"))
            sid = self._cookies.unsign(request.cookies.get(SID_COOKIE))
            if sid is None:
                return None
            session = await self._bff.session(sid)
            if session is None:
                return None
            # the stored token may be past ``exp`` (refreshed later in authenticate); only revocation matters
            claims = await self._codec.verify(session.access_token, verify_exp=False)
            if claims.get("sid") != str(sid):
                return None
            await self._revocation.check(claims)
            await self._guard_device(claims)
            return _uuid(session.tenant_id)
        except (InvalidAccessTokenError, TokenRevokedError, DeviceRevokedError, ValueError, KeyError):
            return None

    async def subscription_status(self, tenant_id: UUID) -> str:
        return await self._subs.status(tenant_id)

    async def permission_limits(self, principal: Principal, code: str) -> list[Decimal | None]:
        return await self._repo.permission_limits(principal.tenant_id, principal.user_id, code)

    async def branch_ids(self, principal: Principal) -> tuple[UUID, ...] | None:
        ctx = await self._repo.membership_context(principal.tenant_id, principal.user_id)
        if ctx is None or ctx.status != "active":
            return None
        return ctx.branch_ids

    async def session_principal(self, session: BffSession) -> Principal:
        """The cookie principal of a session the BFF has just issued (``POST /bff/switch-tenant``)."""
        claims = await self._verify(session.access_token, bearer=False)
        if claims.get("sid") != session.sid:
            raise AppError(ErrorCode.UNAUTHORIZED)
        return self._principal(claims, via_cookie=True)

    def csrf_token(self, sid: UUID) -> str:
        return self._csrf.issue(sid)

    # --- helpers ---------------------------------------------------------------------------------
    async def _cookie_claims(self, sid: UUID, request: Request, *, force: bool) -> dict[str, Any]:
        session = await self._bff.fresh_session(sid, request_meta(request), force=force)
        if session is None:
            raise AppError(ErrorCode.UNAUTHORIZED)
        claims = await self._verify(session.access_token, bearer=False)
        if claims.get("sid") != str(sid):
            raise AppError(ErrorCode.UNAUTHORIZED)
        return claims

    async def _verify(self, token: str, *, bearer: bool) -> dict[str, Any]:
        headers = _BEARER_CHALLENGE if bearer else None
        try:
            claims = await self._codec.verify(token)
        except InvalidAccessTokenError as exc:
            code = ErrorCode.TOKEN_EXPIRED if exc.reason == "expired" else ErrorCode.UNAUTHORIZED
            raise AppError(code, headers=headers) from exc
        try:
            await self._revocation.check(claims)
        except TokenRevokedError as exc:
            raise AppError(ErrorCode.TOKEN_REVOKED, headers=headers) from exc
        return claims

    async def _guarded(self, claims: dict[str, Any]) -> GuardVerdict:
        if self._guard is None:
            return "ok"
        try:
            verdict = await self._guard.check(claims)
        except DeviceRevokedError as exc:
            raise AppError(ErrorCode.DEVICE_REVOKED) from exc
        if verdict == "stale" and await self._claims_current(claims):
            return "ok"  # issued after the change (e.g. within the same second) — nothing to re-issue
        return verdict

    async def _claims_current(self, claims: dict[str, Any]) -> bool:
        """Only while a claims-stale watermark is live: do ``roles``/``branch_ids`` match the membership?"""
        user_id, tenant_id = _uuid(claims.get("sub")), _uuid(claims.get("tenant_id"))
        if user_id is None or tenant_id is None:
            return False
        ctx = await self._repo.membership_context(tenant_id, user_id)
        if ctx is None:
            return True  # nothing to re-issue; the permission/branch checks deny on their own
        roles = sorted(str(r) for r in claims.get("roles") or ())
        branches = {str(b) for b in claims.get("branch_ids") or ()}
        return roles == sorted(ctx.role_codes) and branches == {str(b) for b in ctx.branch_ids}

    async def _guard_device(self, claims: dict[str, Any]) -> None:
        if self._guard is not None:
            await self._guard.check(claims)

    @staticmethod
    def _principal(claims: dict[str, Any], *, via_cookie: bool) -> Principal:
        user_id, tenant_id = _uuid(claims.get("sub")), _uuid(claims.get("tenant_id"))
        if user_id is None or tenant_id is None:
            raise AppError(ErrorCode.UNAUTHORIZED)
        return Principal(
            user_id=user_id,
            tenant_id=tenant_id,
            client_id=str(claims["client_id"]),
            scopes=scope_to_set(str(claims.get("scope", ""))),
            roles=tuple(str(r) for r in claims.get("roles") or ()),
            branch_ids=tuple(b for b in (_uuid(x) for x in claims.get("branch_ids") or ()) if b is not None),
            sid=_uuid(claims.get("sid")),
            device_id=_uuid(claims.get("device_id")),
            jti=str(claims["jti"]),
            issued_at=int(claims["iat"]),
            expires_at=int(claims["exp"]),
            sub_status=claims.get("sub_status"),
            via_cookie=via_cookie,
        )
