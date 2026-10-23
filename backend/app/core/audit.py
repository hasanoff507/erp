"""Append-only ``audit_log`` writer (15 §6).

``audit_log.tenant_id`` is NOT NULL and RLS-bound, so every event belongs to a
tenant; platform-level events without a tenant (e.g. ``signing_key_rotated``)
go to the structured log instead.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.context import session_user_var
from app.core.db.session import tenant_transaction

log = structlog.get_logger(__name__)

_INSERT = text(
    "INSERT INTO app.audit_log (tenant_id, user_id, action, entity, entity_id, before, after, ip, device_id) "
    "VALUES (:tenant_id, :user_id, :action, :entity, :entity_id, CAST(:before AS jsonb), "
    "CAST(:after AS jsonb), CAST(:ip AS inet), :device_id)"
)


def _json(value: dict[str, Any] | None) -> str | None:
    return None if value is None else json.dumps(value, default=str, ensure_ascii=False)


async def record_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    action: str,
    entity: str,
    user_id: UUID | None = None,
    entity_id: UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    device_id: UUID | None = None,
) -> None:
    """Insert inside the caller's ``tenant_transaction``.

    While a PIN-verified actor acts on a device session (14 §4.3), ``user_id`` is the actor and the
    device session's own user is kept in ``after.on_behalf_session_user`` (15 §6.1).
    """
    session_user = session_user_var.get()
    if session_user is not None and session_user != user_id:
        after = {**(after or {}), "on_behalf_session_user": str(session_user)}
    await session.execute(
        _INSERT,
        {
            "tenant_id": tenant_id, "user_id": user_id, "action": action, "entity": entity,
            "entity_id": entity_id, "before": _json(before), "after": _json(after), "ip": ip,
            "device_id": device_id,
        },
    )  # fmt: skip


class AuditLog:
    """Standalone writer: one short tenant transaction per event."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def write(self, *, tenant_id: UUID, action: str, entity: str, **fields: Any) -> None:
        async with (
            self._sf() as session,
            tenant_transaction(session, tenant_id, user_id=fields.get("user_id")),
        ):
            await record_audit(session, tenant_id=tenant_id, action=action, entity=entity, **fields)
        log.info("audit", action=action, tenant_id=str(tenant_id), entity=entity)
