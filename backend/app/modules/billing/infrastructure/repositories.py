"""SQL for ``app.subscriptions`` (12 §2, 0007)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7

_INSERT = text(
    "INSERT INTO app.subscriptions (id, tenant_id, plan_id, period, current_period_end, status) "
    "SELECT :id, :tenant_id, p.id, 'month', :period_end, :status FROM platform.plans p WHERE p.code = :plan "
    "RETURNING id"
)


class SqlSubscriptionStore:
    async def insert_subscription(
        self, session: AsyncSession, tenant_id: UUID, plan_code: str, period_end: datetime, status: str
    ) -> bool:
        params = {
            "id": uuid7(), "tenant_id": tenant_id, "period_end": period_end, "status": status,
            "plan": plan_code,
        }  # fmt: skip
        return (await session.execute(_INSERT, params)).first() is not None
