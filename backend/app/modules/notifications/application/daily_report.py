"""Daily report to Telegram (US-M18-02, QT-M18-02; 07 BO-20 "Kunlik hisobot").

Runs per tenant from the cron (every 5 minutes): for every eligible recipient (active link and membership,
``telegram.link`` + ``reports.finance.view``, ``daily_report`` enabled) whose configured time (default 21:00
Asia/Tashkent) has come today and who has no report of today yet, the day's summary (contract 5,
``reports.daily_summary()``, the recipient's branch scope — sales up to now even if shifts are still open) is
snapshotted into one delivery job ``outbox_jobs(kind='telegram')`` with ``idempotency_key =
"daily_report:<user_id>:<day>"`` (21 §11: once per chat and period). The sender delivers it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.modules.notifications.application.ports import DailySummarySource, NotificationRepository
from app.modules.notifications.domain.policy import (
    AUDIENCE,
    DAILY_REPORT,
    DEFAULT_DAILY_TIME,
    daily_report_due,
    local_now,
)

log = structlog.get_logger(__name__)


def daily_report_key(user_id: UUID, day: str) -> str:
    return f"{DAILY_REPORT}:{user_id}:{day}"


class DailyReportService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: NotificationRepository,
        source: DailySummarySource | None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._source = source

    async def run(self, tenant_id: UUID, now: datetime | None = None) -> dict[str, Any]:
        if self._source is None:
            log.info("daily_report_skipped", reason="reports module not available")
            return {"queued": 0, "skipped": "no_summary_source"}
        moment = local_now(now)
        day = moment.date()
        queued = 0
        cache: dict[tuple[UUID, ...], Mapping[str, Any]] = {}
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            for recipient in await self._repo.recipients(s, DAILY_REPORT, AUDIENCE[DAILY_REPORT]):
                if not daily_report_due(moment, recipient.report_time or DEFAULT_DAILY_TIME):
                    continue
                key = daily_report_key(recipient.user_id, day.isoformat())
                if await self._repo.job_exists(s, key):
                    continue
                scope = tuple(sorted(recipient.branch_ids, key=lambda b: b.int))
                if scope not in cache:
                    cache[scope] = await self._source.for_day(s, tenant_id, day, list(scope) or None)
                payload = {
                    "event": DAILY_REPORT,
                    "deliver_to": str(recipient.user_id),
                    "day": day.isoformat(),
                    "report": cache[scope],
                }
                queued += int(await self._repo.enqueue(s, tenant_id, payload, key))
        return {"queued": queued, "day": day.isoformat()}
