"""SQL of the store-agent registry (12 §2.11, 0028/0028a): ``onec_agents``, ``onec_agent_tasks``,
``onec_task_results``, ``onec_agent_logs`` (+ ``devices``, ``attachments`` rows of an agent). Raw SQL under
RLS — every statement runs inside the caller's ``tenant_transaction``."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onec_integration.application.ports import AgentRow, LogRow, StoredResult, TaskRow

_AGENT_COLS: Final = (
    "a.id, a.tenant_id, a.device_id, a.client_id, a.name, a.pc_name, a.machine_hash, a.os_version, "
    "a.agent_version, a.worker_bits, a.platforms, a.status, a.update_channel, a.capabilities, a.paired_by, "
    "(SELECT u.name FROM app.users u WHERE u.id = a.paired_by), a.paired_at, a.last_hello_at, "
    "a.last_poll_at, a.revoked_at, a.revoke_reason, a.version"
)
_TASK_COLS: Final = (
    "t.id, t.tenant_id, t.agent_id, t.base_id, t.kind, t.purpose, t.is_write, t.attempt, t.timeout_s, "
    "t.payload, t.payload_sha256, t.status, t.lease_id, "
    "t.leased_at, t.lease_until, t.created_by, t.expires_at"
)
_UPDATABLE_AGENT: Final = frozenset(
    {
        "name",
        "pc_name",
        "os_version",
        "agent_version",
        "worker_bits",
        "platforms",
        "capabilities",
        "last_hello_at",
        "last_poll_at",
        "last_ip",
        "machine_hash",
        "machine_hash_changed_at",
    }
)
_UPDATABLE_TASK: Final = frozenset(
    {
        "status",
        "outcome",
        "error_code",
        "finished_at",
        "lease_until",
        "heartbeat_at",
        "progress",
    }
)
_JSON_COLS: Final = frozenset({"platforms", "capabilities", "progress"})


def _json(value: Any) -> Any:
    return value if isinstance(value, dict | list) else json.loads(value) if isinstance(value, str) else value


def _agent(row: Any) -> AgentRow:
    return AgentRow(
        id=row[0],
        tenant_id=row[1],
        device_id=row[2],
        client_id=row[3],
        name=row[4],
        pc_name=row[5],
        machine_hash=row[6],
        os_version=row[7],
        agent_version=row[8],
        worker_bits=list(row[9] or []),
        platforms=_json(row[10]) or [],
        status=row[11],
        update_channel=row[12],
        capabilities=_json(row[13]) or {},
        paired_by=row[14],
        paired_by_name=row[15],
        paired_at=row[16],
        last_hello_at=row[17],
        last_poll_at=row[18],
        revoked_at=row[19],
        revoke_reason=row[20],
        version=row[21],
    )


def _task(row: Any) -> TaskRow:
    return TaskRow(
        id=row[0],
        tenant_id=row[1],
        agent_id=row[2],
        base_id=row[3],
        kind=row[4],
        purpose=row[5],
        is_write=bool(row[6]),
        attempt=int(row[7]),
        timeout_s=int(row[8]),
        payload=_json(row[9]) or {},
        payload_sha256=row[10],
        status=row[11],
        lease_id=row[12],
        leased_at=row[13],
        lease_until=row[14],
        created_by=row[15],
        expires_at=row[16],
    )


def _assignments(values: Mapping[str, Any], allowed: frozenset[str]) -> tuple[str, dict[str, Any]]:
    parts: list[str] = []
    params: dict[str, Any] = {}
    for key, value in values.items():
        if key not in allowed:
            raise ValueError(f"column {key!r} is not updatable here")
        if key in _JSON_COLS:
            parts.append(f"{key} = CAST(:{key} AS jsonb)")
            params[key] = None if value is None else json.dumps(value)
        elif key == "last_ip":
            parts.append(f"{key} = CAST(:{key} AS inet)")
            params[key] = value
        else:
            parts.append(f"{key} = :{key}")
            params[key] = value
    return ", ".join(parts), params


class SqlAgentStore:
    async def db_now(self, s: AsyncSession) -> datetime:
        value: datetime = (await s.execute(text("SELECT now()"))).scalar_one()
        return value

    # --- agents ------------------------------------------------------------------------------------
    async def get_agent(self, s: AsyncSession, agent_id: UUID, *, lock: bool = False) -> AgentRow | None:
        sql = f"SELECT {_AGENT_COLS} FROM app.onec_agents a WHERE a.id = :id"  # noqa: S608 — fixed columns
        if lock:
            sql += " FOR SHARE OF a"
        row = (await s.execute(text(sql), {"id": agent_id})).first()
        return _agent(row) if row else None

    async def list_agents(
        self, s: AsyncSession, status: str | None, limit: int, offset: int
    ) -> tuple[list[AgentRow], int]:
        where = "WHERE a.status = :status" if status else ""
        params: dict[str, Any] = {"status": status, "limit": limit, "offset": offset}
        rows = (
            await s.execute(
                text(
                    f"SELECT {_AGENT_COLS} FROM app.onec_agents a "  # noqa: S608 — fixed columns
                    f"{where} ORDER BY a.name, a.id "
                    "LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).all()
        total = (
            await s.execute(text(f"SELECT count(*) FROM app.onec_agents a {where}"), params)  # noqa: S608
        ).scalar_one()
        return [_agent(r) for r in rows], int(total)

    async def create_device(
        self, s: AsyncSession, device_id: UUID, tenant_id: UUID, version: str | None
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.devices (id, tenant_id, kind, app_version, last_seen_at) "
                "VALUES (:id, :t, 'onec_agent', :v, now())"
            ),
            {"id": device_id, "t": tenant_id, "v": version},
        )

    async def create_agent(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        params = {**values, "public_jwk": json.dumps(values["public_jwk"])}
        await s.execute(
            text(
                "INSERT INTO app.onec_agents (id, tenant_id, device_id, "
                "client_id, name, pc_name, machine_hash, "
                "os_version, agent_version, public_jwk, public_key_thumbprint, paired_by, paired_ip) VALUES "
                "(:id, :tenant_id, :device_id, :client_id, :name, :pc_name, :machine_hash, :os_version, "
                ":agent_version, CAST(:public_jwk AS jsonb), :thumbprint, "
                ":paired_by, CAST(:paired_ip AS inet))"
            ),
            params,
        )

    async def update_agent(self, s: AsyncSession, agent_id: UUID, values: Mapping[str, Any]) -> None:
        if not values:
            return
        assignments, params = _assignments(values, _UPDATABLE_AGENT)
        await s.execute(
            text(f"UPDATE app.onec_agents SET {assignments} WHERE id = :agent_id"),  # noqa: S608 — allow-listed
            {**params, "agent_id": agent_id},
        )

    async def revoke_agent(
        self, s: AsyncSession, agent_id: UUID, *, reason: str, revoked_by: UUID | None
    ) -> int:
        result = await s.execute(
            text(
                "UPDATE app.onec_agents SET status = 'revoked', revoked_at = now(), revoked_by = :by, "
                "revoke_reason = :reason, version = version + 1 WHERE id = :id AND status = 'active' "
                "RETURNING device_id"
            ),
            {"id": agent_id, "by": revoked_by, "reason": reason},
        )
        device_id = result.scalar()
        if device_id is None:
            return 0
        await s.execute(
            text(
                "UPDATE app.devices SET revoked_at = now(), revoked_by = :by, updated_at = now() "
                "WHERE id = :d AND revoked_at IS NULL"
            ),
            {"d": device_id, "by": revoked_by},
        )
        return 1

    async def touch_device(self, s: AsyncSession, device_id: UUID, app_version: str | None) -> None:
        await s.execute(
            text(
                "UPDATE app.devices SET last_seen_at = now(), app_version = COALESCE(:v, app_version) "
                "WHERE id = :d"
            ),
            {"d": device_id, "v": app_version},
        )

    # --- tasks -------------------------------------------------------------------------------------
    async def insert_task(self, s: AsyncSession, values: Mapping[str, Any]) -> UUID | None:
        params = {"attempt": 1, **values, "payload": json.dumps(values["payload"])}
        row = (
            await s.execute(
                text(
                    "INSERT INTO app.onec_agent_tasks (id, tenant_id, "
                    "agent_id, kind, purpose, priority, payload, "
                    "payload_sha256, timeout_s, not_before, expires_at, "
                    "created_by, dedupe_key, attempt) VALUES "
                    "(:id, :tenant_id, :agent_id, :kind, :purpose, :priority, CAST(:payload AS jsonb), "
                    ":payload_sha256, :timeout_s, :not_before, :expires_at, "
                    ":created_by, :dedupe_key, :attempt) "
                    "ON CONFLICT (agent_id, dedupe_key) WHERE dedupe_key IS NOT NULL "
                    "AND status IN ('queued','leased') DO NOTHING RETURNING id"
                ),
                params,
            )
        ).first()
        return row[0] if row else None

    async def task_by_dedupe(self, s: AsyncSession, agent_id: UUID, dedupe_key: str) -> UUID | None:
        value = (
            await s.execute(
                text(
                    "SELECT id FROM app.onec_agent_tasks WHERE agent_id = :a AND dedupe_key = :k "
                    "AND status IN ('queued','leased')"
                ),
                {"a": agent_id, "k": dedupe_key},
            )
        ).scalar()
        return value if isinstance(value, UUID) or value is None else UUID(str(value))

    async def next_leasable(self, s: AsyncSession, agent_id: UUID, kinds: frozenset[str]) -> TaskRow | None:
        row = (
            await s.execute(
                text(
                    f"SELECT {_TASK_COLS} FROM app.onec_agent_tasks t "  # noqa: S608 — fixed columns
                    "WHERE t.agent_id = :a AND t.status = 'queued' AND t.base_id IS NULL "
                    "AND t.kind = ANY(CAST(:kinds AS text[])) AND t.not_before <= now() "
                    "AND (t.expires_at IS NULL OR t.expires_at > now()) "
                    "AND NOT EXISTS (SELECT 1 FROM app.onec_agent_tasks l WHERE l.agent_id = :a "
                    "  AND l.status = 'leased' AND l.base_id IS NULL) "
                    "AND EXISTS (SELECT 1 FROM app.onec_agents ag WHERE ag.id = :a AND ag.status = 'active') "
                    "ORDER BY t.priority, t.not_before, t.id LIMIT 1 FOR UPDATE OF t SKIP LOCKED"
                ),
                {"a": agent_id, "kinds": sorted(kinds)},
            )
        ).first()
        return _task(row) if row else None

    async def mark_leased(self, s: AsyncSession, task_id: UUID, values: Mapping[str, Any]) -> bool:
        try:
            async with s.begin_nested():
                result = await s.execute(
                    text(
                        "UPDATE app.onec_agent_tasks SET status = 'leased', lease_id = :lease_id, "
                        "leased_at = :leased_at, lease_until = :lease_until, "
                        "heartbeat_at = NULL, progress = NULL, "
                        "signing_kid = :signing_kid, signature = :signature "
                        "WHERE id = :id AND status = 'queued'"
                    ),
                    {**values, "id": task_id},
                )
        except IntegrityError:  # uq_onec_tasks_one_leased_agent_level: a parallel poll leased first
            return False
        return bool(getattr(result, "rowcount", 0))

    async def get_task(
        self, s: AsyncSession, task_id: UUID, agent_id: UUID, *, lock: bool = False
    ) -> TaskRow | None:
        sql = f"SELECT {_TASK_COLS} FROM app.onec_agent_tasks t WHERE t.id = :id AND t.agent_id = :a"  # noqa: S608
        if lock:
            sql += " FOR UPDATE"
        row = (await s.execute(text(sql), {"id": task_id, "a": agent_id})).first()
        return _task(row) if row else None

    async def update_task(self, s: AsyncSession, task_id: UUID, values: Mapping[str, Any]) -> None:
        assignments, params = _assignments(values, _UPDATABLE_TASK)
        await s.execute(
            text(f"UPDATE app.onec_agent_tasks SET {assignments} WHERE id = :task_id"),  # noqa: S608
            {**params, "task_id": task_id},
        )

    async def cancel_queued(self, s: AsyncSession, agent_id: UUID) -> int:
        result = await s.execute(
            text(
                "UPDATE app.onec_agent_tasks SET status = 'cancelled', finished_at = now() "
                "WHERE agent_id = :a AND status = 'queued'"
            ),
            {"a": agent_id},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def expire_due(self, s: AsyncSession, limit: int) -> list[TaskRow]:
        rows = (
            await s.execute(
                text(
                    "WITH due AS (SELECT id FROM app.onec_agent_tasks "  # noqa: S608 — fixed columns
                    "  WHERE (status = 'leased' AND lease_until < now()) "
                    "     OR (status = 'queued' AND expires_at IS NOT NULL AND expires_at < now()) "
                    "  ORDER BY id LIMIT :n FOR UPDATE SKIP LOCKED) "
                    "UPDATE app.onec_agent_tasks t SET status = 'expired', finished_at = now() FROM due "
                    f"WHERE t.id = due.id RETURNING {_TASK_COLS}"
                ),
                {"n": limit},
            )
        ).all()
        return [_task(r) for r in rows]

    async def find_result(self, s: AsyncSession, task_id: UUID, lease_id: UUID) -> StoredResult | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, lease_id, late FROM app.onec_task_results "
                    "WHERE task_id = :t AND lease_id = :l"
                ),
                {"t": task_id, "l": lease_id},
            )
        ).first()
        return StoredResult(row[0], row[1], bool(row[2])) if row else None

    async def insert_result(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        params = {
            **values,
            "data": json.dumps(values["data"]),
            "error": None if values.get("error") is None else json.dumps(values["error"]),
        }
        await s.execute(
            text(
                "INSERT INTO app.onec_task_results (id, tenant_id, "
                "task_id, lease_id, attempt, outcome, data, "
                "data_trimmed, error, duration_ms, agent_version, "
                "worker_bits, late) VALUES (:id, :tenant_id, "
                ":task_id, :lease_id, :attempt, :outcome, CAST(:data AS jsonb), :data_trimmed, "
                "CAST(:error AS jsonb), :duration_ms, :agent_version, :worker_bits, :late)"
            ),
            params,
        )

    # --- logs --------------------------------------------------------------------------------------
    async def insert_logs(self, s: AsyncSession, rows: list[Mapping[str, Any]]) -> int:
        if not rows:
            return 0
        payload = json.dumps([{**r, "at": r["at"].isoformat()} for r in rows], default=str)
        result = await s.execute(
            text(
                "INSERT INTO app.onec_agent_logs (id, tenant_id, "
                "agent_id, client_log_id, base_id, task_id, at, "
                "level, code, message, context) "
                "SELECT r.id, r.tenant_id, r.agent_id, r.client_log_id, "
                "NULL, r.task_id, r.at, r.level, r.code, "
                "r.message, COALESCE(r.context, '{}'::jsonb) FROM "
                "jsonb_to_recordset(CAST(:rows AS jsonb)) AS "
                "r(id uuid, tenant_id uuid, agent_id uuid, client_log_id uuid, task_id uuid, at timestamptz, "
                "level text, code text, message text, context jsonb) "
                "ON CONFLICT (agent_id, client_log_id) DO NOTHING RETURNING 1"
            ),
            {"rows": payload},
        )
        return len(result.all())

    async def list_logs(
        self,
        s: AsyncSession,
        agent_id: UUID,
        *,
        levels: frozenset[str] | None,
        at_gte: datetime | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[LogRow]:
        """Agent log rows ∪ server events of the agent (B5: ``diagnostics_ready`` of a done
        ``collect_diagnostics`` task — 33 W-08); newest first, cursor ``(at, id)``."""
        filters: list[str] = []
        params: dict[str, Any] = {"a": agent_id, "limit": limit}
        if levels:
            filters.append("x.level = ANY(CAST(:levels AS text[]))")
            params["levels"] = sorted(levels)
        if at_gte is not None:
            filters.append("x.at >= :at_gte")
            params["at_gte"] = at_gte
        if after is not None:
            filters.append("(x.at, x.id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        rows = (
            await s.execute(
                text(
                    "SELECT x.id, x.at, x.level, x.code, x.message, "  # noqa: S608 — fixed filters
                    "x.message_key, x.base_id, x.task_id, x.context, "
                    "x.source FROM ("
                    " SELECT l.id, l.at, l.level, l.code, l.message, NULL::text AS message_key, l.base_id, "
                    "  l.task_id, l.context, 'agent'::text AS source FROM "
                    "app.onec_agent_logs l WHERE l.agent_id = :a"
                    " UNION ALL"
                    " SELECT r.id, r.received_at, 'info', 'diagnostics_ready', "
                    "NULL, 'onec.events.diagnostics_ready',"
                    "  NULL::uuid, t.id, "
                    "jsonb_build_object('attachment_id', r.data->>'attachment_id'), 'server'"
                    "  FROM app.onec_task_results r JOIN app.onec_agent_tasks t ON t.id = r.task_id"
                    "  WHERE t.agent_id = :a AND t.kind = 'collect_diagnostics' AND r.outcome = 'done'"
                    "  AND r.data ? 'attachment_id'"
                    f") x {where} ORDER BY x.at DESC, x.id DESC LIMIT :limit"
                ),
                params,
            )
        ).all()
        return [
            LogRow(
                id=r[0],
                at=r[1],
                level=r[2],
                code=r[3],
                message=r[4],
                message_key=r[5],
                base_id=r[6],
                task_id=r[7],
                context=_json(r[8]) or {},
                source=r[9],
            )
            for r in rows
        ]

    # --- A-07 diagnostics attachment ---------------------------------------------------------------
    async def insert_attachment(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.attachments (id, tenant_id, s3_key, "
                "content_type, original_name, sha256, kind, "
                "size_bytes, uploaded_by) VALUES (:id, :tenant_id, :s3_key, :content_type, :original_name, "
                ":sha256, 'onec_diagnostics', :size_bytes, :uploaded_by)"
            ),
            dict(values),
        )
