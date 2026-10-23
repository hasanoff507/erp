"""Public entry points of the marking integration (21 §4; 23 §1 ``wiring.py``; contracts/marking.md).

* :func:`marking_hooks` — document hooks (goods receipt / supplier return / write-off / sales), run in the
  caller's transaction;
* :func:`marking_port_provider` — the tenant's ``MarkingPort`` (``ERP_MARKING_PROVIDER``: ``crpt`` — the
  tenant's ``crpt_api_key`` from ``tenant_secrets`` → ``CrptXtraceAdapter`` (⛔ 26 #40); ``fake`` — one
  process-wide :class:`FakeMarkingAdapter`, refused in prod);
* :func:`build_marking_module` (``app.state.marking`` — ``POST /marking-codes/verify``),
  :func:`marking_outbox_service`, :func:`acceptance_monitor` — REST / worker / cron;
* :func:`verify_tenant_credentials` — the ``PUT /tenant/integrations/crpt`` check
  (contracts/tenant-integrations.md).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.integrations.marking.application.hooks import (
    ALERT,
    DUE,
    MarkedLine,
    MarkingHooks,
    acceptance_view,
)
from app.modules.integrations.marking.application.monitor import AcceptanceMonitor, MonitorReport
from app.modules.integrations.marking.application.outbox import MarkingOutboxService, Outcome
from app.modules.integrations.marking.application.ports import (
    MarkingAcceptResult,
    MarkingPort,
    MarkingPortProvider,
    MarkingProviderError,
    MarkingResult,
    MarkingVerifyResult,
)
from app.modules.integrations.marking.application.verify import MarkingVerifyService, VerifyRequest
from app.modules.integrations.marking.domain import rules
from app.modules.integrations.marking.infrastructure.fake import FakeMarkingAdapter
from app.modules.integrations.marking.infrastructure.marking_sql import SqlMarkingRepository
from app.modules.integrations.marking.infrastructure.providers import (
    CrptPortProvider,
    SecretReader,
    StaticPortProvider,
)
from app.modules.notifications.wiring import event_recorder

OUTBOX_RUN_JOB: Final = "marking_outbox_run"  # SAQ: one marking outbox job (after commit)
OUTBOX_SWEEP_JOB: Final = "marking_outbox_sweep"  # SAQ: the tenant's due marking jobs (cron backstop)
MONITOR_JOB: Final = "marking_acceptance_monitor"  # SAQ: acceptance deadline stages (QT-NFR-07)
JOB_KINDS: Final = rules.JOB_KINDS
ALERT_KIND: Final = ALERT
DUE_KIND: Final = DUE

__all__ = [
    "ALERT_KIND",
    "DUE_KIND",
    "JOB_KINDS",
    "MONITOR_JOB",
    "OUTBOX_RUN_JOB",
    "OUTBOX_SWEEP_JOB",
    "AcceptanceMonitor",
    "FakeMarkingAdapter",
    "MarkedLine",
    "MarkingAcceptResult",
    "MarkingHooks",
    "MarkingModule",
    "MarkingOutboxService",
    "MarkingPort",
    "MarkingProviderError",
    "MarkingResult",
    "MarkingVerifyResult",
    "MarkingVerifyService",
    "MonitorReport",
    "Outcome",
    "VerifyRequest",
    "acceptance_monitor",
    "acceptance_view",
    "build_marking_module",
    "fake_marking_adapter",
    "marking_hooks",
    "marking_outbox_service",
    "marking_port_provider",
    "verify_tenant_credentials",
]

_FAKE: Final = FakeMarkingAdapter()


def fake_marking_adapter() -> FakeMarkingAdapter:
    """The process-wide fake CRPT (tests set ``statuses`` / ``fail`` / ``delay_s`` / ``reject`` on it)."""
    return _FAKE


def _secret_reader(settings: Settings) -> SecretReader | None:
    """``tenant_keys.wiring.tenant_secrets(settings)`` (b5-payments, contracts/tenant-integrations.md);
    ``None`` until that module is installed — the tenant then counts as "no CRPT key"."""
    try:
        module = importlib.import_module("app.modules.integrations.tenant_keys.wiring")
    except ImportError:
        return None
    factory: Callable[[Settings], SecretReader] = module.tenant_secrets
    return factory(settings)


def marking_port_provider(settings: Settings) -> MarkingPortProvider:
    if settings.marking_provider == "fake":
        if settings.environment == "prod":  # defence in depth: Settings already refuses this
            raise RuntimeError("ERP_MARKING_PROVIDER=fake is not allowed in prod (21 §4)")
        return StaticPortProvider(_FAKE)
    return CrptPortProvider(_secret_reader(settings))


def marking_hooks() -> MarkingHooks:
    return MarkingHooks(SqlMarkingRepository(), event_recorder())


@dataclass(frozen=True, slots=True)
class MarkingModule:
    verify: MarkingVerifyService


def build_marking_module(settings: Settings, db: Database) -> MarkingModule:
    return MarkingModule(
        verify=MarkingVerifyService(
            db.session_factory,
            SqlMarkingRepository(),
            marking_port_provider(settings),
            timeout_s=settings.marking_verify_timeout_s,
        )
    )


def marking_outbox_service(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    ports: MarkingPortProvider | None = None,
    clock: Callable[[], datetime] | None = None,
) -> MarkingOutboxService:
    return MarkingOutboxService(
        session_factory,
        SqlMarkingRepository(),
        ports or marking_port_provider(settings),
        event_recorder(),
        clock=clock,
    )


def acceptance_monitor(session_factory: async_sessionmaker[AsyncSession]) -> AcceptanceMonitor:
    return AcceptanceMonitor(session_factory, SqlMarkingRepository(), event_recorder())


async def verify_tenant_credentials(
    settings: Settings, provider_kind: str, secret: Mapping[str, Any]
) -> None:
    """``PUT /tenant/integrations/crpt``: ``api_key`` must be a non-empty string. No CRPT round trip — the
    xTrace endpoint is not available yet (26 #40); the key is checked on its first real use."""
    del settings
    if provider_kind != "crpt":
        return
    key = secret.get("api_key")
    if not isinstance(key, str) or not key.strip() or len(key) > 4096:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="api_key", message_key="validation.required")],
        )
