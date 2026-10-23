"""Purchase orders (19 §10). Tag ``purchasing`` (M07).

Writes (``POST``, ``PATCH``, ``send``, ``cancel``) — ``purchases.create``; reads — ``stock.view``.
Every write needs ``Idempotency-Key`` (17 §6); the replay returns the stored response.
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
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import PriceStr, QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.purchasing.application.module import PurchasingModule
from app.modules.purchasing.application.ports import PoFilter
from app.modules.purchasing.application.purchase_orders import PoInput, PoLineInput, scope_branches

router = APIRouter(tags=["purchasing"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanCreate = Annotated[PermissionGrant, Depends(require_permission("purchases.create"))]
Comment = Annotated[str, StringConstraints(max_length=1000)]
PoStatusParam = Literal["draft", "sent", "partially_received", "closed", "cancelled"]


# --- schemas --------------------------------------------------------------------------------------
class PoLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    qty: QtyStr = Field(description="> 0, 3 dp")
    price: PriceStr | None = Field(default=None, description="Expected price for planning (4 dp), optional")


class PoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID
    warehouse_id: UUID
    doc_date: date
    lines: list[PoLineIn] = Field(min_length=1, max_length=1000)
    comment: Comment | None = None


class PoUpdate(BaseModel):
    """19 §10 PATCH (draft/sent only): given fields replace the stored ones; ``lines`` replaces all lines."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID | None = None
    warehouse_id: UUID | None = None
    doc_date: date | None = None
    lines: list[PoLineIn] | None = Field(default=None, min_length=1, max_length=1000)
    comment: Comment | None = None


class PoCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupplierRef(BaseModel):
    id: UUID
    name: str | None
    stir: str | None


class PoLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str | None
    unit_code: str | None
    qty: str
    price: str | None
    amount: str | None = Field(description="qty × price (2 dp); null without a price")


class ReceivedLineOut(BaseModel):
    product_id: UUID
    ordered_qty: str
    received_qty: str = Field(description="Σ qty of POSTED goods receipts linked by po_id (derived, 19 §10)")


class PoHeaderOut(BaseModel):
    id: UUID
    number: str | None = Field(description="Z-… assigned when the order is sent; null in draft")
    status: PoStatusParam
    doc_date: str
    branch_id: UUID
    warehouse_id: UUID
    supplier_id: UUID
    supplier: SupplierRef
    comment: str | None
    total: str | None = Field(description="Σ qty × price over priced lines (2 dp)")
    line_count: int
    created_by: UUID
    created_by_name: str | None
    created_at: str
    updated_at: str
    sent_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class PoOut(PoHeaderOut):
    lines: list[PoLineOut]
    received_lines: list[ReceivedLineOut]


class PoPage(BaseModel):
    items: list[PoHeaderOut]
    next_cursor: str | None


def purchasing_module(request: Request) -> PurchasingModule:
    module: PurchasingModule | None = getattr(request.app.state, "purchasing", None)
    if module is None:
        raise RuntimeError("purchasing module is not configured (app.state.purchasing)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _lines(lines: list[PoLineIn]) -> list[PoLineInput]:
    return [
        PoLineInput(
            product_id=ln.product_id,
            qty=Decimal(ln.qty),
            price=None if ln.price is None else Decimal(ln.price),
        )
        for ln in lines
    ]


# --- routes ---------------------------------------------------------------------------------------
@router.get("/purchase-orders", operation_id="purchasing_list_purchase_orders", response_model=PoPage)
async def list_purchase_orders(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    supplier_id: UUID | None = None,
    status: PoStatusParam | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = PoFilter(
        branch_ids=scope_branches(scope),
        supplier_id=supplier_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=(search or "").strip() or None,
    )
    return await purchasing_module(request).purchase_orders.list_page(actor, flt, cursor, limit)


@router.post(
    "/purchase-orders", operation_id="purchasing_create_purchase_order", response_model=PoOut, status_code=201
)
async def create_purchase_order(
    request: Request, response: Response, body: PoCreate, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    data = PoInput(
        supplier_id=body.supplier_id,
        warehouse_id=body.warehouse_id,
        doc_date=body.doc_date,
        lines=_lines(body.lines),
        comment=body.comment,
    )
    po = await purchasing_module(request).purchase_orders.create(actor, scope, data, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{po['id']}"
    return po


@router.get("/purchase-orders/{po_id}", operation_id="purchasing_get_purchase_order", response_model=PoOut)
async def get_purchase_order(
    request: Request, po_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await purchasing_module(request).purchase_orders.get(actor, scope, po_id)


@router.patch(
    "/purchase-orders/{po_id}", operation_id="purchasing_update_purchase_order", response_model=PoOut
)
async def update_purchase_order(
    request: Request, po_id: UUID, body: PoUpdate, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    fields = body.model_fields_set - {"lines"}
    changes = {k: getattr(body, k) for k in fields}
    for field in sorted({"supplier_id", "warehouse_id", "doc_date"} & changes.keys()):
        if changes[field] is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field=field, message_key="validation.required")],
            )
    if "lines" in body.model_fields_set and body.lines is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="lines", message_key="validation.required")],
        )
    lines = _lines(body.lines) if body.lines is not None else None
    return await purchasing_module(request).purchase_orders.update(
        actor, scope, po_id, changes, lines, _ip(request)
    )


@router.post(
    "/purchase-orders/{po_id}/send", operation_id="purchasing_send_purchase_order", response_model=PoOut
)
async def send_purchase_order(
    request: Request, po_id: UUID, actor: Actor, scope: Scope, _: CanCreate, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await purchasing_module(request).purchase_orders.send(actor, scope, po_id, _ip(request))


@router.post(
    "/purchase-orders/{po_id}/cancel", operation_id="purchasing_cancel_purchase_order", response_model=PoOut
)
async def cancel_purchase_order(
    request: Request, po_id: UUID, body: PoCancel, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    return await purchasing_module(request).purchase_orders.cancel(
        actor, scope, po_id, body.reason, _ip(request)
    )
