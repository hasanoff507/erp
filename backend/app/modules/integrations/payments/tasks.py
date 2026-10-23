"""SAQ jobs of the payments slice (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.db.session import Database, TenantContextError
from app.modules.integrations.payments.wiring import checkout_expiry


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


async def payments_checkout_expire(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Every 5 min: ``pending`` checkouts past ``expires_at`` → ``expired`` (18 §16.2, qaror #54)."""
    db: Database = ctx["db"]
    return {"expired": await checkout_expiry(db.session_factory).run(_tenant(tenant_id))}
