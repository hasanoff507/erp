"""Stock registers, valuation/stock settings, recost jobs, openings (19 §7, §16–§18). Tag ``inventory``."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import PriceStr, QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.inventory.application.module import InventoryModule
from app.modules.inventory.application.openings import OpeningLineInput
from app.modules.inventory.application.queries import BalanceFilter, LotFilter, MoveFilter

router = APIRouter(tags=["inventory"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanOpen = Annotated[PermissionGrant, Depends(require_permission("stock.opening.manage"))]
CanValuate = Annotated[PermissionGrant, Depends(require_permission("valuation.settings.manage"))]
CanPost = Annotated[PermissionGrant, Depends(require_permission("accounting.post"))]
CanCatalog = Annotated[PermissionGrant, Depends(require_permission("catalog.manage"))]
Cursor = Annotated[str | None, Query(max_length=512)]
Limit = Annotated[int, Query(ge=1, le=200)]


def inventory_module(request: Request) -> InventoryModule:
    module: InventoryModule | None = getattr(request.app.state, "inventory", None)
    if module is None:
        raise RuntimeError("inventory module is not configured (app.state.inventory)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- schemas -------------------------------------------------------------------------------------
class StockBalanceOut(BaseModel):
    product_id: UUID
    product_name: str
    warehouse_id: UUID
    qty: str
    value: str = Field(description="Register value (tannarx), 2 dp")
    avg_cost: str | None = Field(description="value / qty (4 dp); null when qty ≤ 0 (BO-03 'tannarx')")
    min_stock: str | None
    is_low: bool
    is_negative: bool = Field(description="qty < 0 — offline overselling (16 §5)")
    updated_at: str | None


class StockBalancePage(BaseModel):
    items: list[StockBalanceOut]
    next_cursor: str | None


class StockLotOut(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    warehouse_id: UUID
    received_at: str
    qty_in: str
    qty_left: str
    blocked_qty: str
    unit_cost: str
    expiry_date: date | None
    receipt_line_id: UUID | None
    source_doc_type: str
    source_doc_id: UUID


class StockLotPage(BaseModel):
    items: list[StockLotOut]
    next_cursor: str | None


class StockMoveOut(BaseModel):
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    lot_id: UUID | None
    qty: str = Field(description="Signed: receipt +, issue −")
    cost_amount: str = Field(description="Signed, 2 dp")
    doc_type: str
    doc_id: UUID
    line_id: UUID | None
    reversal_of_id: UUID | None
    moved_at: str


class StockMovePage(BaseModel):
    items: list[StockMoveOut]
    next_cursor: str | None


Method = Literal["fifo", "aveco"]


class PendingChange(BaseModel):
    method: Method
    effective_from: date


class ValuationSettingsOut(BaseModel):
    current_method: Method
    effective_from: date | None
    pending_change: PendingChange | None


class ValuationSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Method


# 19 §17 /stock-settings — EAN-13 `PP CCCCC VVVVV K` weight-barcode templates (US-M09-06)
WeightPrefix = Annotated[str, StringConstraints(pattern=r"^2[0-9]$")]


class WeightBarcodeTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefixes: list[WeightPrefix] = Field(min_length=1, max_length=10, description="2 digits, 20–29")
    item_code_len: int = Field(default=5, ge=4, le=6, description="PLU code length")
    value_len: int = Field(default=5, ge=4, le=6, description="item_code_len + value_len = 10 (EAN-13)")
    value_kind: Literal["WEIGHT", "AMOUNT"]
    decimals: int = Field(ge=0, le=3, description="WEIGHT: 3 (grams → kg); AMOUNT: 0 (so'm)")
    enabled: bool = True


class StockSettingsOut(BaseModel):
    weight_barcode_templates: list[WeightBarcodeTemplate]
    low_stock_check_enabled: bool
    expiry_warning_days: int
    version: int = Field(description="tenants.version — send it back in PATCH (17 §8)")


class StockSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_barcode_templates: list[WeightBarcodeTemplate] | None = Field(default=None, max_length=10)
    low_stock_check_enabled: bool | None = None
    expiry_warning_days: int | None = Field(default=None, ge=0, le=365)
    version: int


class RecostJobOut(BaseModel):
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    from_date: date
    status: str
    reason_doc_type: str
    reason_doc_id: UUID
    attempts: int
    last_error: str | None
    created_at: str
    finished_at: str | None


class RecostJobPage(BaseModel):
    items: list[RecostJobOut]
    next_cursor: str | None


class RecostJobDetail(RecostJobOut):
    ledger_entries: list[dict[str, Any]] = Field(description="Storno + new cost lines tagged recost_job_id")
    stock_moves: list[dict[str, Any]] = Field(
        description="Settlement moves of the job's (warehouse, product)"
    )


class OpeningLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    qty: QtyStr
    unit_cost: PriceStr
    expiry_date: date | None = None


class OpeningCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID
    doc_date: date
    lines: list[OpeningLineIn] = Field(min_length=1, max_length=5000)
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class OpeningCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpeningLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    qty: str
    unit_cost: str
    amount: str
    expiry_date: date | None


class OpeningOut(BaseModel):
    id: UUID
    number: str | None
    status: str
    doc_date: date
    branch_id: UUID
    warehouse_id: UUID
    comment: str | None
    line_count: int
    total_amount: str
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None
    lines: list[OpeningLineOut]


class OpeningSummary(BaseModel):
    id: UUID
    number: str | None
    status: str
    doc_date: date
    branch_id: UUID
    warehouse_id: UUID
    comment: str | None
    line_count: int
    total_amount: str
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class OpeningPage(BaseModel):
    items: list[OpeningSummary]
    next_cursor: str | None


# --- stock registers (19 §7) ---------------------------------------------------------------------
@router.get("/stock-balances", operation_id="inventory_list_stock_balances", response_model=StockBalancePage)
async def list_stock_balances(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    warehouse_id: UUID | None = None,
    product_id: UUID | None = None,
    low_stock: bool = False,
    search: Annotated[str | None, Query(max_length=255)] = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    flt = BalanceFilter(product_id=product_id, search=(search or "").strip() or None, low_stock=low_stock)
    return await inventory_module(request).queries.balances(actor, scope, warehouse_id, flt, cursor, limit)


@router.get("/stock-lots", operation_id="inventory_list_stock_lots", response_model=StockLotPage)
async def list_stock_lots(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    warehouse_id: UUID | None = None,
    product_id: UUID | None = None,
    expiring_within_days: Annotated[int | None, Query(ge=0, le=3650)] = None,
    include_empty: bool = False,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    flt = LotFilter(
        product_id=product_id, expiring_within_days=expiring_within_days, include_empty=include_empty
    )
    return await inventory_module(request).queries.lots(actor, scope, warehouse_id, flt, cursor, limit)


@router.get("/stock-moves", operation_id="inventory_list_stock_moves", response_model=StockMovePage)
async def list_stock_moves(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    warehouse_id: UUID | None = None,
    product_id: UUID | None = None,
    doc_type: Annotated[str | None, Query(max_length=64)] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    flt = MoveFilter(product_id=product_id, doc_type=doc_type, date_from=date_from, date_to=date_to)
    return await inventory_module(request).queries.moves(actor, scope, warehouse_id, flt, cursor, limit)


# --- valuation settings (19 §17) -----------------------------------------------------------------
@router.get(
    "/valuation-settings",
    operation_id="inventory_get_valuation_settings",
    response_model=ValuationSettingsOut,
)
async def get_valuation_settings(request: Request, actor: Actor, _: CanView) -> dict[str, Any]:
    return await inventory_module(request).valuation.settings(actor)


@router.patch(
    "/valuation-settings",
    operation_id="inventory_update_valuation_settings",
    response_model=ValuationSettingsOut,
)
async def update_valuation_settings(
    request: Request, body: ValuationSettingsPatch, actor: Actor, _: CanValuate
) -> dict[str, Any]:
    return await inventory_module(request).valuation.change(actor, body.method, _ip(request))


@router.get("/stock-settings", operation_id="inventory_get_stock_settings", response_model=StockSettingsOut)
async def get_stock_settings(request: Request, actor: Actor, _: CanView) -> dict[str, Any]:
    return await inventory_module(request).stock_settings.get(actor)


@router.patch(
    "/stock-settings", operation_id="inventory_update_stock_settings", response_model=StockSettingsOut
)
async def update_stock_settings(
    request: Request, body: StockSettingsPatch, actor: Actor, _: CanCatalog
) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True, exclude={"version"})
    for key in ("weight_barcode_templates", "low_stock_check_enabled", "expiry_warning_days"):
        if key in patch and patch[key] is None:
            del patch[key]  # null = unchanged
    return await inventory_module(request).stock_settings.update(actor, body.version, patch, _ip(request))


# --- recost jobs (19 §18) ------------------------------------------------------------------------
RecostStatus = Literal["queued", "running", "done", "failed", "rejected_period_closed"]


@router.get("/recost-jobs", operation_id="inventory_list_recost_jobs", response_model=RecostJobPage)
async def list_recost_jobs(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    status: RecostStatus | None = None,
    warehouse_id: UUID | None = None,
    product_id: UUID | None = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    return await inventory_module(request).recost.page(
        actor,
        scope,
        status=status,
        warehouse_id=warehouse_id,
        product_id=product_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/recost-jobs/{job_id}", operation_id="inventory_get_recost_job", response_model=RecostJobDetail)
async def get_recost_job(
    request: Request, job_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await inventory_module(request).recost.get(actor, scope, job_id)


@router.post(
    "/recost-jobs/{job_id}/retry", operation_id="inventory_retry_recost_job", response_model=RecostJobOut
)
async def retry_recost_job(
    request: Request, job_id: UUID, actor: Actor, scope: Scope, _: CanPost, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await inventory_module(request).recost.retry(actor, scope, job_id, _ip(request))


# --- stock openings (19 §16) ---------------------------------------------------------------------
@router.post(
    "/stock-openings",
    operation_id="inventory_create_stock_opening",
    response_model=OpeningOut,
    status_code=201,
)
async def create_stock_opening(
    request: Request, response: Response, body: OpeningCreate, actor: Actor, scope: Scope, _: CanOpen
) -> dict[str, Any]:
    lines = [
        OpeningLineInput(ln.product_id, Decimal(ln.qty), Decimal(ln.unit_cost), ln.expiry_date)
        for ln in body.lines
    ]
    doc = await inventory_module(request).openings.create(
        actor, scope, body.warehouse_id, body.doc_date, lines, body.comment, _ip(request)
    )
    response.headers["Location"] = f"{request.url.path}/{doc['id']}"
    return doc


@router.get("/stock-openings", operation_id="inventory_list_stock_openings", response_model=OpeningPage)
async def list_stock_openings(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanOpen,
    status: Literal["draft", "posted", "cancelled"] | None = None,
    warehouse_id: UUID | None = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    return await inventory_module(request).openings.page(
        actor, scope, status=status, warehouse_id=warehouse_id, cursor=cursor, limit=limit
    )


@router.get("/stock-openings/{doc_id}", operation_id="inventory_get_stock_opening", response_model=OpeningOut)
async def get_stock_opening(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanOpen
) -> dict[str, Any]:
    return await inventory_module(request).openings.get(actor, scope, doc_id)


@router.post(
    "/stock-openings/{doc_id}/post", operation_id="inventory_post_stock_opening", response_model=OpeningOut
)
async def post_stock_opening(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanOpen, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await inventory_module(request).openings.post(actor, scope, doc_id, _ip(request))


@router.post(
    "/stock-openings/{doc_id}/cancel",
    operation_id="inventory_cancel_stock_opening",
    response_model=OpeningOut,
)
async def cancel_stock_opening(
    request: Request, doc_id: UUID, body: OpeningCancel, actor: Actor, scope: Scope, _: CanOpen
) -> dict[str, Any]:
    return await inventory_module(request).openings.cancel(actor, scope, doc_id, body.reason, _ip(request))
