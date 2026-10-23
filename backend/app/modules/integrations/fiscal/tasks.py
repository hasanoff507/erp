"""SAQ jobs of the fiscal package (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError
from app.modules.integrations.fiscal.wiring import (
    LOCAL_BRIDGE,
    agent_status_sweep,
    ofd_send_service,
    provider_ack_poller,
    unacked_monitor,
)


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


def _settings(ctx: dict[str, Any]) -> Settings:
    settings: Settings = ctx.get("settings") or get_settings()
    return settings


async def fiscal_ofd_send(
    ctx: dict[str, Any], *, tenant_id: object = None, receipt_id: str
) -> dict[str, Any]:
    """Fiscalize one receipt through the provider (``outbox_jobs(kind='ofd_send')``, 21 §1)."""
    db: Database = ctx["db"]
    service = ofd_send_service(db.session_factory, _settings(ctx), ctx.get("fiscal_port"))
    outcome = await service.run(_tenant(tenant_id), UUID(receipt_id))
    return outcome.as_json() if outcome else {"skipped": True}


async def fiscal_ofd_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Cron backstop: every due ``ofd_send`` job of the tenant (retries, lost enqueues, dead workers)."""
    db: Database = ctx["db"]
    service = ofd_send_service(db.session_factory, _settings(ctx), ctx.get("fiscal_port"))
    done = await service.process_due(_tenant(tenant_id))
    return {"processed": len(done), "statuses": [o.status for o in done]}


async def fiscal_unacked_monitor(
    ctx: dict[str, Any], *, tenant_id: object = None, now: str | None = None
) -> dict[str, int]:
    """24/40/46/48 h stages of the oldest unacked receipt per register (16 §6, 21 §1 monitoring)."""
    db: Database = ctx["db"]
    at = datetime.fromisoformat(now) if now else None
    report = await unacked_monitor(db.session_factory).run(_tenant(tenant_id), at)
    return report.as_json()


async def fiscal_agent_status(
    ctx: dict[str, Any], *, tenant_id: object = None, now: str | None = None
) -> dict[str, int]:
    """Every 5 min: ``fiscal.status`` for each register bound to a store agent (21 §1, §16; 23 §4.2)."""
    db: Database = ctx["db"]
    at = datetime.fromisoformat(now) if now else None
    return await agent_status_sweep(db.session_factory).run(_tenant(tenant_id), at)


async def fiscal_ack_poll(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Every 5 min, server-side providers: ``resend_unsent`` → ``acked[]`` → ``ofd_acked_at`` (DoD-05)."""
    settings = _settings(ctx)
    if settings.fiscal_provider in LOCAL_BRIDGE:  # the store agent reports acks (fiscal.status)
        return {"registers": 0, "acked": 0, "failed": 0}
    db: Database = ctx["db"]
    return await provider_ack_poller(db.session_factory, settings, ctx.get("fiscal_port")).run(
        _tenant(tenant_id)
    )
