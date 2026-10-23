"""M12 report endpoints — ``/reports/dashboard``, ``/reports/sales``, ``/reports/top-products``,
``/reports/stock``, ``/reports/profit-and-loss``, ``/reports/discounts`` (20 #12, #17–#20, #19a). Read-only,
no ``Idempotency-Key``."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.access.domain.approvals import PERMISSION_BY_KIND
from app.modules.reports.application.ports import SalesGroup
from app.modules.reports.application.reports import DiscountGroup, Grants, ReportsService
from app.modules.reports.domain.periods import DashboardPeriod

router = APIRouter(tags=["reports"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanSales = Annotated[PermissionGrant, Depends(require_permission("reports.sales.view"))]
CanFinance = Annotated[PermissionGrant, Depends(require_permission("reports.finance.view"))]
CanStock = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
Limit = Annotated[int, Query(ge=1, le=200)]

# permissions that change what the dashboard shows (fields, alerts) — 07 BO-02, 06 §1.9
DASHBOARD_CODES: tuple[str, ...] = (
    "reports.finance.view",
    "debts.payment.accept",
    "stock.view",
    "tax.compare.review",
    "tax.vat.view",
    "settings.tenant",
    "accounting.post",
    "einvoice.sign",
    *sorted(set(PERMISSION_BY_KIND.values())),
)


# --- response schemas (decimal strings; 17 §4)
# ----------------------------------------------------------------
class AlertOut(BaseModel):
    type: str
    message_key: str
    severity: Literal["info", "warning", "critical"]
    count: int
    amount: str | None
    route: str


class DashboardBranchOut(BaseModel):
    branch_id: UUID
    name: str
    sales: str
    receipt_count: int
    avg_receipt: str
    profit: str | None
    cash_on_hand: str
    low_stock_count: int | None


class DashboardTopOut(BaseModel):
    product_id: UUID
    name: str
    unit_code: str
    qty: str


class ReceivablesOut(BaseModel):
    total: str
    debtors_count: int
    overdue_count: int
    overdue_amount: str


class StockKpiOut(BaseModel):
    value: str
    positions: int
    low_stock_count: int
    expiring_lots: int


class DashboardOut(BaseModel):
    period: Literal["today", "week", "month"]
    date_from: date
    date_to: date
    branch_id: UUID | None
    total_sales: str
    gross_sales: str
    returns_total: str
    receipt_count: int
    avg_receipt: str
    previous_total_sales: str
    net_profit: str | None
    expenses_total: str | None
    cash_on_hand: str
    by_branch: list[DashboardBranchOut]
    top_products: list[DashboardTopOut]
    receivables: ReceivablesOut | None
    stock: StockKpiOut | None
    alerts: list[AlertOut]
    unsynced_devices: int
    data_complete: bool


class SalesRowOut(BaseModel):
    group_key: str
    group_label: str | None
    total_sales: str
    gross_sales: str
    returns_total: str
    receipt_count: int
    avg_receipt: str


class SalesReportOut(BaseModel):
    date_from: date
    date_to: date
    branch_id: UUID | None
    group_by: Literal["day", "branch", "cashier"]
    rows: list[SalesRowOut]
    total: SalesRowOut
    unsynced_devices: int
    data_complete: bool


class TopProductOut(BaseModel):
    product_id: UUID
    name: str
    unit_code: str
    qty_sold: str
    revenue: str


class TopProductsOut(BaseModel):
    date_from: date
    date_to: date
    branch_id: UUID | None
    order: Literal["top", "bottom"]
    items: list[TopProductOut]
    unsynced_devices: int
    data_complete: bool


class StockBranchQtyOut(BaseModel):
    branch_id: UUID
    branch_name: str | None
    qty: str
    value: str
    below_min: bool


class StockItemOut(BaseModel):
    product_id: UUID
    name: str
    name_ru: str | None
    unit_code: str
    category_id: UUID | None
    category_name: str | None
    barcode: str | None
    is_marked: bool
    is_weighed: bool
    min_stock: str | None
    qty: str
    value: str
    avg_cost: str | None
    below_min: bool
    by_branch: list[StockBranchQtyOut]


class StockBranchOut(BaseModel):
    branch_id: UUID
    name: str
    value: str
    positions: int
    below_min_count: int


class StockTotalOut(BaseModel):
    value: str
    positions: int
    below_min_count: int


class StockReportOut(BaseModel):
    branch_id: UUID | None
    consolidated: bool
    items: list[StockItemOut]
    branches: list[StockBranchOut]
    total: StockTotalOut


class ExpenseCategoryOut(BaseModel):
    category_id: UUID | None
    category: str | None
    account: str
    source: str
    amount: str


class PnlFigures(BaseModel):
    revenue: str
    returns: str
    discounts: str
    net_revenue: str
    cogs: str
    gross_profit: str
    gross_margin_pct: str | None
    other_income: str
    expenses_by_category: list[ExpenseCategoryOut]
    expenses_total: str
    net_profit: str


class PnlBranchOut(PnlFigures):
    branch_id: UUID
    name: str


class ProfitAndLossOut(PnlFigures):
    period: str | None
    date_from: date
    date_to: date
    branch_id: UUID | None
    discount_posting: Literal["gross_9050", "net"]
    by_branch: list[PnlBranchOut]
    unsynced_devices: int
    data_complete: bool


class DiscountRowOut(BaseModel):
    group_key: str
    group_label: str | None
    sales_total: str
    discount_total: str
    discount_net: str
    revenue_net: str
    cost: str
    margin: str
    margin_without_discounts: str
    margin_pct: str | None
    margin_pct_without_discounts: str | None


class DiscountReportOut(BaseModel):
    date_from: date
    date_to: date
    branch_id: UUID | None
    group_by: Literal["day", "branch", "cashier", "product"]
    rows: list[DiscountRowOut]
    total: DiscountRowOut
    unsynced_devices: int
    data_complete: bool


def reports_service(request: Request) -> ReportsService:
    service: ReportsService | None = getattr(request.app.state, "reports", None)
    if service is None:
        raise RuntimeError("reports module is not configured (app.state.reports)")
    return service


async def caller_grants(request: Request, principal: Principal, codes: tuple[str, ...]) -> Grants:
    """The subset of ``codes`` the caller holds (token scope prefix + live role grants, like
    ``require_permission``) with the most generous limit (``None`` = unlimited)."""
    gateway = auth_gateway(request)
    out: dict[str, Decimal | None] = {}
    for code in codes:
        if not principal.has_scope(code.split(".", 1)[0]):
            continue
        limits = await gateway.permission_limits(principal, code)
        if not limits:
            continue
        out[code] = None if any(v is None for v in limits) else max(v for v in limits if v is not None)
    return out


@router.get("/reports/dashboard", operation_id="reports_get_dashboard", response_model=DashboardOut)
async def dashboard(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanSales,
    period: DashboardPeriod = "today",
    branch_id: UUID | None = None,
) -> dict[str, Any]:
    grants = await caller_grants(request, actor, DASHBOARD_CODES)
    return await reports_service(request).dashboard(
        actor, scope, period=period, branch_id=branch_id, grants=grants
    )


@router.get("/reports/sales", operation_id="reports_get_sales", response_model=SalesReportOut)
async def sales_report(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanSales,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: UUID | None = None,
    group_by: SalesGroup = "day",
) -> dict[str, Any]:
    return await reports_service(request).sales(
        actor, scope, date_from=date_from, date_to=date_to, branch_id=branch_id, group_by=group_by
    )


@router.get("/reports/top-products", operation_id="reports_get_top_products", response_model=TopProductsOut)
async def top_products(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanSales,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: UUID | None = None,
    order: Literal["top", "bottom"] = "top",
    limit: Limit = 20,
) -> dict[str, Any]:
    return await reports_service(request).top_products(
        actor, scope, date_from=date_from, date_to=date_to, branch_id=branch_id, order=order, limit=limit
    )


@router.get("/reports/stock", operation_id="reports_get_stock", response_model=StockReportOut)
async def stock_report(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanStock,
    branch_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    below_min_only: bool = False,
    search: Annotated[str | None, Query(max_length=64)] = None,
    category_id: UUID | None = None,
) -> dict[str, Any]:
    return await reports_service(request).stock(
        actor,
        scope,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        below_min_only=below_min_only,
        search=(search or "").strip() or None,
        category_id=category_id,
    )


@router.get(
    "/reports/profit-and-loss", operation_id="reports_get_profit_and_loss", response_model=ProfitAndLossOut
)
async def profit_and_loss(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanFinance,
    period: Annotated[str | None, Query(max_length=7)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: UUID | None = None,
) -> dict[str, Any]:
    return await reports_service(request).profit_and_loss(
        actor, scope, period=period, date_from=date_from, date_to=date_to, branch_id=branch_id
    )


@router.get("/reports/discounts", operation_id="reports_get_discounts", response_model=DiscountReportOut)
async def discounts_report(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanFinance,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: UUID | None = None,
    group_by: DiscountGroup = "day",
) -> dict[str, Any]:
    return await reports_service(request).discounts(
        actor, scope, date_from=date_from, date_to=date_to, branch_id=branch_id, group_by=group_by
    )
