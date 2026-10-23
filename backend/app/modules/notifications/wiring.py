"""Composition of the notifications module (23 §1 ``wiring.py``).

Other modules record events through :func:`event_recorder` (``record_event(session, tenant_id, kind,
payload, dedupe_key)`` inside their own transaction). Bosqich 4 adds the Telegram side (M18): linking (BO-20,
webhook), per-user settings, the delivery log, the outbox sender and the daily report.

The daily report reads ``app.modules.reports.wiring.daily_summary()`` (PLAN contract 5, owner b4-reports)
through a defensive import — until that module exists the daily report job is a no-op.
"""

from __future__ import annotations

import dataclasses
import importlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.notifications.application.daily_report import DailyReportService
from app.modules.notifications.application.links import TelegramLinkService, revoke_user_links
from app.modules.notifications.application.outbox import EventRecorder
from app.modules.notifications.application.ports import DailySummarySource, TelegramPort
from app.modules.notifications.application.sender import Outcome, TelegramSender
from app.modules.notifications.application.settings import NotificationSettingsService
from app.modules.notifications.domain.events import EVENT_KINDS, OUTBOX_KIND, EventKind
from app.modules.notifications.infrastructure.fake_telegram import FakeTelegram, SentMessage
from app.modules.notifications.infrastructure.link_codes import RedisLinkCodeStore
from app.modules.notifications.infrastructure.notifications_sql import SqlNotificationRepository
from app.modules.notifications.infrastructure.repositories import SqlOutboxRepository
from app.modules.notifications.infrastructure.telegram_bot import TelegramBotAdapter

log = structlog.get_logger(__name__)

TELEGRAM_SWEEP_JOB = "notifications_telegram_sweep"  # SAQ: the tenant's due telegram outbox jobs
DAILY_REPORT_JOB = "notifications_daily_report"  # SAQ: queue today's daily reports that are due
REPORTS_MODULE = "app.modules.reports.wiring"

__all__ = [
    "DAILY_REPORT_JOB",
    "EVENT_KINDS",
    "OUTBOX_KIND",
    "TELEGRAM_SWEEP_JOB",
    "EventKind",
    "EventRecorder",
    "FakeTelegram",
    "NotificationsModule",
    "Outcome",
    "SentMessage",
    "build_notifications_module",
    "daily_report_service",
    "daily_summary_source",
    "event_recorder",
    "telegram_links_revoker",
    "telegram_port",
    "telegram_sender",
]


def event_recorder() -> EventRecorder:
    return EventRecorder(SqlOutboxRepository())


@dataclass(frozen=True, slots=True)
class NotificationsModule:
    links: TelegramLinkService
    settings: NotificationSettingsService
    webhook_secret: str | None


def build_notifications_module(
    settings: Settings, db: Database, redis: Callable[[], Redis]
) -> NotificationsModule:
    repo = SqlNotificationRepository()
    links = TelegramLinkService(
        db.session_factory,
        repo,
        RedisLinkCodeStore(redis),
        bot_username=settings.telegram_bot_username,
        code_ttl_s=settings.telegram_link_code_ttl_s,
    )
    secret = settings.telegram_webhook_secret.get_secret_value() if settings.telegram_webhook_secret else None
    return NotificationsModule(links, NotificationSettingsService(db.session_factory, repo), secret or None)


def telegram_port(settings: Settings) -> TelegramPort | None:
    """``FakeTelegram`` (``ERP_TELEGRAM_FAKE``, never in prod), the Bot API adapter, or ``None`` (no
    token)."""
    if settings.telegram_fake:
        if settings.environment == "prod":  # defence in depth: Settings already refuses this
            raise RuntimeError("ERP_TELEGRAM_FAKE is not allowed in prod (qaror #34)")
        return FakeTelegram()
    if settings.telegram_bot_token is None:
        return None
    from app.modules.auth.wiring import outbound_http  # same short-lived client factory as the OTP channel

    return TelegramBotAdapter(
        outbound_http(settings),
        token=settings.telegram_bot_token.get_secret_value(),
        base_url=settings.telegram_api_base_url,
    )


def telegram_sender(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, port: TelegramPort | None = None
) -> TelegramSender | None:
    """``None`` when no Telegram channel is configured: due jobs then wait (nothing is dead-lettered)."""
    chosen = port or telegram_port(settings)
    if chosen is None:
        return None
    return TelegramSender(session_factory, SqlNotificationRepository(), chosen)


def daily_report_service(
    session_factory: async_sessionmaker[AsyncSession], source: DailySummarySource | None = None
) -> DailyReportService:
    return DailyReportService(session_factory, SqlNotificationRepository(), source or daily_summary_source())


def telegram_links_revoker() -> Callable[[AsyncSession, UUID, UUID], Awaitable[bool]]:
    """For the auth module (QT-M18-05): revoke a blocked user's link in the blocking transaction."""
    repo = SqlNotificationRepository()

    async def revoke(s: AsyncSession, tenant_id: UUID, user_id: UUID) -> bool:
        return await revoke_user_links(repo, s, tenant_id, user_id)

    return revoke


# --- contract 5 adapter -----------------------------------------------------------------------------
def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


class _ReportsDailySummary:
    """Adapts ``reports.daily_summary().for_day`` (frozen dataclasses) to the JSON snapshot of the message."""

    def __init__(self, service: Any) -> None:
        self._service = service

    async def for_day(
        self, s: AsyncSession, tenant_id: UUID, day: date, branch_ids: Sequence[UUID] | None
    ) -> Mapping[str, Any]:
        summary = await self._service.for_day(s, tenant_id, day, branch_ids)
        is_instance = dataclasses.is_dataclass(summary) and not isinstance(summary, type)
        data = dataclasses.asdict(summary) if is_instance else dict(summary)
        result: Mapping[str, Any] = _jsonable(data)
        return result


def daily_summary_source() -> DailySummarySource | None:
    try:
        module = importlib.import_module(REPORTS_MODULE)
    except ImportError:
        log.info("daily_summary_module_missing", module=REPORTS_MODULE)
        return None
    factory = getattr(module, "daily_summary", None)
    if factory is None:
        log.info("daily_summary_not_exposed", module=REPORTS_MODULE)
        return None
    return _ReportsDailySummary(factory())
