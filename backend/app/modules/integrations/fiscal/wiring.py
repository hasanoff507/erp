"""Public entry points of the fiscal package (21 §1, 23 §1 ``wiring.py``).

* :func:`fiscal_service` → ``FiscalService`` (contracts.py) — sales, returns, cash (Z-report);
* :func:`fiscal_port` → the adapter selected by ``ERP_FISCAL_PROVIDER`` (``fake`` — one process-wide
  :class:`FakeFiscalAdapter`, refused in prod by ``Settings``; the real adapters are Bosqich 5);
* :func:`ofd_send_service`, :func:`unacked_monitor`, :func:`fiscal_receipt_queries` — worker / cron / REST.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
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
from app.modules.integrations.fiscal.application.ports import FiscalPort, ReceiptFilter
from app.modules.integrations.fiscal.application.service import (
    MONITOR_JOB,
    OFD_SEND_JOB,
    OFD_SWEEP_JOB,
    FiscalServiceImpl,
    JobEnqueuer,
)
from app.modules.integrations.fiscal.domain.rules import effective_created_at, payment_form
from app.modules.integrations.fiscal.infrastructure.fake import FakeFiscalAdapter
from app.modules.integrations.fiscal.infrastructure.fiscal_sql import SqlFiscalRepository
from app.modules.integrations.fiscal.infrastructure.queue import SaqEnqueuer
from app.modules.integrations.fiscal.infrastructure.unavailable import UnavailableFiscalAdapter
from app.modules.notifications.wiring import event_recorder

__all__ = [
    "MONITOR_JOB",
    "OFD_SEND_JOB",
    "OFD_SWEEP_JOB",
    "FakeFiscalAdapter",
    "FiscalKind",
    "FiscalReceiptQueries",
    "FiscalReceiptRef",
    "FiscalService",
    "FiscalServiceImpl",
    "MonitorReport",
    "PaymentForm",
    "ReceiptFilter",
    "SendOutcome",
    "effective_created_at",
    "fake_fiscal_adapter",
    "fiscal_port",
    "fiscal_receipt_queries",
    "fiscal_service",
    "ofd_send_service",
    "payment_form",
    "unacked_monitor",
]

_FAKE: Final = FakeFiscalAdapter()


def fake_fiscal_adapter() -> FakeFiscalAdapter:
    """The process-wide fake FM (tests flip ``fail`` / ``ack`` / ``device_state`` on it)."""
    return _FAKE


def fiscal_port(settings: Settings) -> FiscalPort:
    if settings.fiscal_provider == "fake":
        if settings.environment == "prod":  # defence in depth: Settings already refuses this
            raise RuntimeError("ERP_FISCAL_PROVIDER=fake is not allowed in prod (21 §1)")
        return _FAKE
    return UnavailableFiscalAdapter(settings.fiscal_provider)


def _queue(settings: Settings) -> JobEnqueuer:
    return SaqEnqueuer(settings.redis_url.get_secret_value(), settings.queue_name)


def fiscal_service(settings: Settings, *, queue: JobEnqueuer | None = None) -> FiscalServiceImpl:
    """The ``FiscalService`` contract; ``enqueue`` sends the ``fiscal_ofd_send`` SAQ jobs after commit."""
    return FiscalServiceImpl(
        SqlFiscalRepository(), fiscal_port(settings), settings.fiscal_provider, queue or _queue(settings)
    )


def ofd_send_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: FiscalPort | None = None
) -> OfdSendService:
    return OfdSendService(session_factory, SqlFiscalRepository(), port or fiscal_port(settings))


def unacked_monitor(session_factory: async_sessionmaker[AsyncSession]) -> UnackedMonitor:
    return UnackedMonitor(session_factory, SqlFiscalRepository(), event_recorder())


def fiscal_receipt_queries(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> FiscalReceiptQueries:
    return FiscalReceiptQueries(session_factory, SqlFiscalRepository(), fiscal_service(settings))
