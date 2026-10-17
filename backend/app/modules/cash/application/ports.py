"""Ports of the cash module (implemented in ``cash.infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.domain.approvals import UserGrant
from app.modules.cash.domain.shifts import ShiftTotals


@dataclass(frozen=True, slots=True)
class ShiftRow:
    id: UUID
    branch_id: UUID
    cash_register_id: UUID
    device_id: UUID
    shift_no: int
    status: str
    opened_by: UUID
    opened_at: datetime
    closed_by: UUID | None
    closed_at: datetime | None
    opening_cash: Decimal
    expected_cash: Decimal | None
    counted_cash: Decimal | None
    variance: Decimal | None
    variance_note: str | None
    counted_card_total: Decimal | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class RegisterRow:
    id: UUID
    branch_id: UUID
    archived: bool


@dataclass(frozen=True, slots=True)
class MovementRow:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    cash_register_id: UUID
    shift_id: UUID
    direction: str
    amount: Decimal
    reason: str
    account: str | None
    counterparty_id: UUID | None
    employee_id: UUID | None
    comment: str | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    device_id: UUID | None


@dataclass(frozen=True, slots=True)
class MovementFilter:
    branch_ids: tuple[UUID, ...] | None
    cash_register_id: UUID | None
    shift_id: UUID | None
    direction: str | None
    reason: str | None
    cursor: tuple[datetime, UUID] | None
    limit: int


@dataclass(frozen=True, slots=True)
class ShiftFilter:
    branch_ids: tuple[UUID, ...] | None
    cash_register_id: UUID | None
    status: str | None
    cursor: tuple[datetime, UUID] | None
    limit: int


class CashRepository(Protocol):
    # shifts
    async def get_shift(
        self, s: AsyncSession, shift_id: UUID, *, lock: str | None = None
    ) -> ShiftRow | None: ...

    async def open_shift_of_register(self, s: AsyncSession, register_id: UUID) -> UUID | None: ...

    async def shift_no_taken(self, s: AsyncSession, register_id: UUID, shift_no: int) -> bool: ...

    async def insert_shift(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def close_shift(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def cash_moves_total(self, s: AsyncSession, shift_id: UUID) -> Decimal: ...

    async def doc_cash_delta(
        self, s: AsyncSession, shift_id: UUID, doc_type: str, doc_id: UUID
    ) -> Decimal: ...

    async def adjust_expected(self, s: AsyncSession, shift_id: UUID, delta: Decimal, note: str) -> None: ...

    async def shift_totals(self, s: AsyncSession, shift_id: UUID) -> ShiftTotals: ...

    async def unresolved_card_attempts(self, s: AsyncSession, shift_id: UUID) -> int: ...

    async def list_shifts(self, s: AsyncSession, flt: ShiftFilter) -> list[ShiftRow]: ...

    async def shifts_between(
        self, s: AsyncSession, register_id: UUID, start: datetime | None, end: datetime | None
    ) -> list[ShiftRow]: ...

    async def z_fiscal(self, s: AsyncSession, shift_id: UUID) -> Mapping[str, Any] | None: ...

    # references
    async def get_register(self, s: AsyncSession, register_id: UUID) -> RegisterRow | None: ...

    async def tenant_legal(self, s: AsyncSession) -> tuple[str, str | None]: ...

    async def counterparty(self, s: AsyncSession, cp_id: UUID) -> tuple[bool, bool] | None: ...

    async def is_member(self, s: AsyncSession, user_id: UUID) -> bool: ...

    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant: ...

    async def last_closed_period(self, s: AsyncSession) -> date | None: ...

    # movements
    async def insert_movement(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def get_movement(
        self, s: AsyncSession, movement_id: UUID, *, lock: bool = False
    ) -> MovementRow | None: ...

    async def mark_posted(self, s: AsyncSession, movement_id: UUID, number: str) -> None: ...

    async def mark_cancelled(
        self, s: AsyncSession, movement_id: UUID, user_id: UUID, reason: str
    ) -> None: ...

    async def insert_cash_move(self, s: AsyncSession, row: Mapping[str, Any]) -> UUID: ...

    async def live_cash_moves(
        self, s: AsyncSession, doc_type: str, doc_id: UUID
    ) -> list[tuple[UUID, Decimal, UUID | None, UUID | None, str]]: ...

    async def list_movements(self, s: AsyncSession, flt: MovementFilter) -> list[MovementRow]: ...

    async def insert_approval_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def pending_request_of(self, s: AsyncSession, movement_id: UUID) -> UUID | None: ...


class FiscalZ(Protocol):
    """The slice of ``FiscalService`` (b3-sales) the Z-report uses."""

    async def record(self, s: AsyncSession, **kwargs: Any) -> Any: ...


Rows = Sequence[Mapping[str, Any]]
