"""Ports the catalog application layer depends on (23 §1: implemented in ``infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import BranchScope
from app.modules.catalog.domain.barcodes import BarcodeKind
from app.modules.catalog.domain.mxik import MxikCandidate
from app.modules.catalog.domain.products import Barcode, Category, Product, Unit


@dataclass(frozen=True, slots=True)
class ProductFilter:
    search: str | None = None
    category_id: UUID | None = None
    archived: bool = False
    is_weighed: bool | None = None
    low_stock: bool = False
    # low_stock scope: warehouses of these branches; None = every branch
    branch_ids: tuple[UUID, ...] | None = None


class CatalogRepository(Protocol):
    # --- reference data ---------------------------------------------------------------------------
    async def list_units(self, s: AsyncSession) -> list[Unit]: ...
    async def unit_codes(self, s: AsyncSession) -> set[str]: ...
    async def marking_group_exists(self, s: AsyncSession, code: str) -> bool: ...
    async def vat_payer(self, s: AsyncSession, on: date) -> bool: ...

    # --- categories -------------------------------------------------------------------------------
    async def get_category(
        self, s: AsyncSession, category_id: UUID, *, lock: bool = False
    ) -> Category | None: ...
    async def list_categories(
        self, s: AsyncSession, parent_id: UUID | None, offset: int, limit: int
    ) -> tuple[list[Category], int]: ...
    async def insert_category(
        self, s: AsyncSession, tenant_id: UUID, category_id: UUID, name: str, parent_id: UUID | None
    ) -> None: ...
    async def update_category(
        self, s: AsyncSession, category_id: UUID, version: int, values: Mapping[str, Any]
    ) -> bool: ...
    async def category_ancestors(self, s: AsyncSession, category_id: UUID) -> list[UUID]: ...
    async def set_category_archived(self, s: AsyncSession, category_id: UUID) -> None: ...
    async def category_has_active_products(self, s: AsyncSession, category_id: UUID) -> bool: ...
    async def category_has_active_children(self, s: AsyncSession, category_id: UUID) -> bool: ...
    async def active_categories_by_name(self, s: AsyncSession) -> dict[str, UUID]: ...

    # --- products ---------------------------------------------------------------------------------
    async def get_product(
        self, s: AsyncSession, product_id: UUID, *, lock: bool = False
    ) -> Product | None: ...
    async def list_products(
        self, s: AsyncSession, flt: ProductFilter, offset: int, limit: int
    ) -> tuple[list[Product], int]: ...
    async def insert_products(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def update_product(
        self, s: AsyncSession, product_id: UUID, version: int, values: Mapping[str, Any]
    ) -> bool: ...
    async def set_product_archived(self, s: AsyncSession, product_id: UUID, archived: bool) -> None: ...
    async def existing_product_ids(self, s: AsyncSession, product_ids: Sequence[UUID]) -> set[UUID]: ...

    # --- barcodes ---------------------------------------------------------------------------------
    async def list_barcodes(self, s: AsyncSession, product_id: UUID) -> list[Barcode]: ...
    async def insert_barcode(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        product_id: UUID,
        barcode: str,
        kind: BarcodeKind,
        units_per_barcode: str,
    ) -> Barcode | None:
        """``None`` when the barcode already exists in the tenant (UNIQUE (tenant_id, barcode))."""
        ...

    async def insert_barcodes(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> int: ...
    async def taken_barcodes(self, s: AsyncSession, barcodes: Sequence[str]) -> set[str]: ...
    async def delete_barcode(self, s: AsyncSession, product_id: UUID, barcode_id: UUID) -> Barcode | None: ...
    async def lock_internal_seq(self, s: AsyncSession, tenant_id: UUID) -> int: ...
    async def set_internal_seq(self, s: AsyncSession, tenant_id: UUID, next_value: int) -> None: ...

    # --- label queue (US-M09-04) ------------------------------------------------------------------
    async def queue_labels(
        self, s: AsyncSession, tenant_id: UUID, product_ids: Sequence[UUID], reason: str
    ) -> None: ...


class CurrentPricesPort(Protocol):
    """Pricing: effective retail price per product for the request's branch (19 §1/§4), one query.

    Products without an effective price are absent from the result.
    """

    async def __call__(
        self, s: AsyncSession, product_ids: Sequence[UUID], scope: BranchScope
    ) -> Mapping[UUID, Decimal]: ...


class CurrentCostsPort(Protocol):
    """Inventory: unit cost per product in the request branch's warehouse (19 §1 ``current_cost``), one
    query; products without a known cost are absent."""

    async def __call__(
        self, s: AsyncSession, product_ids: Sequence[UUID], scope: BranchScope
    ) -> Mapping[UUID, Decimal]: ...


class MxikCatalogPort(Protocol):
    """tasnif.soliq.uz classifier (21 §7 ``ClassifierAdapter``). Raises ``MxikUnavailableError``."""

    async def search(self, query: str, limit: int) -> list[MxikCandidate]: ...
    async def get(self, code: str) -> MxikCandidate | None: ...


class MxikCachePort(Protocol):
    """Platform-wide MXIK cache (no tenant data, 15 §1.5): ``(payload, fresh)`` or ``None``."""

    async def get(self, key: str) -> tuple[Any, bool] | None: ...
    async def put(self, key: str, payload: Any) -> None: ...


class MxikUnavailableError(Exception):
    """The classifier did not answer (network error, timeout, 5xx)."""
