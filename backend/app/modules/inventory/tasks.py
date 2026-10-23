"""SAQ jobs of the inventory module (registered in ``app/workers/jobs/__init__.py``, 23 §4).

``ctx["db"]`` comes from the worker startup; ``ctx["settings"]`` may override the process settings.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError, tenant_transaction
from app.modules.inventory.wiring import recost_service, stock_notifier, valuation_service


def _uuid(raw: object, what: str) -> UUID:
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except ValueError as exc:
        if what == "tenant_id":
            raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc
        raise


def _settings(ctx: dict[str, Any]) -> Settings:
    settings: Settings = ctx.get("settings") or get_settings()
    return settings


async def inventory_recost(ctx: dict[str, Any], *, tenant_id: object = None, job_id: str) -> dict[str, Any]:
    """Run one ``recost_jobs`` row (13 §3.3)."""
    db: Database = ctx["db"]
    service = recost_service(db.session_factory, _settings(ctx))
    return await service.run(_uuid(tenant_id, "tenant_id"), _uuid(job_id, "job_id"))


async def inventory_recost_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Re-enqueue the tenant's queued recost jobs (cron backstop for lost enqueues)."""
    db: Database = ctx["db"]
    service = recost_service(db.session_factory, _settings(ctx))
    return {"enqueued": await service.sweep(_uuid(tenant_id, "tenant_id"))}


async def inventory_daily(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Daily per tenant: apply a FIFO↔AVECO switch that took effect, then record the ``expiry_soon`` /
    ``low_stock`` telegram events (27 B2; QT-M04-02, QT-M04-07)."""
    db: Database = ctx["db"]
    tid = _uuid(tenant_id, "tenant_id")
    async with db.session_factory() as s, tenant_transaction(s, tid):
        method = await valuation_service().ensure_applied(s, tid)
    async with db.session_factory() as s, tenant_transaction(s, tid):
        events = await stock_notifier().run(s, tid)
    return {"valuation_method": method, **events}
