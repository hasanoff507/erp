"""Ports of the accounting application layer (implemented in ``accounting.infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class StoredEntry:
    """One ``ledger_entries`` row."""

    id: UUID
    entry_date: date
    branch_id: UUID | None
    account_dt: str
    account_kt: str
    amount: Decimal
    doc_type: str
    doc_id: UUID
    analytics: dict[str, Any]
    reversal_of_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredVat:
    """One ``vat_moves`` row."""

    id: UUID
    period: date
    kind: str
    base_amount: Decimal
    vat_amount: Decimal
    doc_type: str
    doc_id: UUID
    einvoice_id: UUID | None
    reversal_of_id: UUID | None


@dataclass(frozen=True, slots=True)
class JournalFilter:
    entry_date_gte: date | None = None
    entry_date_lte: date | None = None
    account_dt: str | None = None
    account_kt: str | None = None
    doc_type: str | None = None
    doc_id: UUID | None = None
    branch_ids: tuple[UUID, ...] | None = None  # None = every branch (and branch-less rows)


class LedgerRepository(Protocol):
    async def last_closed_period(self, s: AsyncSession) -> date | None: ...
    async def insert_entries(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...
    async def insert_vat(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...
    async def doc_entries(
        self,
        s: AsyncSession,
        doc_type: str,
        doc_id: UUID,
        *,
        analytics: Mapping[str, Any] | None = None,
        live_only: bool = False,
    ) -> list[StoredEntry]: ...
    async def live_vat(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> list[StoredVat]: ...
    async def journal(
        self, s: AsyncSession, flt: JournalFilter, after: tuple[date, UUID] | None, limit: int
    ) -> list[StoredEntry]: ...
    async def doc_numbers(self, s: AsyncSession, refs: Mapping[str, Sequence[UUID]]) -> dict[UUID, str]: ...
