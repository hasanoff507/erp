"""SAQ jobs of the card slice (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.db.session import Database, TenantContextError
from app.modules.integrations.card_terminal.wiring import orphan_sweep


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


async def card_orphan_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Hourly: approved purchases without a document after 24 h → ``card_orphan_transaction``."""
    db: Database = ctx["db"]
    return {"reported": await orphan_sweep(db.session_factory).run(_tenant(tenant_id))}
