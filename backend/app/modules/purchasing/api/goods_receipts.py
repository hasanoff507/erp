"""Goods receipts (19 §8). Tag ``purchasing`` (M07).

``POST`` / ``PATCH`` (draft) — ``purchases.receive``; ``post`` / ``cancel`` — ``purchases.post``
(qaror #49); reads — ``stock.view``. Every write needs ``Idempotency-Key`` (17 §6). ``from-einvoice``
is Bosqich 5.
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
from app.core.money import PercentStr, PriceStr, QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.purchasing.api.purchase_orders import SupplierRef, purchasing_module
from app.modules.purchasing.application.goods_receipts import ReceiptInput, ReceiptLineInput
from app.modules.purchasing.application.ports import DocFilter
from app.modules.purchasing.application.purchase_orders import scope_branches

router = APIRouter(tags=["purchasing"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanReceive = Annotated[PermissionGrant, Depends(require_permission("purchases.receive"))]
CanPost = Annotated[PermissionGrant, Depends(require_permission("purchases.post"))]
Text = Annotated[str, StringConstraints(max_length=1000)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=255)]
MarkingCode = Annotated[str, StringConstraints(min_length=1, max_length=512)]
ReceiptStatus = Literal["draft", "posted", "cancelled"]
DiscrepancyReason = Literal["short", "excess", "damaged", "wrong_item", "other"]


# --- schemas --------------------------------------------------------------------------------------
class ReceiptLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    qty: QtyStr = Field(description="> 0, 3 dp; bonus units are part of the quantity (13 §2.6)")
    cost: PriceStr | None = Field(
        default=None,
        description="Unit cost WITHOUT VAT, 4 dp; defaults to the PO line price when po_id is given",
    )
    vat_rate: PercentStr | None = Field(default=None, description='"12.00" / "0.00"; default — product card')
    vat_exemption_code: ShortText | None = None
    expiry_date: date | None = None
    marking_codes: list[MarkingCode] | None = Field(
        default=None, max_length=100000, description="is_marked products: exactly qty codes, GS kept as sent"
    )
    discrepancy_reason: DiscrepancyReason | None = Field(
        default=None, description="Required when po_id is given and the quantity differs from the PO"
    )


class ReceiptIn(BaseModel):
    """19 §8 ``POST`` body; ``PATCH`` takes the same body and replaces the whole draft."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID | None = Field(default=None, description="Required unless po_id is given")
    warehouse_id: UUID
    po_id: UUID | None = None
    doc_date: date
    lines: list[ReceiptLineIn] = Field(min_length=1, max_length=1000)
    paid_immediately: bool = Field(default=False, description="true → paid from the bank account (13 §2.8)")
    kind: Literal["purchase", "gratuitous"] = "purchase"
    ettn_ref: ShortText | None = None
    poa_id: UUID | None = None
    poa_number: ShortText | None = None
    comment: Text | None = None


class ReceiptCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarkingAcceptance(BaseModel):
    status: Literal["not_required", "pending", "accepted", "overdue"]
    due_at: str | None
    deadline_kind: Literal["3_business_days", "72_hours"] | None


class ReceiptLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str | None
    unit_code: str | None
    qty: str
    cost: str
    vat_rate: str
    vat_exemption_code: str | None
    vat_amount: str = Field(description="ROUND_HALF_UP(net_amount × vat_rate / 100, 2)")
    net_amount: str = Field(description="ROUND_HALF_UP(qty × cost, 2)")
    total_amount: str
    expiry_date: str | None
    discrepancy_reason: DiscrepancyReason | None
    is_marked: bool
    marking_codes: list[str]
    lot_id: UUID | None = Field(description="The lot created by posting this line")
    lot_qty_left: str | None
    returned_qty: str = Field(description="Σ qty of posted supplier returns of this line")


class ReceiptHeaderOut(BaseModel):
    id: UUID
    number: str | None = Field(description="M-… assigned on post; null in draft")
    status: ReceiptStatus
    doc_date: str
    branch_id: UUID
    warehouse_id: UUID
    supplier_id: UUID
    supplier: SupplierRef
    po_id: UUID | None
    kind: Literal["purchase", "gratuitous"]
    source: Literal["manual", "purchase_order", "einvoice", "ocr"]
    paid_immediately: bool
    einvoice_id: UUID | None
    einvoice_risk_flag: Literal["green", "red", "unknown"] | None
    ettn_ref: str | None
    ettn_status: Literal["none", "received", "accepted", "rejected"]
    poa_id: UUID | None
    poa_number: str | None
    comment: str | None
    line_count: int
    net_total: str
    vat_total: str
    total: str = Field(description="Invoice total = net_total + vat_total")
    created_by: UUID
    created_by_name: str | None
    created_at: str
    updated_at: str
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class ReceiptOut(ReceiptHeaderOut):
    marking_acceptance: MarkingAcceptance | None
    lines: list[ReceiptLineOut]


