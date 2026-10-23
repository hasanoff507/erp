"""Public entry points of the billing module (23 §1 ``wiring.py``) — Bosqich 1: signup trial, terms."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import unscoped_transaction
from app.modules.billing.application import terms, trial
from app.modules.billing.application.terms import TermsVersion
from app.modules.billing.infrastructure.repositories import SqlSubscriptionStore
from app.modules.billing.infrastructure.terms import SqlTermsReader

__all__ = ["TermsVersion", "current_terms", "start_trial"]

_STORE = SqlSubscriptionStore()
_TERMS = SqlTermsReader()


async def start_trial(session: AsyncSession, tenant_id: UUID) -> datetime:
    """``subscriptions(status='trial', 30 days, plan standard)`` in the caller's transaction."""
    return await trial.start_trial(_STORE, session, tenant_id)


async def current_terms(session_factory: async_sessionmaker[AsyncSession]) -> list[TermsVersion]:
    """Current text versions; a global table, read without a tenant context."""
    async with session_factory() as session, unscoped_transaction(session):
        return await terms.current_terms(_TERMS, session)
