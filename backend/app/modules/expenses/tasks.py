"""SAQ jobs of the expenses slice (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.db.session import Database, TenantContextError
from app.modules.expenses.wiring import remind_recurring


async def expenses_recurring_remind(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """Daily: due recurring expenses → ``recurring_expense_due`` reminder (US-M15-02; never auto-paid)."""
    try:
        tid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {tenant_id!r}") from exc
    db: Database = ctx["db"]
    return {"reminded": await remind_recurring(db, tid)}
