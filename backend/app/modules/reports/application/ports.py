"""What the M12 report services read (23 §1: Protocols here, raw SQL in ``infrastructure/reports_sql.py``).

Every method runs inside the caller's tenant transaction (RLS ``app.tenant_id``) and only reads.
``branch_ids`` ``None`` = every branch of the tenant; a tuple = only those branches.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.domain.debts import DebtDoc
from app.modules.reports.domain.periods import DateRange

Branches = tuple[UUID, ...] | None
SalesGroup = Literal["day", "branch", "cashier"]


@dataclass(frozen=True, slots=True)
class BranchRow:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class SalesAgg:
    group_key: str
    group_label: str | None
    gross_sales: Decimal
    receipts_count: int
    returns_total: Decimal


@dataclass(frozen=True, slots=True)
class ProductSales:
    product_id: UUID
    name: str
    unit_code: str
    qty_sold: Decimal
    revenue: Decimal


@dataclass(frozen=True, slots=True)
class LedgerTotals:
    """P&L account balances of one branch over a range (sign: the natural side of each account)."""

    branch_id: UUID | None
    revenue_9020: Decimal
    returns_9040: Decimal
    discounts_9050: Decimal
    cogs_9120: Decimal
    other_income_9390: Decimal


@dataclass(frozen=True, slots=True)
class ExpenseLine:
    branch_id: UUID | None
    account: str
    source: str  # ledger doc_type ('expenses', 'write_offs', 'debt_writeoffs', 'bank_settlements', …)
    category_id: UUID | None
    category_name: str | None
    amount: Decimal  # Dt − Kt


@dataclass(frozen=True, slots=True)
class DiscountAgg:
    group_key: str
    group_label: str | None
    sales_total: Decimal  # Σ line_total (VAT incl., after discount) net of returns
    discount_total: Decimal  # Σ discount_amount (VAT incl.) net of returned share
    discount_net: Decimal  # the same excl. VAT — the margin it cost
    revenue_net: Decimal  # Σ (line_total − vat_amount) net of returns
    cost: Decimal  # Σ cost_amount net of returns


@dataclass(frozen=True, slots=True)
class StockRow:
    product_id: UUID
    name: str
    name_ru: str | None
    unit_code: str
    category_id: UUID | None
    category_name: str | None
    barcode: str | None
    is_marked: bool
    is_weighed: bool
    min_stock: Decimal | None
    branch_id: UUID
    qty: Decimal
    value: Decimal
    below_min: bool


@dataclass(frozen=True, slots=True)
class RegisterCash:
    cash_register_id: UUID
    name: str
    branch_id: UUID
    cash_on_hand: Decimal


@dataclass(frozen=True, slots=True)
class Counterparty:
    id: UUID
    name: str
    phone: str | None
    balance: Decimal


@dataclass(frozen=True, slots=True)
class UnsyncedDevices:
    count: int
    oldest_pending_at: datetime | None


@dataclass(frozen=True, slots=True)
class ApprovalPending:
    permission_code: str
    kind: str
    requested_value: Decimal | None


class ReportsRepository(Protocol):
    async def branches(self, s: AsyncSession, branch_ids: Branches) -> list[BranchRow]: ...

    async def tenant_settings(self, s: AsyncSession) -> dict[str, object]: ...

    async def sales(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches, group_by: SalesGroup
    ) -> list[SalesAgg]: ...

    async def product_sales(
        self,
        s: AsyncSession,
        rng: DateRange,
        branch_ids: Branches,
        order: Literal["top", "bottom"],
        limit: int,
    ) -> list[ProductSales]: ...

    async def ledger_totals(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> list[LedgerTotals]: ...

    async def expense_lines(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> list[ExpenseLine]: ...

    async def discounts(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches, group_by: str
    ) -> list[DiscountAgg]: ...

    async def stock(
        self,
        s: AsyncSession,
        branch_ids: Branches,
        *,
        warehouse_id: UUID | None,
        search: str | None,
        category_id: UUID | None,
    ) -> list[StockRow]: ...

    async def low_stock(self, s: AsyncSession, branch_ids: Branches) -> dict[UUID, set[UUID]]: ...

    async def stock_value(self, s: AsyncSession, branch_ids: Branches) -> tuple[Decimal, int]: ...

    async def warehouse_branch(self, s: AsyncSession, warehouse_id: UUID) -> UUID | None: ...

    async def expiring_lots(self, s: AsyncSession, branch_ids: Branches, until: date) -> int: ...

    async def register_cash(
        self, s: AsyncSession, branch_ids: Branches, at: datetime
    ) -> list[RegisterCash]: ...

    async def new_debts(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> dict[UUID, Decimal]: ...

    async def debt_payments(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> dict[UUID, Decimal]: ...

    async def receivables(self, s: AsyncSession) -> tuple[list[Counterparty], list[DebtDoc]]: ...

    async def unsynced_devices(self, s: AsyncSession, branch_ids: Branches) -> UnsyncedDevices: ...

    async def cash_variance(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> tuple[int, Decimal]: ...

    async def pending_approvals(self, s: AsyncSession, branch_ids: Branches) -> list[ApprovalPending]: ...

    async def fiscal_unacked(self, s: AsyncSession, branch_ids: Branches, older_than: datetime) -> int: ...

    async def tenant_counts(self, s: AsyncSession) -> dict[str, int]: ...


def branch_tuple(ids: Sequence[UUID] | None) -> Branches:
    return None if ids is None else tuple(ids)
