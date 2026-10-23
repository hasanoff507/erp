"""Tax settlement documents (20 #8a–#8d). Tag ``tax`` (M10). Reads — ``tax.vat.view``; writes —
``accounting.post`` with ``Idempotency-Key``. Back-office only (no sync event)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.vat.application.tax_settlements import (
    SettlementFilter,
    SettlementInput,
    TaxSettlementService,
)
from app.modules.vat.application.vat import parse_period

router = APIRouter(tags=["tax"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("tax.vat.view"))]
CanPost = Annotated[PermissionGrant, Depends(require_permission("accounting.post"))]
TaxKind = Literal["vat_offset", "turnover_tax"]
Status = Literal["draft", "posted", "cancelled"]
PeriodStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$")]


class SettlementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tax_kind: TaxKind = Field(
        description="Must match the tenant_tax_regimes row in force on the period's last day"
    )
    period: PeriodStr = Field(description="YYYY-MM")
    branch_id: UUID | None = Field(default=None, description="turnover_tax only (required there)")
    doc_date: date | None = Field(default=None, description="Inside the period; default — its last day")
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class SettlementCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SettlementOut(BaseModel):
    id: UUID
    number: str | None = Field(description="ST-… assigned on post")
    branch_id: UUID
    doc_date: str
    status: Status
    tax_kind: TaxKind
    period: str
    base_amount: str
    rate: str | None = Field(description="turnover_tax only (effective rate when a tobacco share exists)")
    amount: str
    expense_account: Literal["9430", "9820"] | None
    comment: str | None
    created_by: UUID
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class SettlementPosted(SettlementOut):
    recalculated: bool = Field(
        description="true — the amounts changed since the draft and were re-posted fresh"
    )


class SettlementPage(BaseModel):
    items: list[SettlementOut]
    next_cursor: str | None


def service(request: Request) -> TaxSettlementService:
    found: TaxSettlementService | None = getattr(request.app.state, "tax_settlements", None)
    if found is None:
        raise RuntimeError("tax settlements are not configured (app.state.tax_settlements)")
    return found


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/tax-settlements", operation_id="tax_list_tax_settlements", response_model=SettlementPage)
async def list_tax_settlements(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    tax_kind: TaxKind | None = None,
    period: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    status: Status | None = None,
    branch_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    if branch_id is not None:
        branches: tuple[UUID, ...] | None = (branch_id,)
        if not scope.unrestricted and branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
    else:
        branches = None if scope.unrestricted else scope.allowed
    flt = SettlementFilter(
        branch_ids=branches,
        tax_kind=tax_kind,
        period=None if period is None else parse_period(period),
        status=status,
    )
    return await service(request).list_page(actor, flt, cursor, limit)


@router.post(
    "/tax-settlements",
    operation_id="tax_create_tax_settlement",
    response_model=SettlementOut,
    status_code=201,
)
async def create_tax_settlement(
    request: Request, response: Response, body: SettlementIn, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    data = SettlementInput(
        tax_kind=body.tax_kind,
        period=body.period,
        branch_id=body.branch_id,
        doc_date=body.doc_date,
        comment=body.comment,
    )
    created = await service(request).create(actor, scope, data, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.get(
    "/tax-settlements/{settlement_id}", operation_id="tax_get_tax_settlement", response_model=SettlementOut
)
async def get_tax_settlement(
    request: Request, settlement_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await service(request).get(actor, scope, settlement_id)


@router.post(
    "/tax-settlements/{settlement_id}/post",
    operation_id="tax_post_tax_settlement",
    response_model=SettlementPosted,
)
async def post_tax_settlement(
    request: Request,
    settlement_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanPost,
    body: EmptyBody | None = None,
) -> dict[str, Any]:
    return await service(request).post(actor, scope, settlement_id, _ip(request))


@router.post(
    "/tax-settlements/{settlement_id}/cancel",
    operation_id="tax_cancel_tax_settlement",
    response_model=SettlementOut,
)
async def cancel_tax_settlement(
    request: Request, settlement_id: UUID, body: SettlementCancel, actor: Actor, scope: Scope, _: CanPost
) -> dict[str, Any]:
    return await service(request).cancel(actor, scope, settlement_id, body.reason, _ip(request))
