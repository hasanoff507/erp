"""Ledger adjustments (20 #10/#10a/#10b) and month closing (20 #14–#16). Tag ``accounting`` (17 §11, M11)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import MoneyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.accounting.api.ledger import accounting_module
from app.modules.accounting.application.adjustments import LedgerAdjustmentService
from app.modules.accounting.application.closings import PeriodClosingService, period_of

router = APIRouter(tags=["accounting"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanPost = Annotated[PermissionGrant, Depends(require_permission("accounting.post"))]
CanClose = Annotated[PermissionGrant, Depends(require_permission("accounting.period.close"))]
AccountCode = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")]
PeriodStr = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}$")]
Status = Literal["posted", "cancelled"]


def _adjustments(request: Request) -> LedgerAdjustmentService:
    service = accounting_module(request).adjustments
    if service is None:
        raise RuntimeError("ledger adjustments are not configured")
    return service


def _closings(request: Request) -> PeriodClosingService:
    service = accounting_module(request).closings
    if service is None:
        raise RuntimeError("period closings are not configured")
    return service


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- schemas --------------------------------------------------------------------------------------
class LedgerAdjustmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    doc_date: date = Field(
        description="= entry_date; an open period, ≤ today. A 0000 (opening balance) line: go_live_date − 1"
    )
    account_dt: AccountCode
    account_kt: AccountCode = Field(description="≠ account_dt; 2910/2920/2970 are register-managed (refused)")
    amount: MoneyStr = Field(description="> 0")
    comment: Annotated[str, StringConstraints(max_length=1000)]
    correction_of_period: PeriodStr | None = Field(
        default=None, description="YYYY-MM of the CLOSED month this entry corrects"
    )
    analytics: dict[str, str] = Field(
        default_factory=dict,
        description="13 §1 dimensions: counterparty_id (required for 4010/6010/6310), product_id, "
        "employee_id, warehouse_id, cash_register_id, expense_category_id, payment_method, tax_type, "
        "vat_credit, doc_id",
    )

    @field_validator("analytics")
    @classmethod
    def _size(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 20:
            raise ValueError("too many analytics keys")
        return value


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class LedgerAdjustmentOut(BaseModel):
    id: UUID
    number: str | None
    status: Status
    branch_id: UUID
    doc_date: str
    account_dt: str
    account_kt: str
    amount: str
    correction_of_period: str | None
    analytics: dict[str, Any]
    comment: str
    created_by: UUID
    created_at: str
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class LedgerAdjustmentCancelled(BaseModel):
    id: UUID
    status: Literal["cancelled"]
    cancelled_at: str | None


class LedgerAdjustmentPage(BaseModel):
    items: list[LedgerAdjustmentOut]
    next_cursor: str | None


class PeriodCloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: PeriodStr


class PeriodClosingOut(BaseModel):
    period: str
    closed_at: str
    closed_by: UUID


class PeriodClosingPage(BaseModel):
    items: list[PeriodClosingOut]
    next_cursor: str | None


class UnsyncedDeviceOut(BaseModel):
    device_id: UUID
    cash_register_name: str | None
    outbox_pending_count: int
    outbox_oldest_pending_at: str | None


class StaleSettlementOut(BaseModel):
    id: UUID
    tax_kind: Literal["vat_offset", "turnover_tax"]
    branch_id: UUID | None
    amount: str
    current_amount: str


class StockMismatchOut(BaseModel):
    account: str
    ledger_balance: str
    stock_value: str
    difference: str


class ReadinessOut(BaseModel):
    period: str
    ready: bool
    blockers: list[Literal["recost_pending", "fiscal_pending", "devices_unsynced"]]
    warnings: list[
        Literal[
            "tax_settlement_missing",
            "tax_settlement_stale",
            "opening_0000_nonzero",
            "open_shifts",
            "drafts_in_period",
            "devices_not_synced_after_period_end",
            "ledger_stock_mismatch",
        ]
    ]
    pending_recost_jobs: int
    pending_fiscal_receipts: int
    unsynced_devices: list[UnsyncedDeviceOut]
    opening_balance_unresolved: bool
    opening_0000_balance: str
    stale_tax_settlements: list[StaleSettlementOut]
    ledger_stock_mismatches: list[StockMismatchOut]


# --- 20 #10 / #10a / #10b -------------------------------------------------------------------------
@router.post(
    "/ledger-adjustments",
    operation_id="accounting_create_ledger_adjustment",
    response_model=LedgerAdjustmentOut,
    status_code=201,
)
async def create_ledger_adjustment(
    request: Request, response: Response, body: LedgerAdjustmentIn, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    values = body.model_dump()
    if body.correction_of_period is not None:
        values["correction_of_period"] = period_of(body.correction_of_period, "correction_of_period")
    result = await _adjustments(request).create(actor, scope, values, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{result['id']}"
    return result


@router.post(
    "/ledger-adjustments/{adjustment_id}/cancel",
    operation_id="accounting_cancel_ledger_adjustment",
    response_model=LedgerAdjustmentCancelled,
)
async def cancel_ledger_adjustment(
    request: Request, adjustment_id: UUID, body: CancelIn, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    return await _adjustments(request).cancel(actor, scope, adjustment_id, body.reason, _ip(request))


@router.get(
    "/ledger-adjustments",
    operation_id="accounting_list_ledger_adjustments",
    response_model=LedgerAdjustmentPage,
)
async def list_ledger_adjustments(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanPost,
    branch_id: UUID | None = None,
    status: Status | None = None,
    doc_date_gte: Annotated[date | None, Query(alias="doc_date__gte")] = None,
    doc_date_lte: Annotated[date | None, Query(alias="doc_date__lte")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _adjustments(request).page(
        actor,
        scope,
        branch_id=branch_id,
        status=status,
        doc_date_gte=doc_date_gte,
        doc_date_lte=doc_date_lte,
        cursor=cursor,
        limit=limit,
    )


# --- 20 #14 / #15 / #16 ---------------------------------------------------------------------------
@router.get(
    "/period-closings", operation_id="accounting_list_period_closings", response_model=PeriodClosingPage
)
async def list_period_closings(
    request: Request,
    actor: Actor,
    _: CanPost,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _closings(request).page(actor, cursor, limit)


@router.post(
    "/period-closings",
    operation_id="accounting_close_period",
    response_model=PeriodClosingOut,
    status_code=201,
)
async def close_period(request: Request, body: PeriodCloseIn, actor: Actor, _: CanClose) -> dict[str, Any]:
    return await _closings(request).close(actor, body.period, _ip(request))


@router.get(
    "/period-closings/{period}/readiness",
    operation_id="accounting_get_period_closing_readiness",
    response_model=ReadinessOut,
)
async def period_closing_readiness(
    request: Request,
    actor: Actor,
    _: CanPost,
    period: Annotated[str, Path(max_length=7, description="YYYY-MM")],
) -> dict[str, Any]:
    return await _closings(request).readiness(actor, period)
