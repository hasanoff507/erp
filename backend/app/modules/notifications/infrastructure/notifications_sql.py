"""SQL of the notifications module: ``telegram_links``, ``notification_settings``, ``notifications_log``
and the ``outbox_jobs(kind='telegram')`` worker queries (12 §2.x). Runs inside the caller's
``tenant_transaction`` (RLS)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.notifications.application.ports import ClaimedJob, LinkRow, LogRow, Recipient, SettingRow
from app.modules.notifications.domain.events import OUTBOX_KIND
from app.modules.notifications.domain.policy import LINK_PERMISSION

STALE_RUNNING_S = 600  # a 'running' job untouched this long lost its worker


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


def _has_permission(code_param: str) -> str:
    """``EXISTS`` over the member's live roles (same rule as ``require_permission``, 15 §2)."""
    return (
        "EXISTS (SELECT 1 FROM app.roles r JOIN app.role_permissions rp "  # noqa: S608
        "ON rp.tenant_id = r.tenant_id AND rp.role_id = r.id "
        "WHERE r.tenant_id = m.tenant_id AND r.id = ANY(m.role_ids) AND r.archived_at IS NULL "
        f"AND rp.permission_code = :{code_param})"
    )


_GET_LINK = text(
    "SELECT chat_id, linked_at, revoked_at FROM app.telegram_links WHERE tenant_id = :t AND user_id = :u"
)
_UPSERT_LINK = text(
    "INSERT INTO app.telegram_links (id, tenant_id, user_id, chat_id) VALUES (:id, :t, :u, :chat) "
    "ON CONFLICT (tenant_id, user_id) DO UPDATE SET chat_id = EXCLUDED.chat_id, linked_at = now(), "
    "revoked_at = NULL"
)
_REVOKE_LINK = text(
    "UPDATE app.telegram_links SET revoked_at = now() "
    "WHERE tenant_id = :t AND user_id = :u AND revoked_at IS NULL RETURNING id"
)
_REVOKE_CHAT = text(
    "UPDATE app.telegram_links SET revoked_at = now() "
    "WHERE chat_id = :chat AND revoked_at IS NULL RETURNING id"
)
_CAN_LINK = text(
    "SELECT 1 FROM app.memberships m WHERE m.tenant_id = :t AND m.user_id = :u AND m.status = 'active' "  # noqa: S608
    f"AND {_has_permission('link')}"
)
_NAMES = text(
    "SELECT tn.name, u.name, u.locale FROM app.users u JOIN app.tenants tn ON tn.id = :t WHERE u.id = :u"
)
_SETTINGS = text(
    "SELECT kind, enabled, time FROM app.notification_settings WHERE tenant_id = :t AND user_id = :u "
    "ORDER BY kind"
)
_UPSERT_SETTING = text(
    "INSERT INTO app.notification_settings (id, tenant_id, user_id, kind, enabled, time) "
    "VALUES (:id, :t, :u, :kind, :enabled, :at) ON CONFLICT (tenant_id, user_id, kind) DO UPDATE SET "
    "enabled = EXCLUDED.enabled, time = COALESCE(EXCLUDED.time, app.notification_settings.time), "
    "updated_at = now()"
)
_RECIPIENTS = text(
    "SELECT tl.user_id, tl.chat_id, u.locale, m.branch_ids, ns.time "  # noqa: S608
    "FROM app.telegram_links tl "
    "JOIN app.memberships m ON m.tenant_id = tl.tenant_id AND m.user_id = tl.user_id AND m.status = 'active' "
    "JOIN app.users u ON u.id = tl.user_id "
    "LEFT JOIN app.notification_settings ns "
    "ON ns.tenant_id = tl.tenant_id AND ns.user_id = tl.user_id AND ns.kind = :kind "
    "WHERE tl.revoked_at IS NULL AND COALESCE(ns.enabled, true) "
    "AND (CAST(:only AS uuid) IS NULL OR tl.user_id = CAST(:only AS uuid)) "
    f"AND {_has_permission('link')} AND {_has_permission('audience')} "
    "ORDER BY tl.user_id"
)
_REGISTER_BRANCH = text("SELECT branch_id FROM app.cash_registers WHERE id = :id")
_BRANCH_NAME = text("SELECT name FROM app.branches WHERE id = :id")
_CLAIM = text(
    "UPDATE app.outbox_jobs j SET status = 'running', attempts = j.attempts + 1, updated_at = now() "
    "WHERE j.id = (SELECT o.id FROM app.outbox_jobs o WHERE o.kind = 'telegram' "
    "AND ((o.status IN ('queued', 'retry') AND o.next_run_at <= now()) "
    "OR (o.status = 'running' AND o.updated_at < now() - make_interval(secs => :stale))) "
    "ORDER BY o.next_run_at, o.id LIMIT 1 FOR UPDATE SKIP LOCKED) "
    "RETURNING j.id, j.payload, j.attempts, j.idempotency_key, "
    "j.created_at >= now() - make_interval(secs => :max_age) AS fresh"
)
_ENQUEUE = text(
    "INSERT INTO app.outbox_jobs (id, tenant_id, kind, payload, status, idempotency_key) "
    "VALUES (:id, :t, :kind, CAST(:payload AS jsonb), 'queued', :key) "
    "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING id"
)
_JOB_EXISTS = text("SELECT 1 FROM app.outbox_jobs WHERE idempotency_key = :key")
_FINISH = text(
    "UPDATE app.outbox_jobs SET status = :st, last_error = :err, "
    "next_run_at = CASE WHEN CAST(:after AS double precision) IS NULL THEN next_run_at "
    "ELSE now() + make_interval(secs => CAST(:after AS double precision)) END, "
    "updated_at = now() WHERE id = :id AND kind = 'telegram'"
)
_LOG = text(
    "INSERT INTO app.notifications_log (id, tenant_id, channel, recipient, template, status) "
    "VALUES (:id, :t, 'telegram', :recipient, :template, :status)"
)
_LOG_PAGE = text(
    "SELECT id, channel, recipient, template, status, cost, created_at FROM app.notifications_log "
    "WHERE (CAST(:channel AS text) IS NULL OR channel = :channel) "
    "AND (CAST(:status AS text) IS NULL OR status = :status) "
    "AND (CAST(:before AS uuid) IS NULL OR id < CAST(:before AS uuid)) "
    "ORDER BY id DESC LIMIT :limit"
)


