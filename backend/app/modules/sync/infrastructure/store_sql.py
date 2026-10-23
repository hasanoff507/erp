"""SQL of the sync module's own rows (``sync_receipts``, ``sync_exceptions``, ``devices`` sync columns) and
the read-only actor lookups of ``/sync/push`` (caller's ``tenant_transaction``, RLS-bound)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sync.application.ports import (
    ActorInfo,
    DeviceInfo,
    ExceptionFilter,
    ExceptionRow,
    StoredReceipt,
)

_DEVICE = text(
    "SELECT d.id, d.kind, d.revoked_at, d.cash_register_id, cr.branch_id FROM app.devices d "
    "LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id WHERE d.id = :id"
)
_CUTOFF = text(
    "SELECT now() AS now, least(now() - make_interval(secs => :settle), "
    "coalesce((SELECT min(a.xact_start) FROM pg_stat_activity a WHERE a.xact_start IS NOT NULL "
    "AND a.pid <> pg_backend_pid() AND a.datname = current_database() AND a.usename = current_user "
    "AND a.backend_type = 'client backend'), now())) - interval '1 microsecond' AS cutoff"
)
_TOUCH = text("UPDATE app.devices SET last_seen_at = now() WHERE id = :id")
_REPORT = text(
    "UPDATE app.devices SET last_sync_at = now(), last_seen_at = now(), outbox_reported_at = now(), "
    "outbox_pending_count = :pending, outbox_oldest_pending_at = :oldest WHERE id = :id"
)
_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_RECEIPT = text("SELECT id, device_id, result FROM app.sync_receipts WHERE client_event_id = :cid")
_INSERT_RECEIPT = text(
    "INSERT INTO app.sync_receipts (id, tenant_id, device_id, client_event_id, result) "
    "VALUES (:id, :tenant_id, :device_id, :cid, CAST(:result AS jsonb))"
)
_INSERT_EXCEPTION = text(
    "INSERT INTO app.sync_exceptions (id, tenant_id, device_id, client_event_id, kind, doc_type, doc_id, "
    "details) "
    "VALUES (:id, :tenant_id, :device_id, :client_event_id, :kind, :doc_type, :doc_id, CAST(:details AS "
    "jsonb))"
)
_ACTOR = text("SELECT status, branch_ids, updated_at FROM app.memberships WHERE user_id = :u")
_ACTOR_LIMITS = text(
    "SELECT rp.limit_value FROM app.memberships m "
    "JOIN app.roles r ON r.tenant_id = m.tenant_id AND r.id = ANY(m.role_ids) AND r.archived_at IS NULL "
    "JOIN app.role_permissions rp ON rp.tenant_id = m.tenant_id AND rp.role_id = r.id "
    "WHERE m.user_id = :u AND rp.permission_code = :code"
)
_GRACE = text("SELECT COALESCE(grace_ends_at, current_period_end) FROM app.subscriptions")
_AUDIT_EXISTS = text(
    "SELECT EXISTS (SELECT 1 FROM app.audit_log WHERE action = :action AND device_id = :d AND at >= :since)"
)


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


class SqlSyncStore:
    async def device(self, s: AsyncSession, device_id: UUID) -> DeviceInfo | None:
        row = (await s.execute(_DEVICE, {"id": device_id})).first()
        if row is None:
            return None
        return DeviceInfo(row.id, row.kind, row.revoked_at, row.cash_register_id, row.branch_id)

    async def touch_seen(self, s: AsyncSession, device_id: UUID) -> None:
        await s.execute(_TOUCH, {"id": device_id})

    async def db_now(self, s: AsyncSession) -> datetime:
        value: datetime = (await s.execute(text("SELECT now()"))).scalar_one()
        return value

    async def settle_cutoff(self, s: AsyncSession, settle_s: float) -> tuple[datetime, datetime]:
        """``(now, cutoff)``: rows stamped after ``cutoff`` are not delivered yet (16 §3.2, SYNC-07).

        ``cutoff = least(now − settle, start of the oldest transaction still open in this database by the
        application role) − 1 µs``: a running writer (an import, a long posting) stamps its rows with its
        own start time and commits later, so the cursor must not pass that instant before it ends. The app
        role sees ``xact_start`` of its own sessions in ``pg_stat_activity`` — every API/worker writer runs as
        that role. Transactions that have not written yet are included too (they may still write)."""
        row = (await s.execute(_CUTOFF, {"settle": settle_s})).one()
        return row.now, row.cutoff

    async def report_outbox(
        self, s: AsyncSession, device_id: UUID, pending_count: int, oldest_pending_at: datetime | None
    ) -> None:
        await s.execute(_REPORT, {"id": device_id, "pending": pending_count, "oldest": oldest_pending_at})

    async def lock_event(self, s: AsyncSession, tenant_id: UUID, client_event_id: UUID) -> None:
        await s.execute(_LOCK, {"key": f"sync:{tenant_id}:{client_event_id}"})

    async def receipt(self, s: AsyncSession, client_event_id: UUID) -> StoredReceipt | None:
        row = (await s.execute(_RECEIPT, {"cid": client_event_id})).first()
        return StoredReceipt(row.id, row.device_id, _json(row.result)) if row else None

    async def insert_receipt(
        self,
        s: AsyncSession,
        *,
        receipt_id: UUID,
        tenant_id: UUID,
        device_id: UUID,
        client_event_id: UUID,
        result: Mapping[str, Any],
    ) -> None:
        await s.execute(
            _INSERT_RECEIPT,
            {
                "id": receipt_id,
                "tenant_id": tenant_id,
                "device_id": device_id,
                "cid": client_event_id,
                "result": json.dumps(dict(result), default=str, ensure_ascii=False),
            },
        )

    async def insert_exception(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(_INSERT_EXCEPTION, dict(row))

    async def actor(self, s: AsyncSession, user_id: UUID) -> ActorInfo | None:
        row = (await s.execute(_ACTOR, {"u": user_id})).first()
        return ActorInfo(row.status, tuple(row.branch_ids or ()), row.updated_at) if row else None

    async def actor_limits(self, s: AsyncSession, user_id: UUID, code: str) -> list[Decimal | None]:
        return [r.limit_value for r in await s.execute(_ACTOR_LIMITS, {"u": user_id, "code": code})]

    async def grace_ends_at(self, s: AsyncSession) -> datetime | None:
        value: datetime | None = (await s.execute(_GRACE)).scalar()
        return value

    async def audit_exists(self, s: AsyncSession, action: str, device_id: UUID, since: datetime) -> bool:
        return bool(
            (await s.execute(_AUDIT_EXISTS, {"action": action, "d": device_id, "since": since})).scalar()
        )


_EXC_COLUMNS = (
    "e.id, e.kind, e.device_id, cr.branch_id, e.client_event_id, e.doc_type, e.doc_id, e.details, "
    "e.created_at, "
    "e.reviewed_at, e.reviewed_by, e.review_note"
)
_EXC_FROM = (
    "FROM app.sync_exceptions e LEFT JOIN app.devices d ON d.id = e.device_id "
    "LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id"
)


def _exception(row: Any) -> ExceptionRow:
    data = dict(row._mapping)
    data["details"] = _json(data["details"]) or {}
    return ExceptionRow(**data)


class SqlExceptionStore:
    async def page(
        self,
        s: AsyncSession,
        flt: ExceptionFilter,
        *,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[ExceptionRow]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if flt.reviewed is not None:
            where.append("e.reviewed_at IS NOT NULL" if flt.reviewed else "e.reviewed_at IS NULL")
        if flt.branch_id is not None:
            where.append("cr.branch_id = :branch_id")
            params["branch_id"] = flt.branch_id
        if flt.device_id is not None:
            where.append("e.device_id = :device_id")
            params["device_id"] = flt.device_id
        if flt.created_from is not None:
            where.append("e.created_at >= :created_from")
            params["created_from"] = flt.created_from
        if flt.created_to is not None:
            where.append("e.created_at <= :created_to")
            params["created_to"] = flt.created_to
        if branch_ids is not None:
            where.append("cr.branch_id = ANY(CAST(:branches AS uuid[]))")
            params["branches"] = list(branch_ids)
        if after is not None:
            where.append("(e.created_at, e.id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        rows = await s.execute(
            text(
                f"SELECT {_EXC_COLUMNS} {_EXC_FROM} {clause}ORDER BY e.created_at DESC, e.id DESC LIMIT "
                ":limit"
            ),
            params,
        )
        return [_exception(r) for r in rows]

    async def get(self, s: AsyncSession, exception_id: UUID, *, lock: bool = False) -> ExceptionRow | None:
        suffix = " FOR UPDATE OF e" if lock else ""
        row = (
            await s.execute(
                text(f"SELECT {_EXC_COLUMNS} {_EXC_FROM} WHERE e.id = :id{suffix}"), {"id": exception_id}
            )
        ).first()
        return _exception(row) if row else None

    async def mark_reviewed(self, s: AsyncSession, exception_id: UUID, user_id: UUID, note: str) -> datetime:
        at: datetime = (
            await s.execute(
                text(
                    "UPDATE app.sync_exceptions SET reviewed_at = now(), reviewed_by = :u, review_note = :n "
                    "WHERE id = :id RETURNING reviewed_at"
                ),
                {"id": exception_id, "u": user_id, "n": note},
            )
        ).scalar_one()
        return at
