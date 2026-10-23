"""Ports of the supplier-payment service (``purchasing.infrastructure.supplier_payments_sql``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchasing.domain.supplier_payments import OpenDoc


@dataclass(frozen=True, slots=True)
class ShiftRef:
    id: UUID
    branch_id: UUID
    cash_register_id: UUID
    status: str


@dataclass(frozen=True, slots=True)
class AllocationRow:
    target_doc_type: str
    target_doc_id: UUID
    target_number: str | None
    target_doc_date: date | None
    target_einvoice_id: UUID | None
    amount: Decimal


@dataclass(frozen=True, slots=True)
class PaymentRow:
    id: UUID
    number: str | None
    status: str
    doc_date: date
    branch_id: UUID
    supplier_id: UUID
    supplier_name: str | None
    supplier_stir: str | None
    method: str
    amount: Decimal
    cash_register_id: UUID | None
    shift_id: UUID | None
    comment: str | None
    created_by: UUID
    created_by_name: str | None
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    allocations: tuple[AllocationRow, ...] = ()
    vat_unlocked: tuple[tuple[UUID | None, Decimal], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PaymentFilter:
    branch_ids: tuple[UUID, ...] | None
    supplier_id: UUID | None = None
    status: str | None = None
    method: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class SupplierPaymentRepository(Protocol):
    async def shift(self, s: AsyncSession, shift_id: UUID) -> ShiftRef | None: ...  # FOR SHARE
    async def default_branch(self, s: AsyncSession) -> UUID: ...
    async def overpay_policy(self, s: AsyncSession) -> str: ...
    async def advance_balance(self, s: AsyncSession, supplier_id: UUID) -> Decimal: ...  # 4310 debit
    async def open_docs(self, s: AsyncSession, supplier_id: UUID) -> list[OpenDoc]: ...
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], allocations: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def get(self, s: AsyncSession, payment_id: UUID, *, lock: bool = False) -> PaymentRow | None: ...
    async def list_page(
        self, s: AsyncSession, flt: PaymentFilter, after: UUID | None, limit: int
    ) -> list[PaymentRow]: ...
    async def mark_cancelled(self, s: AsyncSession, payment_id: UUID, user_id: UUID, reason: str) -> None: ...
    async def insert_cash_move(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def live_cash_moves(
        self, s: AsyncSession, payment_id: UUID
    ) -> list[tuple[UUID, Decimal, UUID | None, UUID | None, str]]: ...
