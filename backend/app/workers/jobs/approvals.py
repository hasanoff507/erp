"""Approval-request expiry fan-out (18 §9.1): the scheduler only enqueues per-tenant jobs."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue

EXPIRE_JOB = "approval_requests_expire"


async def approval_requests_expire_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), EXPIRE_JOB)}
