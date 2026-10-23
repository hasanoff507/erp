"""Public entry points of the fiscal package (21 §1, §16; 23 §1 ``wiring.py``).

* :func:`fiscal_service` → ``FiscalService`` (contracts.py) — sales, returns, debts, cash (Z-report);
* :func:`fiscal_port` → the adapter selected by ``ERP_FISCAL_PROVIDER``: ``fake`` — one process-wide
  :class:`FakeFiscalAdapter` (FM emulator, refused in prod); ``partner_cloud`` —
  :class:`PartnerCloudFiscalAdapter` over :class:`FakePartnerCloud` (``ERP_FISCAL_PARTNER_FAKE``, refused in
  prod)
  or the real partner client (⛔ 26 #109 — :class:`UnavailablePartnerCloud`); ``multikassa_local`` /
  ``fiscaldrive_local`` — :class:`LocalBridgeServerAdapter` (the FM signs on the device);
* :func:`ofd_send_service`, :func:`unacked_monitor`, :func:`fiscal_receipt_queries`,
  :func:`agent_status_sweep`,
  :func:`provider_ack_poller` — worker / cron / REST;
* :func:`agent_task_handlers` — ``fiscal.status`` / ``fiscal.resend_unsent`` / ``fiscal.zreport`` result
  handlers
  for the store-agent task registry (PLAN contract 1); :func:`fiscal_dispatcher` — queues those tasks;
* :func:`fiscal_readiness`, :func:`fiscal_alerts` — PLAN contract 4 (period close readiness, BO-02).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.integrations.fiscal.application.agent_tasks import (
    KINDS as AGENT_TASK_KINDS,
)
from app.modules.integrations.fiscal.application.agent_tasks import (
    AgentStatusSweep,
    FiscalAgentDispatcher,
    FiscalAlerts,
    FiscalReadiness,
    FiscalTaskHandlers,
    ProviderAckPoller,
    TaskHandler,
    alerts,
    readiness,
)
from app.modules.integrations.fiscal.application.contracts import (
    FiscalKind,
    FiscalReceiptRef,
    FiscalService,
    PaymentForm,
)
from app.modules.integrations.fiscal.application.outbox import (
    FiscalReceiptQueries,
    MonitorReport,
    OfdSendService,
    SendOutcome,
    UnackedMonitor,
)
from app.modules.integrations.fiscal.application.ports import AgentTaskPort, FiscalPort, ReceiptFilter
from app.modules.integrations.fiscal.application.registers import FiscalRegisterQueries
from app.modules.integrations.fiscal.application.service import (
    LOCAL_BRIDGE,
    MONITOR_JOB,
    OFD_SEND_JOB,
    OFD_SWEEP_JOB,
    FiscalServiceImpl,
    JobEnqueuer,
    ZReportRequester,
)
from app.modules.integrations.fiscal.domain.rules import effective_created_at, payment_form
from app.modules.integrations.fiscal.infrastructure.fake import FakeFiscalAdapter
from app.modules.integrations.fiscal.infrastructure.fiscal_sql import SqlFiscalRepository
from app.modules.integrations.fiscal.infrastructure.partner_cloud import (
    FakePartnerCloud,
    PartnerCloudFiscalAdapter,
    UnavailablePartnerCloud,
)
from app.modules.integrations.fiscal.infrastructure.queue import SaqEnqueuer
from app.modules.integrations.fiscal.infrastructure.unavailable import LocalBridgeServerAdapter
from app.modules.notifications.wiring import event_recorder

__all__ = [
    "ACK_POLL_JOB",
    "AGENT_STATUS_JOB",
    "AGENT_TASK_KINDS",
    "LOCAL_BRIDGE",
    "MONITOR_JOB",
    "OFD_SEND_JOB",
    "OFD_SWEEP_JOB",
    "FakeFiscalAdapter",
    "FakePartnerCloud",
    "FiscalAlerts",
    "FiscalKind",
    "FiscalReadiness",
    "FiscalReceiptQueries",
    "FiscalReceiptRef",
    "FiscalRegisterQueries",
    "FiscalService",
    "FiscalServiceImpl",
    "MonitorReport",
    "PaymentForm",
    "ReceiptFilter",
    "SendOutcome",
    "agent_status_sweep",
    "agent_task_handlers",
    "agent_task_port",
    "effective_created_at",
    "fake_fiscal_adapter",
    "fake_partner_cloud",
    "fiscal_alerts",
    "fiscal_dispatcher",
    "fiscal_port",
    "fiscal_readiness",
    "fiscal_receipt_queries",
    "fiscal_register_queries",
    "fiscal_service",
    "ofd_send_service",
    "payment_form",
    "provider_ack_poller",
    "request_fiscal_status",
    "unacked_monitor",
]

AGENT_STATUS_JOB: Final = "fiscal_agent_status"
ACK_POLL_JOB: Final = "fiscal_ack_poll"
_FAKE: Final = FakeFiscalAdapter()
_FAKE_PARTNER: Final = FakePartnerCloud()
_REPO: Final = SqlFiscalRepository()


def fake_fiscal_adapter() -> FakeFiscalAdapter:
    """The process-wide fake FM (tests flip ``fail`` / ``ack`` / ``device_state`` on it)."""
    return _FAKE


def fake_partner_cloud() -> FakePartnerCloud:
    """The process-wide fake partner cloud behind ``ERP_FISCAL_PARTNER_FAKE`` (tests flip ``online``,
    ``fail``)."""
    return _FAKE_PARTNER


def fiscal_port(settings: Settings) -> FiscalPort:
    provider = settings.fiscal_provider
    if provider == "fake":
        if settings.environment == "prod":  # defence in depth: Settings already refuses this
            raise RuntimeError("ERP_FISCAL_PROVIDER=fake is not allowed in prod (21 §1)")
        return _FAKE
    if provider == "partner_cloud":
        if settings.fiscal_partner_fake:
            if settings.environment == "prod":
                raise RuntimeError("ERP_FISCAL_PARTNER_FAKE is not allowed in prod (21 §1)")
            return PartnerCloudFiscalAdapter(_FAKE_PARTNER)
        return PartnerCloudFiscalAdapter(UnavailablePartnerCloud())  # real client — ⛔ 26 #109
    return LocalBridgeServerAdapter(provider)


def agent_task_port() -> AgentTaskPort | None:
    """The store-agent task queue (``onec_integration.wiring.agent_tasks()``, PLAN contract 1). Imported
    lazily: ``onec_integration.wiring`` discovers this module's ``agent_task_handlers`` (no import cycle)."""
    try:
        from app.modules.onec_integration.wiring import agent_tasks
    except ImportError:  # pragma: no cover - the store-agent module is part of every Bosqich 5 build
        return None
    return agent_tasks()