class SqlNotificationRepository:
    def __init__(self, stale_running_s: int = STALE_RUNNING_S) -> None:
        self._stale = stale_running_s

    # --- links --------------------------------------------------------------------------------------
    async def get_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> LinkRow | None:
        row = (await s.execute(_GET_LINK, {"t": tenant_id, "u": user_id})).first()
        return LinkRow(row[0], row[1], row[2]) if row else None

    async def upsert_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID, chat_id: str) -> None:
        await s.execute(_UPSERT_LINK, {"id": uuid7(), "t": tenant_id, "u": user_id, "chat": chat_id})

    async def revoke_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> bool:
        return (await s.execute(_REVOKE_LINK, {"t": tenant_id, "u": user_id})).first() is not None

    async def revoke_chat(self, s: AsyncSession, chat_id: str) -> int:
        return len((await s.execute(_REVOKE_CHAT, {"chat": chat_id})).all())

    async def member_can_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> bool:
        params = {"t": tenant_id, "u": user_id, "link": LINK_PERMISSION}
        return (await s.execute(_CAN_LINK, params)).first() is not None

    async def names(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> tuple[str, str, str]:
        row = (await s.execute(_NAMES, {"t": tenant_id, "u": user_id})).first()
        return (str(row[0]), str(row[1]), str(row[2])) if row else ("", "", "uz")

    # --- settings -----------------------------------------------------------------------------------
    async def settings(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> list[SettingRow]:
        rows = (await s.execute(_SETTINGS, {"t": tenant_id, "u": user_id})).all()
        return [SettingRow(r[0], bool(r[1]), r[2]) for r in rows]

    async def upsert_setting(
        self, s: AsyncSession, tenant_id: UUID, user_id: UUID, kind: str, enabled: bool, at: time | None
    ) -> None:
        params = {"id": uuid7(), "t": tenant_id, "u": user_id, "kind": kind, "enabled": enabled, "at": at}
        await s.execute(_UPSERT_SETTING, params)

    # --- recipients ---------------------------------------------------------------------------------
    async def recipients(
        self, s: AsyncSession, kind: str, audience: str, user_id: UUID | None = None
    ) -> list[Recipient]:
        params = {
            "kind": kind,
            "only": str(user_id) if user_id else None,
            "link": LINK_PERMISSION,
            "audience": audience,
        }
        rows = (await s.execute(_RECIPIENTS, params)).all()
        return [Recipient(r[0], str(r[1]), str(r[2] or "uz"), tuple(r[3] or ()), r[4]) for r in rows]

    async def branch_of_register(self, s: AsyncSession, cash_register_id: UUID) -> UUID | None:
        value = (await s.execute(_REGISTER_BRANCH, {"id": cash_register_id})).scalar()
        return value if isinstance(value, UUID) else None

    async def branch_name(self, s: AsyncSession, branch_id: UUID) -> str | None:
        value = (await s.execute(_BRANCH_NAME, {"id": branch_id})).scalar()
        return str(value) if value is not None else None

    # --- outbox -------------------------------------------------------------------------------------
    async def claim(self, s: AsyncSession, max_age: timedelta) -> ClaimedJob | None:
        params = {"stale": self._stale, "max_age": max_age.total_seconds()}
        row = (await s.execute(_CLAIM, params)).first()
        return ClaimedJob(row[0], _json(row[1]) or {}, row[2], row[3], bool(row[4])) if row else None

    async def enqueue(
        self, s: AsyncSession, tenant_id: UUID, payload: Mapping[str, Any], idempotency_key: str
    ) -> bool:
        params = {
            "id": uuid7(),
            "t": tenant_id,
            "kind": OUTBOX_KIND,
            "payload": json.dumps(dict(payload), default=str, ensure_ascii=False),
            "key": idempotency_key,
        }
        return (await s.execute(_ENQUEUE, params)).first() is not None

    async def job_exists(self, s: AsyncSession, idempotency_key: str) -> bool:
        return (await s.execute(_JOB_EXISTS, {"key": idempotency_key})).first() is not None

    async def finish(
        self, s: AsyncSession, job_id: UUID, status: str, last_error: str | None, run_after: timedelta | None
    ) -> None:
        params = {
            "st": status,
            "err": last_error,
            "id": job_id,
            "after": run_after.total_seconds() if run_after is not None else None,
        }
        await s.execute(_FINISH, params)

    async def log(self, s: AsyncSession, tenant_id: UUID, recipient: str, template: str, status: str) -> None:
        params = {
            "id": uuid7(),
            "t": tenant_id,
            "recipient": recipient,
            "template": template,
            "status": status,
        }
        await s.execute(_LOG, params)

    async def log_page(
        self,
        s: AsyncSession,
        *,
        channel: str | None,
        status: str | None,
        before: UUID | None,
        limit: int,
    ) -> list[LogRow]:
        params = {
            "channel": channel,
            "status": status,
            "before": str(before) if before else None,
            "limit": limit,
        }
        rows = (await s.execute(_LOG_PAGE, params)).all()
        return [LogRow(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]
