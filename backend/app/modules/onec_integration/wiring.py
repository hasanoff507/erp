"""Composition of the store-agent part of ``onec_integration`` (23 §1 ``wiring.py``;
contracts/agent-tasks.md).

* :func:`build_onec_agents_module` — the API side (``app.state.onec_agents``);
* :func:`agent_tasks` — :class:`AgentTaskPort` for other modules (fiscal, card terminal, cloud print);
* :func:`agent_directory` — the agent read model;
* :data:`TASK_HANDLER_MODULES` / :func:`collect_task_handlers` — the A-05 result-handler registry
  (modules expose ``wiring.agent_task_handlers(settings, db)``, same pattern as sync ``HANDLER_MODULES``).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.auth.application.agent_grants import AgentGrantService
from app.modules.auth.wiring import signing_key_ring
from app.modules.notifications.domain.events import EVENT_KINDS
from app.modules.notifications.wiring import event_recorder
from app.modules.onec_integration.application.agents import AgentPrincipal, AgentService, SqlAgentDirectory
from app.modules.onec_integration.application.pairing import PairingService
from app.modules.onec_integration.application.ports import (
    AgentDirectory,
    AgentNotifier,
    AgentTaskPort,
    AgentTaskResult,
    AgentTaskResultHandler,
    AgentTaskView,
    AgentView,
    PollWaiter,
)
from app.modules.onec_integration.application.tasks import AgentTaskService, LeaseSweeper
from app.modules.onec_integration.infrastructure.agents_sql import SqlAgentStore
from app.modules.onec_integration.infrastructure.files import FilesystemDiagnosticsFiles
from app.modules.onec_integration.infrastructure.pairing_sql import SqlPairingStore
from app.modules.onec_integration.infrastructure.signals import RedisAgentSignals
from app.modules.onec_integration.infrastructure.task_signer import RingTaskSigner

log = structlog.get_logger(__name__)

PURPOSE_ONEC_TASK: Final = "onec_task"
SWEEP_JOB: Final = "onec_lease_sweeper"

# modules exposing ``wiring.agent_task_handlers(settings, db) -> Mapping[kind, handler]`` (contract 1)
TASK_HANDLER_MODULES: Final = (
    "app.modules.integrations.fiscal.wiring",  # b5-fiscal: fiscal.status, .resend_unsent, .zreport
    "app.modules.integrations.card_terminal.wiring",  # b5-devices: card.status, card.settlement
    "app.modules.integrations.cloud_print.wiring",  # b5-devices: print.raw
)

__all__ = [
    "SWEEP_JOB",
    "TASK_HANDLER_MODULES",
    "AgentDirectory",
    "AgentPrincipal",
    "AgentTaskPort",
    "AgentTaskResult",
    "AgentTaskResultHandler",
    "AgentTaskView",
    "AgentView",
    "OneCAgentsModule",
    "agent_directory",
    "agent_tasks",
    "build_onec_agents_module",
    "collect_task_handlers",
    "lease_sweeper",
]


def collect_task_handlers(settings: Settings, db: Database) -> dict[str, AgentTaskResultHandler]:
    handlers: dict[str, AgentTaskResultHandler] = {}
    for name in TASK_HANDLER_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            log.info("agent_task_handlers_module_missing", module=name)
            continue
        factory = getattr(module, "agent_task_handlers", None)
        if factory is None:
            continue
        found: Mapping[str, AgentTaskResultHandler] = factory(settings, db)
        for kind, handler in found.items():
            if kind in handlers:
                raise RuntimeError(f"two modules register an agent task handler for {kind!r}")
            handlers[kind] = handler
    return handlers


def build_notifier() -> AgentNotifier:
    """M18 events ``onec_agent_paired`` / ``onec_base_error`` (33 §13.3) — recorded once the notifications
    module knows the kind (render + audience); until then a no-op (requests/b5-agent-telegram-kinds.md)."""
    recorder = event_recorder()

    async def notify(s: AsyncSession, tenant_id: UUID, template: str, payload: dict[str, Any]) -> None:
        if template not in EVENT_KINDS:
            log.info("onec_notification_kind_not_wired", template=template)
            return
        await recorder.record_event(s, tenant_id, template, payload, f"onec:{template}:{uuid7()}")

    return notify


class _NoSigner:
    async def sign(self, claims: dict[str, Any]) -> tuple[str, str]:
        raise RuntimeError("task signing is done by the API process (A-03)")


class _NoWait:
    async def next(self, deadline: float) -> str | None:
        return None

    async def close(self) -> None:
        return None


class _NoSignals:
    """Signals for callers without Redis: the long-poll re-check tick picks the task up (≤ recheck_s)."""

    def wake_after_commit(self, s: AsyncSession, agent_id: UUID) -> None:
        return None

    def revoked_after_commit(self, s: AsyncSession, agent_id: UUID) -> None:
        return None

    async def wake(self, agent_id: UUID) -> None:
        return None

    async def claim_poll(self, agent_id: UUID, poll_id: str) -> None:
        return None

    async def is_current_poll(self, agent_id: UUID, poll_id: str) -> bool:
        return True

    async def wait(self, agent_id: UUID, recheck_s: float) -> PollWaiter:
        return _NoWait()

    async def cached_status(self, agent_id: UUID) -> str | None:
        return None

    async def cache_status(self, agent_id: UUID, status: str) -> None:
        return None


@dataclass(frozen=True, slots=True)
class OneCAgentsModule:
    agents: AgentService
    tasks: AgentTaskService
    pairing: PairingService
    directory: SqlAgentDirectory
    grants: AgentGrantService
    diagnostics_max_bytes: int = 20 * 1024 * 1024


_built: OneCAgentsModule | None = None


def build_onec_agents_module(
    settings: Settings, db: Database, redis: Callable[[], Redis], grants: AgentGrantService
) -> OneCAgentsModule:
    """API side (``app.state.onec_agents``); ``grants`` — the auth module's agent grants (artefact reader)."""
    global _built
    store = SqlAgentStore()
    signals = RedisAgentSignals(redis, status_ttl_s=settings.agent_status_cache_s)
    signer = RingTaskSigner(signing_key_ring(settings, db, PURPOSE_ONEC_TASK))
    tasks = AgentTaskService(store, signals, signer, collect_task_handlers(settings, db))
    notify = build_notifier()
    agents = AgentService(
        db.session_factory,
        store,
        signals,
        tasks,
        grants,
        FilesystemDiagnosticsFiles(settings.file_storage_dir),
        notify,
        min_agent_version=settings.agent_min_version,
        poll_max_wait_s=settings.agent_poll_max_wait_s,
        poll_recheck_s=settings.agent_poll_recheck_s,
        api_prefix=settings.api_prefix,
    )
    pairing = PairingService(store, SqlPairingStore(), agents, notify)
    _built = OneCAgentsModule(
        agents, tasks, pairing, SqlAgentDirectory(store), grants, settings.agent_diagnostics_max_bytes
    )
    return _built


def agent_tasks(redis: Callable[[], Redis] | None = None) -> AgentTaskPort:
    """:class:`AgentTaskPort` for other modules; with ``redis`` (or inside the API process) it also wakes the
    agent's long-poll after COMMIT, otherwise the poll's re-check tick finds the task."""
    if redis is None and _built is not None:
        return _built.tasks
    signals = RedisAgentSignals(redis) if redis is not None else _NoSignals()
    return AgentTaskService(SqlAgentStore(), signals, _NoSigner())


def agent_directory() -> AgentDirectory:
    """Agent read model (contracts/agent-tasks.md §3) — runs in the caller's tenant transaction."""
    return SqlAgentDirectory(SqlAgentStore())


def lease_sweeper(settings: Settings, db: Database) -> LeaseSweeper:
    store = SqlAgentStore()
    return LeaseSweeper(db.session_factory, AgentTaskService(store, _NoSignals(), _NoSigner()))
