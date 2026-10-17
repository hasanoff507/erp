"""Ports of the inventory application layer (implemented in ``inventory.infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.domain.costing import AvgState, LotView
from app.modules.inventory.domain.valuation import MethodRow

Key = tuple[UUID, UUID]  # (warehouse_id, product_id) — the stock lock unit (23 §2.1)


@dataclass(frozen=True, slots=True)
class Warehouse:
    id: UUID
    branch_id: UUID
    inventory_account: str
    archived: bool


@dataclass(frozen=True, slots=True)
class Balance:
    qty: Decimal
    value: Decimal


@dataclass(frozen=True, slots=True)
class MoveRow:
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    lot_id: UUID | None
    qty: Decimal
    cost_amount: Decimal
    doc_type: str
    doc_id: UUID
    line_id: UUID | None
    reversal_of_id: UUID | None
    moved_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LotRow:
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    source_doc_type: str
    source_doc_id: UUID
    source_line_id: UUID
    receipt_line_id: UUID | None
    received_at: datetime
    qty_in: Decimal
    qty_left: Decimal
    blocked_qty: Decimal
    unit_cost: Decimal
    expiry_date: date | None

    def view(self) -> LotView:
        return LotView(self.id, self.received_at, self.qty_left, self.blocked_qty, self.unit_cost)


@dataclass(frozen=True, slots=True)
class TenantStock:
    """``tenants`` bits the stock toolkit needs (``settings`` keys with defaults applied)."""

    negative_stock_policy: str  # 'allow' | 'block'
    expiry_warning_days: int
    low_stock_check_enabled: bool
    go_live_date: date | None
    valuation_state: dict[str, Any] | None


class StockRepository(Protocol):
    # --- locks & tenant -------------------------------------------------------------------------
    async def advisory_lock(self, s: AsyncSession, tenant_id: UUID, *, shared: bool) -> None: ...
    async def lock_balances(
        self, s: AsyncSession, tenant_id: UUID, keys: Sequence[Key]
    ) -> dict[Key, Balance]: ...
    async def tenant_stock(self, s: AsyncSession) -> TenantStock: ...
    async def save_valuation_state(
        self, s: AsyncSession, tenant_id: UUID, state: Mapping[str, Any]
    ) -> None: ...
    async def method_history(self, s: AsyncSession) -> list[MethodRow]: ...
    async def upsert_method(
        self, s: AsyncSession, tenant_id: UUID, valid_from: date, method: str, user_id: UUID
    ) -> None: ...
    async def has_moves_since(self, s: AsyncSession, since: datetime) -> bool: ...
    # --- reference data ---------------------------------------------------------------------------
    async def warehouse(self, s: AsyncSession, warehouse_id: UUID) -> Warehouse | None: ...
    async def branch_warehouse(self, s: AsyncSession, branch_id: UUID) -> Warehouse | None: ...
    async def warehouse_ids(self, s: AsyncSession, branch_ids: Sequence[UUID]) -> list[UUID]: ...
    async def default_branch_id(self, s: AsyncSession) -> UUID | None: ...
    async def product_ids(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, bool]: ...
    async def products_by_barcode(self, s: AsyncSession, barcodes: Sequence[str]) -> dict[str, UUID]: ...
    # --- registers --------------------------------------------------------------------------------
    async def open_lots(self, s: AsyncSession, key: Key) -> list[LotRow]: ...
    async def lot(self, s: AsyncSession, lot_id: UUID) -> LotRow | None: ...
    async def lots_of_source(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> list[LotRow]: ...
    async def insert_lot(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def set_lot(
        self, s: AsyncSession, lot_id: UUID, *, qty_left: Decimal, blocked_qty: Decimal
    ) -> None: ...
    async def insert_moves(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None: ...
    async def add_balance(self, s: AsyncSession, key: Key, qty: Decimal, value: Decimal) -> None: ...
    async def avg_state(self, s: AsyncSession, key: Key) -> AvgState | None: ...
    async def save_avg(self, s: AsyncSession, tenant_id: UUID, key: Key, state: AvgState) -> None: ...
    async def pending_moves(self, s: AsyncSession, key: Key) -> list[MoveRow]: ...
    async def doc_moves(
        self, s: AsyncSession, doc_type: str, doc_id: UUID, *, live_only: bool
    ) -> list[MoveRow]: ...
    async def line_cost(
        self, s: AsyncSession, key: Key, doc_type: str, doc_id: UUID, line_id: UUID | None
    ) -> Decimal: ...
    async def pending_history_lines(
        self, s: AsyncSession, key: Key, since: datetime
    ) -> list[tuple[str, UUID, UUID | None]]: ...
    async def live_issues_since(
        self, s: AsyncSession, key: Key, created_at: datetime, exclude_doc: tuple[str, UUID]
    ) -> bool: ...
    async def lot_value(self, s: AsyncSession, lot_id: UUID) -> tuple[Decimal, int]: ...
    async def last_lot_cost(self, s: AsyncSession, key: Key) -> Decimal | None: ...
    async def last_purchase_cost(
        self, s: AsyncSession, product_id: UUID, warehouse_id: UUID
    ) -> Decimal | None: ...
    async def insert_sync_exception(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def cost_unknown_template(
        self, s: AsyncSession, doc_type: str, doc_id: UUID, line_id: UUID | None, product_id: UUID
    ) -> dict[str, Any] | None: ...
    # --- valuation switch -------------------------------------------------------------------------
    async def all_balances(self, s: AsyncSession) -> dict[Key, Balance]: ...
    async def all_open_lots(self, s: AsyncSession) -> list[LotRow]: ...
    async def all_avg(self, s: AsyncSession) -> dict[Key, AvgState]: ...
    async def pending_estimates(self, s: AsyncSession) -> dict[Key, Decimal]: ...
    async def set_lot_unit_cost(self, s: AsyncSession, lot_id: UUID, unit_cost: Decimal) -> None: ...


@dataclass(frozen=True, slots=True)
class RecostJob:
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    from_date: date
    status: str
    reason_doc_type: str
    reason_doc_id: UUID
    attempts: int
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None


class RecostRepository(Protocol):
    async def upsert_queued(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        key: Key,
        from_date: date,
        reason_doc_type: str,
        reason_doc_id: UUID,
    ) -> UUID: ...
    async def get(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> RecostJob | None: ...
    async def queued_for(self, s: AsyncSession, key: Key) -> RecostJob | None: ...
    async def claim(self, s: AsyncSession, job_id: UUID) -> RecostJob | None: ...
    async def finish(self, s: AsyncSession, job_id: UUID, status: str, error: str | None) -> None: ...
    async def fail(self, s: AsyncSession, job_id: UUID, error: str) -> None: ...
    async def requeue(self, s: AsyncSession, job_id: UUID, from_date: date) -> None: ...
    async def queued_ids(self, s: AsyncSession, limit: int) -> list[UUID]: ...
    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_ids: Sequence[UUID] | None,
        product_id: UUID | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[RecostJob]: ...
    async def corrections(
        self, s: AsyncSession, job_id: UUID
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...


class JobEnqueuer(Protocol):
    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> None: ...


class EventRecorderPort(Protocol):
    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class TenantSettingsRow:
    """``tenants.settings`` + optimistic ``version`` (19 §17 ``/stock-settings``)."""

    settings: dict[str, Any]
    version: int


class StockSettingsRepository(Protocol):
    async def read(
        self, s: AsyncSession, tenant_id: UUID, *, for_update: bool = False
    ) -> TenantSettingsRow: ...
    async def write(self, s: AsyncSession, tenant_id: UUID, patch: Mapping[str, Any]) -> int:
        """Merge ``patch`` into ``tenants.settings`` (top-level keys), ``version + 1``; new version."""
        ...
