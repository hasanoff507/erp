"""Supplier returns (19 §12). Tag ``purchasing`` (M07).

``POST`` — ``purchases.return``; ``post`` / ``cancel`` — ``purchases.post``; reads — ``stock.view``.
Every write needs ``Idempotency-Key`` (17 §6).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.purchasing.api.purchase_orders import SupplierRef, purchasing_module
from app.modules.purchasing.application.ports import DocFilter
from app.modules.purchasing.application.purchase_orders import scope_branches
from app.modules.purchasing.application.supplier_returns import ReturnInput, ReturnLineInput

router = APIRouter(tags=["purchasing"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanReturn = Annotated[PermissionGrant, Depends(require_permission("purchases.return"))]
CanPost = Annotated[PermissionGrant, Depends(require_permission("purchases.post"))]
ReturnStatus = Literal["draft", "posted", "cancelled"]
ReturnReason = Literal["expired", "damaged", "excess", "other"]


class ReturnLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_line_id: UUID
    lot_id: UUID = Field(description="The lot created from that receipt line")
    qty: QtyStr = Field(description="> 0, ≤ lot qty_left − blocked_qty")
    marking_codes: list[Annotated[str, StringConstraints(min_length=1, max_length=512)]] = Field(
        default_factory=list, max_length=100000, description="Marked products: exactly qty in-stock codes"
    )


class ReturnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: UUID
    doc_date: date
    reason: ReturnReason
    lines: list[ReturnLineIn] = Field(min_length=1, max_length=1000)
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class ReturnCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReturnLineOut(BaseModel):
    id: UUID
    line_no: int
    receipt_line_id: UUID
    lot_id: UUID
    product_id: UUID
    product_name: str | None
    unit_code: str | None
    qty: str
    cost: str = Field(description="Derived: the receipt line's unit cost (without VAT)")
    vat_amount: str = Field(description="Derived: this quantity's share of the receipt line VAT")
    net_amount: str = Field(description="ROUND_HALF_UP(qty × cost, 2)")
    marking_codes: list[str]
    invoice_amount: str = Field(
        description="Settlement value with the supplier (net; + VAT share when the receipt was in the "
        "turnover regime)"
    )


class ReturnHeaderOut(BaseModel):
    id: UUID
    number: str | None = Field(description="MV-… assigned on post")
    status: ReturnStatus
    doc_date: str
    branch_id: UUID
    warehouse_id: UUID
    supplier_id: UUID
    supplier: SupplierRef
    receipt_id: UUID
    receipt_number: str | None
    reason: ReturnReason
    comment: str | None
    line_count: int
    net_total: str
    vat_total: str
    invoice_total: str = Field(description="Payable decrease written on post")
    vat_adjustment_status: Literal["awaiting_einvoice", "adjusted", "not_required"] | None = Field(
        description="awaiting_einvoice — the input-VAT decrease waits for the supplier's additional "
        "e-invoice; "
        "adjusted — written when that e-invoice was accepted (13 §2.20)"
    )
    created_by: UUID
    created_by_name: str | None
    created_at: str
    updated_at: str
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class ReturnOut(ReturnHeaderOut):
    lines: list[ReturnLineOut]


class ReturnPage(BaseModel):
    items: list[ReturnHeaderOut]
    next_cursor: str | None


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/supplier-returns", operation_id="purchasing_list_supplier_returns", response_model=ReturnPage)
async def list_supplier_returns(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    supplier_id: UUID | None = None,
    receipt_id: UUID | None = None,
    status: ReturnStatus | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = DocFilter(
        branch_ids=scope_branches(scope),
        supplier_id=supplier_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        receipt_id=receipt_id,
    )
    return await purchasing_module(request).supplier_returns.list_page(actor, flt, cursor, limit)


@router.post(
    "/supplier-returns",
    operation_id="purchasing_create_supplier_return",
    response_model=ReturnOut,
    status_code=201,
)
async def create_supplier_return(
    request: Request, response: Response, body: ReturnIn, actor: Actor, scope: Scope, _: CanReturn
) -> dict[str, Any]:
    data = ReturnInput(
        receipt_id=body.receipt_id,
        doc_date=body.doc_date,
        reason=body.reason,
        lines=[
            ReturnLineInput(ln.receipt_line_id, ln.lot_id, Decimal(ln.qty), tuple(ln.marking_codes))
            for ln in body.lines
        ],
        comment=body.comment,
    )
    sr = await purchasing_module(request).supplier_returns.create(actor, scope, data, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{sr['id']}"
    return sr


@router.get(
    "/supplier-returns/{return_id}", operation_id="purchasing_get_supplier_return", response_model=ReturnOut
)
async def get_supplier_return(
    request: Request, return_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await purchasing_module(request).supplier_returns.get(actor, scope, return_id)


@router.post(
    "/supplier-returns/{return_id}/post",
    operation_id="purchasing_post_supplier_return",
    response_model=ReturnOut,
)
async def post_supplier_return(
    request: Request,
    return_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanPost,
    body: EmptyBody | None = None,
) -> dict[str, Any]:
    return await purchasing_module(request).supplier_returns.post(actor, scope, return_id, _ip(request))


@router.post(
    "/supplier-returns/{return_id}/cancel",
    operation_id="purchasing_cancel_supplier_return",
    response_model=ReturnOut,
)
async def cancel_supplier_return(
    request: Request, return_id: UUID, body: ReturnCancel, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    return await purchasing_module(request).supplier_returns.cancel(
        actor, scope, return_id, body.reason, _ip(request)
    )
