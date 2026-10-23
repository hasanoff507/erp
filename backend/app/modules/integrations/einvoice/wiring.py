"""Public entry points of the e-invoice operator adapters (23 §1 ``wiring.py``).

Other modules (debts — STIR lookup; inventory — ``outbox_jobs(kind='ettn_send')``; later e-invoices
and powers of attorney) get the port only through :func:`einvoice_port` and depend on the
``EInvoicePort`` protocol from ``application.ports``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.modules.integrations.einvoice.application.ettn_outbox import EttnOutboxService, Outcome
from app.modules.integrations.einvoice.application.ports import (
    CompanyInfo,
    EInvoicePort,
    EInvoiceProviderError,
    EInvoiceResult,
    ETtnResult,
    IncomingInvoice,
    Pkcs7Signature,
    PoaResult,
)
from app.modules.integrations.einvoice.infrastructure.ettn_sql import SqlEttnOutboxRepository
from app.modules.integrations.einvoice.infrastructure.fake import FakeEInvoiceAdapter
from app.modules.integrations.einvoice.infrastructure.faktura_uz import FakturaUzEInvoiceAdapter

ETTN_SEND_JOB = "einvoice_ettn_send"  # SAQ job: one ``outbox_jobs(kind='ettn_send')`` row
ETTN_SWEEP_JOB = "einvoice_ettn_sweep"  # SAQ job: the tenant's due ``ettn_send`` rows (cron backstop)

__all__ = [
    "ETTN_SEND_JOB",
    "ETTN_SWEEP_JOB",
    "CompanyInfo",
    "EInvoicePort",
    "EInvoiceProviderError",
    "EInvoiceResult",
    "ETtnResult",
    "EttnOutboxService",
    "FakeEInvoiceAdapter",
    "IncomingInvoice",
    "Outcome",
    "Pkcs7Signature",
    "PoaResult",
    "einvoice_port",
    "ettn_auto_send",
    "ettn_outbox_service",
]


def einvoice_port(settings: Settings) -> EInvoicePort:
    """The adapter selected by ``ERP_EINVOICE_PROVIDER`` (``fake`` is refused in prod by ``Settings``)."""
    if settings.einvoice_provider == "fake":
        if settings.environment == "prod":  # defence in depth: Settings already refuses this
            raise RuntimeError("ERP_EINVOICE_PROVIDER=fake is not allowed in prod (27 Bosqich 2)")
        return FakeEInvoiceAdapter()
    return FakturaUzEInvoiceAdapter()


def ettn_auto_send(settings: Settings) -> bool:
    """27 B2: the fake operator registers an e-TTN without E-IMZO, so a vehicle transfer ``post`` queues
    ``ettn_send`` at once; with the real operator the e-TTN waits for the Bosqich 5 sign flow (19 §20)."""
    return settings.einvoice_provider == "fake"


def ettn_outbox_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: EInvoicePort | None = None
) -> EttnOutboxService:
    return EttnOutboxService(session_factory, SqlEttnOutboxRepository(), port or einvoice_port(settings))
