"""Payments cron fan-out (23 §4 ``payments_checkout_expire``; 18 §16.2)."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.integrations.payments.wiring import PAYMENTS_CHECKOUT_EXPIRE_JOB


async def payments_checkout_expire_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every 5 min: per tenant, mark pending checkouts past ``expires_at`` as ``expired``."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), PAYMENTS_CHECKOUT_EXPIRE_JOB)}
