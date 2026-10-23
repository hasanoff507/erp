"""Write-offs (19 §15). Tag ``inventory`` (M04)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.inventory.application.module import InventoryModule
from app.modules.inventory.application.write_offs import WriteOffLineInput

router = APIRouter(tags=["inventory"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanWriteOff = Annotated[PermissionGrant, Depends(require_permission("stock.writeoff"))]
WriteOffStatus = Literal["draft", "posted", "cancelled"]


def _module(request: Request) -> InventoryModule:
    module: InventoryModule | None = getattr(request.app.state, "inventory", None)
    if module is None:
        raise RuntimeError("inventory module is not configured (app.state.inventory)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- schemas -------------------------------------------------------------------------------------
class WriteOffLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    lot_id: UUID | None = Field(default=None, description="Optional — FIFO/AVECO allocation when omitted")
    qty: QtyStr
    reason: Literal["expired", "damaged", "gift", "expired_return", "other"] = Field(
        description="expired_return is created by returns only (qaror #48) — 422 here"
    )
    gift_kind: Literal["promo_justified", "other"] | None = None


class WriteOffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID
    doc_date: date
    lines: list[WriteOffLineIn] = Field(min_length=1, max_length=1000)
    promo_order_ref: Annotated[str, StringConstraints(max_length=255)] | None = None
    responsible_user_id: UUID | None = Field(default=None, description="Set → Dt 4730, else 9430 (13 §2.12)")
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class WriteOffCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WriteOffLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    lot_id: UUID | None
    expiry_date: date | None = Field(description="Expiry of the named lot (US-M04-06)")
    qty: str
    reason: str
    gift_kind: str | None
    cost_amount: str


class WriteOffOut(BaseModel):
    id: UUID
    number: str | None
    status: WriteOffStatus
    doc_date: date
    branch_id: UUID
    warehouse_id: UUID
    responsible_user_id: UUID | None
    promo_order_ref: str | None
    source_return_id: UUID | None
    comment: str | None
    line_count: int
    total_cost: str
    approval_request_id: UUID | None = Field(description="202 path: pending write_off_over_limit request")
    approval_status: str | None
    created_by: UUID
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None
    lines: list[WriteOffLineOut]


class WriteOffPage(BaseModel):
    items: list[WriteOffOut]
    next_cursor: str | None


# --- routes --------------------------------------------------------------------------------------
@router.post(
    "/write-offs", operation_id="inventory_create_write_off", response_model=WriteOffOut, status_code=201
)
async def create_write_off(
    request: Request, response: Response, body: WriteOffCreate, actor: Actor, scope: Scope, _: CanWriteOff
) -> dict[str, Any]:
    doc = await _module(request).write_offs.create(
        actor,
        scope,
        warehouse_id=body.warehouse_id,
        doc_date=body.doc_date,
        lines=[
            WriteOffLineInput(ln.product_id, Decimal(ln.qty), ln.reason, ln.gift_kind, ln.lot_id)
            for ln in body.lines
        ],
        responsible_user_id=body.responsible_user_id,
        promo_order_ref=body.promo_order_ref,
        comment=body.comment,
        ip=_ip(request),
    )
    response.headers["Location"] = f"{request.url.path}/{doc['id']}"
    return doc


@router.get("/write-offs", operation_id="inventory_list_write_offs", response_model=WriteOffPage)
async def list_write_offs(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    status: WriteOffStatus | None = None,
    warehouse_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _module(request).write_offs.page(
        actor, scope, status=status, warehouse_id=warehouse_id, cursor=cursor, limit=limit
    )


@router.get("/write-offs/{doc_id}", operation_id="inventory_get_write_off", response_model=WriteOffOut)
async def get_write_off(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await _module(request).write_offs.get(actor, scope, doc_id)


@router.post(
    "/write-offs/{doc_id}/post",
    operation_id="inventory_post_write_off",
    response_model=WriteOffOut,
    responses={
        202: {"model": WriteOffOut, "description": "Over the stock.writeoff limit — approval requested"}
    },
)
async def post_write_off(
    request: Request,
    doc_id: UUID,
    actor: Actor,
    scope: Scope,
    grant: CanWriteOff,
    body: EmptyBody | None = None,
) -> Any:
    result = await _module(request).write_offs.post(actor, scope, doc_id, grant.limit_value, _ip(request))
    if result.status_code == 202:
        return JSONResponse(WriteOffOut.model_validate(result.body).model_dump(mode="json"), status_code=202)
    return result.body


@router.post(
    "/write-offs/{doc_id}/cancel", operation_id="inventory_cancel_write_off", response_model=WriteOffOut
)
async def cancel_write_off(
    request: Request, doc_id: UUID, body: WriteOffCancel, actor: Actor, scope: Scope, _: CanWriteOff
) -> dict[str, Any]:
    return await _module(request).write_offs.cancel(actor, scope, doc_id, body.reason, _ip(request))
