"""Fiscal cron fan-outs (Bosqich 3, 21 §1): the scheduler lists tenants and enqueues per-tenant jobs."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.integrations.fiscal.wiring import MONITOR_JOB, OFD_SWEEP_JOB


async def fiscal_ofd_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every minute: per tenant, the due ``outbox_jobs(kind='ofd_send')`` (retry backoff ≥ 30 s)."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), OFD_SWEEP_JOB)}


async def fiscal_unacked_monitor_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every 5 minutes: the 24/40/46/48 h fiscal timer of every register (16 §6)."""
    from app.workers.cron import fan_out

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), MONITOR_JOB)}
