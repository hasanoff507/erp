"""Ports of the billing application layer (23 §1)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class SubscriptionStore(Protocol):
    async def insert_subscription(
        self, session: AsyncSession, tenant_id: UUID, plan_code: str, period_end: datetime, status: str
    ) -> bool:
        """``False`` when the plan is missing (global seed not run)."""
        ...
