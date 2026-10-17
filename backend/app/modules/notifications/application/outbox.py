"""Record a notification event in the caller's transaction (``outbox_jobs``, 23 §2.1 step 5).

``record_event`` writes ``outbox_jobs(kind='telegram', status='queued', payload={"event": kind, ...},
idempotency_key=dedupe_key)`` with ``ON CONFLICT (tenant_id, idempotency_key) DO NOTHING`` — so a
daily cron that runs twice, or a retried posting, records each event once. Nothing consumes
``kind='telegram'`` before Bosqich 4 (the sender).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.domain.events import EVENT_KINDS, OUTBOX_KIND


class OutboxRepository(Protocol):
    async def insert_once(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], idempotency_key: str
    ) -> bool: ...


class EventRecorder:
    def __init__(self, repo: OutboxRepository) -> None:
        self._repo = repo

    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool:
        """``True`` when a new row was written, ``False`` when ``dedupe_key`` was already recorded."""
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown notification event kind {kind!r} (20 #69)")
        if not dedupe_key or len(dedupe_key) > 200:
            raise ValueError("dedupe_key must be 1..200 characters")
        body = {"event": kind, **{k: v for k, v in payload.items() if k != "event"}}
        return await self._repo.insert_once(s, tenant_id, OUTBOX_KIND, body, dedupe_key)
