"""SAQ jobs of the store-agent part (registered in ``app/workers/jobs/__init__.py``, 33 §4.4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError
from app.modules.onec_integration.wiring import lease_sweeper


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


async def onec_lease_sweeper(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Every minute per tenant: lost leases / unleased past ``expires_at`` → ``expired`` (33 §4.4, §9.9)."""
    db: Database = ctx["db"]
    settings: Settings = ctx.get("settings") or get_settings()
    return {"expired": await lease_sweeper(settings, db).run(_tenant(tenant_id))}
