"""Offline-only columns of the inventory documents for ``/sync/push`` (19 §13–§14; caller's txn, RLS)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlInventorySyncRepository:
    async def tag_transfer(
        self,
        s: AsyncSession,
        transfer_id: UUID,
        client_event_id: UUID,
        device_id: UUID,
        temp_number: str | None,
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.transfers SET client_event_id = :cid, device_id = :d, temp_number = :temp "
                "WHERE id = :id"
            ),
            {"id": transfer_id, "cid": client_event_id, "d": device_id, "temp": temp_number},
        )

    async def claim_count(self, s: AsyncSession, count_id: UUID, device_id: UUID) -> UUID | None:
        """``stock_counts.device_id`` — the first offline device owns the count (19 §14, MVP)."""
        await s.execute(
            text("UPDATE app.stock_counts SET device_id = :d WHERE id = :id AND device_id IS NULL"),
            {"id": count_id, "d": device_id},
        )
        owner: UUID | None = (
            await s.execute(text("SELECT device_id FROM app.stock_counts WHERE id = :id"), {"id": count_id})
        ).scalar()
        return owner

    async def temp_number_taken(self, s: AsyncSession, device_id: UUID, temp_number: str) -> bool:
        found = await s.execute(
            text("SELECT 1 FROM app.transfers WHERE device_id = :d AND temp_number = :t"),
            {"d": device_id, "t": temp_number},
        )
        return found.first() is not None
