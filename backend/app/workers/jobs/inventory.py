"""Inventory cron fan-outs (27 B2): the scheduler only lists tenants and enqueues per-tenant jobs."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.db.session import Database
from app.core.queue import SaqJobQueue

log = structlog.get_logger(__name__)

DAILY_JOB = "inventory_daily"
SWEEP_JOB = "inventory_recost_sweep"


async def inventory_daily_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily (00:20 Tashkent): valuation switch + ``expiry_soon``/``low_stock`` events, per tenant."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    tenants = await fan_out(db, SaqJobQueue(ctx["worker"].queue), DAILY_JOB)
    log.info("inventory_daily_enqueued", tenants=tenants)
    return {"tenants": tenants}


async def inventory_recost_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every 15 minutes: re-enqueue queued ``recost_jobs`` per tenant (lost enqueue backstop)."""
    from app.workers.cron import fan_out

    db: Database = ctx["db"]
    tenants = await fan_out(db, SaqJobQueue(ctx["worker"].queue), SWEEP_JOB)
    return {"tenants": tenants}
