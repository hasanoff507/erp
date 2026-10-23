"""BO-14 «Fiskal» tab (18 §14.3–§14.4; 21 §0 BO-14, §1 Monitoring, §16 ``fiscal.resend_unsent``).

Tag ``sales``.

``GET /fiscal-registers`` — ``reports.sales.view`` (branch scope applies); ``POST
/cash-registers/{id}/fiscal-resend`` — ``integrations.retry`` + ``Idempotency-Key``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.integrations.fiscal.application.registers import FiscalRegisterQueries

router = APIRouter(tags=["sales"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("reports.sales.view"))]
CanRetry = Annotated[PermissionGrant, Depends(require_permission("integrations.retry"))]
FmState = Literal["ok", "locked", "ack_overdue", "memory_full", "unknown"]


class FiscalRegisterOut(BaseModel):
    cash_register_id: UUID
    name: str
    branch_id: UUID
    fiscal_agent_id: UUID | None = Field(description="Store agent of a local-bridge register (BO-12)")
    fiscal_local_device_id: str | None
    fm_state: FmState
    fm_receipts_pending: int | None = Field(description="FM's own unsent count (agent fiscal.status)")
    last_unacked_receipt_at: str | None
    unacked_count: int = Field(description="Server receipts with ofd_acked_at IS NULL (48 h timer)")
    failed_count: int
    oldest_unacked_at: str | None
    oldest_unacked_age_s: int | None


class FiscalRegisterList(BaseModel):
    items: list[FiscalRegisterOut]


class FiscalResendBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiscalResendOut(BaseModel):
    task_id: UUID
    status: Literal["queued"]


def register_queries(request: Request) -> FiscalRegisterQueries:
    queries: FiscalRegisterQueries | None = getattr(request.app.state, "fiscal_registers", None)
    if queries is None:
        raise RuntimeError("fiscal module is not configured (app.state.fiscal_registers)")
    return queries


@router.get(
    "/fiscal-registers", operation_id="sales_list_fiscal_registers", response_model=FiscalRegisterList
)
async def list_fiscal_registers(request: Request, actor: Actor, scope: Scope, _: CanView) -> dict[str, Any]:
    return await register_queries(request).list_registers(actor.tenant_id, actor.user_id, scope)


@router.post(
    "/cash-registers/{register_id}/fiscal-resend",
    operation_id="sales_resend_fiscal_unsent",
    response_model=FiscalResendOut,
    status_code=202,
)
async def resend_fiscal_unsent(
    request: Request,
    register_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanRetry,
    body: FiscalResendBody | None = None,
) -> dict[str, Any]:
    ip = request.client.host if request.client else None
    return await register_queries(request).resend(actor.tenant_id, actor.user_id, scope, register_id, ip)
