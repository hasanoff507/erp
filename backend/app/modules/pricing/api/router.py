"""Price history and price-change documents (19 §4). OpenAPI tag ``pricing`` (17 §11, M09)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import PriceStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.pricing.application.module import PricingModule
from app.modules.pricing.application.price_changes import LineInput
from app.modules.pricing.domain.price_changes import DEFAULT_APPROVAL_LIMIT_PCT

router = APIRouter(tags=["pricing"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanEdit = Annotated[PermissionGrant, Depends(require_permission("prices.edit"))]


class PriceHistoryItem(BaseModel):
    price: str
    valid_from: str
    valid_to: str | None
    set_by: UUID | None
    set_by_name: str | None = Field(
        description="Display name of the user who set the price; null for system/legacy rows (19 §4)"
    )
    price_change_doc_id: UUID | None
    branch_id: UUID | None


class PriceHistory(BaseModel):
    items: list[PriceHistoryItem]
    next_cursor: str | None


class PriceChangeLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    new_price: PriceStr
    valid_from: datetime | None = None
    branch_id: UUID | None = None


class PriceChangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_date: date
    lines: list[PriceChangeLineIn] = Field(min_length=1, max_length=1000)
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class PriceChangeLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    branch_id: UUID | None
    old_price: str
    new_price: str
    valid_from: str | None


class PriceChangeOut(BaseModel):
    id: UUID
    status: str
    number: str | None
    doc_date: str
    branch_id: UUID
    comment: str | None
    posted_at: str | None
    approval_request_id: UUID | None
    warnings: list[str]
    lines: list[PriceChangeLineOut]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def pricing_module(request: Request) -> PricingModule:
    module: PricingModule | None = getattr(request.app.state, "pricing", None)
    if module is None:
        raise RuntimeError("pricing module is not configured (app.state.pricing)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def approval_limit(request: Request, principal: Principal) -> Decimal | None:
    """The poster's ``prices.approve`` limit (most generous role; ``None`` = unlimited).

    Without any ``prices.approve`` grant the catalog default ±10% applies (26 #5, US-M09-02).
    """
    limits = await auth_gateway(request).permission_limits(principal, "prices.approve")
    if not limits:
        return DEFAULT_APPROVAL_LIMIT_PCT
    if any(limit is None for limit in limits):
        return None
    return max(limit for limit in limits if limit is not None)


@router.get(
    "/products/{product_id}/prices", operation_id="pricing_list_product_prices", response_model=PriceHistory
)
async def list_product_prices(
    request: Request,
    product_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanView,
    branch_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await pricing_module(request).price_changes.history(
        actor, scope, product_id, branch_id, cursor, limit
    )


@router.post(
    "/price-changes",
    operation_id="pricing_create_price_change",
    response_model=PriceChangeOut,
    status_code=201,
)
async def create_price_change(
    request: Request, response: Response, body: PriceChangeCreate, actor: Actor, scope: Scope, _: CanEdit
) -> dict[str, Any]:
    lines = [
        LineInput(
            product_id=ln.product_id,
            new_price=Decimal(ln.new_price),
            valid_from=ln.valid_from,
            branch_id=ln.branch_id,
        )
        for ln in body.lines
    ]
    doc = await pricing_module(request).price_changes.create(
        actor, scope, body.doc_date, lines, body.comment, _ip(request)
    )
    response.headers["Location"] = f"{request.url.path}/{doc['id']}"
    return doc


@router.post(
    "/price-changes/{doc_id}/post",
    operation_id="pricing_post_price_change",
    response_model=PriceChangeOut,
    responses={202: {"model": PriceChangeOut, "description": "pending_approval (APPROVAL_REQUIRED)"}},
)
async def post_price_change(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanEdit, body: EmptyBody | None = None
) -> Any:
    limit = await approval_limit(request, actor)
    result = await pricing_module(request).price_changes.post(actor, scope, doc_id, limit, _ip(request))
    if result.status_code == 202:
        return JSONResponse(
            PriceChangeOut.model_validate(result.body).model_dump(mode="json"), status_code=202
        )
    return result.body
