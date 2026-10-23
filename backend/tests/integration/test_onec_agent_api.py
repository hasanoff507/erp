"""Store-agent channel (33 §9.3 A-01, A-03…A-10; §10 W-01…W-05, W-07, W-08; contracts/agent-wire.md) and
the task queue port (contracts/agent-tasks.md). Real app, real PG + Redis, protocol-level fake agent."""

from __future__ import annotations

import asyncio
import base64
import gzip
import io
import json
import time
import uuid
import zipfile
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.session import Database
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.compact_jws import public_key_from_jwk, verify_compact
from app.modules.onec_integration.domain.jcs import payload_sha256
from app.modules.onec_integration.wiring import AgentTaskResult, AgentTaskView, lease_sweeper
from tests.conftest import MigratedDb
from tests.support.agent import (
    FULL_CAPABILITIES,
    AgentFixture,
    agent_platform,
    enqueue,
    hello,
    pair_agent,
    poll,
    result,
    root_key,
)
from tests.support.auth import auth_settings
from tests.support.branches import add_member, api, make_shop

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def ctx(
    oauth_platform: None,
    migrated_db: MigratedDb,
    redis_url: str,
    clean_redis: Redis,
    migrator_engine: AsyncEngine,
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    await agent_platform(migrator_engine)
    async with api(migrated_db, redis_url) as (app, c):
        # the queue/protocol is tested here on its own: other slices' result handlers (fiscal, card,
        # print — contract 1) are exercised by their own tests
        app.state.onec_agents.tasks._handlers.clear()
        yield app, c


@pytest.fixture
def client(ctx: tuple[FastAPI, httpx.AsyncClient]) -> httpx.AsyncClient:
    return ctx[1]


async def _agent(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine, **caps: Any
) -> AgentFixture:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    r = await hello(client, fx, caps.get("capabilities", FULL_CAPABILITIES))
    assert r.status_code == 200, r.text
    return fx


async def _one(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).first()


async def _task_key(engine: AsyncEngine, kid: str) -> Ed25519PublicKey:
    row = await _one(engine, "SELECT public_key FROM platform.signing_keys WHERE kid = :k", k=uuid.UUID(kid))
    return public_key_from_jwk(json.loads(row[0]))


# --- W-01 / W-02 / A-01 ---------------------------------------------------------------------------
async def test_onec_agent_list_and_detail_after_hello(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    listing = await client.get("/api/v1/onec-agents", headers=fx.shop.owner.headers())
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1 and body["page"] == 1
    item = body["items"][0]
    assert item["id"] == str(fx.agent_id) and item["status"] == "active" and item["online"] is True
    assert item["name"] == "DOKON-PC" and item["paired_by_name"] == "Egasi"
    assert item["capabilities"]["fiscal"]["devices"] == [{"local_id": "fm-1", "status": "ok"}]
    assert item["update_available"] == "1.4.3" and item["bases_count"] == 0
    detail = await client.get(f"/api/v1/onec-agents/{fx.agent_id}", headers=fx.shop.owner.headers())
    assert detail.status_code == 200 and detail.json()["bases"] == []
    missing = await client.get(f"/api/v1/onec-agents/{uuid.uuid4()}", headers=fx.shop.owner.headers())
    assert missing.status_code == 404


async def test_onec_agent_hello_keyset_update_and_machine_change(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    first = await hello(client, fx, FULL_CAPABILITIES)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["agent_id"] == str(fx.agent_id) and body["hello_interval_s"] == 600
    assert body["bases_control"] == [] and body["subscription"] in ("trial", "active")
    assert body["task_keyset"].count(".") == 2  # task_keyset_version null → the current keyset
    assert body["update"] == {
        "version": "1.4.3",
        "channel": "stable",
        "mandatory": False,
        "manifest_url": "/api/v1/onec-agent/update-manifest?channel=stable",
    }
    current = (await client.get("/api/v1/onec-agent/task-keys", headers=fx.headers())).json()["version"]
    same = await hello(client, fx, FULL_CAPABILITIES, task_keyset_version=current, machine_hash="ab" * 32)
    assert same.json()["task_keyset"] is None
    row = await _one(
        admin_engine,
        "SELECT machine_hash, machine_hash_changed_at FROM app.onec_agents WHERE id = :a",
        a=fx.agent_id,
    )
    assert row[0] == "ab" * 32 and row[1] is not None
    audit = await _one(
        admin_engine,
        "SELECT count(*) FROM app.audit_log WHERE entity_id = :a AND action = 'onec.agent.machine_changed'",
        a=fx.agent_id,
    )
    assert audit[0] == 1
    upgraded = await client.post(
        "/api/v1/onec-agent/hello", json={"agent_version": "1.4.3"}, headers=fx.headers(version="1.4.3")
    )
    assert upgraded.status_code == 200 and upgraded.json()["update"] is None
    updated = await _one(
        admin_engine,
        "SELECT count(*) FROM app.audit_log WHERE entity_id = :a AND action = 'onec.agent.updated'",
        a=fx.agent_id,
    )
    assert updated[0] == 1
    # a hello without the field → only the 1C module (33 §9.3 A-01)
    caps = await _one(admin_engine, "SELECT capabilities FROM app.onec_agents WHERE id = :a", a=fx.agent_id)
    assert caps[0] == {"onec": {"enabled": True, "version": 1}}


async def test_onec_agent_hello_rejects_bad_capabilities(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    r = await hello(client, fx, {"fiscal": {"enabled": "yes"}})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "capabilities.fiscal.enabled"


async def test_onec_agent_version_gate_426(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    old_protocol = await client.post("/api/v1/onec-agent/hello", json={}, headers=fx.headers(protocol="1"))
    assert (
        old_protocol.status_code == 426
        and old_protocol.json()["error"]["code"] == "ONEC_AGENT_UPDATE_REQUIRED"
    )
    old_agent = await client.post("/api/v1/onec-agent/poll", json={}, headers=fx.headers(version="0.9.0"))
    assert old_agent.status_code == 426
    # A-09 stays reachable for the old agent (34 §4.4)
    manifest = await client.get("/api/v1/onec-agent/update-manifest", headers=fx.headers(version="0.9.0"))
    assert manifest.status_code == 200


# --- AgentTaskPort ------------------------------------------------------------------------------------
async def test_onec_agent_enqueue_checks_capability_and_payload(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    with pytest.raises(AppError) as disabled:  # no hello yet: capabilities {}
        await enqueue(app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "x"})
    assert disabled.value.code == ErrorCode.AGENT_CAPABILITY_DISABLED and disabled.value.status_code == 409
    assert disabled.value.params == {
        "agent_id": str(fx.agent_id),
        "kind": "fiscal.status",
        "family": "fiscal",
    }
    await hello(client, fx, {**FULL_CAPABILITIES, "card_terminal": {"enabled": False, "version": 0}})
    first = await enqueue(
        app_db,
        fx.tenant_id,
        fx.agent_id,
        "fiscal.status",
        {"cash_register_id": "a"},
        dedupe_key="fiscal.status:a",
    )
    again = await enqueue(
        app_db,
        fx.tenant_id,
        fx.agent_id,
        "fiscal.status",
        {"cash_register_id": "a"},
        dedupe_key="fiscal.status:a",
    )
    assert again == first
    with pytest.raises(AppError) as card:
        await enqueue(app_db, fx.tenant_id, fx.agent_id, "card.status", {})
    assert card.value.code == ErrorCode.AGENT_CAPABILITY_DISABLED
    for kind, payload in (("write_object", {}), ("fiscal.status", {"amount": 1.5})):
        with pytest.raises(AppError) as bad:
            await enqueue(app_db, fx.tenant_id, fx.agent_id, kind, payload)
        assert bad.value.code == ErrorCode.VALIDATION_ERROR
    other = await make_shop(app_db, client)
    with pytest.raises(AppError) as foreign:  # RLS: another tenant's agent does not exist
        await enqueue(app_db, other.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "a"})
    assert foreign.value.code == ErrorCode.NOT_FOUND
    row = await _one(
        admin_engine,
        "SELECT purpose, base_id, status, payload_sha256, timeout_s FROM app.onec_agent_tasks WHERE id = :t",
        t=first,
    )
    assert row[0] == "device_service" and row[1] is None and row[2] == "queued" and row[4] == 60
    assert row[3] == payload_sha256({"cash_register_id": "a"})


# --- A-03 / A-04 / A-05 -----------------------------------------------------------------------------
async def test_onec_agent_poll_leases_one_signed_task(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    empty = await poll(client, fx)
    assert empty.status_code == 204
    payload = {
        "printer_local_id": "pr-1",
        "data_base64": base64.b64encode(b"\x1b@hi").decode(),
        "encoding": "cp866",
    }
    task_id = await enqueue(app_db, fx.tenant_id, fx.agent_id, "print.raw", payload)
    await enqueue(app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "b"})
    r = await poll(client, fx)
    assert r.status_code == 200, r.text
    (task,) = r.json()["tasks"]
    assert (
        task["task_id"] == str(task_id)
        and task["kind"] == "print.raw"
        and task["purpose"] == "device_service"
    )
    assert (
        task["base_id"] is None
        and task["local_id"] is None
        and task["attempt"] == 1
        and task["timeout_s"] == 60
    )
    assert task["payload"] == payload and task["payload_sha256"] == payload_sha256(payload)
    header, claims = verify_compact(task["signature"], await _task_key(migrator_engine, task["kid"]))
    assert header == {"alg": "EdDSA", "typ": "onec-task+jwt", "kid": task["kid"]}
    assert claims["iss"] == "urn:erp:onec" and claims["aud"] == f"urn:erp:onec-agent:{fx.agent_id}"
    assert claims["tid"] == str(task_id) and claims["att"] == 1 and claims["lid"] == task["lease_id"]
    assert claims["ten"] == str(fx.tenant_id) and claims["aid"] == str(fx.agent_id) and claims["bid"] is None
    assert claims["knd"] == "print.raw" and claims["psh"] == task["payload_sha256"]
    assert claims["exp"] - claims["iat"] == 60 + 300
    # one agent-level lease at a time (uq_onec_tasks_one_leased_agent_level)
    busy = await poll(client, fx)
    assert busy.status_code == 204
    assert (await poll(client, fx, agent_level_busy=True)).status_code == 204


async def test_onec_agent_heartbeat_extends_and_lease_lost(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    await enqueue(
        app_db, fx.tenant_id, fx.agent_id, "fiscal.zreport", {"cash_register_id": "c", "shift_id": "s"}
    )
    task = (await poll(client, fx)).json()["tasks"][0]
    url = f"/api/v1/onec-agent/tasks/{task['task_id']}/heartbeat"
    ok = await client.post(
        url,
        json={"lease_id": task["lease_id"], "progress": {"stage": "writing", "pct": 40}},
        headers=fx.headers(),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["cancel_requested"] is False and ok.json()["lease_until"] >= task["lease_until"]
    row = await _one(
        admin_engine,
        "SELECT progress, heartbeat_at FROM app.onec_agent_tasks WHERE id = :t",
        t=uuid.UUID(task["task_id"]),
    )
    assert row[0] == {"stage": "writing", "pct": 40} and row[1] is not None
    lost = await client.post(url, json={"lease_id": str(uuid.uuid4())}, headers=fx.headers())
    assert lost.status_code == 409 and lost.json()["error"]["code"] == "ONEC_TASK_LEASE_LOST"
    unknown = await client.post(
        f"/api/v1/onec-agent/tasks/{uuid.uuid4()}/heartbeat",
        json={"lease_id": task["lease_id"]},
        headers=fx.headers(),
    )
    assert unknown.status_code == 404


async def test_onec_agent_result_idempotent_and_dispatched(
    ctx: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = ctx
    calls: list[tuple[AgentTaskView, AgentTaskResult]] = []

    async def handler(
        s: AsyncSession, tenant_id: uuid.UUID, agent_id: uuid.UUID, task: AgentTaskView, res: AgentTaskResult
    ) -> None:
        assert (await s.execute(text("SELECT app.current_tenant_id()"))).scalar() == tenant_id
        calls.append((task, res))

    tasks = app.state.onec_agents.tasks
    previous = tasks._handlers.get("card.status")
    tasks._handlers["card.status"] = handler
    try:
        fx = await _agent(client, app_db, admin_engine)
        task_id = await enqueue(app_db, fx.tenant_id, fx.agent_id, "card.status", {"card_terminal_ids": []})
        task = (await poll(client, fx)).json()["tasks"][0]
        data = {"terminals": [], "unresolved": []}
        first = await result(client, fx, task, data=data)
        assert first.status_code == 200 and first.json() == {
            "accepted": True,
            "duplicate": False,
            "late": False,
        }
        dup = await result(client, fx, task, data=data)
        assert dup.json() == {"accepted": True, "duplicate": True, "late": False}
        assert len(calls) == 1
        view, res = calls[0]
        assert (
            view.id == task_id and view.kind == "card.status" and res.outcome == "done" and res.data == data
        )
        row = await _one(
            admin_engine,
            "SELECT status, outcome, finished_at FROM app.onec_agent_tasks WHERE id = :t",
            t=task_id,
        )
        assert row[0] == "done" and row[1] == "done" and row[2] is not None
        stored = await _one(
            admin_engine,
            "SELECT count(*), max(agent_version) FROM app.onec_task_results WHERE task_id = :t",
            t=task_id,
        )
        assert stored[0] == 1 and stored[1] == "1.4.2"
    finally:
        if previous is None:
            tasks._handlers.pop("card.status", None)
        else:
            tasks._handlers["card.status"] = previous


async def test_onec_agent_result_validation_and_rejection_audit(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    await enqueue(app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "r"})
    task = (await poll(client, fx)).json()["tasks"][0]
    no_error = await result(client, fx, task, outcome="failed")
    assert no_error.status_code == 422
    unknown = await result(client, fx, task, outcome="unknown", error={"code": "ONEC_TIMEOUT"})
    assert unknown.status_code == 422
    wrong_attempt = await result(client, fx, task, attempt=2)
    assert (
        wrong_attempt.status_code == 409 and wrong_attempt.json()["error"]["code"] == "ONEC_TASK_LEASE_LOST"
    )
    rejected = await result(
        client, fx, task, outcome="failed", error={"code": "ONEC_TASK_REJECTED", "message": "signature"}
    )
    assert rejected.status_code == 200, rejected.text
    audit = await _one(
        admin_engine,
        "SELECT after FROM app.audit_log WHERE entity_id = :t AND action = 'onec.task.rejected'",
        t=uuid.UUID(task["task_id"]),
    )
    assert audit[0]["reason"] == "signature" and audit[0]["kind"] == "fiscal.status"


async def test_onec_agent_lease_sweeper_and_late_result(
    client: httpx.AsyncClient,
    app_db: Database,
    admin_engine: AsyncEngine,
    migrated_db: MigratedDb,
    redis_url: str,
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    await enqueue(
        app_db,
        fx.tenant_id,
        fx.agent_id,
        "print.raw",
        {"printer_local_id": "pr-1", "data_base64": "", "encoding": "cp866"},
    )
    stale = await enqueue(
        app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "q"}, expires_in_s=60
    )
    task = (await poll(client, fx)).json()["tasks"][0]
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE app.onec_agent_tasks SET lease_until = now() - interval '1 second' WHERE id = :t"),
            {"t": uuid.UUID(task["task_id"])},
        )
        await conn.execute(
            text("UPDATE app.onec_agent_tasks SET expires_at = now() - interval '1 second' WHERE id = :t"),
            {"t": stale},
        )
    sweeper = lease_sweeper(auth_settings(migrated_db, redis_url), app_db)
    assert await sweeper.run(fx.tenant_id) == 2
    rows = await _one(
        admin_engine,
        "SELECT count(*) FILTER (WHERE status = 'expired'), count(*) FROM app.onec_agent_tasks WHERE agent_id = :a",
        a=fx.agent_id,
    )
    assert rows[0] == 2 and rows[1] == 2  # device_service: no automatic retry (print.raw never prints twice)
    late = await result(client, fx, task)
    assert late.status_code == 200 and late.json() == {"accepted": True, "duplicate": False, "late": True}
    status = await _one(
        admin_engine, "SELECT status FROM app.onec_agent_tasks WHERE id = :t", t=uuid.UUID(task["task_id"])
    )
    assert status[0] == "done"


async def test_onec_agent_lease_sweeper_retries_diagnostics_read_task(
    client: httpx.AsyncClient,
    app_db: Database,
    admin_engine: AsyncEngine,
    migrated_db: MigratedDb,
    redis_url: str,
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    requested = await client.post(
        f"/api/v1/onec-agents/{fx.agent_id}/diagnostics-requests",
        json={},
        headers=fx.shop.owner.headers(write=True),
    )
    assert requested.status_code == 202, requested.text
    task = (await poll(client, fx)).json()["tasks"][0]
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE app.onec_agent_tasks SET lease_until = now() - interval '1 second' WHERE id = :t"),
            {"t": uuid.UUID(task["task_id"])},
        )
    await lease_sweeper(auth_settings(migrated_db, redis_url), app_db).run(fx.tenant_id)
    retry = (await poll(client, fx)).json()["tasks"][0]
    assert (
        retry["kind"] == "collect_diagnostics"
        and retry["attempt"] == 2
        and retry["task_id"] != task["task_id"]
    )


async def test_qt_nfr_15_long_poll_wake_single_agent(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-NFR-15 (single agent): a new task reaches the waiting long-poll through Redis in ≤ 1 s."""
    fx = await _agent(client, app_db, admin_engine)
    started = time.monotonic()
    waiting = asyncio.create_task(poll(client, fx, wait_s=20))
    await asyncio.sleep(0.5)
    queued_at = time.monotonic()
    await enqueue(app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "w"})
    r = await asyncio.wait_for(waiting, timeout=15)
    assert r.status_code == 200, r.text
    assert time.monotonic() - queued_at < 1.5 and time.monotonic() - started < 5


async def test_onec_agent_newer_poll_closes_older(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    older = asyncio.create_task(poll(client, fx, wait_s=20))
    await asyncio.sleep(0.5)
    newer = asyncio.create_task(poll(client, fx, wait_s=2))
    first = await asyncio.wait_for(older, timeout=10)
    assert first.status_code == 204
    assert (await newer).status_code == 204


# --- revoke / unpair / lockout / isolation ------------------------------------------------------------
async def test_qt_m19_21_revoke_is_immediate(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M19-21 (store-agent part): after W-05 the agent gets 403 ONEC_AGENT_REVOKED at once."""
    fx = await _agent(client, app_db, admin_engine)
    queued = await enqueue(app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "v"})
    assert (await hello(client, fx, FULL_CAPABILITIES)).status_code == 200  # status cached as active
    r = await client.post(
        f"/api/v1/onec-agents/{fx.agent_id}/revoke",
        json={"reason": "replaced", "note": "PC almashdi"},
        headers=fx.shop.owner.headers(write=True),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "revoked" and r.json()["revoke_reason"] == "replaced"
    for call in (hello(client, fx, FULL_CAPABILITIES), poll(client, fx)):
        denied = await call
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "ONEC_AGENT_REVOKED"
    row = await _one(admin_engine, "SELECT status FROM app.onec_agent_tasks WHERE id = :t", t=queued)
    assert row[0] == "cancelled"
    device = await _one(admin_engine, "SELECT revoked_at FROM app.devices WHERE id = :d", d=fx.device_id)
    assert device[0] is not None
    again = await client.post(
        f"/api/v1/onec-agents/{fx.agent_id}/revoke",
        json={"reason": "user"},
        headers=fx.shop.owner.headers(write=True),
    )
    assert again.status_code == 200 and again.json()["revoke_reason"] == "replaced"
    audits = await _one(
        admin_engine,
        "SELECT count(*) FROM app.audit_log WHERE entity_id = :a AND action = 'onec.agent.revoked'",
        a=fx.agent_id,
    )
    assert audits[0] == 1


async def test_onec_agent_unpair_a10(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    r = await client.post("/api/v1/onec-agent/unpair", json={"reason": "uninstall"}, headers=fx.headers())
    assert r.status_code == 204, r.text
    row = await _one(
        admin_engine,
        "SELECT status, revoke_reason, revoked_by FROM app.onec_agents WHERE id = :a",
        a=fx.agent_id,
    )
    assert row[0] == "revoked" and row[1] == "uninstall" and row[2] is None
    audit = await _one(
        admin_engine,
        "SELECT device_id FROM app.audit_log WHERE entity_id = :a AND action = 'onec.agent.unpaired'",
        a=fx.agent_id,
    )
    assert audit[0] == fx.device_id
    after = await client.get("/api/v1/onec-agent/task-keys", headers=fx.headers())
    assert after.status_code == 403


async def test_onec_agent_subscription_lockout(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    """33 §9.1 / 14 §21: restricted tenant — hello/poll 403, heartbeat/result/logs still accepted."""
    fx = await _agent(client, app_db, admin_engine)
    await enqueue(app_db, fx.tenant_id, fx.agent_id, "fiscal.status", {"cash_register_id": "l"})
    task = (await poll(client, fx)).json()["tasks"][0]
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE app.subscriptions SET status = 'restricted' WHERE tenant_id = :t"),
            {"t": fx.tenant_id},
        )
    await clean_redis.set(f"sub_status:{fx.tenant_id}", "restricted")
    for call in (hello(client, fx, FULL_CAPABILITIES), poll(client, fx)):
        denied = await call
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "SUBSCRIPTION_RESTRICTED"
    hb = await client.post(
        f"/api/v1/onec-agent/tasks/{task['task_id']}/heartbeat",
        json={"lease_id": task["lease_id"]},
        headers=fx.headers(),
    )
    assert hb.status_code == 200
    assert (await result(client, fx, task)).status_code == 200
    logs = await client.post(
        "/api/v1/onec-agent/logs",
        headers=fx.headers(),
        json={
            "entries": [
                {
                    "client_log_id": str(uuid.uuid4()),
                    "at": "2026-10-15T18:03:41Z",
                    "level": "info",
                    "message": "ok",
                }
            ]
        },
    )
    assert logs.status_code == 200
    # the token endpoint still serves the agent (14 §16.1.2 exception)
    from tests.support.agent import assertion_token

    assert (await assertion_token(client, fx)).status_code == 200


async def test_qt_m19_23_agent_tenant_isolation(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M19-23: agent A never sees or touches agent B's (tenant B's) task; body tenant ignored."""
    a = await _agent(client, app_db, admin_engine)
    b = await _agent(client, app_db, admin_engine)
    await enqueue(app_db, b.tenant_id, b.agent_id, "fiscal.status", {"cash_register_id": "b"})
    assert (await poll(client, a, tenant_id=str(b.tenant_id), agent_id=str(b.agent_id))).status_code == 204
    task_b = (await poll(client, b)).json()["tasks"][0]
    hb = await client.post(
        f"/api/v1/onec-agent/tasks/{task_b['task_id']}/heartbeat",
        json={"lease_id": task_b["lease_id"], "tenant_id": str(b.tenant_id)},
        headers=a.headers(),
    )
    assert hb.status_code == 404
    res = await result(client, a, task_b, tenant_id=str(b.tenant_id))
    assert res.status_code == 404
    logs = await client.get(f"/api/v1/onec-agents/{b.agent_id}/logs", headers=a.shop.owner.headers())
    assert logs.status_code == 404


# --- A-06 / W-08 / A-07 / W-07 ---------------------------------------------------------------------------
async def test_onec_agent_logs_masked_deduped_and_listed(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    dup_id = str(uuid.uuid4())
    entries = [
        {
            "client_log_id": dup_id,
            "at": "2026-10-15T18:03:41Z",
            "level": "warn",
            "code": "ONEC_LOCK_CONFLICT",
            "message": "Srvr=1c;Ref=shop;Usr=erp;Pwd=Secret123; Bearer eyJhbGciOi.eyJzdWIiOi.c2ln card 8600123412345678",
            "context": {"stage": "posting", "password": "x", "nested": {"client_assertion": "y"}},
        },
        {
            "client_log_id": str(uuid.uuid4()),
            "at": "2026-10-15T18:03:42Z",
            "level": "info",
            "message": "poll ok",
        },
        {"client_log_id": dup_id, "at": "2026-10-15T18:03:41Z", "level": "warn", "message": "again"},
    ]
    r = await client.post("/api/v1/onec-agent/logs", json={"entries": entries}, headers=fx.headers())
    assert r.status_code == 200 and r.json() == {"accepted": 2, "duplicates": 1}
    again = await client.post("/api/v1/onec-agent/logs", json={"entries": entries[:1]}, headers=fx.headers())
    assert again.json() == {"accepted": 0, "duplicates": 1}
    listed = await client.get(
        f"/api/v1/onec-agents/{fx.agent_id}/logs",
        params={"level__in": "warn,error"},
        headers=fx.shop.owner.headers(),
    )
    assert listed.status_code == 200, listed.text
    (item,) = listed.json()["items"]
    assert (
        "Secret123" not in item["message"]
        and "eyJ" not in item["message"]
        and "8600123412345678" not in item["message"]
    )
    assert item["message"].endswith("***5678") and item["source"] == "agent" and item["message_key"] is None
    assert item["context"] == {"stage": "posting", "password": "***", "nested": {"client_assertion": "***"}}
    page1 = await client.get(
        f"/api/v1/onec-agents/{fx.agent_id}/logs", params={"limit": 1}, headers=fx.shop.owner.headers()
    )
    cursor = page1.json()["next_cursor"]
    assert cursor and page1.json()["items"][0]["message"] == "poll ok"
    page2 = await client.get(
        f"/api/v1/onec-agents/{fx.agent_id}/logs",
        params={"limit": 1, "cursor": cursor},
        headers=fx.shop.owner.headers(),
    )
    assert page2.json()["items"][0]["level"] == "warn" and page2.json()["next_cursor"] is None
    bad = await client.get(
        f"/api/v1/onec-agents/{fx.agent_id}/logs",
        params={"level__in": "fatal"},
        headers=fx.shop.owner.headers(),
    )
    assert bad.status_code == 422


async def test_onec_agent_gzip_request_body(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await _agent(client, app_db, admin_engine)
    body = json.dumps(
        {
            "entries": [
                {
                    "client_log_id": str(uuid.uuid4()),
                    "at": "2026-10-15T18:03:41Z",
                    "level": "info",
                    "message": "x" * 3000,
                }
            ]
        }
    ).encode()
    r = await client.post(
        "/api/v1/onec-agent/logs",
        content=gzip.compress(body),
        headers={**fx.headers(), "Content-Encoding": "gzip", "Content-Type": "application/json"},
    )
    assert r.status_code == 200 and r.json()["accepted"] == 1


def _zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("logs/agent.log", "ok")
    return buffer.getvalue()


async def test_onec_agent_diagnostics_request_upload_and_journal(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """W-07 → collect_diagnostics → A-07 upload → A-05 → W-08 ``diagnostics_ready``."""
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    offline = await client.post(
        f"/api/v1/onec-agents/{fx.agent_id}/diagnostics-requests",
        json={"include_logs_days": 2},
        headers=fx.shop.owner.headers(write=True),
    )
    assert offline.status_code == 202, offline.text
    assert offline.json()["warnings"][0]["code"] == "ONEC_AGENT_OFFLINE"
    await hello(client, fx, FULL_CAPABILITIES)
    task = (await poll(client, fx)).json()["tasks"][0]
    assert task["kind"] == "collect_diagnostics" and task["purpose"] == "diagnostics"
    assert task["payload"] == {"include_logs_days": 2, "include_settings": True}
    not_zip = await client.post(
        "/api/v1/onec-agent/diagnostics",
        data={"task_id": task["task_id"]},
        files={"file": ("d.zip", b"not a zip", "application/zip")},
        headers=fx.headers(),
    )
    assert not_zip.status_code == 422
    up = await client.post(
        "/api/v1/onec-agent/diagnostics",
        data={"task_id": task["task_id"]},
        files={"file": ("diag.zip", _zip(), "application/zip")},
        headers=fx.headers(),
    )
    assert up.status_code == 201, up.text
    attachment_id = up.json()["attachment_id"]
    row = await _one(
        admin_engine,
        "SELECT kind, uploaded_by FROM app.attachments WHERE id = :i",
        i=uuid.UUID(attachment_id),
    )
    assert row[0] == "onec_diagnostics" and row[1] == fx.shop.owner.user_id
    assert (await result(client, fx, task, data={"attachment_id": attachment_id})).status_code == 200
    journal = await client.get(f"/api/v1/onec-agents/{fx.agent_id}/logs", headers=fx.shop.owner.headers())
    ready = [i for i in journal.json()["items"] if i["code"] == "diagnostics_ready"]
    assert (
        ready and ready[0]["source"] == "server" and ready[0]["context"] == {"attachment_id": attachment_id}
    )
    assert ready[0]["message_key"] == "onec.events.diagnostics_ready"
    audit = await _one(
        admin_engine,
        "SELECT count(*) FROM app.audit_log WHERE tenant_id = :t AND action = 'onec.diagnostics.requested'",
        t=fx.tenant_id,
    )
    assert audit[0] == 1


async def test_onec_agent_task_keys_and_signed_manifest(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    keys = await client.get("/api/v1/onec-agent/task-keys", headers=fx.headers())
    assert keys.status_code == 200
    header, payload = verify_compact(keys.json()["task_keyset"], root_key().public_key())
    assert header["typ"] == "onec-task-keyset+jwt" and payload["ver"] == keys.json()["version"]
    assert payload["keys"] and payload["exp"] - payload["iat"] == 180 * 86400
    m = await client.get(
        "/api/v1/onec-agent/update-manifest", params={"channel": "stable"}, headers=fx.headers()
    )
    assert m.status_code == 200
    raw = base64.b64decode(m.json()["manifest"])
    root_key().public_key().verify(base64.b64decode(m.json()["signature"]), raw)
    assert json.loads(raw)["version"] == "1.4.3"
    pilot = await client.get(
        "/api/v1/onec-agent/update-manifest", params={"channel": "pilot"}, headers=fx.headers()
    )
    assert pilot.status_code == 404
    bad = await client.get(
        "/api/v1/onec-agent/update-manifest", params={"channel": "beta"}, headers=fx.headers()
    )
    assert bad.status_code == 422


# --- W-03 / W-04 permissions and idempotency ---------------------------------------------------------------
async def test_onec_agent_pairing_permissions_and_idempotency(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    from tests.support.agent import AgentKey, device_authorize

    shop = await make_shop(app_db, client)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    started = (await device_authorize(client, AgentKey())).json()
    code = started["user_code"]
    card = await client.get(f"/api/v1/onec-agents/pairing-requests/{code}", headers=shop.owner.headers())
    assert card.status_code == 200, card.text
    assert card.json()["pc_name"] == "DOKON-PC" and card.json()["request_ip"] == "127.0.0.1"
    assert (
        await client.get(f"/api/v1/onec-agents/pairing-requests/{code}", headers=cashier.headers())
    ).status_code == 403
    no_key = await client.post(
        "/api/v1/onec-agents/pair", json={"user_code": code}, headers=shop.owner.headers()
    )
    assert no_key.status_code == 422
    key = str(uuid.uuid4())
    headers = {**shop.owner.headers(), "Idempotency-Key": key}
    first = await client.post(
        "/api/v1/onec-agents/pair", json={"user_code": code, "name": "Kassa PK"}, headers=headers
    )
    assert first.status_code == 201 and first.json()["name"] == "Kassa PK"
    replay = await client.post(
        "/api/v1/onec-agents/pair", json={"user_code": code, "name": "Kassa PK"}, headers=headers
    )
    assert replay.status_code == 201 and replay.json()["id"] == first.json()["id"]
    assert replay.headers.get("idempotent-replayed") == "true"
    used = await client.post(
        "/api/v1/onec-agents/pair", json={"user_code": code}, headers=shop.owner.headers(write=True)
    )
    assert used.status_code == 404 and used.json()["error"]["code"] == "ONEC_PAIRING_CODE_INVALID"
    garbage = await client.get("/api/v1/onec-agents/pairing-requests/AAAA-1111", headers=shop.owner.headers())
    assert garbage.status_code == 404
    audit = await _one(
        admin_engine,
        "SELECT count(*) FROM app.audit_log WHERE tenant_id = :t AND action = 'onec.agent.paired'",
        t=shop.tenant_id,
    )
    assert audit[0] == 1
