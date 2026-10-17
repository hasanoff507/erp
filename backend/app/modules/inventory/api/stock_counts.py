"""Stock counts (19 §14). Tag ``stock-counts`` (17 §11, M05)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.inventory.application.module import InventoryModule
from app.modules.inventory.application.stock_counts import CountLineInput

router = APIRouter(tags=["stock-counts"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanCount = Annotated[PermissionGrant, Depends(require_permission("stock.count.create"))]
CanPost = Annotated[PermissionGrant, Depends(require_permission("stock.count.post"))]
CountStatus = Literal["counting", "review", "posted", "cancelled"]


def _module(request: Request) -> InventoryModule:
    module: InventoryModule | None = getattr(request.app.state, "inventory", None)
    if module is None:
        raise RuntimeError("inventory module is not configured (app.state.inventory)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- schemas -------------------------------------------------------------------------------------
class CountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID
    doc_date: date
    product_ids: list[UUID] = Field(
        default_factory=list, max_length=5000, description="Empty — the whole warehouse"
    )
    responsible_user_id: UUID | None = Field(default=None, description="Shortage → 4730 when set, else 5910")
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class CountLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID | None = None
    barcode: Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)] | None = (
        None
    )
    counted: QtyStr

    @model_validator(mode="after")
    def _product_or_barcode(self) -> CountLineIn:
        if self.product_id is None and self.barcode is None:
            raise ValueError("product_id or barcode is required")
        return self


class CountLinesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[CountLineIn] = Field(min_length=1, max_length=5000)


class CountLinePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted: QtyStr


class CountCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CountLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    snapshot_qty: str = Field(description="Balance at started_at")
    expected: str = Field(
        description="13 X-02: snapshot + moves (started_at, counted_at]; live while counting"
    )
    counted: str | None
    counted_at: str | None
    diff: str | None
    amount: str | None = Field(description="Estimated value of the difference (2 dp)")


class CountSummary(BaseModel):
    id: UUID
    number: str | None
    status: CountStatus
    doc_date: date
    branch_id: UUID
    warehouse_id: UUID
    started_at: str | None
    responsible_user_id: UUID | None
    comment: str | None
    line_count: int
    counted_count: int
    uncounted_count: int
    created_by: UUID
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class CountOut(CountSummary):
    lines: list[CountLineOut]


class CountPage(BaseModel):
    items: list[CountSummary]
    next_cursor: str | None


class PostedLineOut(BaseModel):
    line_id: UUID
    product_id: UUID
    expected: str
    counted: str
    diff: str
    amount: str


class CountPostOut(BaseModel):
    id: UUID
    number: str
    status: Literal["posted"]
    shortage_lines: list[PostedLineOut]
    surplus_lines: list[PostedLineOut]


# --- routes --------------------------------------------------------------------------------------
@router.post(
    "/stock-counts", operation_id="stock_counts_create_stock_count", response_model=CountOut, status_code=201
)
async def create_stock_count(
    request: Request, response: Response, body: CountCreate, actor: Actor, scope: Scope, _: CanCount
) -> dict[str, Any]:
    doc = await _module(request).stock_counts.create(
        actor,
        scope,
        warehouse_id=body.warehouse_id,
        doc_date=body.doc_date,
        product_ids=body.product_ids,
        responsible_user_id=body.responsible_user_id,
        comment=body.comment,
        ip=_ip(request),
    )
    response.headers["Location"] = f"{request.url.path}/{doc['id']}"
    return doc


@router.get("/stock-counts", operation_id="stock_counts_list_stock_counts", response_model=CountPage)
async def list_stock_counts(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    status: CountStatus | None = None,
    warehouse_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _module(request).stock_counts.page(
        actor, scope, status=status, warehouse_id=warehouse_id, cursor=cursor, limit=limit
    )


@router.get("/stock-counts/{doc_id}", operation_id="stock_counts_get_stock_count", response_model=CountOut)
async def get_stock_count(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await _module(request).stock_counts.get(actor, scope, doc_id)


@router.post(
    "/stock-counts/{doc_id}/lines",
    operation_id="stock_counts_record_stock_count_lines",
    response_model=CountOut,
)
async def record_stock_count_lines(
    request: Request, doc_id: UUID, body: CountLinesIn, actor: Actor, scope: Scope, _: CanCount
) -> dict[str, Any]:
    lines = [CountLineInput(ln.product_id, ln.barcode, Decimal(ln.counted)) for ln in body.lines]
    return await _module(request).stock_counts.record_lines(actor, scope, doc_id, lines, _ip(request))


@router.patch(
    "/stock-counts/{doc_id}/lines/{line_id}",
    operation_id="stock_counts_update_stock_count_line",
    response_model=CountOut,
)
async def update_stock_count_line(
    request: Request,
    doc_id: UUID,
    line_id: UUID,
    body: CountLinePatch,
    actor: Actor,
    scope: Scope,
    _: CanCount,
) -> dict[str, Any]:
    return await _module(request).stock_counts.update_line(
        actor, scope, doc_id, line_id, Decimal(body.counted), _ip(request)
    )


@router.post(
    "/stock-counts/{doc_id}/submit-for-review",
    operation_id="stock_counts_submit_stock_count",
    response_model=CountOut,
)
async def submit_stock_count(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanCount, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await _module(request).stock_counts.submit(actor, scope, doc_id, _ip(request))


@router.post(
    "/stock-counts/{doc_id}/post", operation_id="stock_counts_post_stock_count", response_model=CountPostOut
)
async def post_stock_count(
    request: Request,
    doc_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanPost,
    treat_uncounted_as_zero: bool = False,
    body: EmptyBody | None = None,
) -> dict[str, Any]:
    return await _module(request).stock_counts.post(
        actor, scope, doc_id, treat_uncounted_as_zero, _ip(request)
    )


@router.post(
    "/stock-counts/{doc_id}/cancel", operation_id="stock_counts_cancel_stock_count", response_model=CountOut
)
async def cancel_stock_count(
    request: Request, doc_id: UUID, body: CountCancel, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    return await _module(request).stock_counts.cancel(actor, scope, doc_id, body.reason, _ip(request))
