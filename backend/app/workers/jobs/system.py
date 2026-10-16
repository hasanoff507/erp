"""Infrastructure jobs."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db.rls import db_tenant_id
from app.core.db.session import Database
from app.core.queue import SaqJobQueue, tenant_job
from app.modules.auth.wiring import build_auth_store

log = structlog.get_logger(__name__)

PURGE_IDEMPOTENCY_JOB = "purge_idempotency_keys"

_PURGE_IDEMPOTENCY = text(
    "DELETE FROM app.idempotency_keys WHERE created_at < now() - make_interval(days => :days)"
)


@tenant_job
async def noop(session: AsyncSession, **_: Any) -> dict[str, str | None]:
    """Does nothing but prove the job ran in its tenant's transaction."""
    tenant = await db_tenant_id(session)
    return {"tenant_id": str(tenant) if tenant else None}


async def purge_login_attempts(ctx: dict[str, Any], *, retention_days: int | None = None) -> dict[str, int]:
    """Daily ``auth.login_attempts`` retention (14 §19, 23 §4).

    Platform-level and tenant-less: no business query, only the SECURITY DEFINER
    ``app.auth_purge_login_attempts`` (12 §4.5) inside an unscoped transaction.
    """
    db: Database = ctx["db"]
    days = retention_days if retention_days is not None else get_settings().login_attempts_retention_days
    deleted = await build_auth_store(db).purge_login_attempts(days)
    log.info("login_attempts_purged", deleted=deleted, retention_days=days)
    return {"deleted": deleted, "retention_days": days}


@tenant_job
async def purge_idempotency_keys(session: AsyncSession, *, retention_days: int) -> dict[str, int]:
    """One tenant's ``idempotency_keys`` retention (23 §3/§4): rows older than the journal window.

    Runs in the tenant's transaction, so RLS limits the DELETE to that tenant.
    """
    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    result = await session.execute(_PURGE_IDEMPOTENCY, {"days": retention_days})
    deleted = int(getattr(result, "rowcount", 0) or 0)
    return {"deleted": deleted, "retention_days": retention_days}


async def purge_idempotency_keys_fanout(
    ctx: dict[str, Any], *, retention_days: int | None = None
) -> dict[str, int]:
    """Daily cron (03:30 Tashkent, 23 §4): enqueue :func:`purge_idempotency_keys` per active tenant.

    ``ERP_IDEMPOTENCY_RETENTION_DAYS`` (default 30) — the scheduler itself runs no
    business query (tenant ids come from ``app.list_active_tenant_ids()``).
    """
    from app.workers.cron import fan_out  # cron imports this module

    db: Database = ctx["db"]
    days = retention_days if retention_days is not None else get_settings().idempotency_retention_days
    queue = SaqJobQueue(ctx["worker"].queue)
    tenants = await fan_out(db, queue, PURGE_IDEMPOTENCY_JOB, retention_days=days)
    log.info("idempotency_purge_enqueued", tenants=tenants, retention_days=days)
    return {"tenants": tenants, "retention_days": days}
