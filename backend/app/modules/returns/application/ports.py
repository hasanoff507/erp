"""Ports of the returns module (SQL in ``infrastructure/returns_sql.py``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SoldLine:
    id: UUID
    product_id: UUID
    qty: Decimal
    price: Decimal
    vat_rate: Decimal
    vat_exemption_code: str | None
    line_total: Decimal
    marking_code: str | None
    returned_qty: Decimal  # posted returns so far
    refunded: Decimal  # Σ return_lines.line_total so far
    vat_amount: Decimal  # sale_lines.vat_amount
    refunded_vat: Decimal  # Σ return_lines.vat_amount so far


@dataclass(frozen=True, slots=True)
class SoldDoc:
    id: UUID
    branch_id: UUID
    status: str
    counterparty_id: UUID | None
    lines: Mapping[UUID, SoldLine]
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FreeLot:
    lot_id: UUID
    room: Decimal  # qty_in − qty_left
    unit_cost: Decimal


@dataclass(frozen=True, slots=True)
class ReturnFilter:
    branch_ids: tuple[UUID, ...] | None = None
    sale_id: UUID | None = None
    shift_id: UUID | None = None
    without_receipt: bool | None = None
    date_from: date | None = None
    date_to: date | None = None


class ReturnsRepository(Protocol):
    async def return_exists(self, s: AsyncSession, return_id: UUID) -> bool: ...

    async def sale_for_return(self, s: AsyncSession, sale_id: UUID) -> SoldDoc | None:
        """The sale with its lines locked ``FOR UPDATE`` (two returns of one line serialise)."""
        ...

    async def open_debt_of_sale(self, s: AsyncSession, sale_id: UUID) -> Decimal: ...

    async def fiscal_room(self, s: AsyncSession, sale_id: UUID) -> Decimal:
        """``fiscalized_amount(sale) − already_fiscally_refunded(sale)`` (18 §7.1)."""
        ...

    async def lot_expiry(self, s: AsyncSession, lot_ids: Sequence[UUID]) -> dict[UUID, date | None]: ...

    async def free_lots(self, s: AsyncSession, warehouse_id: UUID, product_id: UUID) -> list[FreeLot]: ...

    async def approver_of(self, s: AsyncSession, doc_approval_id: UUID) -> UUID | None: ...

    async def mark_codes_returned(self, s: AsyncSession, codes: Sequence[str], return_id: UUID) -> None: ...

    async def insert_return(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def insert_lines(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...

    async def insert_write_off(
        self, s: AsyncSession, header: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None: ...

    async def page(
        self, s: AsyncSession, flt: ReturnFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[dict[str, Any]]: ...

    async def get(self, s: AsyncSession, return_id: UUID) -> dict[str, Any] | None: ...
