"""Ports of the notifications module (23 §1): Telegram Bot API, link-code store, SQL, daily summary source."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# --- Telegram Bot API (21 §11) ----------------------------------------------------------------------
ErrorKind = Literal["transient", "blocked", "invalid", "auth"]


@dataclass(frozen=True, slots=True)
class TelegramSendResult:
    """``ok`` or a classified failure (21 §0): ``transient`` (timeout/5xx/429 → retry), ``blocked`` (403 /
    chat not found → the link is revoked, 21 §11 "inactive"), ``invalid`` (other 4xx → failed), ``auth``
    (401)."""

    ok: bool
    error_kind: ErrorKind | None = None
    description: str | None = None
    retry_after_s: int | None = None


class TelegramPort(Protocol):
    async def send_message(self, chat_id: str, text: str) -> TelegramSendResult: ...


# --- one-time link codes (US-M18-01, qaror #54: 10 min, single use) ---------------------------------
@dataclass(frozen=True, slots=True)
class LinkGrant:
    tenant_id: UUID
    user_id: UUID


class LinkCodeStore(Protocol):
    async def put(self, code: str, grant: LinkGrant, ttl_s: int) -> None:
        """Store ``code`` (replacing the user's previous unused code)."""
        ...

    async def take(self, code: str) -> LinkGrant | None:
        """Atomically read-and-delete (single use); ``None`` when unknown or expired."""
        ...

    async def seen_update(self, update_id: int, ttl_s: int) -> bool:
        """``True`` when this Telegram ``update_id`` was already processed (21 §11 idempotency)."""
        ...

    async def forget_update(self, update_id: int) -> None: ...


# --- SQL ------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LinkRow:
    chat_id: str
    linked_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class SettingRow:
    kind: str
    enabled: bool
    time: time | None


@dataclass(frozen=True, slots=True)
class Recipient:
    user_id: UUID
    chat_id: str
    locale: str
    branch_ids: tuple[UUID, ...]  # empty = every branch (15 §2.4)
    report_time: time | None  # notification_settings.time of the kind (daily_report)


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    payload: Mapping[str, Any]
    attempts: int
    idempotency_key: str
    fresh: bool  # created within EVENT_MAX_AGE (database clock)


@dataclass(frozen=True, slots=True)
class LogRow:
    id: UUID
    channel: str
    recipient: str
    template: str
    status: str
    cost: Any
    created_at: datetime


class NotificationRepository(Protocol):
    # links
    async def get_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> LinkRow | None: ...
    async def upsert_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID, chat_id: str) -> None: ...
    async def revoke_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> bool: ...
    async def revoke_chat(self, s: AsyncSession, chat_id: str) -> int: ...
    async def member_can_link(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> bool: ...
    async def names(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> tuple[str, str, str]:
        """``(tenant name, user name, user locale)``."""
        ...

    # settings
    async def settings(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> list[SettingRow]: ...
    async def upsert_setting(
        self, s: AsyncSession, tenant_id: UUID, user_id: UUID, kind: str, enabled: bool, at: time | None
    ) -> None: ...

    # recipients (re-read on every fan-out and delivery)
    async def recipients(
        self, s: AsyncSession, kind: str, audience: str, user_id: UUID | None = None
    ) -> list[Recipient]: ...
    async def branch_of_register(self, s: AsyncSession, cash_register_id: UUID) -> UUID | None: ...
    async def branch_name(self, s: AsyncSession, branch_id: UUID) -> str | None: ...

    # outbox (kind='telegram')
    async def claim(self, s: AsyncSession, max_age: timedelta) -> ClaimedJob | None: ...
    async def enqueue(
        self, s: AsyncSession, tenant_id: UUID, payload: Mapping[str, Any], idempotency_key: str
    ) -> bool: ...
    async def job_exists(self, s: AsyncSession, idempotency_key: str) -> bool: ...
    async def finish(
        self, s: AsyncSession, job_id: UUID, status: str, last_error: str | None, run_after: timedelta | None
    ) -> None: ...
    async def log(
        self, s: AsyncSession, tenant_id: UUID, recipient: str, template: str, status: str
    ) -> None: ...
    async def log_page(
        self,
        s: AsyncSession,
        *,
        channel: str | None,
        status: str | None,
        before: UUID | None,
        limit: int,
    ) -> list[LogRow]: ...


# --- daily summary (contract 5, owner b4-reports) ---------------------------------------------------
class DailySummarySource(Protocol):
    async def for_day(
        self, s: AsyncSession, tenant_id: UUID, day: date, branch_ids: Sequence[UUID] | None
    ) -> Mapping[str, Any]:
        """The report of ``day`` as plain JSON-able data (the wiring adapts ``reports.daily_summary()``)."""
        ...
