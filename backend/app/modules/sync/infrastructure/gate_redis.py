"""Backpressure of ``/sync/push`` in Redis (16 §3.1, QT-NFR-09; counters as in ``app/core/ratelimit.py``).

* ≤ ``rate_per_s`` requests per second per device (fixed 1 s window);
* one push of a device at a time (``SET NX`` lock with a TTL — keeps the device's ``seq`` order);
* ≤ ``tenant_concurrency`` pushes of a tenant at the same time (counter with a TTL safety net).

Refusal → ``429 RATE_LIMITED`` + ``Retry-After``. Redis unavailable → the push is let through (an offline
POS must never lose a sale because of the limiter) and a warning is logged.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.ratelimit import hit

log = structlog.get_logger(__name__)

_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
_UNAVAILABLE = "-"


@dataclass(frozen=True, slots=True)
class GateConfig:
    rate_per_s: int = 5
    tenant_concurrency: int = 4
    lock_ttl_s: int = 120


def _limited(reason: str, retry_after: int) -> AppError:
    return AppError(
        ErrorCode.RATE_LIMITED, params={"reason": reason}, headers={"Retry-After": str(max(retry_after, 1))}
    )


class RedisPushGate:
    def __init__(self, redis: Callable[[], Redis], config: GateConfig) -> None:
        self._redis = redis
        self._cfg = config

    async def enter(self, tenant_id: UUID, device_id: UUID) -> str:
        redis = self._redis()
        token = secrets.token_hex(8)
        lock = f"sync:push:lock:{device_id}"
        conc = f"sync:push:conc:{tenant_id}"
        try:
            rate = await hit(redis, f"sync:push:rate:{device_id}", 1)
            if rate.count > self._cfg.rate_per_s:
                raise _limited("device_rate", rate.retry_after_s)
            if not await redis.set(lock, token, nx=True, ex=self._cfg.lock_ttl_s):
                raise _limited("device_busy", 1)
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(conc)
                pipe.expire(conc, self._cfg.lock_ttl_s)
                running, _ = await pipe.execute()
            if int(running) > self._cfg.tenant_concurrency:
                await redis.decr(conc)
                await redis.eval(_RELEASE, 1, lock, token)
                raise _limited("tenant_concurrency", 1)
        except RedisError:
            log.warning("sync_push_gate_unavailable", device_id=str(device_id), exc_info=True)
            return _UNAVAILABLE
        return token

    async def leave(self, tenant_id: UUID, device_id: UUID, token: str) -> None:
        if token == _UNAVAILABLE:
            return
        redis = self._redis()
        try:
            await redis.decr(f"sync:push:conc:{tenant_id}")
            await redis.eval(_RELEASE, 1, f"sync:push:lock:{device_id}", token)
        except RedisError:
            log.warning("sync_push_gate_release_failed", device_id=str(device_id), exc_info=True)
