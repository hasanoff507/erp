"""SAQ enqueue adapter for e-document outbox jobs (23 §4: first job argument is the tenant id) and the
Redis store of E-IMZO sign challenges (21 §5: single use, 10 min)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.db.session import TenantContextError
from app.core.queue import make_queue

_PREFIX = "edoc:challenge:"


class SaqEnqueuer:
    """A short-lived Redis connection per enqueue — the API process keeps no SAQ queue open."""

    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._url = redis_url
        self._name = queue_name

    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> None:
        if not isinstance(tenant_id, UUID):
            raise TenantContextError("jobs are always enqueued for one tenant")
        queue = make_queue(self._url, self._name)
        try:
            await queue.enqueue(job, tenant_id=str(tenant_id), retries=1, timeout=600, **kwargs)
        finally:
            await queue.disconnect()


class RedisChallengeStore:
    def __init__(self, redis: Callable[[], Redis]) -> None:
        self._redis = redis

    async def put(self, challenge_id: str, data: Mapping[str, str], ttl_s: int) -> None:
        await self._redis().set(_PREFIX + challenge_id, json.dumps(dict(data)), ex=ttl_s)

    async def take(self, challenge_id: str) -> dict[str, str] | None:
        if not challenge_id or len(challenge_id) > 128:
            return None
        raw = await self._redis().getdel(_PREFIX + challenge_id)
        if raw is None:
            return None
        data = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else None