def fiscal_dispatcher(tasks: AgentTaskPort | None = None) -> FiscalAgentDispatcher:
    return FiscalAgentDispatcher(tasks if tasks is not None else agent_task_port())


def _queue(settings: Settings) -> JobEnqueuer:
    return SaqEnqueuer(settings.redis_url.get_secret_value(), settings.queue_name)


def fiscal_service(
    settings: Settings, *, queue: JobEnqueuer | None = None, tasks: AgentTaskPort | None = None
) -> FiscalServiceImpl:
    """The ``FiscalService`` contract; ``enqueue`` sends the ``fiscal_ofd_send`` SAQ jobs after commit; in
    local-bridge mode a Z-report row queues ``fiscal.zreport`` for the register's agent."""
    requester: ZReportRequester | None = None
    if settings.fiscal_provider in LOCAL_BRIDGE:
        dispatcher = fiscal_dispatcher(tasks)

        async def _zreport(
            s: AsyncSession, tenant_id: UUID, register_id: UUID, shift_id: UUID, receipt_id: UUID
        ) -> object:
            reg = await _REPO.binding(s, register_id)
            return None if reg is None else await dispatcher.zreport(s, tenant_id, reg, shift_id, receipt_id)

        requester = _zreport
    return FiscalServiceImpl(
        _REPO, fiscal_port(settings), settings.fiscal_provider, queue or _queue(settings), requester
    )


def ofd_send_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: FiscalPort | None = None
) -> OfdSendService:
    return OfdSendService(session_factory, _REPO, port or fiscal_port(settings))


def unacked_monitor(
    session_factory: async_sessionmaker[AsyncSession], *, tasks: AgentTaskPort | None = None
) -> UnackedMonitor:
    dispatcher = fiscal_dispatcher(tasks)

    async def resend(s: AsyncSession, tenant_id: UUID, register_id: UUID, receipt_key: str) -> object:
        reg = await _REPO.binding(s, register_id)
        return None if reg is None else await dispatcher.resend(s, tenant_id, reg, receipt_key)

    return UnackedMonitor(session_factory, _REPO, event_recorder(), resend)


def agent_status_sweep(
    session_factory: async_sessionmaker[AsyncSession], *, tasks: AgentTaskPort | None = None
) -> AgentStatusSweep:
    return AgentStatusSweep(session_factory, _REPO, fiscal_dispatcher(tasks))


def provider_ack_poller(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: FiscalPort | None = None
) -> ProviderAckPoller:
    return ProviderAckPoller(session_factory, _REPO, port or fiscal_port(settings))


def agent_task_handlers(settings: Settings, db: Database | None = None) -> dict[str, TaskHandler]:
    """PLAN contract 1: ``{kind: handler}`` for ``fiscal.status`` / ``fiscal.resend_unsent`` /
    ``fiscal.zreport``;
    a handler runs inside the A-05 result transaction."""
    return FiscalTaskHandlers(_REPO, event_recorder()).as_registry()


def fiscal_receipt_queries(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> FiscalReceiptQueries:
    return FiscalReceiptQueries(session_factory, _REPO, fiscal_service(settings))


def fiscal_register_queries(
    session_factory: async_sessionmaker[AsyncSession], *, tasks: AgentTaskPort | None = None
) -> FiscalRegisterQueries:
    return FiscalRegisterQueries(session_factory, _REPO, fiscal_dispatcher(tasks))


async def request_fiscal_status(
    s: AsyncSession, tenant_id: UUID, register_id: UUID, *, tasks: AgentTaskPort | None = None
) -> UUID | None:
    """Queue one ``fiscal.status`` for a register's store agent now (BO-12 binding, 21 §16); best effort."""
    reg = await _REPO.binding(s, register_id)
    return None if reg is None else await fiscal_dispatcher(tasks).status(s, tenant_id, reg)


async def fiscal_readiness(s: AsyncSession, period: str) -> FiscalReadiness:
    """PLAN contract 4 (20 #16, QT-M11-05) — inside the caller's tenant transaction."""
    return await readiness(_REPO, s, period)


async def fiscal_alerts(
    s: AsyncSession, *, at: datetime, branch_ids: tuple[UUID, ...] | None = None
) -> FiscalAlerts:
    """PLAN contract 4 (BO-02 ``fiscal_unacked``, 20 #17) — inside the caller's tenant transaction."""
    return await alerts(_REPO, s, at, branch_ids)
