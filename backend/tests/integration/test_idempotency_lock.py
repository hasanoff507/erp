"""Idempotency lock ownership (23 §3): only the request that took the lock may release it."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from redis.asyncio import Redis

from app.core.idempotency import IdempotencyMiddleware, StoredResponse, lock_key, release_lock

pytestmark = pytest.mark.redis

TENANT = uuid4()


class MemoryStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], StoredResponse] = {}

    async def get(self, tenant_id: UUID, key: str) -> StoredResponse | None:
        return self.rows.get((tenant_id, key))

    async def save(self, tenant_id: UUID, key: str, response: StoredResponse) -> None:
        self.rows.setdefault((tenant_id, key), response)


async def test_release_is_compare_and_delete(clean_redis: Redis) -> None:
    await clean_redis.set("idem:t:k", "mine", ex=60)
    assert await release_lock(clean_redis, "idem:t:k", "other") is False
    assert await clean_redis.get("idem:t:k") == "mine"
    assert await release_lock(clean_redis, "idem:t:k", "mine") is True
    assert await clean_redis.exists("idem:t:k") == 0
    assert await release_lock(clean_redis, "idem:t:k", "mine") is False  # already gone


async def test_lock_taken_over_after_ttl_is_not_deleted(clean_redis: Redis) -> None:
    """Our TTL expired mid-request and a duplicate took the lock: we must leave its lock alone."""
    name = lock_key(TENANT, "k-takeover")
    seen_tokens: list[str | None] = []

    async def resolve_tenant(_: Request) -> UUID | None:
        return TENANT

    app = FastAPI()

    @app.post("/api/v1/things")
    async def create_thing() -> dict[str, bool]:
        seen_tokens.append(await clean_redis.get(name))
        await clean_redis.set(name, "duplicate-request-token", ex=60)  # simulated expiry + takeover
        return {"ok": True}

    store = MemoryStore()
    wrapped = IdempotencyMiddleware(
        app, redis=lambda: clean_redis, store=lambda: store, resolve_tenant=resolve_tenant
    )
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/things", headers={"Idempotency-Key": "k-takeover"})

    assert r.status_code == 200
    # the lock held a random per-request token, not something derivable from the request
    assert seen_tokens[0] is not None and len(seen_tokens[0]) == 32
    assert await clean_redis.get(name) == "duplicate-request-token"


async def test_own_lock_is_released(clean_redis: Redis) -> None:
    async def resolve_tenant(_: Request) -> UUID | None:
        return TENANT

    app = FastAPI()

    @app.post("/api/v1/things")
    async def create_thing() -> dict[str, bool]:
        return {"ok": True}

    store = MemoryStore()
    wrapped = IdempotencyMiddleware(
        app, redis=lambda: clean_redis, store=lambda: store, resolve_tenant=resolve_tenant
    )
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/things", headers={"Idempotency-Key": "k-own"})
    assert r.status_code == 200
    assert await clean_redis.exists(lock_key(TENANT, "k-own")) == 0
