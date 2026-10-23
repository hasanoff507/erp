"""SAQ jobs of the notifications module (registered in ``app/workers/jobs/__init__.py``, 23 §4).

``ctx["db"]`` comes from the worker startup; ``ctx["settings"]`` may override the process settings;
``ctx["telegram_port"]`` / ``ctx["daily_summary_source"]`` let tests inject a fake port / summary source.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError
from app.modules.notifications.wiring import daily_report_service, telegram_sender


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


def _settings(ctx: dict[str, Any]) -> Settings:
    settings: Settings = ctx.get("settings") or get_settings()
    return settings


async def notifications_telegram_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Every minute: fan out new events and deliver the tenant's due Telegram messages (21 §11)."""
    db: Database = ctx["db"]
    sender = telegram_sender(db.session_factory, _settings(ctx), ctx.get("telegram_port"))
    if sender is None:
        return {"processed": 0, "skipped": "telegram_not_configured"}
    done = await sender.process_due(_tenant(tenant_id))
    return {"processed": len(done), "statuses": [o.status for o in done]}


async def notifications_daily_report(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Every 5 minutes: queue the daily report of every recipient whose time has come (US-M18-02)."""
    db: Database = ctx["db"]
    service = daily_report_service(db.session_factory, ctx.get("daily_summary_source"))
    return await service.run(_tenant(tenant_id))
