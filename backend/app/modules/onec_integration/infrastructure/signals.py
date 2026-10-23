"""Redis side of the agent channel (33 §4.5): long-poll wake-up ``onec:wake:{agent_id}`` (pub/sub), the
current long-poll id ``onec:poll:{agent_id}`` (a newer poll closes the older one with ``204``) and the
status cache ``onec:agent_status:{agent_id}`` (60 s; revoke writes ``revoked`` at once)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)

POLL_KEY_TTL_S: Final = 30
WAKE: Final = "wake"
_background: set[asyncio.Task[None]] = set()


def wake_channel(agent_id: UUID) -> str:
    return f"onec:wake:{agent_id}"


def poll_key(agent_id: UUID) -> str:
    return f"onec:poll:{agent_id}"


def status_key(agent_id: UUID) -> str:
    return f"onec:agent_status:{agent_id}"


class RedisAgentSignals:
    def __init__(self, redis: Callable[[], Redis], *, status_ttl_s: int = 60) -> None:
        self._redis = redis
        self._status_ttl = status_ttl_s

    # --- wake-up -----------------------------------------------------------------------------------
    async def wake(self, agent_id: UUID) -> None:
        try:
            await self._redis().publish(wake_channel(agent_id), WAKE)
        except RedisError:
            log.warning("onec_wake_unavailable", agent_id=str(agent_id))  # the poll re-checks on its own

    def wake_after_commit(self, s: AsyncSession, agent_id: UUID) -> None:
        """Publish once the caller's transaction commits (a wake-up before COMMIT would find nothing)."""

        def _after_commit(_session: object) -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            task = loop.create_task(self.wake(agent_id))
            _background.add(task)
            task.add_done_callback(_background.discard)

        event.listen(s.sync_session, "after_commit", _after_commit, once=True)

    def revoked_after_commit(self, s: AsyncSession, agent_id: UUID) -> None:
        """Revoke/unpair: ``revoked`` into the status cache right after COMMIT (14 §2.3 — immediate) and
        wake an open long-poll so it ends."""

        async def _mark() -> None:
            await self.cache_status(agent_id, "revoked")
            await self.wake(agent_id)

        def _after_commit(_session: object) -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            task = loop.create_task(_mark())
            _background.add(task)
            task.add_done_callback(_background.discard)

        event.listen(s.sync_session, "after_commit", _after_commit, once=True)

    # --- long-poll ---------------------------------------------------------------------------------
    async def claim_poll(self, agent_id: UUID, poll_id: str) -> None:
        """Become the agent's current poll and wake the previous one (it answers ``204``)."""
        try:
            redis = self._redis()
            await redis.set(poll_key(agent_id), poll_id, ex=POLL_KEY_TTL_S)
            await redis.publish(wake_channel(agent_id), f"poll:{poll_id}")
        except RedisError:
            log.warning("onec_poll_claim_unavailable", agent_id=str(agent_id))

    async def is_current_poll(self, agent_id: UUID, poll_id: str) -> bool:
        try:
            current = await self._redis().get(poll_key(agent_id))
        except RedisError:
            return True
        return current is None or current == poll_id

    async def wait(self, agent_id: UUID, recheck_s: float) -> AsyncWaiter:
        waiter = AsyncWaiter(self._redis(), wake_channel(agent_id), recheck_s)
        await waiter.start()
        return waiter

    # --- status cache ------------------------------------------------------------------------------
    async def cached_status(self, agent_id: UUID) -> str | None:
        try:
            value = await self._redis().get(status_key(agent_id))
        except RedisError:
            return None
        return str(value) if value else None

    async def cache_status(self, agent_id: UUID, status: str) -> None:
        try:
            await self._redis().set(status_key(agent_id), status, ex=self._status_ttl)
        except RedisError:
            log.warning("onec_status_cache_unavailable", agent_id=str(agent_id))


class AsyncWaiter:
    """One subscription for the life of a long-poll; ``next()`` returns the message or ``None`` (tick)."""

    def __init__(self, redis: Redis, channel: str, recheck_s: float) -> None:
        self._redis = redis
        self._channel = channel
        self._recheck = recheck_s
        self._pubsub = None if redis is None else redis.pubsub()
        self._ok = False

    async def start(self) -> None:
        try:
            assert self._pubsub is not None
            await self._pubsub.subscribe(self._channel)
            self._ok = True
        except RedisError:
            log.warning("onec_wake_subscribe_unavailable", channel=self._channel)

    async def next(self, deadline: float) -> str | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        timeout = min(remaining, self._recheck)
        if not self._ok or self._pubsub is None:
            await asyncio.sleep(timeout)
            return None
        try:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
        except RedisError:
            self._ok = False
            return None
        if not message:
            return None
        data = message.get("data")
        return data if isinstance(data, str) else str(data)

    async def close(self) -> None:
        if self._pubsub is None:
            return
        try:
            await self._pubsub.unsubscribe(self._channel)
            await self._pubsub.aclose()  # type: ignore[no-untyped-call]
        except RedisError:
            pass
