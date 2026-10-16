"""/health/ready against real PostgreSQL + Redis, and Idempotency-Key handling (23 §3, §8)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Request
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import Settings
from app.core.context import idempotency_var
from app.core.db.session import Database, tenant_transaction
from app.core.idempotency import request_hash, stage_response
from app.main import create_app
from tests.conftest import MigratedDb
from tests.support.factories import TenantWorld, create_tenant_world

pytestmark = pytest.mark.db


def _settings(migrated_db: MigratedDb, redis_url: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr(migrated_db.app_url),
        redis_url=SecretStr(redis_url),
        log_json=False,
    )


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_health_ready_gates_on_postgres_schema_and_redis(
    migrated_db: MigratedDb, redis_url: str
) -> None:
    app = create_app(_settings(migrated_db, redis_url))
    async for client in _client(app):
        r = await client.get("/health/ready")
        assert r.status_code == 200, r.text
        assert r.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}
        assert (await client.get("/health")).status_code == 200


async def test_health_ready_fails_when_redis_is_down(migrated_db: MigratedDb) -> None:
    app = create_app(_settings(migrated_db, "redis://127.0.0.1:1/0"))
    async for client in _client(app):
        r = await client.get("/health/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "fail"
        assert body["checks"]["postgres"] == "ok"
        assert body["checks"]["redis"].startswith("fail")


# --- idempotency -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def tenant(app_db: Database) -> TenantWorld:
    return await create_tenant_world(app_db, "Idem tenant")


def _idem_app(
    migrated_db: MigratedDb,
    redis_url: str,
    calls: list[str],
    gate: asyncio.Event | None = None,
    entered: asyncio.Event | None = None,
) -> FastAPI:
    async def resolve_tenant(request: Request) -> UUID | None:
        raw = request.headers.get("x-test-tenant")
        return UUID(raw) if raw else None

    app = create_app(_settings(migrated_db, redis_url), resolve_tenant=resolve_tenant)

    @app.post("/api/v1/things", status_code=201)
    async def create_thing(payload: dict[str, str]) -> dict[str, object]:
        calls.append(payload["name"])
        if entered is not None:
            entered.set()
        if gate is not None:
            await gate.wait()
        return {"n": len(calls), "name": payload["name"]}

    @app.post("/api/v1/fails")
    async def fails() -> None:
        calls.append("fail")
        raise ValueError("boom")

    @app.post("/api/v1/sync/push")
    async def sync_push() -> dict[str, int]:
        calls.append("sync")
        return {"n": len(calls)}

    return app


async def test_replay_returns_stored_response_without_re_executing(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis, app_db: Database
) -> None:
    calls: list[str] = []
    headers = {"x-test-tenant": str(tenant.tenant_id), "Idempotency-Key": "k-replay-1"}
    async for client in _client(_idem_app(migrated_db, redis_url, calls)):
        first = await client.post("/api/v1/things", json={"name": "a"}, headers=headers)
        second = await client.post("/api/v1/things", json={"name": "a"}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json() == {"n": 1, "name": "a"}
    assert second.headers["idempotent-replayed"] == "true"
    assert calls == ["a"]
    async with app_db.session_factory() as s, tenant_transaction(s, tenant.tenant_id):
        row = (
            await s.execute(
                text(
                    "SELECT response_status, response_body FROM app.idempotency_keys WHERE key = 'k-replay-1'"
                )
            )
        ).one()
    assert row == (201, {"n": 1, "name": "a"})


async def test_same_key_different_body_is_rejected(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis
) -> None:
    calls: list[str] = []
    headers = {"x-test-tenant": str(tenant.tenant_id), "Idempotency-Key": "k-reuse-1"}
    async for client in _client(_idem_app(migrated_db, redis_url, calls)):
        await client.post("/api/v1/things", json={"name": "a"}, headers=headers)
        r = await client.post("/api/v1/things", json={"name": "b"}, headers=headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert calls == ["a"]


async def test_parallel_duplicate_gets_in_progress(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis
) -> None:
    calls: list[str] = []
    gate, entered = asyncio.Event(), asyncio.Event()
    headers = {"x-test-tenant": str(tenant.tenant_id), "Idempotency-Key": "k-parallel-1"}
    async for client in _client(_idem_app(migrated_db, redis_url, calls, gate, entered)):
        first = asyncio.create_task(client.post("/api/v1/things", json={"name": "a"}, headers=headers))
        await asyncio.wait_for(entered.wait(), timeout=10)
        dup = await client.post("/api/v1/things", json={"name": "a"}, headers=headers)
        gate.set()
        done = await first
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"
    assert dup.headers["retry-after"] == "1"
    assert done.status_code == 201
    assert calls == ["a"]


async def test_key_is_required_for_writes_and_tenants_are_separate(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, app_db: Database, clean_redis: Redis
) -> None:
    other = await create_tenant_world(app_db, "Idem other")
    calls: list[str] = []
    async for client in _client(_idem_app(migrated_db, redis_url, calls)):
        missing = await client.post(
            "/api/v1/things", json={"name": "a"}, headers={"x-test-tenant": str(tenant.tenant_id)}
        )
        a = await client.post(
            "/api/v1/things", json={"name": "a"},
            headers={"x-test-tenant": str(tenant.tenant_id), "Idempotency-Key": "shared-key"},
        )  # fmt: skip
        b = await client.post(
            "/api/v1/things", json={"name": "a"},
            headers={"x-test-tenant": str(other.tenant_id), "Idempotency-Key": "shared-key"},
        )  # fmt: skip
    assert missing.status_code == 422
    assert missing.json()["error"]["details"] == [
        {"field": "Idempotency-Key", "message_key": "validation.required"}
    ]
    assert a.status_code == b.status_code == 201
    assert calls == ["a", "a"]  # same key in two tenants = two different requests


async def test_failures_are_not_stored_and_sync_push_is_exempt(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis
) -> None:
    calls: list[str] = []
    headers = {"x-test-tenant": str(tenant.tenant_id), "Idempotency-Key": "k-fail-1"}
    async for client in _client(_idem_app(migrated_db, redis_url, calls)):
        r1 = await client.post("/api/v1/fails", headers=headers)
        r2 = await client.post("/api/v1/fails", headers=headers)
        s1 = await client.post("/api/v1/sync/push", headers={"x-test-tenant": str(tenant.tenant_id)})
    assert r1.status_code == r2.status_code == 500
    assert calls[:2] == ["fail", "fail"]  # retried, not replayed
    assert s1.status_code == 200


# --- journal row in the business transaction (23 §3) ---------------------------------------------


def _journal_app(migrated_db: MigratedDb, redis_url: str, calls: list[str]) -> FastAPI:
    """Write routes that commit a business row through ``tenant_transaction`` + ``stage_response``."""

    async def resolve_tenant(request: Request) -> UUID | None:
        raw = request.headers.get("x-test-tenant")
        return UUID(raw) if raw else None

    app = create_app(_settings(migrated_db, redis_url), resolve_tenant=resolve_tenant)

    async def _insert_category(request: Request, name: str) -> dict[str, object]:
        db: Database = request.app.state.db
        tenant = UUID(request.headers["x-test-tenant"])
        async with db.session_factory() as session, tenant_transaction(session, tenant):
            await session.execute(
                text("INSERT INTO app.expense_categories (tenant_id, name) VALUES (:t, :n)"),
                {"t": tenant, "n": name},
            )
            body: dict[str, object] = {"name": name, "n": len(calls)}
            stage_response(body, 201)
            if name.startswith("fail-"):
                raise RuntimeError("failure before COMMIT")
            if name.startswith("race-"):
                # a duplicate request with the same key commits first (e.g. after the Redis lock TTL expired)
                outside = idempotency_var.set(None)  # the duplicate runs in its own request context
                async with db.session_factory() as other, tenant_transaction(other, tenant):
                    await other.execute(
                        text(
                            "INSERT INTO app.idempotency_keys "
                            "(tenant_id, key, request_hash, response_status, response_body) "
                            "VALUES (:t, :k, :h, 201, CAST(:b AS jsonb))"
                        ),
                        {
                            "t": tenant,
                            "k": request.headers["idempotency-key"],
                            "h": _hash_of(request, name),
                            "b": json.dumps({"name": name, "winner": True}),
                        },
                    )
                idempotency_var.reset(outside)
        return body

    @app.post("/api/v1/categories", status_code=201)
    async def create_category(request: Request, payload: dict[str, str]) -> dict[str, object]:
        calls.append(payload["name"])
        body = await _insert_category(request, payload["name"])
        if payload["name"].startswith("crash-"):
            # the business COMMIT (with its journal row) is done; the process dies before answering
            raise RuntimeError("crash after COMMIT")
        return body

    return app


def _hash_of(request: Request, name: str) -> str:
    return request_hash("POST", "/api/v1/categories", b"", json.dumps({"name": name}).encode())


async def _categories(app_db: Database, tenant: UUID, name: str) -> int:
    async with app_db.session_factory() as s, tenant_transaction(s, tenant):
        value = (
            await s.execute(text("SELECT count(*) FROM app.expense_categories WHERE name = :n"), {"n": name})
        ).scalar_one()
    return int(value)


async def _journal(app_db: Database, tenant: UUID, key: str) -> tuple[int, object] | None:
    async with app_db.session_factory() as s, tenant_transaction(s, tenant):
        row = (
            await s.execute(
                text("SELECT response_status, response_body FROM app.idempotency_keys WHERE key = :k"),
                {"k": key},
            )
        ).first()
    return (row[0], row[1]) if row else None


async def test_crash_after_business_commit_still_replays(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis, app_db: Database
) -> None:
    """The journal row commits with the business write, so a crash after COMMIT cannot lose it."""
    calls: list[str] = []
    headers = {
        "x-test-tenant": str(tenant.tenant_id),
        "Idempotency-Key": "k-journal-crash",
        "Content-Type": "application/json",
    }
    payload = {"name": "crash-rent"}
    async for client in _client(_journal_app(migrated_db, redis_url, calls)):
        crashed = await client.post("/api/v1/categories", content=json.dumps(payload), headers=headers)
        retry = await client.post("/api/v1/categories", content=json.dumps(payload), headers=headers)
    assert crashed.status_code == 500  # the client never saw the result
    assert await _categories(app_db, tenant.tenant_id, "crash-rent") == 1
    assert await _journal(app_db, tenant.tenant_id, "k-journal-crash") == (
        201,
        {"name": "crash-rent", "n": 1},
    )
    assert retry.status_code == 201
    assert retry.headers["idempotent-replayed"] == "true"
    assert retry.json() == {"name": "crash-rent", "n": 1}
    assert calls == ["crash-rent"]  # not executed twice


async def test_failure_before_commit_rolls_back_row_and_journal(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis, app_db: Database
) -> None:
    calls: list[str] = []
    headers = {
        "x-test-tenant": str(tenant.tenant_id),
        "Idempotency-Key": "k-journal-fail",
        "Content-Type": "application/json",
    }
    payload = {"name": "fail-rent"}
    async for client in _client(_journal_app(migrated_db, redis_url, calls)):
        first = await client.post("/api/v1/categories", content=json.dumps(payload), headers=headers)
        second = await client.post("/api/v1/categories", content=json.dumps(payload), headers=headers)
    assert first.status_code == second.status_code == 500
    assert await _categories(app_db, tenant.tenant_id, "fail-rent") == 0
    assert await _journal(app_db, tenant.tenant_id, "k-journal-fail") is None
    assert calls == ["fail-rent", "fail-rent"]  # retried, not replayed


async def test_duplicate_that_committed_first_wins_and_ours_rolls_back(
    migrated_db: MigratedDb, redis_url: str, tenant: TenantWorld, clean_redis: Redis, app_db: Database
) -> None:
    calls: list[str] = []
    headers = {
        "x-test-tenant": str(tenant.tenant_id),
        "Idempotency-Key": "k-journal-race",
        "Content-Type": "application/json",
    }
    payload = {"name": "race-rent"}
    async for client in _client(_journal_app(migrated_db, redis_url, calls)):
        r = await client.post("/api/v1/categories", content=json.dumps(payload), headers=headers)
    assert r.status_code == 201
    assert r.headers["idempotent-replayed"] == "true"
    assert r.json() == {"name": "race-rent", "winner": True}
    assert await _categories(app_db, tenant.tenant_id, "race-rent") == 0  # our business write rolled back
