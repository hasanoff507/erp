"""Telegram (M18) cron fan-outs (27 B4): the scheduler only lists tenants and enqueues per-tenant jobs."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.notifications.wiring import DAILY_REPORT_JOB, TELEGRAM_SWEEP_JOB


async def notifications_telegram_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every minute: per tenant, fan out recorded events and send due Telegram messages (QT-M18-03)."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), TELEGRAM_SWEEP_JOB)}


async def notifications_daily_report_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every 5 minutes: per tenant, queue the daily reports whose configured time has come (QT-M18-02)."""
    from app.workers.cron import fan_out

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), DAILY_REPORT_JOB)}
