"""Public entry points of the e-documents slice (23 §1 ``wiring.py``).

* :func:`einvoice_port` — the tenant-less adapter (debts STIR lookup; B2 callers);
* :func:`build_edocs_module` — the REST services (``/einvoices``, ``/ettn-documents``,
  ``/powers-of-attorney``) published on ``app.state.edocs``;
* :func:`einvoice_hooks` — contract 5a (sales posting → outgoing draft), :func:`einvoice_alerts` — 5c;
* :func:`ettn_outbox_service`, :func:`doc_outbox_service`, :func:`inbox_poller` — the SAQ workers.

Other modules depend on the ``EInvoicePort`` protocol from ``application.ports`` only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.integrations.einvoice.application.common import DOC_JOB, ETTN_JOB, JobEnqueuer
from app.modules.integrations.einvoice.application.doc_outbox import DocOutboxService
from app.modules.integrations.einvoice.application.einvoices import EInvoiceService
from app.modules.integrations.einvoice.application.ettn_docs import EttnDocService
from app.modules.integrations.einvoice.application.ettn_outbox import EttnOutboxService, Outcome
from app.modules.integrations.einvoice.application.hooks import EInvoiceHooks
from app.modules.integrations.einvoice.application.inbox import InboxPoller
from app.modules.integrations.einvoice.application.poa import PowerOfAttorneyService
from app.modules.integrations.einvoice.application.ports import (
    CompanyInfo,
    EInvoicePort,
    EInvoicePortProvider,
    EInvoiceProviderError,
    EInvoiceResult,
    ETtnResult,
    IncomingInvoice,
    Pkcs7Signature,
    PoaResult,
    SignaturePort,
    StaticPortProvider,
)
from app.modules.integrations.einvoice.application.signing import ChallengeStore, Signer
from app.modules.integrations.einvoice.application.vat_credit import VatCredit
from app.modules.integrations.einvoice.infrastructure.credentials_sql import SqlFakturaCredentialsReader
from app.modules.integrations.einvoice.infrastructure.edocs_sql import SqlEDocsRepository
from app.modules.integrations.einvoice.infrastructure.eimzo_server import EImzoServerVerifier
from app.modules.integrations.einvoice.infrastructure.ettn_sql import SqlEttnOutboxRepository
from app.modules.integrations.einvoice.infrastructure.fake import (
    FakeEInvoiceAdapter,
    FakeSignatureVerifier,
    fake_pkcs7,
)
from app.modules.integrations.einvoice.infrastructure.faktura_uz import (
    FakturaCredentials,
    FakturaUzEInvoiceAdapter,
)
from app.modules.integrations.einvoice.infrastructure.jobs_sql import SqlDocJobRepository
from app.modules.integrations.einvoice.infrastructure.queue import RedisChallengeStore, SaqEnqueuer
from app.modules.integrations.einvoice.infrastructure.vat_sql import SqlVatCreditRepository

ETTN_SEND_JOB = ETTN_JOB  # SAQ job: one ``outbox_jobs(kind='ettn_send')`` row
ETTN_SWEEP_JOB = "einvoice_ettn_sweep"  # SAQ job: the tenant's due ``ettn_send`` rows (cron backstop)
DOC_SEND_JOB = DOC_JOB  # SAQ job: one einvoice_send / einvoice_accept / poa_send / ettn_accept row
DOC_SWEEP_JOB = "einvoice_doc_sweep"  # SAQ job: the tenant's due signed-document rows (cron backstop)
POLL_JOB = "einvoice_poll"  # SAQ job: operator inbox + status poll of one tenant (every 10 min)

__all__ = [
    "DOC_SEND_JOB",
    "DOC_SWEEP_JOB",
    "ETTN_SEND_JOB",
    "ETTN_SWEEP_JOB",
    "POLL_JOB",
    "CompanyInfo",
    "EDocsModule",
    "EInvoiceHooks",
    "EInvoicePort",
    "EInvoiceProviderError",
    "EInvoiceResult",
    "ETtnResult",
    "EttnOutboxService",
    "FakeEInvoiceAdapter",
    "FakeSignatureVerifier",
    "IncomingInvoice",
    "Outcome",
    "Pkcs7Signature",
    "PoaResult",
    "build_edocs_module",
    "doc_outbox_service",
    "einvoice_alerts",
    "einvoice_hooks",
    "einvoice_port",
    "ettn_auto_send",
    "ettn_outbox_service",
    "fake_pkcs7",
    "inbox_poller",
    "port_provider",
    "verify_tenant_credentials",
]


def einvoice_port(settings: Settings) -> EInvoicePort:
    """The tenant-less adapter selected by ``ERP_EINVOICE_PROVIDER`` (``fake`` is refused in prod by
    ``Settings``). The Faktura.uz adapter without tenant credentials answers ``auth`` errors (→ 503)."""
    if settings.einvoice_provider == "fake":
        if settings.environment == "prod":  # defence in depth: Settings already refuses this
            raise RuntimeError("ERP_EINVOICE_PROVIDER=fake is not allowed in prod (27 Bosqich 2)")
        return FakeEInvoiceAdapter()
    return FakturaUzEInvoiceAdapter(None)


@dataclass(frozen=True, slots=True)
class FakturaPortProvider:
    """Faktura.uz adapter bound to the tenant's own credentials (``tenant_secrets(kind='faktura_uz')``)."""

    reader: SqlFakturaCredentialsReader

    async def for_tenant(self, tenant_id: UUID) -> EInvoicePort:
        return FakturaUzEInvoiceAdapter(await self.reader.read(tenant_id))


