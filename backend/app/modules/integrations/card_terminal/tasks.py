"""SAQ jobs of the card slice (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from app.core.db.session import Database, TenantContextError
from app.modules.integrations.card_terminal.domain.model import tashkent_date
from app.modules.integrations.card_terminal.wiring import card_agent_service, orphan_sweep


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


async def card_orphan_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Hourly: approved purchases without a document after 24 h → ``card_orphan_transaction``."""
    db: Database = ctx["db"]
    return {"reported": await orphan_sweep(db.session_factory).run(_tenant(tenant_id))}


async def card_status_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Every 5 min: one deduplicated ``card.status`` task per agent with the ``card_terminal`` capability."""
    db: Database = ctx["db"]
    report = await card_agent_service(None, db.session_factory).status_sweep(_tenant(tenant_id))
    return {"enqueued": report.enqueued, "skipped": report.skipped}


async def card_settlement_sweep(
    ctx: dict[str, Any], *, tenant_id: object = None, business_date: str | None = None
) -> dict[str, int]:
    """23:30 Tashkent: ``card.settlement`` for active agent terminals without a settlement of the day."""
    db: Database = ctx["db"]
    day = date.fromisoformat(business_date) if business_date else tashkent_date(datetime.now(UTC))
    report = await card_agent_service(None, db.session_factory).settlement_sweep(
        _tenant(tenant_id), business_date=day
    )
    return {"enqueued": report.enqueued, "skipped": report.skipped}
