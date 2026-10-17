"""Ports of the imports application layer (``imports.infrastructure`` implements, ``wiring`` composes)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import BranchScope


@dataclass(frozen=True, slots=True)
class ImportJob:
    id: UUID
    kind: str
    attachment_id: UUID
    status: str
    total_rows: int
    ok_rows: int
    errors: list[dict[str, Any]]
    result: dict[str, Any]
    created_by: UUID
    created_at: datetime
    s3_key: str
    content_type: str


class FileStoragePort(Protocol):
    """Object storage behind ``attachments.s3_key`` (23 §7 ``StoragePort``)."""

    async def put(self, key: str, content: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...


class JobEnqueuer(Protocol):
    """``JobQueue`` (core) enqueue with SAQ job options (timeout)."""

    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> None: ...


class ImportJobRepository(Protocol):
    async def insert_attachment(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def insert_job(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def get_job(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> ImportJob | None: ...
    async def set_status(self, s: AsyncSession, job_id: UUID, status: str) -> None: ...
    async def save_validation(
        self,
        s: AsyncSession,
        job_id: UUID,
        *,
        status: str,
        total_rows: int,
        ok_rows: int,
        errors: Sequence[Mapping[str, Any]],
    ) -> None: ...
    async def save_commit(
        self,
        s: AsyncSession,
        job_id: UUID,
        *,
        status: str,
        ok_rows: int,
        errors: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any],
    ) -> None: ...


class CatalogImportPort(Protocol):
    """What the products import needs from the catalog module (composed in ``imports.wiring``)."""

    async def unit_codes(self, s: AsyncSession) -> set[str]: ...
    async def taken_barcodes(self, s: AsyncSession, barcodes: Sequence[str]) -> set[str]: ...
    async def marking_group_exists(self, s: AsyncSession, code: str) -> bool: ...
    async def active_categories_by_name(self, s: AsyncSession) -> dict[str, UUID]: ...
    async def insert_category(
        self, s: AsyncSession, tenant_id: UUID, category_id: UUID, name: str, parent_id: UUID | None
    ) -> None: ...
    async def insert_products(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def insert_barcodes(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> int: ...
    async def queue_labels(
        self, s: AsyncSession, tenant_id: UUID, product_ids: Sequence[UUID], reason: str
    ) -> None: ...


class OpeningStockPort(Protocol):
    """Inventory: the ``opening_stock`` import posts ONE ``stock_openings`` document (19 §6, 13 §2.21)."""

    async def barcode_products(self, s: AsyncSession, barcodes: Sequence[str]) -> dict[str, UUID]: ...
    async def check_scope(self, s: AsyncSession, scope: BranchScope) -> UUID | None:
        """``403 BRANCH_SCOPE_DENIED`` unless ``scope`` covers the branch the opening is posted to."""
        ...

    async def post_opening(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        lines: Sequence[tuple[UUID, Decimal, Decimal, date | None]],
        comment: str,
        scope: BranchScope,
    ) -> UUID: ...


class InitialPricesPort(Protocol):
    """Pricing: post the imported products' first prices as one ``price_changes`` document."""

    async def post_initial_prices(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        prices: Sequence[tuple[UUID, Decimal]],
        comment: str,
    ) -> UUID | None: ...
