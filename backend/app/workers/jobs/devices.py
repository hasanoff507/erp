"""B5 devices cron fan-out — agent ``card_terminal`` capability (23 §4.2 ``card.status``,
``card_settlement_sweep``; qaror #71)."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.integrations.card_terminal.wiring import CARD_SETTLEMENT_SWEEP_JOB, CARD_STATUS_SWEEP_JOB


async def card_status_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Every 5 min: per tenant, ``card.status`` for agents with the ``card_terminal`` capability."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), CARD_STATUS_SWEEP_JOB)}


async def card_settlement_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """23:30 Tashkent: per tenant, ``card.settlement`` for terminals not settled today."""
    from app.workers.cron import fan_out

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), CARD_SETTLEMENT_SWEEP_JOB)}
