"""Signed task queue of the store agent (33 §5.15, §7.6, §9.3 A-03…A-05, §9.9): enqueue
(:class:`AgentTaskPort`), lease + Ed25519 signature, heartbeat, result acceptance with the handler
registry, and the lease sweeper.

Bosqich 5 leases only agent-level kinds (``base_id IS NULL``): the device-service family
(``fiscal.*``, ``print.raw``, ``scale.plu_upload``, ``card.*``) and ``collect_diagnostics``; one of them per
agent at a time (``uq_onec_tasks_one_leased_agent_level``). Device-service tasks are never retried
automatically after a lost lease — a second ``print.raw`` must not print twice; periodic kinds are
re-enqueued by their owner module.
"""

from __future__ import annotations

import hmac
from collections.abc import Mapping
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
    AgentSignals,
    AgentStore,
    AgentTaskResult,
    AgentTaskResultHandler,
    AgentTaskView,
    TaskRow,
    TaskSigner,
)
from app.modules.onec_integration.domain.capabilities import capability_enabled
from app.modules.onec_integration.domain.envelope import LeaseFacts, task_claims
from app.modules.onec_integration.domain.jcs import (
    JcsError,
    contains_non_integer_number,
    payload_sha256,
)
from app.modules.onec_integration.domain.kinds import (
    B5_LEASABLE_KINDS,
    DEVICE_SERVICE_KINDS,
    PURPOSE_DEVICE_SERVICE,
    clamp_timeout,
    default_timeout_s,
    family_of,
)

log = structlog.get_logger(__name__)

LEASE_EXTENSION_S: Final = 90  # A-04: lease_until = min(now + 90 s, leased_at + timeout_s + 60 s)
LEASE_INITIAL_MARGIN_S: Final = 30  # A-03: lease_until = now + min(timeout_s, 90) + 30 s
LEASE_HARD_MARGIN_S: Final = 60
MAX_DATA_BYTES: Final = 1024 * 1024  # onec_task_results.data kept in full up to 1 MB, else trimmed
OUTCOMES: Final = frozenset({"done", "failed", "unknown"})
REJECTED_CODE: Final = "ONEC_TASK_REJECTED"
UNKNOWN_OUTCOME_CODE: Final = "ONEC_UNKNOWN_OUTCOME"


def _validation(field: str, key: str = "validation.invalid") -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def lease_lost(task_id: UUID) -> AppError:
    return AppError(ErrorCode.ONEC_TASK_LEASE_LOST, params={"task_id": str(task_id)})


def _view(task: TaskRow) -> AgentTaskView:
    return AgentTaskView(
        id=task.id,
        tenant_id=task.tenant_id,
        agent_id=task.agent_id,
        kind=task.kind,
        purpose=task.purpose,
        attempt=task.attempt,
        payload=task.payload,
        created_by=task.created_by,
        lease_id=task.lease_id,
    )


@dataclass(frozen=True, slots=True)
class Envelope:
    body: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ResultAck:
    accepted: bool
    duplicate: bool
    late: bool

    def as_json(self) -> dict[str, bool]:
        return {"accepted": self.accepted, "duplicate": self.duplicate, "late": self.late}


