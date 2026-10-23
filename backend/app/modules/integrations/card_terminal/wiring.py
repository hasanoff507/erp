"""Composition of the card-terminal slice (23 §1 ``wiring.py``; qaror #71).

Public entry points: :func:`card_payments` (the :class:`CardPayments` contract used inside document
postings — sales, returns, shift close), :func:`build_card_terminal_module` (REST services on
``app.state.card_terminal``), :func:`orphan_sweep` (cron job) and :func:`fake_card_terminal` /
:func:`uzqr_port` (the B3 adapters).
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.access.wiring import approval_gate
from app.modules.integrations.card_terminal.application.agent_tasks import (
    SETTLEMENT_KIND,
    STATUS_KIND,
    AgentTasks,
    CardAgentService,
    TaskResult,
    TaskView,
)
from app.modules.integrations.card_terminal.application.contracts import CardPayments
from app.modules.integrations.card_terminal.application.module import CardTerminalModule
from app.modules.integrations.card_terminal.application.orphans import OrphanSweep
from app.modules.integrations.card_terminal.application.payments import CardPaymentsService
from app.modules.integrations.card_terminal.application.settlements import SettlementService, SettlementWriter
from app.modules.integrations.card_terminal.application.terminals import CardTerminalService
from app.modules.integrations.card_terminal.application.transactions import CardTransactionService
from app.modules.integrations.card_terminal.application.uzqr import UzqrPort
from app.modules.integrations.card_terminal.infrastructure.fake import FakeCardTerminalAdapter
from app.modules.integrations.card_terminal.infrastructure.sql import SqlCardRepository
from app.modules.integrations.card_terminal.infrastructure.uzqr_stub import UzqrStubAdapter
from app.modules.notifications.wiring import event_recorder

CARD_ORPHAN_SWEEP_JOB = "card_orphan_sweep"  # SAQ job: one tenant's orphan approved purchases (23 §4)
CARD_STATUS_SWEEP_JOB = "card_status_sweep"  # SAQ job: card.status for every capable agent (23 §4.2)
CARD_SETTLEMENT_SWEEP_JOB = "card_settlement_sweep"  # SAQ job: card.settlement at 23:30 Tashkent (23 §4.2)

TaskHandler = Callable[[AsyncSession, UUID, UUID, Any, Any], Awaitable[None]]

__all__ = [
    "CARD_ORPHAN_SWEEP_JOB",
    "CARD_SETTLEMENT_SWEEP_JOB",
    "CARD_STATUS_SWEEP_JOB",
    "CardAgentService",
    "CardPayments",
    "CardTerminalModule",
    "FakeCardTerminalAdapter",
    "agent_task_handlers",
    "build_card_terminal_module",
    "card_agent_service",
    "card_payments",
    "fake_card_terminal",
    "orphan_sweep",
    "uzqr_port",
]


def _settlement_writer(repo: SqlCardRepository) -> SettlementWriter:
    return SettlementWriter(repo, event_recorder())


def card_payments(settings: Settings | None = None) -> CardPayments:
    """Card rules for document postings — call inside the caller's transaction."""
    repo = SqlCardRepository()
    return CardPaymentsService(repo, approval_gate(), _settlement_writer(repo))


def build_card_terminal_module(settings: Settings, db: Database) -> CardTerminalModule:
    repo = SqlCardRepository()
    return CardTerminalModule(
        terminals=CardTerminalService(
            db.session_factory,
            repo,
            fake_allowed=settings.card_fake_terminals and settings.environment != "prod",
        ),
        transactions=CardTransactionService(db.session_factory, repo, approval_gate()),
        settlements=SettlementService(db.session_factory, repo, _settlement_writer(repo)),
        orphans=OrphanSweep(db.session_factory, repo),
    )


def orphan_sweep(session_factory: async_sessionmaker[AsyncSession]) -> OrphanSweep:
    return OrphanSweep(session_factory, SqlCardRepository())


def fake_card_terminal(settings: Settings) -> FakeCardTerminalAdapter:
    """The B3 terminal emulator (tests, dev agent emulator); never in prod (21 §9.4)."""
    if settings.environment == "prod":
        raise RuntimeError("FakeCardTerminalAdapter is not allowed in prod (21 §9.4)")
    return FakeCardTerminalAdapter()


def uzqr_port(settings: Settings) -> UzqrPort:
    """Dynamic UzQR — stub until Bosqich 5 (21 §9.1, 26 #49)."""
    return UzqrStubAdapter()


def _agent_tasks() -> AgentTasks:
    """The agent slice's ``AgentTaskPort`` (contracts/agent-tasks.md §1), resolved at call time: the agent
    wiring imports this module's ``agent_task_handlers`` (no import cycle at module load)."""
    module = importlib.import_module("app.modules.onec_integration.wiring")
    return cast(AgentTasks, module.agent_tasks())


def card_agent_service(
    settings: Settings | None,
    session_factory: async_sessionmaker[AsyncSession],
    tasks: AgentTasks | None = None,
) -> CardAgentService:
    """``card.status`` / ``card.settlement`` enqueue + result handling (qaror #71, 23 §4.2)."""
    repo = SqlCardRepository()
    return CardAgentService(session_factory, repo, tasks or _agent_tasks(), _settlement_writer(repo))


def agent_task_handlers(settings: Settings, db: Database) -> Mapping[str, TaskHandler]:
    """Result handlers registered with the agent slice (contracts/agent-tasks.md §2)."""
    service = CardAgentService(
        db.session_factory, SqlCardRepository(), _NoEnqueue(), _settlement_writer(SqlCardRepository())
    )

    async def status(
        s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: TaskView, result: TaskResult
    ) -> None:
        await service.handle_status(s, tenant_id, agent_id, task, result)

    async def settlement(
        s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: TaskView, result: TaskResult
    ) -> None:
        await service.handle_settlement(s, tenant_id, agent_id, task, result)

    return {STATUS_KIND: status, SETTLEMENT_KIND: settlement}


class _NoEnqueue:
    """Result handlers never enqueue."""

    async def enqueue(self, *args: Any, **kwargs: Any) -> UUID:
        raise RuntimeError("result handlers do not enqueue agent tasks")
