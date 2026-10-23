"""M11 statements — ``/reports/trial-balance`` (20 #11), ``/reports/balance-sheet`` (20 #13),
``/reports/stock-as-of`` (20 #20a, ACC-09). Tag ``reports``; read-only, ``reports.finance.view``."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.reports.application.accounting_reports import AccountingReportsService

router = APIRouter(tags=["reports"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanFinance = Annotated[PermissionGrant, Depends(require_permission("reports.finance.view"))]


def _service(request: Request) -> AccountingReportsService:
    service: AccountingReportsService | None = getattr(request.app.state, "accounting_reports", None)
    if service is None:
        raise RuntimeError("accounting reports are not configured (app.state.accounting_reports)")
    return service


class TaxTypeTurnover(BaseModel):
    tax_type: str
    opening_balance: str
    debit_turnover: str
    credit_turnover: str
    closing_balance: str


class TrialBalanceRow(BaseModel):
    account: str
    name: str
    type: str
    opening_balance: str
    debit_turnover: str
    credit_turnover: str
    closing_balance: str
    by_tax_type: list[TaxTypeTurnover] | None


class TrialBalanceTotals(BaseModel):
    debit_turnover: str
    credit_turnover: str


class TrialBalanceOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    branch_id: UUID | None
    rows: list[TrialBalanceRow]
    totals: TrialBalanceTotals


class StatementLine(BaseModel):
    account: str
    name: str
    amount: str


class BalanceSheetOut(BaseModel):
    as_of: str
    branch_id: UUID | None
    assets: list[StatementLine]
    liabilities: list[StatementLine]
    equity: list[StatementLine]
    total_assets: str
    total_liabilities_and_equity: str
    opening_balance_unresolved: bool
    opening_0000_balance: str
    warnings: list[Literal["opening_0000_nonzero"]]


class StockAsOfItem(BaseModel):
    product_id: UUID
    name: str
    warehouse_id: UUID
    branch_id: UUID
    qty: str
    value: str


class StockAsOfAccount(BaseModel):
    account: str
    stock_value: str
    ledger_value: str | None
    difference: str | None


class StockAsOfOut(BaseModel):
    as_of: str
    basis: Literal["doc_date"]
    branch_id: UUID | None
    warehouse_id: UUID | None
    items: list[StockAsOfItem]
    accounts: list[StockAsOfAccount]


@router.get(
    "/reports/trial-balance", operation_id="reports_get_trial_balance", response_model=TrialBalanceOut
)
async def trial_balance(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanFinance,
    period: Annotated[str, Query(max_length=7, description="YYYY-MM")],
    branch_id: UUID | None = None,
    account: Annotated[str | None, Query(pattern=r"^[0-9]{4}$")] = None,
) -> dict[str, Any]:
    return await _service(request).trial_balance(
        actor, scope, period=period, branch_id=branch_id, account=account
    )


@router.get(
    "/reports/balance-sheet", operation_id="reports_get_balance_sheet", response_model=BalanceSheetOut
)
async def balance_sheet(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanFinance,
    as_of: date | None = None,
    branch_id: UUID | None = None,
) -> dict[str, Any]:
    return await _service(request).balance_sheet(actor, scope, as_of=as_of, branch_id=branch_id)


@router.get("/reports/stock-as-of", operation_id="reports_get_stock_as_of", response_model=StockAsOfOut)
async def stock_as_of(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanFinance,
    as_of: date,
    branch_id: UUID | None = None,
    warehouse_id: UUID | None = None,
) -> dict[str, Any]:
    return await _service(request).stock_as_of(
        actor, scope, as_of=as_of, branch_id=branch_id, warehouse_id=warehouse_id
    )
