"""``purge_idempotency_keys`` cron (23 §3/§4, 27 Bosqich 1): tenant fan-out, retention window, RLS."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database, tenant_transaction
from app.workers.cron import CRON_JOBS
from app.workers.jobs import FUNCTIONS
from app.workers.jobs.system import (
    PURGE_IDEMPOTENCY_JOB,
    purge_idempotency_keys,
    purge_idempotency_keys_fanout,
)
from tests.support.factories import create_tenant_world

pytestmark = pytest.mark.db


async def _insert_key(admin_engine: AsyncEngine, tenant_id: UUID, key: str, age_days: int) -> None:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO app.idempotency_keys (tenant_id, key, request_hash, response_status, "
                "response_body, created_at) VALUES (:t, :k, 'h', 200, '{}'::jsonb, "
                "now() - make_interval(days => :d))"
            ),
            {"t": tenant_id, "k": key, "d": age_days},
        )


async def _keys(db: Database, tenant_id: UUID) -> set[str]:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        rows = await s.execute(text("SELECT key FROM app.idempotency_keys"))
        return {row[0] for row in rows}


async def test_purge_deletes_only_expired_rows_of_its_own_tenant(
    app_db: Database, admin_engine: AsyncEngine
) -> None:
    a = await create_tenant_world(app_db, "Purge A")
    b = await create_tenant_world(app_db, "Purge B")
    await _insert_key(admin_engine, a.tenant_id, "old-a", 31)
    await _insert_key(admin_engine, a.tenant_id, "fresh-a", 29)
    await _insert_key(admin_engine, b.tenant_id, "old-b", 31)

    result = await purge_idempotency_keys({"db": app_db}, tenant_id=str(a.tenant_id), retention_days=30)

    assert result == {"deleted": 1, "retention_days": 30}
    assert await _keys(app_db, a.tenant_id) == {"fresh-a"}
    # tenant B is untouched: the DELETE ran under tenant A's RLS context
    assert await _keys(app_db, b.tenant_id) == {"old-b"}


async def test_purge_rejects_a_window_shorter_than_one_day(app_db: Database) -> None:
    w = await create_tenant_world(app_db, "Purge C")
    with pytest.raises(ValueError, match="retention_days"):
        await purge_idempotency_keys({"db": app_db}, tenant_id=str(w.tenant_id), retention_days=0)


class _RecordingSaqQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, job: str, **kwargs: Any) -> None:
        self.calls.append((job, kwargs))
        return None


class _Worker:
    def __init__(self, queue: _RecordingSaqQueue) -> None:
        self.queue = queue


async def test_fanout_enqueues_one_job_per_active_tenant(app_db: Database, seeded: None) -> None:
    w = await create_tenant_world(app_db, "Purge fan-out")
    async with app_db.session_factory() as s, tenant_transaction(s, w.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.subscriptions (tenant_id, plan_id, period, current_period_end, status) "
                "SELECT :t, id, 'month', now() + interval '30 days', 'trial' FROM platform.plans "
                "WHERE code = 'standard'"
            ),
            {"t": w.tenant_id},
        )
    queue = _RecordingSaqQueue()
    result = await purge_idempotency_keys_fanout({"db": app_db, "worker": _Worker(queue)}, retention_days=30)
    assert result["retention_days"] == 30
    assert result["tenants"] == len(queue.calls) >= 1
    assert any(kw["tenant_id"] == str(w.tenant_id) for _, kw in queue.calls)
    assert all(job == PURGE_IDEMPOTENCY_JOB and kw["retention_days"] == 30 for job, kw in queue.calls)
    assert all(isinstance(UUID(kw["tenant_id"]), UUID) for _, kw in queue.calls)


def test_cron_runs_daily_at_0330_tashkent_and_jobs_are_registered() -> None:
    cron = next(job for job in CRON_JOBS if job.function is purge_idempotency_keys_fanout)
    assert cron.cron == "30 22 * * *"  # 22:30 UTC = 03:30 Asia/Tashkent (UTC+5, no DST)
    registered = dict(FUNCTIONS)
    assert registered[PURGE_IDEMPOTENCY_JOB] is purge_idempotency_keys
