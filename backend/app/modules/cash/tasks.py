"""SAQ jobs of the cash slice (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import Database, TenantContextError, session_tenant_id
from app.modules.access.wiring import expire_approval_requests
from app.modules.pricing.wiring import price_change_service


async def expire_approvals(db: Database, tenant_id: UUID) -> int:
    """Expire overdue ``pending`` requests of one tenant and release their linked documents (18 §9.1, §10)."""
    prices = price_change_service(db.session_factory)

    async def release_price_change(s: AsyncSession, doc_type: str, doc_id: UUID) -> None:
        del doc_type
        tid = session_tenant_id(s)
        if tid is not None:
            await prices.approval_expired(s, tenant_id=tid, doc_id=doc_id)

    return await expire_approval_requests(db, tenant_id, {"price_changes": release_price_change})


async def approval_requests_expire(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, int]:
    """``pending`` approval requests past ``expires_at`` → ``expired`` (18 §9.1; reads treat them so)."""
    try:
        tid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {tenant_id!r}") from exc
    db: Database = ctx["db"]
    return {"expired": await expire_approvals(db, tid)}
