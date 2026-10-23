"""SAQ jobs of the marking integration (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError
from app.modules.integrations.marking.wiring import acceptance_monitor, marking_outbox_service


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


def _settings(ctx: dict[str, Any]) -> Settings:
    settings: Settings = ctx.get("settings") or get_settings()
    return settings


async def marking_outbox_run(ctx: dict[str, Any], *, tenant_id: object = None, job_id: str) -> dict[str, Any]:
    """One CRPT notice / later verification (``outbox_jobs`` marking kinds, 21 §4)."""
    db: Database = ctx["db"]
    service = marking_outbox_service(db.session_factory, _settings(ctx), ports=ctx.get("marking_ports"))
    outcome = await service.run(_tenant(tenant_id), UUID(job_id))
    return outcome.as_json() if outcome else {"skipped": True}


async def marking_outbox_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Cron: every due marking job of the tenant (new rows, retries, dead workers)."""
    db: Database = ctx["db"]
    service = marking_outbox_service(db.session_factory, _settings(ctx), ports=ctx.get("marking_ports"))
    done = await service.process_due(_tenant(tenant_id))
    return {"processed": len(done), "statuses": [o.status for o in done]}


async def marking_acceptance_monitor(
    ctx: dict[str, Any], *, tenant_id: object = None, now: str | None = None
) -> dict[str, Any]:
    """Acceptance deadline stages ``due_soon`` / ``overdue`` → M18 (QT-NFR-07)."""
    db: Database = ctx["db"]
    at = datetime.fromisoformat(now) if now else None
    report = await acceptance_monitor(db.session_factory).run(_tenant(tenant_id), at)
    return report.as_json()
