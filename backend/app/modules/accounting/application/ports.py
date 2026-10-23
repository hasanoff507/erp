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


# --- B5: ledger adjustments, period closings (13 §2.23, §5.1; 20 #10, #14–#16) ---------------------
@dataclass(frozen=True, slots=True)
class AdjustmentRow:
    """One ``ledger_adjustments`` row."""

    id: UUID
    number: str | None
    branch_id: UUID
    doc_date: date
    status: str
    account_dt: str
    account_kt: str
    amount: Decimal
    analytics: dict[str, Any]
    correction_of_period: date | None
    comment: str
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: UUID | None
    cancel_reason: str | None


@dataclass(frozen=True, slots=True)
class AdjustmentFilter:
    doc_date_gte: date | None = None
    doc_date_lte: date | None = None
    status: str | None = None
    branch_ids: tuple[UUID, ...] | None = None  # None = every branch


class AdjustmentRepository(Protocol):
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def get(
        self, s: AsyncSession, adjustment_id: UUID, *, lock: bool = False
    ) -> AdjustmentRow | None: ...
    async def mark_cancelled(
        self, s: AsyncSession, adjustment_id: UUID, user_id: UUID, reason: str
    ) -> None: ...
    async def page(
        self, s: AsyncSession, flt: AdjustmentFilter, after: tuple[date, UUID] | None, limit: int
    ) -> list[AdjustmentRow]: ...
    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool: ...
    async def counterparty_exists(self, s: AsyncSession, counterparty_id: UUID) -> bool: ...
    async def go_live_date(self, s: AsyncSession) -> date | None: ...
    async def advance_6310(self, s: AsyncSession, counterparty_id: UUID) -> Decimal: ...


class DebtRegisterPort(Protocol):
    """``app.modules.debts.wiring.debt_register()`` (13 §2.14: a 4010/6010 line moves ``debt_moves`` too)."""

    async def lock(self, s: AsyncSession, tenant_id: UUID, keys: Any) -> Mapping[Any, Decimal]: ...
    async def post(self, s: AsyncSession, tenant_id: UUID, moves: Sequence[Any]) -> Sequence[Any]: ...
    async def reverse(
        self, s: AsyncSession, tenant_id: UUID, doc_type: str, doc_id: UUID
    ) -> Sequence[Any]: ...


@dataclass(frozen=True, slots=True)
class ClosingRow:
    period: date
    closed_at: datetime
    closed_by: UUID


@dataclass(frozen=True, slots=True)
class DeviceOutbox:
    device_id: UUID
    cash_register_name: str | None
    outbox_pending_count: int
    outbox_oldest_pending_at: datetime | None


class ClosingRepository(Protocol):
    async def lock_exclusive(self, s: AsyncSession) -> bool: ...
    async def last_closed(self, s: AsyncSession) -> date | None: ...
    async def first_activity(self, s: AsyncSession) -> date | None: ...
    async def insert(self, s: AsyncSession, tenant_id: UUID, period: date, user_id: UUID) -> ClosingRow: ...
    async def page(self, s: AsyncSession, after: date | None, limit: int) -> list[ClosingRow]: ...
    async def pending_recost(self, s: AsyncSession, end: date) -> int: ...
    async def unsynced_devices(self, s: AsyncSession, bound: datetime) -> list[DeviceOutbox]: ...
    async def devices_not_synced(self, s: AsyncSession, bound: datetime) -> int: ...
    async def opening_0000_balance(self, s: AsyncSession) -> Decimal: ...
    async def open_shifts(self, s: AsyncSession, bound: datetime) -> int: ...
    async def drafts_in_period(self, s: AsyncSession, start: date, end: date) -> int: ...
    async def ledger_stock_mismatches(self, s: AsyncSession) -> list[tuple[str, Decimal, Decimal]]: ...


class FiscalReadinessReader(Protocol):
    """b5-fiscal ``fiscal_readiness`` (PLAN contract 4): receipts of the period not fiscalised yet."""

    async def __call__(self, s: AsyncSession, tenant_id: UUID, period: date) -> int: ...


@dataclass(frozen=True, slots=True)
class TaxReadiness:
    """``vat`` module answer for a period (13 §5.1, §2.26; B5-T16)."""

    missing: bool
    stale: Sequence[tuple[UUID, str, UUID | None, Decimal, Decimal]]  # id, kind, branch, amount, current


class TaxReadinessReader(Protocol):
    async def __call__(self, s: AsyncSession, tenant_id: UUID, period: date) -> TaxReadiness: ...
