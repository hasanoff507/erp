"""Ports of the store-agent part of ``onec_integration`` (33 §4.3, 23 §4.2; contracts/agent-tasks.md).

Inbound (other modules call): :class:`AgentTaskPort` (queue a device-service task), :class:`AgentDirectory`
(agent read model) and the result-handler registry (:class:`AgentTaskResultHandler`).
Outbound (infrastructure implements): :class:`AgentStore`, :class:`AgentSignals`, :class:`TaskSigner`,
:class:`DiagnosticsFiles`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# --- inbound: AgentTaskPort + result handlers (contracts/agent-tasks.md §1–§2) ----------------------


class AgentTaskPort(Protocol):
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
    ) -> UUID: ...


@dataclass(frozen=True, slots=True)
class AgentTaskView:
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    kind: str
    purpose: str
    attempt: int
    payload: dict[str, Any]
    created_by: UUID | None
    lease_id: UUID | None


@dataclass(frozen=True, slots=True)
class AgentTaskResult:
    outcome: str  # done | failed | unknown
    data: dict[str, Any]
    error: dict[str, Any] | None
    late: bool
    duration_ms: int | None


class AgentTaskResultHandler(Protocol):
    async def __call__(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: AgentTaskView, result: AgentTaskResult
    ) -> None: ...


# --- inbound: agent read model (contracts/agent-tasks.md §3) ---------------------------------------


@dataclass(frozen=True, slots=True)
class AgentView:
    id: UUID
    tenant_id: UUID
    device_id: UUID
    name: str
    pc_name: str
    status: str
    capabilities: dict[str, Any]
    agent_version: str | None
    last_hello_at: datetime | None
    last_poll_at: datetime | None
    last_seen_at: datetime | None
    online: bool


class AgentDirectory(Protocol):
    async def agents_for_tenant(self, s: AsyncSession, tenant_id: UUID) -> list[AgentView]: ...

    async def get_agent(self, s: AsyncSession, tenant_id: UUID, agent_id: UUID) -> AgentView | None: ...


# --- outbound ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentRow:
    id: UUID
    tenant_id: UUID
    device_id: UUID
    client_id: str
    name: str
    pc_name: str
    machine_hash: str
    os_version: str | None
    agent_version: str | None
    worker_bits: list[int]
    platforms: list[Any]
    status: str
    update_channel: str
    capabilities: dict[str, Any]
    paired_by: UUID
    paired_by_name: str | None
    paired_at: datetime
    last_hello_at: datetime | None
    last_poll_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: str | None
    version: int


@dataclass(frozen=True, slots=True)
class TaskRow:
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    base_id: UUID | None
    kind: str
    purpose: str
    is_write: bool
    attempt: int
    timeout_s: int
    payload: dict[str, Any]
    payload_sha256: str
    status: str
    lease_id: UUID | None
    leased_at: datetime | None
    lease_until: datetime | None
    created_by: UUID | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredResult:
    id: UUID
    lease_id: UUID
    late: bool


@dataclass(frozen=True, slots=True)
class LogRow:
    id: UUID
    at: datetime
    level: str
    code: str | None
    message: str | None
    message_key: str | None
    base_id: UUID | None
    task_id: UUID | None
    context: dict[str, Any]
    source: str  # agent | server


class AgentStore(Protocol):
    """SQL of ``onec_agents``/``onec_agent_tasks``/``onec_task_results``/``onec_agent_logs`` (RLS-bound)."""

    async def db_now(self, s: AsyncSession) -> datetime: ...

    # agents
    async def get_agent(self, s: AsyncSession, agent_id: UUID, *, lock: bool = False) -> AgentRow | None: ...

    async def list_agents(
        self, s: AsyncSession, status: str | None, limit: int, offset: int
    ) -> tuple[list[AgentRow], int]: ...

    async def create_agent(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...

    async def update_agent(self, s: AsyncSession, agent_id: UUID, values: Mapping[str, Any]) -> None: ...

    async def revoke_agent(
        self, s: AsyncSession, agent_id: UUID, *, reason: str, revoked_by: UUID | None
    ) -> int: ...

    async def touch_device(self, s: AsyncSession, device_id: UUID, app_version: str | None) -> None: ...

    async def create_device(
        self, s: AsyncSession, device_id: UUID, tenant_id: UUID, version: str | None
    ) -> None: ...

    # tasks
    async def insert_task(self, s: AsyncSession, values: Mapping[str, Any]) -> UUID | None: ...

    async def task_by_dedupe(self, s: AsyncSession, agent_id: UUID, dedupe_key: str) -> UUID | None: ...

    async def next_leasable(
        self, s: AsyncSession, agent_id: UUID, kinds: frozenset[str]
    ) -> TaskRow | None: ...

    async def mark_leased(self, s: AsyncSession, task_id: UUID, values: Mapping[str, Any]) -> bool: ...

    async def get_task(
        self, s: AsyncSession, task_id: UUID, agent_id: UUID, *, lock: bool = False
    ) -> TaskRow | None: ...

    async def update_task(self, s: AsyncSession, task_id: UUID, values: Mapping[str, Any]) -> None: ...

    async def cancel_queued(self, s: AsyncSession, agent_id: UUID) -> int: ...

    async def expire_due(self, s: AsyncSession, limit: int) -> list[TaskRow]: ...

    async def find_result(self, s: AsyncSession, task_id: UUID, lease_id: UUID) -> StoredResult | None: ...

    async def insert_result(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...

    # logs
    async def insert_logs(self, s: AsyncSession, rows: list[Mapping[str, Any]]) -> int: ...

    async def list_logs(
        self,
        s: AsyncSession,
        agent_id: UUID,
        *,
        levels: frozenset[str] | None,
        at_gte: datetime | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[LogRow]: ...

    # diagnostics attachment (A-07)
    async def insert_attachment(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...


class PollWaiter(Protocol):
    async def next(self, deadline: float) -> str | None:
        """A wake-up message, or ``None`` after a re-check tick / at the deadline (``time.monotonic``)."""
        ...

    async def close(self) -> None: ...


class AgentSignals(Protocol):
    """Redis: long-poll wake-up (``onec:wake:{agent}``), poll supersede (``onec:poll:{agent}``) and the agent
    status cache (``onec:agent_status:{agent}``, 33 §4.5)."""

    def wake_after_commit(self, s: AsyncSession, agent_id: UUID) -> None: ...

    def revoked_after_commit(self, s: AsyncSession, agent_id: UUID) -> None: ...

    async def wake(self, agent_id: UUID) -> None: ...

    async def claim_poll(self, agent_id: UUID, poll_id: str) -> None: ...

    async def is_current_poll(self, agent_id: UUID, poll_id: str) -> bool: ...

    async def wait(self, agent_id: UUID, recheck_s: float) -> PollWaiter: ...

    async def cached_status(self, agent_id: UUID) -> str | None: ...

    async def cache_status(self, agent_id: UUID, status: str) -> None: ...


class SignedArtifactView(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def body(self) -> str: ...

    @property
    def signature(self) -> str | None: ...

    @property
    def kid(self) -> str: ...


class ArtifactSource(Protocol):
    """Pre-signed agent artefacts (``platform.agent_signed_artifacts``, read by the auth module)."""

    async def task_keyset(self) -> SignedArtifactView | None: ...

    async def update_manifest(self, channel: str) -> SignedArtifactView | None: ...


class AgentNotifier(Protocol):
    """M18 Telegram events of the agent (33 §13.3 ``onec_agent_paired`` / ``onec_base_error``)."""

    async def __call__(
        self, s: AsyncSession, tenant_id: UUID, template: str, payload: dict[str, Any]
    ) -> None: ...


class TaskSigner(Protocol):
    async def sign(self, claims: dict[str, Any]) -> tuple[str, str]:
        """``(kid, compact JWS)`` with the active ``onec_task`` key (33 §9.4)."""
        ...


class DiagnosticsFiles(Protocol):
    async def put(self, key: str, content: bytes) -> None: ...
