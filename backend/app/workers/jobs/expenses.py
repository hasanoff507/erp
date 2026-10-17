"""Expenses cron fan-out (US-M15-02 recurring reminders, 23 §4)."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.expenses.wiring import REMIND_JOB


async def expenses_recurring_remind_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily 09:00 Tashkent: per tenant, record reminders for due recurring expenses."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), REMIND_JOB)}
