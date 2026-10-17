"""Ports of the sales module (repository rows; SQL in ``infrastructure/sales_sql.py``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProductInfo:
    id: UUID
    name: str
    name_ru: str | None
    unit_code: str
    is_fractional: bool
    is_marked: bool
    vat_rate: Decimal | None
    vat_exemption_code: str | None
    mxik_code: str | None
    package_code: str | None
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class CustomerInfo:
    id: UUID
    name: str
    kind: str
    is_customer: bool
    credit_limit: Decimal | None
    standing_discount_pct: Decimal | None
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class TenantPolicy:
    settings: Mapping[str, Any]
    legal_form: str
    vat_payer: bool


@dataclass(frozen=True, slots=True)
class DiscountRule:
    id: UUID
    scope: str
    target_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    valid_from: date
    valid_to: date | None
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class Checkout:
    checkout_ref: UUID
    provider: str
    status: str
    amount: Decimal
    provider_tx_id: str | None
    cash_register_id: UUID


@dataclass(frozen=True, slots=True)
class SaleFilter:
    branch_ids: tuple[UUID, ...] | None = None
    number: str | None = None
    fiscal_receipt_seq: int | None = None
    shift_id: UUID | None = None
    counterparty_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None


class SalesRepository(Protocol):
    async def products(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, ProductInfo]: ...

    async def prices_at(
        self, s: AsyncSession, ids: Sequence[UUID], branch_id: UUID, at: datetime
    ) -> dict[UUID, Decimal]: ...

    async def sale_warehouse(self, s: AsyncSession, branch_id: UUID) -> UUID | None: ...

    async def tenant_policy(self, s: AsyncSession, on: date) -> TenantPolicy: ...

    async def customer(self, s: AsyncSession, counterparty_id: UUID) -> CustomerInfo | None: ...

    async def discount_rule(self, s: AsyncSession, rule_id: UUID) -> DiscountRule | None: ...

    async def product_category(self, s: AsyncSession, product_id: UUID) -> UUID | None: ...

    async def sale_exists(self, s: AsyncSession, sale_id: UUID) -> bool: ...

    async def temp_number_taken(
        self, s: AsyncSession, table: str, device_id: UUID, temp_number: str
    ) -> bool: ...

    async def checkout(self, s: AsyncSession, checkout_ref: UUID) -> Checkout | None: ...

    async def consume_checkout(self, s: AsyncSession, checkout_ref: UUID) -> None: ...

    async def take_marking_codes(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        codes: Sequence[tuple[str, UUID]],
        doc_id: UUID,
        *,
        keep_free: bool = False,
    ) -> list[str]:
        """Register the codes ``pending_verification`` for ``doc_id``; returns the codes already taken
        (``sold`` / ``pending_verification`` — 18 §4.2). Taken codes are never overwritten; with
        ``keep_free=False`` nothing is written when one is taken, with ``True`` the free ones still are."""
        ...

    async def insert_sale(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def insert_lines(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...

    async def insert_payments(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...

    async def insert_cash_moves(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...

    async def open_shift_of(self, s: AsyncSession, cash_register_id: UUID) -> UUID | None: ...

    async def fiscal_receipt_ref(self, s: AsyncSession, receipt_id: UUID) -> tuple[UUID | None, str] | None:
        """``(sale_id, kind)`` of a fiscal receipt."""
        ...

    async def page(
        self, s: AsyncSession, flt: SaleFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[dict[str, Any]]: ...

    async def get(self, s: AsyncSession, sale_id: UUID) -> dict[str, Any] | None: ...
