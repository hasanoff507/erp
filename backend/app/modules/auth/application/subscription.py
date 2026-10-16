"""``sub_status:{tenant_id}`` cache (14 §16.1.1).

Redis first (60 s); on a miss or a Redis outage the status is read from
``subscriptions`` (fail-to-DB, not fail-closed) and written back. A tenant
without a subscription row is treated as ``restricted`` (conservative).
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.modules.auth.infrastructure.repositories import AuthRepository

log = structlog.get_logger(__name__)

CACHE_TTL_S: Final = 60
MISSING: Final = "restricted"


def cache_key(tenant_id: UUID) -> str:
    return f"sub_status:{tenant_id}"


class SubscriptionStatusService:
    def __init__(self, repo: AuthRepository, redis: Callable[[], Redis]) -> None:
        self._repo = repo
        self._redis = redis

    async def status(self, tenant_id: UUID) -> str:
        try:
            cached = await self._redis().get(cache_key(tenant_id))
        except RedisError:
            cached = None
            log.warning("sub_status_redis_unavailable", tenant_id=str(tenant_id))
        if cached:
            return str(cached)
        status = await self._repo.subscription_status(tenant_id)
        if status is None:
            log.warning("subscription_missing", tenant_id=str(tenant_id))
            status = MISSING
        with contextlib.suppress(RedisError):
            await self._redis().set(cache_key(tenant_id), status, ex=CACHE_TTL_S)
        return status

    async def publish(self, tenant_id: UUID, status: str) -> None:
        """Called by billing/scheduler right after a status change (14 §16.1.5)."""
        await self._redis().set(cache_key(tenant_id), status, ex=CACHE_TTL_S)
