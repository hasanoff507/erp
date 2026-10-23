"""Store-agent registry service (33 §9.3 A-01/A-03/A-06/A-07/A-10, §10 W-01/W-02/W-05/W-07/W-08):
hello, long-poll, logs, diagnostics, unpair/revoke and the agent read model (contracts/agent-tasks.md §3)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.onec_integration.application.ports import (
    AgentNotifier,
    AgentRow,
    AgentSignals,
    AgentStore,
    AgentView,
    ArtifactSource,
    DiagnosticsFiles,
)
from app.modules.onec_integration.application.tasks import AgentTaskService
from app.modules.onec_integration.domain.capabilities import CapabilitiesError, normalize_capabilities
from app.modules.onec_integration.domain.kinds import KIND_COLLECT_DIAGNOSTICS, PURPOSE_DIAGNOSTICS
from app.modules.onec_integration.domain.masking import MAX_MESSAGE, mask_context, mask_text
from app.modules.onec_integration.domain.versions import in_rollout, version_lt

log = structlog.get_logger(__name__)

ONLINE_WINDOW: Final = timedelta(seconds=120)  # W-06/W-07: "2 daqiqadan beri jim" → offline
HELLO_INTERVAL_S: Final = 600
DIAGNOSTICS_EXPIRES_S: Final = 3600
ZIP_MAGIC: Final = (b"PK\x03\x04", b"PK\x05\x06")


@dataclass(frozen=True, slots=True)
class AgentPrincipal:
    """The authenticated agent of an A-call (``current_agent()``): token claims, never the body."""

    tenant_id: UUID
    agent_id: UUID
    device_id: UUID | None
    client_id: str
    agent_version: str | None
    ip: str | None


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if value is not None else None


def _last_seen(agent: AgentRow) -> datetime | None:
    seen = [t for t in (agent.last_hello_at, agent.last_poll_at) if t is not None]
    return max(seen) if seen else None


def is_online(agent: AgentRow, now: datetime) -> bool:
    seen = _last_seen(agent)
    return agent.status == "active" and seen is not None and now - seen <= ONLINE_WINDOW


def _validation(field: str, key: str = "validation.invalid") -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _agent_not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent"})


def decode_manifest(body: str) -> dict[str, Any] | None:
    try:
        data = json.loads(base64.b64decode(body, validate=True))
    except (binascii.Error, ValueError):
        return None
    return data if isinstance(data, dict) else None


class AgentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        store: AgentStore,
        signals: AgentSignals,
        tasks: AgentTaskService,
        artifacts: ArtifactSource,
        files: DiagnosticsFiles,
        notify: AgentNotifier,
        *,
        min_agent_version: str,
        poll_max_wait_s: int,
        poll_recheck_s: float,
        api_prefix: str = "/api/v1",
    ) -> None:
        self._sf = session_factory
        self._store = store
        self._signals = signals
        self._tasks = tasks
        self._artifacts = artifacts
        self._files = files
        self._notify = notify
        self._min_version = min_agent_version
        self._max_wait = poll_max_wait_s
        self._recheck = poll_recheck_s
        self._prefix = api_prefix

    @property
    def min_agent_version(self) -> str:
        return self._min_version

    # --- current_agent(): status (33 §9.2: Redis 60 s, revoke immediate) -----------------------------
    async def agent_status(self, tenant_id: UUID, agent_id: UUID) -> str | None:
        cached = await self._signals.cached_status(agent_id)
        if cached is not None:
            return cached
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            agent = await self._store.get_agent(s, agent_id)
        if agent is None:
            return None
        await self._signals.cache_status(agent_id, agent.status)
        return agent.status

    # --- A-01 hello ---------------------------------------------------------------------------------
    async def hello(self, p: AgentPrincipal, body: Mapping[str, Any], subscription: str) -> dict[str, Any]:
        try:
            capabilities = normalize_capabilities(body.get("capabilities"))
        except CapabilitiesError as exc:
            raise _validation(exc.field) from exc
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            agent = await self._store.get_agent(s, p.agent_id)
            if agent is None:
                raise _agent_not_found()
            now = await self._store.db_now(s)
            version = body.get("agent_version") or p.agent_version
            updates: dict[str, Any] = {
                "last_hello_at": now,
                "capabilities": capabilities,
                "last_ip": p.ip,
                "agent_version": version,
                "os_version": body.get("os_version") or agent.os_version,
                "pc_name": body.get("pc_name") or agent.pc_name,
                "platforms": body.get("platforms") if body.get("platforms") is not None else agent.platforms,
                "worker_bits": body.get("worker_bits")
                if body.get("worker_bits") is not None
                else agent.worker_bits,
            }
            machine_hash = body.get("machine_hash")
            if machine_hash and machine_hash != agent.machine_hash:
                updates["machine_hash"] = machine_hash
                updates["machine_hash_changed_at"] = now
                await record_audit(
                    s,
                    tenant_id=p.tenant_id,
                    action="onec.agent.machine_changed",
                    entity="onec_agents",
                    entity_id=p.agent_id,
                    device_id=p.device_id,
                    ip=p.ip,
                    before={"machine_hash": agent.machine_hash},
                    after={"machine_hash": machine_hash},
                )
                await self._notify(
                    s,
                    p.tenant_id,
                    "onec_base_error",
                    {"agent_id": str(p.agent_id), "name": agent.name, "reason": "machine_changed"},
                )
            if version and agent.agent_version and version != agent.agent_version:
                await record_audit(
                    s,
                    tenant_id=p.tenant_id,
                    action="onec.agent.updated",
                    entity="onec_agents",
                    entity_id=p.agent_id,
                    device_id=p.device_id,
                    ip=p.ip,
                    before={"agent_version": agent.agent_version},
                    after={"agent_version": version},
                )
            await self._store.update_agent(s, p.agent_id, updates)
            await self._store.touch_device(s, agent.device_id, version)
            channel = agent.update_channel
        keyset = await self._artifacts.task_keyset()
        known = body.get("task_keyset_version")
        send_keyset = keyset is not None and (not isinstance(known, int) or known < _int(keyset.version))
        return {
            "agent_id": str(p.agent_id),
            "server_time": _iso(now),
            "hello_interval_s": HELLO_INTERVAL_S,
            "poll_hint_ms": 0,
            "bases_control": [],  # 1C bases — Bosqich 7 (A-02)
            "task_keyset": keyset.body if send_keyset and keyset else None,
            "update": await self._update_offer(p.agent_id, version, channel),
            "min_agent_version": self._min_version,
            "log_level": "info",
            "subscription": subscription,
        }

    async def _update_offer(self, agent_id: UUID, version: str | None, channel: str) -> dict[str, Any] | None:
        artifact = await self._artifacts.update_manifest(channel)
        manifest = decode_manifest(artifact.body) if artifact else None
        if manifest is None:
            return None
        target = str(manifest.get("version", ""))
        mandatory = version_lt(version, self._min_version)
        rollout = manifest.get("rollout_pct", 0)
        offered = mandatory or (isinstance(rollout, int) and in_rollout(agent_id, rollout))
        if not version_lt(version, target) or not offered:
            return None
        return {
            "version": target,
            "channel": channel,
            "mandatory": mandatory,
            "manifest_url": f"{self._prefix}/onec-agent/update-manifest?channel={channel}",
        }

    # --- A-03 long-poll -----------------------------------------------------------------------------
    async def poll(
        self, p: AgentPrincipal, *, max_tasks: int, wait_s: int, agent_level_busy: bool
    ) -> dict[str, Any] | None:
        """``{"tasks": [...]}`` or ``None`` (``204``). No DB connection is held while waiting."""
        if agent_level_busy or max_tasks <= 0:
            await self._touch_poll(p)
            return None
        poll_id = uuid7().hex
        await self._signals.claim_poll(p.agent_id, poll_id)
        waiter = await self._signals.wait(p.agent_id, self._recheck)
        deadline = time.monotonic() + max(0, min(wait_s, self._max_wait))
        first = True
        try:
            while True:
                envelope = await self._lease(p, touch=first)
                first = False
                if envelope is not None:
                    return {"tasks": [envelope]}
                if time.monotonic() >= deadline:
                    return None
                message = await waiter.next(deadline)
                if (
                    message is not None
                    and message.startswith("poll:")
                    and message != f"poll:{poll_id}"
                    and not await self._signals.is_current_poll(p.agent_id, poll_id)
                ):
                    return None  # a newer poll of this agent took over (33 A-03)
        finally:
            await waiter.close()

    async def _lease(self, p: AgentPrincipal, *, touch: bool) -> dict[str, Any] | None:
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            if touch:
                await self._store.update_agent(s, p.agent_id, {"last_poll_at": await self._store.db_now(s)})
            envelope = await self._tasks.lease_one(s, p.tenant_id, p.agent_id)
        return envelope.body if envelope else None

    async def _touch_poll(self, p: AgentPrincipal) -> None:
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            await self._store.update_agent(s, p.agent_id, {"last_poll_at": await self._store.db_now(s)})

    # --- A-06 logs ----------------------------------------------------------------------------------
    async def ingest_logs(self, p: AgentPrincipal, entries: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        rows: list[Mapping[str, Any]] = []
        for entry in entries:
            message = mask_text(str(entry.get("message") or ""), limit=MAX_MESSAGE)
            context = mask_context(entry.get("context") or {})
            base_id = entry.get("base_id")
            if base_id is not None:
                context = {**context, "base_id": str(base_id)}  # no 1C bases in Bosqich 5 (FK in 0029)
            code = entry.get("code")
            rows.append(
                {
                    "id": str(uuid7()),
                    "tenant_id": str(p.tenant_id),
                    "agent_id": str(p.agent_id),
                    "client_log_id": str(entry["client_log_id"]),
                    "task_id": str(entry["task_id"]) if entry.get("task_id") else None,
                    "at": entry["at"],
                    "level": entry["level"],
                    "code": mask_text(str(code), limit=100) if code else None,
                    "message": message,
                    "context": context,
                }
            )
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            accepted = await self._store.insert_logs(s, rows)
        return {"accepted": accepted, "duplicates": len(rows) - accepted}

    # --- A-07 diagnostics upload --------------------------------------------------------------------
    async def upload_diagnostics(
        self, p: AgentPrincipal, task_id: UUID, filename: str | None, content: bytes
    ) -> dict[str, str]:
        if not content.startswith(ZIP_MAGIC):
            raise _validation("file", "validation.invalid")
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            task = await self._store.get_task(s, task_id, p.agent_id)
        if task is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent_task"})
        if task.kind != KIND_COLLECT_DIAGNOSTICS:
            raise _validation("task_id", "validation.invalid_choice")
        if task.created_by is None:
            raise _validation("task_id", "validation.invalid")  # 33 A-07: no requester to own the file
        attachment_id = uuid7()
        key = f"tenants/{p.tenant_id}/attachments/{attachment_id}.zip"
        await self._files.put(key, content)
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            await self._store.insert_attachment(
                s,
                {
                    "id": attachment_id,
                    "tenant_id": p.tenant_id,
                    "s3_key": key,
                    "content_type": "application/zip",
                    "original_name": (filename or "")[:255] or None,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                    "uploaded_by": task.created_by,
                },
            )
        log.info(
            "onec_diagnostics_uploaded", agent_id=str(p.agent_id), task_id=str(task_id), size=len(content)
        )
        return {"attachment_id": str(attachment_id)}

    # --- A-10 unpair / W-05 revoke ---------------------------------------------------------------------
    async def unpair(self, p: AgentPrincipal, reason: str) -> None:
        async with self._sf() as s, tenant_transaction(s, p.tenant_id):
            agent = await self._store.get_agent(s, p.agent_id)
            if agent is None:
                raise _agent_not_found()
            await self._revoke(s, agent, reason=reason, user_id=None, ip=p.ip, action="onec.agent.unpaired")

    async def revoke(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        reason: str,
        note: str | None,
        user_id: UUID,
        ip: str | None,
    ) -> dict[str, Any]:
        """W-05 inside the route's transaction; already revoked → the same answer (idempotent)."""
        agent = await self._store.get_agent(s, agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            raise _agent_not_found()
        if agent.status == "active":
            await self._revoke(
                s, agent, reason=reason, user_id=user_id, ip=ip, action="onec.agent.revoked", note=note
            )
            agent = await self._store.get_agent(s, agent_id)
            assert agent is not None
        return await self.agent_json(s, agent)

    async def _revoke(
        self,
        s: AsyncSession,
        agent: AgentRow,
        *,
        reason: str,
        user_id: UUID | None,
        ip: str | None,
        action: str,
        note: str | None = None,
    ) -> None:
        if not await self._store.revoke_agent(s, agent.id, reason=reason, revoked_by=user_id):
            return
        cancelled = await self._store.cancel_queued(s, agent.id)
        await record_audit(
            s,
            tenant_id=agent.tenant_id,
            user_id=user_id,
            action=action,
            entity="onec_agents",
            entity_id=agent.id,
            ip=ip,
            device_id=agent.device_id if user_id is None else None,
            before={"status": "active"},
            after={"status": "revoked", "reason": reason, "note": note, "cancelled_tasks": cancelled},
        )
        await self._notify(
            s,
            agent.tenant_id,
            "onec_agent_paired",
            {"agent_id": str(agent.id), "name": agent.name, "state": "disconnected", "reason": reason},
        )
        self._signals.revoked_after_commit(s, agent.id)
        log.info("onec_agent_revoked", agent_id=str(agent.id), reason=reason, by_user=user_id is not None)

    # --- W-07 diagnostics request -----------------------------------------------------------------------
    async def request_diagnostics(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        include_logs_days: int,
        user_id: UUID,
        ip: str | None,
    ) -> dict[str, Any]:
        agent = await self._store.get_agent(s, agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            raise _agent_not_found()
        payload = {"include_logs_days": include_logs_days, "include_settings": True}
        task_id = await self._tasks.enqueue_agent_level(
            s,
            tenant_id,
            agent_id,
            KIND_COLLECT_DIAGNOSTICS,
            PURPOSE_DIAGNOSTICS,
            payload,
            priority=10,
            created_by=user_id,
            expires_in_s=DIAGNOSTICS_EXPIRES_S,
        )
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=user_id,
            action="onec.diagnostics.requested",
            entity="onec_agent_tasks",
            entity_id=task_id,
            ip=ip,
            after={"agent_id": str(agent_id), "include_logs_days": include_logs_days},
        )
        now = await self._store.db_now(s)
        warnings: list[dict[str, Any]] = []
        if not is_online(agent, now):
            since = _last_seen(agent)
            warnings.append(
                {"code": "ONEC_AGENT_OFFLINE", "params": {"pc_name": agent.pc_name, "since": _iso(since)}}
            )
        return {"task_id": str(task_id), "warnings": warnings}

    # --- W-01 / W-02 / W-08 + read model ------------------------------------------------------------------
    async def agent_json(self, s: AsyncSession, agent: AgentRow) -> dict[str, Any]:
        now = await self._store.db_now(s)
        artifact = await self._artifacts.update_manifest(agent.update_channel)
        manifest = decode_manifest(artifact.body) if artifact else None
        target = str(manifest.get("version")) if manifest else None
        return {
            "id": str(agent.id),
            "device_id": str(agent.device_id),
            "name": agent.name,
            "pc_name": agent.pc_name,
            "os_version": agent.os_version,
            "agent_version": agent.agent_version,
            "worker_bits": agent.worker_bits,
            "platforms": agent.platforms,
            "status": agent.status,
            "online": is_online(agent, now),
            "last_hello_at": _iso(agent.last_hello_at),
            "last_poll_at": _iso(agent.last_poll_at),
            "paired_by": str(agent.paired_by),
            "paired_by_name": agent.paired_by_name,
            "paired_at": _iso(agent.paired_at),
            "update_channel": agent.update_channel,
            "update_available": target if target and version_lt(agent.agent_version, target) else None,
            "capabilities": agent.capabilities,
            "revoked_at": _iso(agent.revoked_at),
            "revoke_reason": agent.revoke_reason,
            "bases_count": 0,
            "version": agent.version,
        }

    async def list_agents(self, s: AsyncSession, status: str | None, page: int, size: int) -> dict[str, Any]:
        rows, total = await self._store.list_agents(s, status, size, (page - 1) * size)
        return {
            "items": [await self.agent_json(s, a) for a in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    async def get_agent_json(self, s: AsyncSession, agent_id: UUID) -> dict[str, Any]:
        agent = await self._store.get_agent(s, agent_id)
        if agent is None:
            raise _agent_not_found()
        return {**await self.agent_json(s, agent), "bases": []}

    async def list_logs(
        self,
        s: AsyncSession,
        agent_id: UUID,
        *,
        levels: frozenset[str] | None,
        at_gte: datetime | None,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> tuple[list[dict[str, Any]], tuple[datetime, UUID] | None]:
        if await self._store.get_agent(s, agent_id) is None:
            raise _agent_not_found()
        rows = await self._store.list_logs(
            s, agent_id, levels=levels, at_gte=at_gte, after=cursor, limit=limit + 1
        )
        page, more = rows[:limit], len(rows) > limit
        items = [
            {
                "id": str(r.id),
                "at": r.at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "level": r.level,
                "code": r.code,
                "message": r.message,
                "message_key": r.message_key,
                "base_id": str(r.base_id) if r.base_id else None,
                "task_id": str(r.task_id) if r.task_id else None,
                "context": r.context,
                "source": r.source,
            }
            for r in page
        ]
        return items, ((page[-1].at, page[-1].id) if more and page else None)


def directory_view(agent: AgentRow, now: datetime) -> AgentView:
    return AgentView(
        id=agent.id,
        tenant_id=agent.tenant_id,
        device_id=agent.device_id,
        name=agent.name,
        pc_name=agent.pc_name,
        status=agent.status,
        capabilities=agent.capabilities,
        agent_version=agent.agent_version,
        last_hello_at=agent.last_hello_at,
        last_poll_at=agent.last_poll_at,
        last_seen_at=_last_seen(agent),
        online=is_online(agent, now),
    )


def _int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


class SqlAgentDirectory:
    """:class:`AgentDirectory` for other modules (b5-fiscal, b5-devices) — inside their transaction."""

    def __init__(self, store: AgentStore) -> None:
        self._store = store

    async def agents_for_tenant(self, s: AsyncSession, tenant_id: UUID) -> list[AgentView]:
        rows, _ = await self._store.list_agents(s, None, 1000, 0)
        now = await self._store.db_now(s)
        return [directory_view(a, now) for a in rows if a.tenant_id == tenant_id]

    async def get_agent(self, s: AsyncSession, tenant_id: UUID, agent_id: UUID) -> AgentView | None:
        agent = await self._store.get_agent(s, agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            return None
        return directory_view(agent, await self._store.db_now(s))
