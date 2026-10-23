"""Fixed-window counters in Redis (14 §12).

23 §5 names ``slowapi``; its storage layer is synchronous, so the few auth
limits are kept here as plain Redis ``INCR``/``EXPIRE`` counters with the same
semantics (one shared counter per key across all API replicas).
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class WindowState:
    count: int
    retry_after_s: int


async def hit(redis: Redis, key: str, window_s: int) -> WindowState:
    """Count one event in the window that started with the first event."""
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_s, nx=True)
        pipe.ttl(key)
        count, _, ttl = await pipe.execute()
    return WindowState(int(count), max(int(ttl), 1))


async def peek(redis: Redis, key: str) -> WindowState:
    async with redis.pipeline(transaction=False) as pipe:
        pipe.get(key)
        pipe.ttl(key)
        raw, ttl = await pipe.execute()
    return WindowState(int(raw or 0), max(int(ttl), 1))
