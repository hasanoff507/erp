"""Store-agent cron fan-out (Bosqich 5, 33 §4.4): the scheduler lists tenants and enqueues per-tenant jobs.

Bosqich 5 fans out over ``app.list_active_tenant_ids()``; ``app.onec_tenants_due('sweep')`` (only tenants
with a 1C base) arrives with revision 0029 (Bosqich 7) — store-agent tasks need no 1C base.
"""

from __future__ import annotations

from typing import Any

from app.core.db.session import Database
from app.core.queue import SaqJobQueue
from app.modules.onec_integration.wiring import SWEEP_JOB


async def onec_lease_sweeper_fanout(ctx: dict[str, Any]) -> dict[str, int]:
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    return {"tenants": await fan_out(db, SaqJobQueue(ctx["worker"].queue), SWEEP_JOB)}
