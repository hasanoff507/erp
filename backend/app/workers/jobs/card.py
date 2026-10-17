"""Card-terminal cron fan-out (23 §4 ``card_orphan_sweep``; qaror #71)."""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.integrations.card_terminal.wiring import CARD_ORPHAN_SWEEP_JOB


async def card_orphan_sweep_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    """Hourly: per tenant, report approved purchases left without a document for 24 h (no auto void)."""
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), CARD_ORPHAN_SWEEP_JOB)}
