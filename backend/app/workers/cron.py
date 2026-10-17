"""SAQ cron list and tenant fan-out (23 §4).

The scheduler runs no business queries itself: it asks the SECURITY DEFINER
``app.list_active_tenant_ids()`` for tenants and enqueues one job per tenant.
The only tenant-less cron job is the ``auth.login_attempts`` retention purge; the
``idempotency_keys`` purge fans out one job per tenant.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from saq import CronJob
from sqlalchemy import text

from app.core.db.session import Database, unscoped_transaction
from app.core.queue import JobQueue
from app.workers.jobs.approvals import approval_requests_expire_fanout
from app.workers.jobs.card import card_orphan_sweep_fanout
from app.workers.jobs.einvoice import einvoice_ettn_sweep_fanout
from app.workers.jobs.fiscal import fiscal_ofd_sweep_fanout, fiscal_unacked_monitor_fanout
from app.workers.jobs.inventory import inventory_daily_fanout, inventory_recost_sweep_fanout
from app.workers.jobs.system import purge_idempotency_keys_fanout, purge_login_attempts

# SAQ cron runs in UTC; Asia/Tashkent is UTC+5 all year (no DST)
CRON_JOBS: list[CronJob[Any]] = [
    CronJob(purge_login_attempts, cron="15 22 * * *"),  # 03:15 Tashkent (23 §4)
    CronJob(purge_idempotency_keys_fanout, cron="30 22 * * *"),  # 03:30 Tashkent, tenant fan-out (23 §4)
    # Bosqich 2 inventory: valuation switch + expiry_soon/low_stock events (00:20 Tashkent), recost sweeper
    CronJob(inventory_daily_fanout, cron="20 19 * * *"),
    CronJob(inventory_recost_sweep_fanout, cron="*/15 * * * *"),
    # e-TTN outbox: retries (backoff ≥ 1 min), lost enqueues, dead workers
    CronJob(einvoice_ettn_sweep_fanout, cron="* * * * *"),
    # --- B3 sales/fiscal cron ---
    CronJob(fiscal_ofd_sweep_fanout, cron="* * * * *"),  # ofd_send retries / lost enqueues (21 §1)
    CronJob(fiscal_unacked_monitor_fanout, cron="*/5 * * * *"),  # 24/40/46/48 h fiscal timer (16 §6)
    # --- B3 cash cron ---
    CronJob(approval_requests_expire_fanout, cron="*/5 * * * *"),  # pending past expires_at → expired
    # --- B3 card cron ---
    CronJob(card_orphan_sweep_fanout, cron="5 * * * *"),  # hourly: approved purchase w/o document > 24 h
    # --- B3 sync cron ---
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
