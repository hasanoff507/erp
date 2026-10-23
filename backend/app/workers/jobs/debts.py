"""Debts cron fan-out (27 B4): the scheduler only lists tenants and enqueues per-tenant jobs."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.db.session import Database
from app.core.queue import SaqJobQueue

log = structlog.get_logger(__name__)

DAILY_JOB = "debts_daily"


async def debts_daily_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily (09:00 Tashkent): ``debt_due_today`` / ``debt_aging_60`` per tenant (US-M08-09/10)."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    tenants = await fan_out(db, SaqJobQueue(ctx["worker"].queue), DAILY_JOB)
    log.info("debts_daily_enqueued", tenants=tenants)
    return {"tenants": tenants}
