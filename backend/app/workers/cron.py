"""SAQ cron list and tenant fan-out (23 §4).

The scheduler runs no business queries itself: it asks the SECURITY DEFINER
``app.list_active_tenant_ids()`` for tenants and enqueues one job per tenant.
The only tenant-less cron job is the ``auth.login_attempts`` retention purge.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from saq import CronJob
from sqlalchemy import text

from app.core.db.session import Database, unscoped_transaction
from app.core.queue import JobQueue
from app.workers.jobs.system import purge_login_attempts

# SAQ cron runs in UTC; Asia/Tashkent is UTC+5 all year (no DST)
CRON_JOBS: list[CronJob[Any]] = [
    CronJob(purge_login_attempts, cron="15 22 * * *"),  # 03:15 Tashkent (23 §4)
]

_ACTIVE_TENANTS = text("SELECT app.list_active_tenant_ids()")


async def active_tenant_ids(db: Database) -> list[UUID]:
    async with db.session_factory() as session, unscoped_transaction(session):
        return [row[0] for row in await session.execute(_ACTIVE_TENANTS)]


async def fan_out(db: Database, queue: JobQueue, job: str, **kwargs: Any) -> int:
    """Enqueue ``job`` once per active tenant; returns the number of jobs."""
    tenants = await active_tenant_ids(db)
    for tenant_id in tenants:
        await queue.enqueue(job, tenant_id, **kwargs)
    return len(tenants)
