"""``card_orphan_sweep`` (23 §4, 16 §2.1, QT-M01-29): an approved ``purchase`` that no document claimed within
24 h → one ``sync_exceptions(kind='card_orphan_transaction')`` row for manual review (BO-14). Never an
automatic
``void`` — the money was taken, only a person decides."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.core.money import money_str
from app.modules.integrations.card_terminal.application.ports import CardRepository
from app.modules.integrations.card_terminal.domain.model import ORPHAN_AFTER_HOURS

BATCH = 500


class OrphanSweep:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: CardRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def run(self, tenant_id: UUID, *, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(UTC)) - timedelta(hours=ORPHAN_AFTER_HOURS)
        reported = 0
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            for row in await self._repo.orphans(s, cutoff, BATCH):
                if await self._repo.orphan_reported(s, row.id):
                    continue
                await self._repo.insert_sync_exception(
                    s, kind="card_orphan_transaction", device_id=row.device_id,
                    client_event_id=row.client_event_id,
                    doc_type="card_terminal_transactions", doc_id=row.id,
                    details={"attempt_id": str(row.id), "card_terminal_id": str(row.card_terminal_id),
                             "branch_id": str(row.branch_id), "amount": money_str(row.amount), "rrn": row.rrn,
                             "approved_at": row.created_at.isoformat()},
                )  # fmt: skip
                reported += 1
        return reported
