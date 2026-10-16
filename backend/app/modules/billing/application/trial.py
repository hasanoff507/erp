"""Trial subscription of a new tenant (15 §1.5, US-M17-01): ``status='trial'``, 30 days, plan ``standard``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.application.ports import SubscriptionStore
from app.modules.billing.domain.plans import STANDARD_PLAN_CODE, TRIAL_DAYS


async def start_trial(store: SubscriptionStore, session: AsyncSession, tenant_id: UUID) -> datetime:
    """Inside the signup transaction; returns the trial end (``current_period_end``)."""
    period_end = datetime.now(UTC) + timedelta(days=TRIAL_DAYS)
    if not await store.insert_subscription(session, tenant_id, STANDARD_PLAN_CODE, period_end, "trial"):
        raise RuntimeError("platform.plans 'standard' is missing — run `scripts.seed global` (12 §5.1)")
    return period_end
