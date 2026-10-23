"""Marking cron fan-out (B5-T07, 21 §4): CRPT notice outbox and the acceptance deadline monitor."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.integrations.marking.wiring import MONITOR_JOB, OUTBOX_SWEEP_JOB


async def marking_outbox_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every minute: per tenant, the due marking outbox jobs (backoff base 1 min)."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), OUTBOX_SWEEP_JOB)}


async def marking_acceptance_monitor_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every 15 minutes: per tenant, acceptance deadline stages (72 h / 3 business days)."""
    from app.workers.cron import fan_out

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), MONITOR_JOB)}
