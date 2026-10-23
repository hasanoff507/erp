"""Shifts — back-office views (18 §3.3) and the cash history of a register (20 #55). Tag ``cash`` (M01/M16).

Shifts are opened/closed only by the ``shift.opened`` / ``shift.closed`` sync events (18 §3.1–§3.2).
Rights: ``reports.sales.view`` **or** ``cash.count.shift``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.cash.api.deps import cash_module, require_any

router = APIRouter(tags=["cash"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[str, Depends(require_any("reports.sales.view", "cash.count.shift"))]
ShiftStatus = Literal["open", "closed"]


class ShiftListItem(BaseModel):
    id: UUID
    shift_no: int
    cash_register_id: UUID
    branch_id: UUID
    status: ShiftStatus
    opening_cash: str
    opened_at: str
    closed_at: str | None


class ShiftPage(BaseModel):
    items: list[ShiftListItem]
    next_cursor: str | None


class MethodTotals(BaseModel):
    cash: str
    card: str
    uzqr: str
    click: str
    payme: str
    uzum: str
    debt: str


class CardSplit(BaseModel):
    integrated: str = Field(description="card_entry_mode='integrated' payments (terminal results)")
    manual: str = Field(description="card_entry_mode='manual' — terminalsiz (rekvizitsiz) card payments")


class CardSettlementSummary(BaseModel):
    card_terminal_id: UUID
    net_total: str
    expected_total: str
    variance: str
    status: Literal["matched", "mismatch", "failed"]


class ZReport(BaseModel):
    expected_cash: str
    counted_cash: str | None
    variance: str | None
    totals_by_method: MethodTotals
    card_split: CardSplit
    card_settlements: list[CardSettlementSummary]
    vat_total: str
    discount_total: str
    returns_total: str
    sales_count: int
    returns_count: int


class FiscalState(BaseModel):
    id: UUID | None
    status: str
    fiscal_sign: str | None = None
    qr_url: str | None = None
    ofd_acked_at: str | None = None


class RunningTotals(BaseModel):
    totals_by_method: MethodTotals
    sales_count: int
    voided_count: int
    returns_total: str
    cash_in: str
    cash_out: str
    expected_cash: str


class ShiftOut(BaseModel):
    id: UUID
    shift_no: int
    branch_id: UUID
    cash_register_id: UUID
    device_id: UUID
    status: ShiftStatus
    opening_cash: str
    opened_by: UUID
    opened_at: str
    closed_by: UUID | None
    closed_at: str | None
    expected_cash: str | None
    counted_cash: str | None
    variance: str | None
    variance_note: str | None
    counted_card_total: str | None
    comment: str | None
    running_totals: RunningTotals | None = Field(description="Only while status=open (POS-07/POS-15)")
    z_report: ZReport | None = Field(description="Only when status=closed")
    fiscal: FiscalState | None = None


class ZReportOut(ZReport):
    shift_id: UUID
    shift_no: int
    fiscal: FiscalState


class CashHistoryItem(BaseModel):
    shift_id: UUID
    shift_no: int
    status: ShiftStatus
    opened_at: str
    closed_at: str | None
    opening_cash: str
    cash_sales: str = Field(description="Σ cash payments of the shift's posted sales")
    cash_in: str
    cash_out: str
    expected_cash: str
    counted_cash: str | None
    variance: str | None
    variance_note: str | None
    counted_card_total: str | None


class CashHistoryOut(BaseModel):
    items: list[CashHistoryItem]


@router.get("/shifts", operation_id="cash_list_shifts", response_model=ShiftPage)
async def list_shifts(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    cash_register_id: UUID | None = None,
    status: ShiftStatus | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await cash_module(request).shifts.list_page(actor, scope, cash_register_id, status, cursor, limit)


@router.get("/shifts/{shift_id}", operation_id="cash_get_shift", response_model=ShiftOut)
async def get_shift(
    request: Request, shift_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await cash_module(request).shifts.get(actor, scope, shift_id)


@router.get("/shifts/{shift_id}/z-report", operation_id="cash_get_z_report", response_model=ZReportOut)
async def get_z_report(
    request: Request, shift_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await cash_module(request).shifts.z_report(actor, scope, shift_id)


@router.get(
    "/cash-registers/{register_id}/cash-history",
    operation_id="cash_get_cash_history",
    response_model=CashHistoryOut,
)
async def cash_history(
    request: Request,
    register_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanView,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    return await cash_module(request).shifts.cash_history(actor, scope, register_id, date_from, date_to)
