"""Telegram sender — the consumer of ``outbox_jobs(kind='telegram')`` (21 §0, §11; US-M18-02/03, US-M04-02).

Two job shapes share the kind:

* **event** (written by any module through ``EventRecorder``, payload ``{"event": kind, ...}``) —
  *fan-out*: in one transaction the recipients are resolved and one **delivery** job per recipient is inserted
  (``idempotency_key = "<event key>><user_id>"``), then the event job is ``done``. An event older than
  :data:`EVENT_MAX_AGE` when first processed (e.g. recorded before the sender existed) is closed unsent.
* **delivery** (payload has ``deliver_to``; the daily report is created directly in this shape) — one
  message to one user: **claim → commit → Telegram → record**, the Bot API is never called inside a
  transaction (23 §2.1 step 5). The recipient is re-checked at claim time (active link, active membership,
  ``telegram.link`` + the kind's audience permission, the kind enabled in their settings): a
  blocked/unlinked user or a disabled kind gets nothing (QT-M18-05, QT-M18-06).

Recipients: :data:`AUDIENCE` + per-user ``notification_settings`` (default enabled) + branch scope (an event
with ``branch_id`` — or a ``cash_register_id`` — goes only to members whose ``branch_ids`` include it, or
who see every branch; the tenant-wide debt events :data:`TENANT_WIDE_KINDS` go only to members who see every
branch — SEC-01, qaror F7). Result: ``sent`` → job ``done`` + ``notifications_log('sent')``; ``transient`` →
``retry`` with backoff (base 10 s ×2, cap 5 min; Telegram ``retry_after`` honoured), the 10th failed try is
final; ``blocked`` (403 / chat not found) → the chat's links in the tenant are revoked (21 §11 "inactive")
and the job ``failed``; ``invalid``/``auth`` → ``failed``. Every final failure writes
``notifications_log('failed')``.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.modules.notifications.application.ports import (
    ClaimedJob,
    NotificationRepository,
    Recipient,
    TelegramPort,
    TelegramSendResult,
)
from app.modules.notifications.domain.policy import AUDIENCE, EVENT_MAX_AGE, exhausted, retry_delay
from app.modules.notifications.domain.render import lang_of, render

log = structlog.get_logger(__name__)

CHANNEL = "telegram"


@dataclass(frozen=True, slots=True)
class Outcome:
    job_id: UUID
    status: str  # fanned_out | stale | skipped | sent | retry | failed
    recipients: int = 0
    note: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {"job_id": str(self.job_id), "status": self.status, "recipients": self.recipients}


@dataclass(frozen=True, slots=True)
class _Delivery:
    job: ClaimedJob
    kind: str
    user_id: UUID
    chat_id: str


def _uuid(raw: Any) -> UUID | None:
    try:
        return UUID(str(raw)) if raw else None
    except ValueError:
        return None


# tenant-wide payloads (every debtor of the tenant) — never to a branch-restricted member (SEC-01)
TENANT_WIDE_KINDS: Final = frozenset({"debt_due_today", "debt_aging_60"})


def sees_branch(recipient: Recipient, branch_id: UUID | None, kind: str | None = None) -> bool:
    if kind in TENANT_WIDE_KINDS and recipient.branch_ids:
        return False
    return branch_id is None or not recipient.branch_ids or branch_id in recipient.branch_ids


class TelegramSender:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: NotificationRepository,
        port: TelegramPort,
        *,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._port = port
        self._rand = rand

    async def run(self, tenant_id: UUID) -> Outcome | None:
        """Process one due job of the tenant; ``None`` when nothing is due."""
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            job = await self._repo.claim(s, EVENT_MAX_AGE)
            if job is None:
                return None
            if "deliver_to" not in job.payload:
                return await self._fan_out(s, tenant_id, job)
            prepared = await self._prepare(s, job)
            if isinstance(prepared, Outcome):
                return prepared
            delivery, text = prepared
        try:
            result = await self._port.send_message(delivery.chat_id, text)
        except Exception as exc:  # adapter bug / network stack → transient (21 §0)
            log.warning("telegram_send_error", job_id=str(job.id), exc_info=True)
            result = TelegramSendResult(False, "transient", f"{type(exc).__name__}: {exc}")
        return await self._record(tenant_id, delivery, result)

    async def process_due(self, tenant_id: UUID, *, limit: int = 100) -> list[Outcome]:
        """Cron sweep: drain the tenant's due telegram jobs (new events, deliveries, retries, dead
        workers)."""
        out: list[Outcome] = []
        while len(out) < limit:
            outcome = await self.run(tenant_id)
            if outcome is None:
                break
            out.append(outcome)
        return out

    # --- fan-out ------------------------------------------------------------------------------------
    async def _fan_out(self, s: AsyncSession, tenant_id: UUID, job: ClaimedJob) -> Outcome:
        kind = str(job.payload.get("event", ""))
        audience = AUDIENCE.get(kind)
        if audience is None:
            await self._repo.finish(s, job.id, "done", f"unknown event kind {kind!r}", None)
            return Outcome(job.id, "skipped", note="unknown kind")
        if not job.fresh:
            await self._repo.finish(s, job.id, "done", "stale event: not sent", None)
            return Outcome(job.id, "stale")
        branch_id = await self._branch(s, job.payload)
        count = 0
        for recipient in await self._repo.recipients(s, kind, audience):
            if not sees_branch(recipient, branch_id, kind):
                continue
            payload = {**job.payload, "deliver_to": str(recipient.user_id), "source_job_id": str(job.id)}
            if await self._repo.enqueue(s, tenant_id, payload, f"{job.idempotency_key}>{recipient.user_id}"):
                count += 1
        await self._repo.finish(s, job.id, "done", None if count else "no recipients", None)
        return Outcome(job.id, "fanned_out", count)

    async def _branch(self, s: AsyncSession, payload: Mapping[str, Any]) -> UUID | None:
        branch_id = _uuid(payload.get("branch_id"))
        if branch_id is None and (register := _uuid(payload.get("cash_register_id"))) is not None:
            branch_id = await self._repo.branch_of_register(s, register)
        return branch_id

    # --- delivery -----------------------------------------------------------------------------------
    async def _prepare(self, s: AsyncSession, job: ClaimedJob) -> Outcome | tuple[_Delivery, str]:
        kind = str(job.payload.get("event", ""))
        user_id = _uuid(job.payload.get("deliver_to"))
        audience = AUDIENCE.get(kind)
        if user_id is None or audience is None:
            await self._repo.finish(s, job.id, "failed", "malformed delivery payload", None)
            return Outcome(job.id, "failed", note="malformed")
        branch_id = await self._branch(s, job.payload)
        eligible = [
            r
            for r in await self._repo.recipients(s, kind, audience, user_id)
            if sees_branch(r, branch_id, kind)
        ]
        if not eligible:  # unlinked, blocked, lost the permission or disabled the kind since the fan-out
            await self._repo.finish(s, job.id, "done", "recipient no longer eligible: not sent", None)
            return Outcome(job.id, "skipped")
        recipient = eligible[0]
        branch_name = await self._repo.branch_name(s, branch_id) if branch_id is not None else None
        text = render(kind, job.payload, lang_of(recipient.locale), branch_name=branch_name)
        return _Delivery(job, kind, user_id, recipient.chat_id), text

    async def _record(self, tenant_id: UUID, d: _Delivery, result: TelegramSendResult) -> Outcome:
        job = d.job
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            if result.ok:
                await self._repo.finish(s, job.id, "done", None, None)
                await self._repo.log(s, tenant_id, d.chat_id, d.kind, "sent")
                return Outcome(job.id, "sent", 1)
            error = f"{result.error_kind}: {result.description or ''}"[:1000]
            if result.error_kind == "transient" and not exhausted(job.attempts):
                delay = retry_delay(job.attempts, self._rand(), result.retry_after_s)
                await self._repo.finish(s, job.id, "retry", error, delay)
                return Outcome(job.id, "retry", note=error)
            if result.error_kind == "blocked":
                revoked = await self._repo.revoke_chat(s, d.chat_id)
                log.info("telegram_chat_inactive", job_id=str(job.id), links_revoked=revoked)
            if result.error_kind == "transient":
                error = f"transient, {job.attempts} attempts: {result.description or ''}"[:1000]
            await self._repo.finish(s, job.id, "failed", error, None)
            await self._repo.log(s, tenant_id, d.chat_id, d.kind, "failed")
        log.warning("telegram_send_failed", job_id=str(job.id), error=error)
        return Outcome(job.id, "failed", note=error)
