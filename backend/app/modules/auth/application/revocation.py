"""Near-immediate revocation of stateless access tokens (14 §5 "sid — revoke uchun kalit").

Per request the RS does one ``MGET``:

* ``auth:sid_revoked:{sid}`` — session revoked (logout, reuse, admin, block);
* ``auth:jti_revoked:{jti}`` — a single token revoked via ``/oauth/revoke``;
* ``auth:fam_revoked:{family}`` — a refresh family revoked (``/oauth/revoke`` of a refresh
  token, reuse detection, device revoke, tenant switch). Every access token carries its
  family in ``fam`` (BFF tokens also ``sid``), so the family's live access tokens die with
  it (14 §7: only that family dies, other devices of the user survive);
* ``auth:user_revoked:{tenant}:{user}`` / ``auth:user_revoked:*:{user}`` —
  watermark (epoch seconds): tokens issued before it are dead (Android
  tokens have no ``sid``);
* ``auth:sid_ok:{sid}`` — positive cache (30 s) of the DB session check.

Markers live for ``access TTL + 2 min`` — after that the tokens they target
have expired anyway. Without Redis every request falls back to the database and
fails closed (14 §5, SEC-08): a token with ``sid`` is checked against its session
row; a token without ``sid`` (Android/Bearer, device tokens) against its refresh
family (``app.auth_family_revoked`` — revoke-all, admin block, reuse and device
revoke all revoke the family rows); a token with neither is refused.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.modules.auth.application.ports import AuthStore

log = structlog.get_logger(__name__)


class TokenRevokedError(Exception):
    pass


def _as_uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def _sid_revoked(sid: str) -> str:
    return f"auth:sid_revoked:{sid}"


def _sid_ok(sid: str) -> str:
    return f"auth:sid_ok:{sid}"


def _jti_revoked(jti: str) -> str:
    return f"auth:jti_revoked:{jti}"


def _family_revoked(family: str) -> str:
    return f"auth:fam_revoked:{family}"


def _user_revoked(tenant: str, user: str) -> str:
    return f"auth:user_revoked:{tenant}:{user}"


async def mark_revoked_markers(
    redis: Redis, *, sids: Iterable[UUID | None], families: Iterable[UUID | None], ttl_s: int
) -> None:
    """``auth:sid_revoked``/``auth:fam_revoked`` markers — the live access tokens die at once (14 §5)."""
    sid_keys = [str(s) for s in sids if s is not None]
    fam_keys = [str(f) for f in families if f is not None]
    if not sid_keys and not fam_keys:
        return
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for sid in sid_keys:
                pipe.set(_sid_revoked(sid), "1", ex=ttl_s)
                pipe.delete(_sid_ok(sid))
            for family in fam_keys:
                pipe.set(_family_revoked(family), "1", ex=ttl_s)
            await pipe.execute()
    except RedisError:
        log.warning("revoke_cache_unavailable", sessions=len(sid_keys), families=len(fam_keys))


class RevocationCache:
    def __init__(
        self,
        repo: AuthStore,
        redis: Callable[[], Redis],
        *,
        access_ttl_s: int,
        session_check_cache_s: int,
    ) -> None:
        self._repo = repo
        self._redis = redis
        self._marker_ttl = access_ttl_s + 120
        self._ok_ttl = session_check_cache_s

    async def mark_sessions_revoked(self, sids: Iterable[UUID | None]) -> None:
        keys = [str(s) for s in sids if s is not None]
        if not keys:
            return
        try:
            async with self._redis().pipeline(transaction=False) as pipe:
                for sid in keys:
                    pipe.set(_sid_revoked(sid), "1", ex=self._marker_ttl)
                    pipe.delete(_sid_ok(sid))
                await pipe.execute()
        except RedisError:
            log.warning("sid_revoke_cache_unavailable", count=len(keys))

    async def mark_revoked(
        self, *, sids: Iterable[UUID | None] = (), families: Iterable[UUID | None] = ()
    ) -> None:
        """Sessions and refresh families in one pipeline — their live access tokens die at once."""
        await mark_revoked_markers(self._redis(), sids=sids, families=families, ttl_s=self._marker_ttl)

    async def mark_user_revoked(self, user_id: UUID, tenant_id: UUID | None) -> None:
        scope = str(tenant_id) if tenant_id is not None else "*"
        try:
            await self._redis().set(
                _user_revoked(scope, str(user_id)), repr(time.time()), ex=self._marker_ttl
            )
        except RedisError:
            log.warning("user_revoke_cache_unavailable", user_id=str(user_id))

    async def mark_family_revoked(self, family_id: UUID) -> None:
        try:
            await self._redis().set(_family_revoked(str(family_id)), "1", ex=self._marker_ttl)
        except RedisError:
            log.warning("family_revoke_cache_unavailable", family_id=str(family_id))

    async def mark_jti_revoked(self, jti: str, exp: int) -> None:
        ttl = max(1, exp - int(time.time()) + 60)
        try:
            await self._redis().set(_jti_revoked(jti), "1", ex=ttl)
        except RedisError:
            log.warning("jti_revoke_cache_unavailable")

    async def is_revoked(self, claims: dict[str, Any]) -> bool:
        try:
            await self.check(claims)
        except TokenRevokedError:
            return True
        return False

    async def check(self, claims: dict[str, Any]) -> None:
        sid = claims.get("sid")
        family = claims.get("fam")
        user, tenant = str(claims["sub"]), str(claims["tenant_id"])
        keys = [
            _sid_revoked(sid) if sid else "auth:-",
            _jti_revoked(str(claims["jti"])),
            _user_revoked(tenant, user),
            _user_revoked("*", user),
            _sid_ok(sid) if sid else "auth:-",
            _family_revoked(str(family)) if family else "auth:-",
        ]
        values: list[Any] | None
        try:
            values = await self._redis().mget(keys)
        except RedisError:
            values = None
        if values is not None:
            if values[0] or values[1] or values[5]:
                raise TokenRevokedError
            watermark = max(float(values[2] or 0), float(values[3] or 0))
            if watermark and int(claims["iat"]) < watermark:
                raise TokenRevokedError
            if not sid or values[4]:
                return
        if sid:
            await self._check_session_row(UUID(str(sid)), cache=values is not None)
            return
        # --- B3 device-auth --- SEC-08: Redis is down and the token has no session row
        family_id = _as_uuid(family)
        if family_id is None or await self._repo.family_revoked(family_id):
            raise TokenRevokedError

    async def _check_session_row(self, sid: UUID, *, cache: bool) -> None:
        row = await self._repo.session_by_id(sid)
        now = datetime.now(UTC)
        dead = (
            row is None
            or row.revoked_at is not None
            or row.idle_expires_at <= now
            or row.absolute_expires_at <= now
        )
        if cache:
            try:
                if dead:
                    await self._redis().set(_sid_revoked(str(sid)), "1", ex=self._marker_ttl)
                else:
                    await self._redis().set(_sid_ok(str(sid)), "1", ex=self._ok_ttl)
            except RedisError:
                pass
        if dead:
            raise TokenRevokedError
