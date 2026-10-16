"""Infrastructure jobs."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db.rls import db_tenant_id
from app.core.db.session import Database
from app.core.queue import tenant_job
from app.modules.auth.infrastructure.repositories import AuthRepository

log = structlog.get_logger(__name__)


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
    deleted = await AuthRepository(db.session_factory).purge_login_attempts(days)
    log.info("login_attempts_purged", deleted=deleted, retention_days=days)
    return {"deleted": deleted, "retention_days": days}
