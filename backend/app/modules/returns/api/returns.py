"""Returns list / detail (18 §7.2; US-M02-01…03). Tag ``returns`` (M02). Read-only — returns come from
``/sync/push`` (``return.created``). Permission ``reports.sales.view``; branch scope applies."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.returns.application.ports import ReturnFilter
from app.modules.returns.wiring import ReturnQueries

router = APIRouter(tags=["returns"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("reports.sales.view"))]
Reason = Literal["defective", "wrong_item", "customer_changed_mind", "other"]
RefundMethod = Literal["cash", "card", "uzqr", "click", "payme", "uzum", "debt_adjustment"]


class CustomerReturnListItem(BaseModel):
    id: UUID
    number: str | None
    temp_number: str | None
    doc_date: str
    status: Literal["draft", "posted", "cancelled"]
    sale_id: UUID | None
    without_receipt: bool = Field(description="Derived: sale_id IS NULL (11 §6)")
    branch_id: UUID
    shift_id: UUID
    cash_register_id: UUID
    reason: Reason
    refund_method: RefundMethod
    is_offline: bool
    total_amount: str
    created_at: str


class CustomerReturnPage(BaseModel):
    items: list[CustomerReturnListItem]
    next_cursor: str | None


class CustomerReturnLineOut(BaseModel):
    id: UUID
    line_no: int
    sale_line_id: UUID | None
    product_id: UUID
    product_name: str
    qty: str
    price: str
    vat_rate: str
    vat_exemption_code: str | None
    vat_amount: str
    line_total: str
    marking_code: str | None
    restock: bool


class CustomerReturnFiscalOut(BaseModel):
    id: UUID
    kind: str
    status: str
    receipt_seq: int | None
    fm_receipt_seq: int | None
    fiscal_sign: str | None
    qr_url: str | None
    payment_form: str | None
    ofd_acked_at: str | None


class CustomerReturnOut(BaseModel):
    id: UUID
    number: str | None
    temp_number: str | None
    doc_date: str
    status: Literal["draft", "posted", "cancelled"]
    sale_id: UUID | None
    without_receipt: bool
    branch_id: UUID
    shift_id: UUID
    cash_register_id: UUID
    counterparty_id: UUID | None
    reason: Reason
    refund_method: RefundMethod
    card_entry_mode: Literal["integrated", "manual"] | None
    card_type: str | None
    card_mask: str | None
    rrn: str | None
    approval_code: str | None
    card_scheme: str | None
    manual_reason: str | None
    is_offline: bool
    approved_by: UUID | None
    approved_at: str | None
    created_by: UUID
    created_at: str
    posted_at: str | None
    device_id: UUID | None
    comment: str | None
    total_amount: str
    write_off_id: UUID | None = Field(description="Draft write-off of expired returned goods (qaror #48)")
    lines: list[CustomerReturnLineOut]
    fiscal_receipts: list[CustomerReturnFiscalOut]


def returns_queries(request: Request) -> ReturnQueries:
    queries: ReturnQueries | None = getattr(request.app.state, "returns", None)
    if queries is None:
        raise RuntimeError("returns module is not configured (app.state.returns)")
    return queries


def _branches(scope: BranchScope, branch_id: UUID | None) -> tuple[UUID, ...] | None:
    if branch_id is not None:
        if (scope.current is not None and branch_id != scope.current) or (
            not scope.unrestricted and branch_id not in scope.allowed
        ):
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return (branch_id,)
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


@router.get("/returns", operation_id="returns_list_returns", response_model=CustomerReturnPage)
async def list_returns(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    branch_id: UUID | None = None,
    sale_id: UUID | None = None,
    shift_id: UUID | None = None,
    without_receipt: bool | None = None,
    doc_date_gte: Annotated[date | None, Query(alias="doc_date__gte")] = None,
    doc_date_lte: Annotated[date | None, Query(alias="doc_date__lte")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = ReturnFilter(
        branch_ids=_branches(scope, branch_id), sale_id=sale_id, shift_id=shift_id,
        without_receipt=without_receipt,
        date_from=doc_date_gte, date_to=doc_date_lte,
    )  # fmt: skip
    return await returns_queries(request).list_page(actor.tenant_id, actor.user_id, flt, cursor, limit)


@router.get("/returns/{return_id}", operation_id="returns_get_return", response_model=CustomerReturnOut)
async def get_return(
    request: Request, return_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await returns_queries(request).get(actor.tenant_id, actor.user_id, scope, return_id)