class LotCreated(BaseModel):
    lot_id: UUID
    product_id: UUID
    qty_in: str
    unit_cost: str


class ReceiptPosted(ReceiptOut):
    lots_created: list[LotCreated]


class ReceiptPage(BaseModel):
    items: list[ReceiptHeaderOut]
    next_cursor: str | None


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _input(body: ReceiptIn) -> ReceiptInput:
    return ReceiptInput(
        supplier_id=body.supplier_id,
        warehouse_id=body.warehouse_id,
        po_id=body.po_id,
        doc_date=body.doc_date,
        lines=[
            ReceiptLineInput(
                product_id=ln.product_id,
                qty=Decimal(ln.qty),
                cost=None if ln.cost is None else Decimal(ln.cost),
                vat_rate=None if ln.vat_rate is None else Decimal(ln.vat_rate),
                vat_exemption_code=ln.vat_exemption_code,
                expiry_date=ln.expiry_date,
                marking_codes=None if ln.marking_codes is None else tuple(ln.marking_codes),
                discrepancy_reason=ln.discrepancy_reason,
            )
            for ln in body.lines
        ],
        paid_immediately=body.paid_immediately,
        kind=body.kind,
        ettn_ref=body.ettn_ref,
        poa_id=body.poa_id,
        poa_number=body.poa_number,
        comment=body.comment,
    )


# --- routes ---------------------------------------------------------------------------------------
@router.get("/goods-receipts", operation_id="purchasing_list_goods_receipts", response_model=ReceiptPage)
async def list_goods_receipts(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    supplier_id: UUID | None = None,
    status: ReceiptStatus | None = None,
    po_id: UUID | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = DocFilter(
        branch_ids=scope_branches(scope),
        supplier_id=supplier_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        po_id=po_id,
        search=(search or "").strip() or None,
    )
    return await purchasing_module(request).goods_receipts.list_page(actor, flt, cursor, limit)


@router.post(
    "/goods-receipts",
    operation_id="purchasing_create_goods_receipt",
    response_model=ReceiptOut,
    status_code=201,
)
async def create_goods_receipt(
    request: Request, response: Response, body: ReceiptIn, actor: Actor, scope: Scope, _: CanReceive
) -> dict[str, Any]:
    gr = await purchasing_module(request).goods_receipts.create(actor, scope, _input(body), _ip(request))
    response.headers["Location"] = f"{request.url.path}/{gr['id']}"
    return gr


@router.get(
    "/goods-receipts/{receipt_id}", operation_id="purchasing_get_goods_receipt", response_model=ReceiptOut
)
async def get_goods_receipt(
    request: Request, receipt_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await purchasing_module(request).goods_receipts.get(actor, scope, receipt_id)


@router.patch(
    "/goods-receipts/{receipt_id}", operation_id="purchasing_update_goods_receipt", response_model=ReceiptOut
)
async def update_goods_receipt(
    request: Request, receipt_id: UUID, body: ReceiptIn, actor: Actor, scope: Scope, _: CanReceive
) -> dict[str, Any]:
    return await purchasing_module(request).goods_receipts.replace(
        actor, scope, receipt_id, _input(body), _ip(request)
    )


@router.post(
    "/goods-receipts/{receipt_id}/post",
    operation_id="purchasing_post_goods_receipt",
    response_model=ReceiptPosted,
)
async def post_goods_receipt(
    request: Request,
    receipt_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanPost,
    body: EmptyBody | None = None,
) -> dict[str, Any]:
    return await purchasing_module(request).goods_receipts.post(actor, scope, receipt_id, _ip(request))


@router.post(
    "/goods-receipts/{receipt_id}/cancel",
    operation_id="purchasing_cancel_goods_receipt",
    response_model=ReceiptOut,
)
async def cancel_goods_receipt(
    request: Request, receipt_id: UUID, body: ReceiptCancel, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    return await purchasing_module(request).goods_receipts.cancel(
        actor, scope, receipt_id, body.reason, _ip(request)
    )