class AgentTaskService:
    """The queue (enqueue = :class:`AgentTaskPort`), the dispatcher and the result service in one."""

    def __init__(
        self,
        store: AgentStore,
        signals: AgentSignals,
        signer: TaskSigner,
        handlers: Mapping[str, AgentTaskResultHandler] | None = None,
    ) -> None:
        self._store = store
        self._signals = signals
        self._signer = signer
        self._handlers = dict(handlers or {})

    # --- AgentTaskPort ---------------------------------------------------------------------------
    async def enqueue(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        kind: str,
        payload: dict[str, Any],
        *,
        priority: int = 100,
        not_before: datetime | None = None,
        dedupe_key: str | None = None,
        created_by: UUID | None = None,
        expires_in_s: int | None = 86400,
        timeout_s: int | None = None,
    ) -> UUID:
        if kind not in DEVICE_SERVICE_KINDS:
            raise _validation("kind", "validation.invalid_choice")
        family = family_of(kind)
        return await self._insert(
            s,
            tenant_id,
            agent_id,
            kind,
            PURPOSE_DEVICE_SERVICE,
            payload,
            family=family,
            priority=priority,
            not_before=not_before,
            dedupe_key=dedupe_key,
            created_by=created_by,
            expires_in_s=expires_in_s,
            timeout_s=timeout_s,
        )

    async def enqueue_agent_level(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        kind: str,
        purpose: str,
        payload: dict[str, Any],
        *,
        priority: int,
        created_by: UUID | None,
        expires_in_s: int | None,
    ) -> UUID:
        """Agent-level non-family task of this module (``collect_diagnostics`` — W-07)."""
        return await self._insert(
            s,
            tenant_id,
            agent_id,
            kind,
            purpose,
            payload,
            family=None,
            priority=priority,
            not_before=None,
            dedupe_key=None,
            created_by=created_by,
            expires_in_s=expires_in_s,
            timeout_s=None,
        )

    async def _insert(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        kind: str,
        purpose: str,
        payload: dict[str, Any],
        *,
        family: str | None,
        priority: int,
        not_before: datetime | None,
        dedupe_key: str | None,
        created_by: UUID | None,
        expires_in_s: int | None,
        timeout_s: int | None,
    ) -> UUID:
        if not isinstance(payload, dict) or contains_non_integer_number(payload):
            raise _validation("payload")
        try:
            psh = payload_sha256(payload)
        except JcsError as exc:
            raise _validation("payload") from exc
        if dedupe_key is not None and not 1 <= len(dedupe_key) <= 200:
            raise _validation("dedupe_key", "validation.max_length")
        if not -32768 <= priority <= 32767:
            raise _validation("priority")
        agent = await self._store.get_agent(s, agent_id, lock=True)
        if agent is None or agent.tenant_id != tenant_id:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent"})
        if agent.status != "active":
            raise AppError(ErrorCode.ONEC_AGENT_REVOKED, params={"agent_id": str(agent_id)})
        if family is not None and not capability_enabled(agent.capabilities, family):
            raise AppError(
                ErrorCode.AGENT_CAPABILITY_DISABLED,
                params={"agent_id": str(agent_id), "kind": kind, "family": family},
            )
        if dedupe_key is not None:
            existing = await self._store.task_by_dedupe(s, agent_id, dedupe_key)
            if existing is not None:
                return existing
        now = await self._store.db_now(s)
        start = not_before or now
        task_id = uuid7()
        inserted = await self._store.insert_task(
            s,
            {
                "id": task_id,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "kind": kind,
                "purpose": purpose,
                "priority": priority,
                "payload": payload,
                "payload_sha256": psh,
                "timeout_s": clamp_timeout(timeout_s or default_timeout_s(kind)),
                "not_before": start,
                "expires_at": start + timedelta(seconds=expires_in_s) if expires_in_s else None,
                "created_by": created_by,
                "dedupe_key": dedupe_key,
            },
        )
        if inserted is None:  # a concurrent enqueue with the same dedupe_key won
            assert dedupe_key is not None
            existing = await self._store.task_by_dedupe(s, agent_id, dedupe_key)
            if existing is None:  # the winner finished already — impossible inside its unique window
                raise RuntimeError("dedupe conflict without a visible task")
            return existing
        self._signals.wake_after_commit(s, agent_id)
        log.info("onec_task_enqueued", agent_id=str(agent_id), task_id=str(task_id), kind=kind)
        return task_id

    # --- A-03 lease --------------------------------------------------------------------------------
    async def lease_one(self, s: AsyncSession, tenant_id: UUID, agent_id: UUID) -> Envelope | None:
        """Lease the next agent-level task and sign it (in the caller's transaction)."""
        task = await self._store.next_leasable(s, agent_id, B5_LEASABLE_KINDS)
        if task is None:
            return None
        now = await self._store.db_now(s)
        lease_id = uuid7()
        lease_until = now + timedelta(seconds=min(task.timeout_s, LEASE_EXTENSION_S) + LEASE_INITIAL_MARGIN_S)
        facts = LeaseFacts(
            task_id=task.id,
            attempt=task.attempt,
            lease_id=lease_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            base_id=task.base_id,
            kind=task.kind,
            payload_sha256=task.payload_sha256,
            leased_at=now,
            timeout_s=task.timeout_s,
        )
        kid, signature = await self._signer.sign(task_claims(facts))
        leased = await self._store.mark_leased(
            s,
            task.id,
            {
                "lease_id": lease_id,
                "leased_at": now,
                "lease_until": lease_until,
                "signing_kid": UUID(kid),
                "signature": signature,
            },
        )
        if not leased:  # another poll of the same agent holds the agent-level lane
            return None
        log.info("onec_task_leased", agent_id=str(agent_id), task_id=str(task.id), kind=task.kind)
        return Envelope(
            {
                "task_id": str(task.id),
                "kind": task.kind,
                "purpose": task.purpose,
                "base_id": str(task.base_id) if task.base_id else None,
                "local_id": None,
                "attempt": task.attempt,
                "lease_id": str(lease_id),
                "lease_until": _iso(lease_until),
                "timeout_s": task.timeout_s,
                "payload": task.payload,
                "payload_sha256": task.payload_sha256,
                "kid": kid,
                "signature": signature,
            }
        )

    # --- A-04 heartbeat ----------------------------------------------------------------------------
    async def heartbeat(
        self, s: AsyncSession, agent_id: UUID, task_id: UUID, lease_id: UUID, progress: dict[str, Any] | None
    ) -> dict[str, Any]:
        task = await self._store.get_task(s, task_id, agent_id, lock=True)
        if task is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent_task"})
        now = await self._store.db_now(s)
        if (
            task.status != "leased"
            or task.lease_id is None
            or not _same(task.lease_id, lease_id)
            or task.lease_until is None
            or task.lease_until < now
            or task.leased_at is None
        ):
            raise lease_lost(task_id)
        hard = task.leased_at + timedelta(seconds=task.timeout_s + LEASE_HARD_MARGIN_S)
        lease_until = max(task.lease_until, min(now + timedelta(seconds=LEASE_EXTENSION_S), hard))
        await self._store.update_task(
            s, task_id, {"lease_until": lease_until, "heartbeat_at": now, "progress": progress}
        )
        # cancel_requested: batch.cancel_requested_at of a read task — 1C batches are Bosqich 7
        return {"lease_until": _iso(lease_until), "cancel_requested": False}

    # --- A-05 result -------------------------------------------------------------------------------
    async def accept_result(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        device_id: UUID | None,
        task_id: UUID,
        body: Mapping[str, Any],
    ) -> ResultAck:
        task = await self._store.get_task(s, task_id, agent_id, lock=True)
        if task is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent_task"})
        lease_id: UUID = body["lease_id"]
        stored = await self._store.find_result(s, task_id, lease_id)
        if stored is not None:
            return ResultAck(accepted=True, duplicate=True, late=stored.late)
        if (
            task.lease_id is None
            or not _same(task.lease_id, lease_id)
            or int(body["attempt"]) != task.attempt
        ):
            raise lease_lost(task_id)
        if task.status not in ("leased", "expired"):
            raise lease_lost(task_id)
        outcome = str(body["outcome"])
        error = body.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if outcome != "done" and not isinstance(code, str):
            raise _validation("error.code", "validation.required")
        if outcome == "unknown" and code != UNKNOWN_OUTCOME_CODE:
            raise _validation("error.code", "validation.invalid_choice")
        now = await self._store.db_now(s)
        late = task.status == "expired" or (task.lease_until is not None and task.lease_until < now)
        data = body.get("data") or {}
        trimmed = len(str(data)) > MAX_DATA_BYTES
        await self._store.insert_result(
            s,
            {
                "id": uuid7(),
                "tenant_id": tenant_id,
                "task_id": task_id,
                "lease_id": lease_id,
                "attempt": task.attempt,
                "outcome": outcome,
                "data": {} if trimmed else data,
                "data_trimmed": trimmed,
                "error": error,
                "duration_ms": body.get("duration_ms"),
                "agent_version": body.get("agent_version"),
                "worker_bits": body.get("worker_bits"),
                "late": late,
            },
        )
        await self._store.update_task(
            s,
            task_id,
            {
                "status": "done" if outcome == "done" else "failed",
                "outcome": outcome,
                "error_code": code,
                "finished_at": now,
            },
        )
        if code == REJECTED_CODE:
            # 33 §9.11: the agent refused a signed task — a security signal (15 §6.1, 33 §15.4)
            await record_audit(
                s,
                tenant_id=tenant_id,
                action="onec.task.rejected",
                entity="onec_agent_tasks",
                entity_id=task_id,
                device_id=device_id,
                after={"kind": task.kind, "reason": (error or {}).get("message"), "agent_id": str(agent_id)},
            )
            log.warning("onec_task_rejected", agent_id=str(agent_id), task_id=str(task_id), kind=task.kind)
        handler = self._handlers.get(task.kind)
        if handler is not None:
            result = AgentTaskResult(
                outcome=outcome,
                data=data if isinstance(data, dict) else {},
                error=error,
                late=late,
                duration_ms=body.get("duration_ms"),
            )
            await handler(s, tenant_id, agent_id, _view(task), result)
        else:
            log.info("agent_task_result_unhandled", kind=task.kind, task_id=str(task_id))
        return ResultAck(accepted=True, duplicate=False, late=late)

    # --- onec_lease_sweeper (33 §4.4, §9.9) ----------------------------------------------------------
    async def sweep(self, s: AsyncSession, limit: int = 500) -> list[TaskRow]:
        """``leased`` past ``lease_until`` → ``expired``; ``queued`` past ``expires_at`` → ``expired``.

        A lost read task of this module (``collect_diagnostics``) gets a new row ``attempt + 1`` (≤ 3);
        device-service tasks do not (see module docstring).
        """
        expired = await self._store.expire_due(s, limit)
        for task in expired:
            if task.purpose != PURPOSE_DEVICE_SERVICE and task.lease_id is not None and task.attempt < 3:
                await self._store.insert_task(
                    s,
                    {
                        "id": uuid7(),
                        "tenant_id": task.tenant_id,
                        "agent_id": task.agent_id,
                        "kind": task.kind,
                        "purpose": task.purpose,
                        "priority": 10,
                        "payload": task.payload,
                        "payload_sha256": task.payload_sha256,
                        "timeout_s": task.timeout_s,
                        "not_before": await self._store.db_now(s),
                        "expires_at": task.expires_at,
                        "created_by": task.created_by,
                        "dedupe_key": None,
                        "attempt": task.attempt + 1,
                    },
                )
                self._signals.wake_after_commit(s, task.agent_id)
            log.info(
                "onec_task_expired", task_id=str(task.id), kind=task.kind, leased=task.lease_id is not None
            )
        return expired


def _same(a: UUID, b: UUID) -> bool:
    return hmac.compare_digest(a.bytes, b.bytes)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class LeaseSweeper:
    """SAQ job body: one tenant's sweep in its own transaction (``onec_lease_sweeper``)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], tasks: AgentTaskService) -> None:
        self._sf = session_factory
        self._tasks = tasks

    async def run(self, tenant_id: UUID) -> int:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            return len(await self._tasks.sweep(s))
