"""``outbox_jobs`` SQL (12 §2.x). Runs inside the caller's ``tenant_transaction`` (RLS-bound)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7

_INSERT = text(
    "INSERT INTO app.outbox_jobs (id, tenant_id, kind, payload, status, idempotency_key) "
    "VALUES (:id, :tenant_id, :kind, CAST(:payload AS jsonb), 'queued', :key) "
    "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING id"
)


class SqlOutboxRepository:
    async def insert_once(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], idempotency_key: str
    ) -> bool:
        row = (
            await s.execute(
                _INSERT,
                {
                    "id": uuid7(),
                    "tenant_id": tenant_id,
                    "kind": kind,
                    "payload": json.dumps(dict(payload), default=str, ensure_ascii=False),
                    "key": idempotency_key,
                },
            )
        ).first()
        return row is not None
