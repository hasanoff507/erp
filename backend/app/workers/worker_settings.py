"""SAQ worker and scheduler settings (23 §4, §9).

    saq app.workers.worker_settings.settings            # worker (scales out)
    saq app.workers.worker_settings.scheduler_settings  # scheduler (single leader)

The scheduler takes a PostgreSQL advisory lock before running cron jobs, so
extra scheduler replicas wait instead of running cron twice.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from saq import Queue
from saq.types import SettingsDict
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db.session import Database
from app.core.logging import configure_logging
from app.core.queue import make_queue
from app.workers.cron import CRON_JOBS
from app.workers.jobs import FUNCTIONS

log = structlog.get_logger(__name__)

SCHEDULER_LOCK_KEY = 0x45525053_4348  # "ERPSCH"
LEADER_POLL_S = 15.0


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json)
    ctx["db"] = Database.from_settings(settings)


async def shutdown(ctx: dict[str, Any]) -> None:
    db: Database | None = ctx.get("db")
    if db is not None:
        await db.dispose()


async def scheduler_startup(ctx: dict[str, Any]) -> None:
    await startup(ctx)
    db: Database = ctx["db"]
    conn = await db.engine.connect()
    while True:
        got = (
            await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": SCHEDULER_LOCK_KEY})
        ).scalar()
        await conn.commit()
        if got:
            break
        log.info("scheduler_standby", reason="another scheduler holds the leader lock")
        await asyncio.sleep(LEADER_POLL_S)
    ctx["leader_conn"] = conn  # session-level lock lives as long as this connection
    log.info("scheduler_leader")


async def scheduler_shutdown(ctx: dict[str, Any]) -> None:
    conn = ctx.pop("leader_conn", None)
    if conn is not None:
        await conn.close()
    await shutdown(ctx)


def _queue() -> Queue:
    settings = get_settings()
    return make_queue(settings.redis_url.get_secret_value(), settings.queue_name)


def _worker_settings() -> SettingsDict[Any]:
    return {
        "queue": _queue(),
        "functions": FUNCTIONS,
        "concurrency": get_settings().worker_concurrency,
        "startup": startup,
        "shutdown": shutdown,
    }


def _scheduler_settings() -> SettingsDict[Any]:
    return {
        "queue": _queue(),
        "functions": FUNCTIONS,
        "concurrency": 1,
        "cron_jobs": CRON_JOBS,
        "startup": scheduler_startup,
        "shutdown": scheduler_shutdown,
    }


settings = _worker_settings
scheduler_settings = _scheduler_settings
