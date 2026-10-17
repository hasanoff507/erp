"""SAQ jobs of the debts module (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.db.session import Database, TenantContextError, tenant_transaction
from app.modules.accounting.domain.calendar import business_today
from app.modules.debts.wiring import debt_daily_check


def _tenant(raw: object) -> UUID:
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


async def debts_daily(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Daily per tenant: ``debt_due_today`` / ``debt_aging_60`` events (US-M08-03/09/10; QT-M08-05/12)."""
    db: Database = ctx["db"]
    tid = _tenant(tenant_id)
    async with db.session_factory() as s, tenant_transaction(s, tid):
        result = await debt_daily_check().run(s, tid, business_today())
    return result.as_json()