def port_provider(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession], port: EInvoicePort | None = None
) -> EInvoicePortProvider:
    if port is not None:
        return StaticPortProvider(port)
    if settings.einvoice_provider == "fake":
        return StaticPortProvider(einvoice_port(settings))
    from app.modules.integrations.tenant_keys.wiring import tenant_secrets  # lazy: tenant_keys discovers us

    return FakturaPortProvider(SqlFakturaCredentialsReader(session_factory, tenant_secrets(settings)))


async def verify_tenant_credentials(
    settings: Settings, provider_kind: str, secret: Mapping[str, str]
) -> None:
    """Contract ``tenant-integrations.md``: ``PUT /tenant/integrations/faktura-uz`` checks the login before
    storing — the documented Faktura.uz password grant (``account.faktura.uz/token``). The fake operator and
    Didox (no adapter yet, 26 #167) store without a check."""
    if provider_kind != "faktura_uz" or settings.einvoice_provider == "fake":
        return
    try:
        creds = FakturaCredentials(
            secret["login"], secret["password"], secret["client_id"], secret["client_secret"], ""
        )
    except KeyError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, params={"field": str(exc.args[0])}) from exc
    try:
        await FakturaUzEInvoiceAdapter(creds).check_credentials()
    except EInvoiceProviderError as exc:
        raise AppError(
            ErrorCode.EINVOICE_PROVIDER_UNAVAILABLE,
            params={"operation": "verify_credentials", "kind": exc.kind},
        ) from exc


def signature_verifier(settings: Settings) -> SignaturePort:
    if settings.eimzo_verifier == "fake":
        if settings.environment == "prod":
            raise RuntimeError("ERP_EIMZO_VERIFIER=fake is not allowed in prod (21 §5)")
        return FakeSignatureVerifier()
    return EImzoServerVerifier()


def ettn_auto_send(settings: Settings) -> bool:
    """27 B2: the fake operator registers an e-TTN without E-IMZO, so a vehicle transfer ``post`` queues
    ``ettn_send`` at once; with the real operator the e-TTN waits for the sign flow (19 §20)."""
    return settings.einvoice_provider == "fake"


def _queue(settings: Settings) -> JobEnqueuer:
    return SaqEnqueuer(settings.redis_url.get_secret_value(), settings.queue_name)


def _vat_credit() -> VatCredit:
    # imported here: debts.wiring imports this module (STIR lookup port) — no import cycle at load time
    from app.modules.accounting.wiring import ledger_poster
    from app.modules.debts.wiring import debt_register

    return VatCredit(SqlVatCreditRepository(), ledger_poster(), debt_register())


@dataclass(slots=True)
class EDocsModule:
    einvoices: EInvoiceService
    ettn: EttnDocService
    poa: PowerOfAttorneyService
    signer: Signer
    verifier: SignaturePort


def build_edocs_module(
    settings: Settings,
    db: Database,
    redis: Callable[[], Redis],
    *,
    verifier: SignaturePort | None = None,
    challenges: ChallengeStore | None = None,
    queue: JobEnqueuer | None = None,
) -> EDocsModule:
    """``app.state.edocs`` (Bosqich 5): e-invoices, e-TTN and powers of attorney with the E-IMZO flow."""
    repo = SqlEDocsRepository()
    verifier = verifier or signature_verifier(settings)
    signer = Signer(challenges or RedisChallengeStore(redis), verifier)
    jobs = queue or _queue(settings)
    sf = db.session_factory
    return EDocsModule(
        einvoices=EInvoiceService(sf, repo, signer, _vat_credit(), jobs),
        ettn=EttnDocService(sf, repo, signer, jobs),
        poa=PowerOfAttorneyService(sf, repo, signer, jobs),
        signer=signer,
        verifier=verifier,
    )


def einvoice_hooks() -> EInvoiceHooks:
    """Contract 5a — ``await einvoice_hooks().on_b2b_credit_sale_posted(s, tenant_id, sale_id)``."""
    return EInvoiceHooks(SqlEDocsRepository())


async def einvoice_alerts(s: AsyncSession) -> dict[str, int]:
    """Contract 5c — counts for BO-02 / readiness (caller's tenant transaction)."""
    return await SqlEDocsRepository().alerts(s)


def ettn_outbox_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: EInvoicePort | None = None
) -> EttnOutboxService:
    return EttnOutboxService(
        session_factory, SqlEttnOutboxRepository(), port_provider(settings, session_factory, port)
    )


def doc_outbox_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: EInvoicePort | None = None
) -> DocOutboxService:
    return DocOutboxService(
        session_factory,
        SqlDocJobRepository(),
        SqlEDocsRepository(),
        port_provider(settings, session_factory, port),
        _vat_credit(),
    )


def inbox_poller(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: EInvoicePort | None = None
) -> InboxPoller:
    return InboxPoller(
        session_factory,
        SqlEDocsRepository(),
        SqlVatCreditRepository(),
        port_provider(settings, session_factory, port),
    )
