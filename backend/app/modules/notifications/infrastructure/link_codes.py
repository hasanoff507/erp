"""One-time Telegram link codes in Redis (US-M18-01; qaror #54: 10 min, single use).

The code itself is never stored — only its SHA-256 (``tg:link:<hash>`` → ``{tenant_id, user_id}`` with a
TTL); the webhook takes it with ``GETDEL`` (atomic single use). ``tg:link:user:<tenant>:<user>`` remembers
the user's current code so a new ``link-start`` invalidates the previous one. Processed Telegram
``update_id`` values are kept for 24 h (``SET NX``) so a re-delivered update is not handled twice (21 §11).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from uuid import UUID

from redis.asyncio import Redis

from app.modules.notifications.application.ports import LinkGrant

_PREFIX = "tg:link:"
_UPDATE = "tg:update:"


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class RedisLinkCodeStore:
    def __init__(self, redis: Callable[[], Redis]) -> None:
        self._redis = redis

    async def put(self, code: str, grant: LinkGrant, ttl_s: int) -> None:
        redis = self._redis()
        user_key = f"{_PREFIX}user:{grant.tenant_id}:{grant.user_id}"
        digest = _hash(code)
        raw_previous = await redis.getset(user_key, digest)
        previous = raw_previous.decode() if isinstance(raw_previous, bytes) else raw_previous
        pipe = redis.pipeline(transaction=True)
        if previous:
            pipe.delete(f"{_PREFIX}{previous}")
        pipe.set(
            f"{_PREFIX}{digest}",
            json.dumps({"tenant_id": str(grant.tenant_id), "user_id": str(grant.user_id)}),
            ex=ttl_s,
        )
        pipe.expire(user_key, ttl_s)
        await pipe.execute()

    async def take(self, code: str) -> LinkGrant | None:
        raw = await self._redis().getdel(f"{_PREFIX}{_hash(code)}")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return LinkGrant(UUID(data["tenant_id"]), UUID(data["user_id"]))
        except (ValueError, KeyError, TypeError):
            return None

    async def seen_update(self, update_id: int, ttl_s: int) -> bool:
        fresh = await self._redis().set(f"{_UPDATE}{update_id}", "1", nx=True, ex=ttl_s)
        return not fresh

    async def forget_update(self, update_id: int) -> None:
        await self._redis().delete(f"{_UPDATE}{update_id}")
