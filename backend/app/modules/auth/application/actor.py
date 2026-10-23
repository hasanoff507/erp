"""PIN actor on device sessions — "who pressed" for online REST calls (14 §4.3, 17 §5 ``X-Actor-User-Id``).

A device session (web-POS cookie or Android Bearer) belongs to whoever logged the device in, often the
Owner/Manager who registered it. The staff member at the till proves themself with the PIN
(``POST /auth/pin/verify``, ``purpose=actor``), which makes them the ONE live actor of
``(device, session)`` in Redis for ``ERP_ACTOR_BINDING_TTL_S`` (default 12 h) — a new actor replaces the
previous one, ``POST /auth/pin/release`` (cashier lock/switch, shift close, logout) ends it, and an
approver's PIN check (``purpose=approval``) never binds. Every ``/api/v1`` request of a device
session — reads too (F-4) — must name the actor in ``X-Actor-User-Id`` (exempt: ``/sync/*``, ``/auth/*``);
the RS accepts it only with a live binding and an active membership that may work in the device's
branch. The request then runs **as the actor**
(``Principal.user_id`` → ``created_by``/``posted_by``/audit user), with permissions, limits and branch
scope never wider than the session user's (intersection), and audit rows keep the session's own user
in ``after.on_behalf_session_user``. ``/sync/*`` is exempt: every event carries and is authorized by
its own ``actor_user_id`` (16 §2). Back-office (non-device) sessions are unchanged. Without Redis no
binding can be proven → fail closed.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

log = structlog.get_logger(__name__)

ACTOR_HEADER = "x-actor-user-id"


class ActorBindingUnavailableError(Exception):
    """Redis is down — a binding can be neither recorded nor proven (fail closed)."""


def session_key(sid: UUID | None, family: UUID | None) -> str | None:
    """The device session a binding belongs to: the BFF ``sid``, else the Bearer refresh family."""
    if sid is not None:
        return f"s:{sid}"
    if family is not None:
        return f"f:{family}"
    return None


def _key(device_id: UUID, session: str) -> str:
    return f"auth:actor:{device_id}:{session}"


class ActorBindings:
    """One live actor per device session (SEC-05): a new PIN actor replaces the previous one."""

    def __init__(self, redis: Callable[[], Redis], *, ttl_s: int) -> None:
        self._redis = redis
        self._ttl = ttl_s

    async def bind(self, device_id: UUID, session: str, user_id: UUID) -> None:
        try:
            await self._redis().set(_key(device_id, session), str(user_id), ex=self._ttl)
        except RedisError as exc:
            log.warning("actor_binding_redis_unavailable")
            raise ActorBindingUnavailableError from exc

    async def release(self, device_id: UUID, session: str) -> None:
        try:
            await self._redis().delete(_key(device_id, session))
        except RedisError as exc:
            log.warning("actor_binding_redis_unavailable")
            raise ActorBindingUnavailableError from exc

    async def bound(self, device_id: UUID, session: str, user_id: UUID) -> bool:
        try:
            current = await self._redis().get(_key(device_id, session))
        except RedisError as exc:
            log.warning("actor_binding_redis_unavailable")
            raise ActorBindingUnavailableError from exc
        return current is not None and str(current) == str(user_id)
