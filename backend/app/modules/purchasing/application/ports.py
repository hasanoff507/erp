"""Ports of the purchasing application layer (implemented in ``purchasing.infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchasing.domain.purchase_orders import PurchaseOrder
from app.modules.purchasing.domain.receipts import GoodsReceipt, Regime
from app.modules.purchasing.domain.supplier_returns import SupplierReturn


@dataclass(frozen=True, slots=True)
class PoFilter:
    branch_ids: tuple[UUID, ...] | None  # None = every branch
    supplier_id: UUID | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    search: str | None = None


@dataclass(frozen=True, slots=True)
class WarehouseRef:
    id: UUID
    branch_id: UUID
    archived: bool


class PurchaseOrderRepository(Protocol):
    async def get(self, s: AsyncSession, po_id: UUID, *, lock: bool = False) -> PurchaseOrder | None: ...
    async def list_page(
        self, s: AsyncSession, flt: PoFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[PurchaseOrder]: ...
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def update(self, s: AsyncSession, po_id: UUID, values: Mapping[str, Any]) -> None: ...
    async def replace_lines(
        self, s: AsyncSession, tenant_id: UUID, po_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def received_qty(self, s: AsyncSession, po_id: UUID) -> dict[UUID, Decimal]: ...
    async def warehouse(self, s: AsyncSession, warehouse_id: UUID) -> WarehouseRef | None: ...
    async def product_archived_flags(
        self, s: AsyncSession, product_ids: Sequence[UUID]
    ) -> dict[UUID, bool]: ...


# --- goods receipts / supplier returns (19 §8, §12) -------------------------------------------------
@dataclass(frozen=True, slots=True)
class DocFilter:
    """List filter of goods receipts / supplier returns."""

    branch_ids: tuple[UUID, ...] | None  # None = every branch
    supplier_id: UUID | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    po_id: UUID | None = None
    receipt_id: UUID | None = None
    search: str | None = None


@dataclass(frozen=True, slots=True)
class ProductRef:
    id: UUID
    archived: bool
    vat_rate: Decimal | None
    vat_exemption_code: str | None
    is_marked: bool
    marking_group_code: str | None


@dataclass(frozen=True, slots=True)
class ReturnedSoFar:
    """Posted supplier returns of one receipt line (other than the document being posted)."""

    qty: Decimal
    vat: Decimal


@dataclass(frozen=True, slots=True)
class EInvoiceSource:
    """An incoming e-invoice for ``from-einvoice`` (19 §8)."""

    id: UUID
    direction: str
    status: str
    counterparty_id: UUID
    doc_date: date | None
    payload: Mapping[str, Any]
    ettn_ref: str | None
    active_receipt_id: UUID | None


class MarkingHooksPort(Protocol):
    """Contract ``marking.md`` (b5-marking) — called inside the posting transaction."""

    async def on_goods_receipt_posted(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        receipt_id: UUID,
        *,
        doc_date: date,
        shipped_on: date | None = None,
        actor_user_id: UUID | None = None,
    ) -> UUID | None: ...
    async def on_goods_receipt_cancelled(
        self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID, *, actor_user_id: UUID | None = None
    ) -> None: ...
    async def acceptance(
        self, s: AsyncSession, receipt_id: UUID, *, now: datetime | None = None
    ) -> dict[str, Any] | None: ...
    async def on_supplier_return_posted(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        return_id: UUID,
        *,
        lines: Sequence[Any],
        actor_user_id: UUID | None = None,
    ) -> UUID | None: ...
    async def on_codes_document_cancelled(
        self, s: AsyncSession, tenant_id: UUID, doc_id: UUID, *, actor_user_id: UUID | None = None
    ) -> None: ...


class GoodsReceiptRepository(Protocol):
    async def get(self, s: AsyncSession, receipt_id: UUID, *, lock: bool = False) -> GoodsReceipt | None: ...
    async def list_page(
        self, s: AsyncSession, flt: DocFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[GoodsReceipt]: ...
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def update(self, s: AsyncSession, receipt_id: UUID, values: Mapping[str, Any]) -> None: ...
    async def replace_lines(
        self, s: AsyncSession, receipt_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def products(self, s: AsyncSession, product_ids: Sequence[UUID]) -> dict[UUID, ProductRef]: ...
    async def regime_on(self, s: AsyncSession, day: date) -> Regime: ...
    async def advance_balance(self, s: AsyncSession, supplier_id: UUID) -> Decimal: ...
    async def poa_number(self, s: AsyncSession, poa_id: UUID) -> tuple[bool, str | None]: ...
    async def einvoice_source(self, s: AsyncSession, einvoice_id: UUID) -> EInvoiceSource | None: ...
    async def product_by_code(
        self, s: AsyncSession, *, barcode: str | None, mxik: str | None
    ) -> UUID | None: ...
    async def shipped_on(self, s: AsyncSession, receipt_id: UUID) -> date | None: ...
    async def foreign_codes(self, s: AsyncSession, receipt_id: UUID, codes: Sequence[str]) -> list[str]: ...
    async def replace_codes(
        self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> list[str]: ...  # the codes another document already holds (not inserted)
    async def set_codes_status(self, s: AsyncSession, receipt_id: UUID, status: str) -> None: ...
    async def drop_codes(self, s: AsyncSession, receipt_id: UUID) -> None: ...
    async def paying_supplier_payments(self, s: AsyncSession, receipt_id: UUID) -> list[UUID]: ...


class SupplierReturnRepository(Protocol):
    async def get(self, s: AsyncSession, return_id: UUID, *, lock: bool = False) -> SupplierReturn | None: ...
    async def list_page(
        self, s: AsyncSession, flt: DocFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[SupplierReturn]: ...
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def returned_so_far(
        self, s: AsyncSession, receipt_line_ids: Sequence[UUID], exclude_id: UUID | None
    ) -> dict[UUID, ReturnedSoFar]: ...
    async def set_line_vat(self, s: AsyncSession, line_id: UUID, vat_amount: Decimal) -> None: ...
    async def update(self, s: AsyncSession, return_id: UUID, values: Mapping[str, Any]) -> None: ...
