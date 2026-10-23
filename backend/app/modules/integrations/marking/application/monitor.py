"""Acceptance deadline monitor (QT-NFR-07; 21 §4 SLA, 19 §8; qaror #63).

Cron (every 15 min, tenant fan-out) over the open ``marking_accept`` jobs: 24 h before ``due_at`` →
M18 ``marking_acceptance_due`` (stage ``due_soon``), at/after ``due_at`` → stage ``overdue`` (once per
stage and receipt — the event dedupe key). The receipt is never blocked (19 §8). ``now`` is injected so the
deadline scenarios run on an explicit clock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.modules.integrations.marking.application.hooks import DUE, EventSink, iso, parse_at
from app.modules.integrations.marking.application.repository import MarkingRepository
from app.modules.integrations.marking.domain import deadline, rules


@dataclass
class MonitorReport:
    checked: int = 0
    events: list[tuple[str, str]] = field(default_factory=list)  # (receipt_id, stage)

    def as_json(self) -> dict[str, Any]:
        return {"checked": self.checked, "events": [list(e) for e in self.events]}


class AcceptanceMonitor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: MarkingRepository,
        events: EventSink,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._events = events
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(self, tenant_id: UUID, now: datetime | None = None) -> MonitorReport:
        at = now or self._clock()
        report = MonitorReport()
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            for job in await self._repo.open_jobs(s, rules.ACCEPT):
                if job.payload.get("cancelled"):
                    continue
                due = parse_at(job.payload.get("due_at"))
                receipt = str(job.payload.get("receipt_id") or "")
                if due is None or not receipt:
                    continue
                report.checked += 1
                current = deadline.stage(due, at)
                if current == "pending":
                    continue
                info = await self._repo.receipt_info(s, UUID(receipt)) or {}
                payload = {
                    "stage": current,
                    "receipt_id": receipt,
                    "number": info.get("number"),
                    "branch_id": str(info["branch_id"]) if info.get("branch_id") else None,
                    "counterparty_name": info.get("supplier_name"),
                    "due_date": iso(due),
                    "deadline_kind": job.payload.get("deadline_kind"),
                    "codes": len(job.payload.get("codes") or []),
                    "job_status": job.status,
                }
                if await self._events.record_event(s, tenant_id, DUE, payload, f"{DUE}:{receipt}:{current}"):
                    report.events.append((receipt, current))
        return report
