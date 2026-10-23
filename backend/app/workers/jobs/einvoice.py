"""E-invoice cron fan-out (27 B2): the scheduler lists tenants and enqueues the ``ettn_send`` sweeper."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.integrations.einvoice.wiring import ETTN_SWEEP_JOB


async def einvoice_ettn_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every minute: per tenant, process the due ``outbox_jobs(kind='ettn_send')`` (retry backoff ≥ 1 min)."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), ETTN_SWEEP_JOB)}
