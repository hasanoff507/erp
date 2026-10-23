"""M10 VAT reads — ``GET /reports/vat-summary``, ``GET /vat-moves`` (20 #1–#2); ``tax.vat.view``."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.vat.application.vat import VatService

router = APIRouter(tags=["tax"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanView = Annotated[PermissionGrant, Depends(require_permission("tax.vat.view"))]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Period = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")]
DocType = Literal["sales", "goods_receipts", "returns", "supplier_returns", "write_offs", "supplier_payments"]


class VatSummaryOut(BaseModel):
    period: str
    regime: Literal["vat", "turnover"]
    output_vat: str | None
    input_vat: str | None
    net_vat: str | None
    pending_credit_red_invoices: int | None
    pending_credit_pct: str | None
    turnover_base: str | None
    turnover_rate_pct: str | None
    turnover_amount: str | None
    tax_settlement_id: UUID | None


class VatMoveOut(BaseModel):
    id: UUID
    kind: Literal["output", "input"]
    period: str
    base_amount: str
    vat_amount: str
    doc_type: str
    doc_id: UUID
    einvoice_id: UUID | None
    created_at: str


class VatMovePage(BaseModel):
    items: list[VatMoveOut]
    next_cursor: str | None


def vat_service(request: Request) -> VatService:
    service: VatService | None = getattr(request.app.state, "vat", None)
    if service is None:
        raise RuntimeError("vat module is not configured (app.state.vat)")
    return service


@router.get("/reports/vat-summary", operation_id="tax_get_vat_summary", response_model=VatSummaryOut)
async def vat_summary(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    period: Period,
    branch_id: UUID | None = None,
) -> dict[str, Any]:
    return await vat_service(request).summary(actor, period, branch_id, scope)


@router.get("/vat-moves", operation_id="tax_list_vat_moves", response_model=VatMovePage)
async def list_vat_moves(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    kind: Literal["output", "input"] | None = None,
    period: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    doc_type: DocType | None = None,
    einvoice_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    if not scope.unrestricted:  # vat_moves are tenant-wide (no branch) — SEC-11
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "tenant_wide_vat"})
    return await vat_service(request).moves(
        actor,
        kind=kind,
        period_raw=period,
        doc_type=doc_type,
        einvoice_id=einvoice_id,
        cursor=cursor,
        limit=limit,
    )
