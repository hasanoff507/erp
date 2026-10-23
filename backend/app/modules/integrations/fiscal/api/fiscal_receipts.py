"""Fiscal receipt status and manual retry (18 §14, BO-14; POS-04/POS-13 reprint lookup). Tag ``sales`` (M01).

``GET`` — ``reports.sales.view`` or ``sales.create`` (branch scope applies); ``POST …/retry`` —
``integrations.retry`` + ``Idempotency-Key``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.integrations.fiscal.application.outbox import FiscalReceiptQueries
from app.modules.integrations.fiscal.application.ports import ReceiptFilter

router = APIRouter(tags=["sales"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanRetry = Annotated[PermissionGrant, Depends(require_permission("integrations.retry"))]
Kind = Literal["sale", "return", "z_report", "debt_settlement", "credit_sale"]
Status = Literal["pending", "sent", "fiscalized", "failed"]


def require_any(*codes: str) -> Callable[..., Awaitable[frozenset[str]]]:
    """The caller holds at least one of ``codes`` (token scope prefix + live ``role_permissions``)."""

    async def dependency(request: Request, principal: Actor) -> frozenset[str]:
        gateway = auth_gateway(request)
        found = {
            code
            for code in codes
            if principal.has_scope(code.split(".", 1)[0]) and await gateway.permission_limits(principal, code)
        }
        if not found:
            raise AppError(
                ErrorCode.PERMISSION_DENIED, params={"permission": codes[0], "any_of": list(codes)}
            )
        return frozenset(found)

    dependency.__name__ = "require_any_" + "_".join(c.replace(".", "_") for c in codes)
    return dependency


CanRead = Annotated[frozenset[str], Depends(require_any("reports.sales.view", "sales.create"))]


class FiscalRetryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiscalReceiptOut(BaseModel):
    id: UUID
    sale_id: UUID | None
    debt_payment_id: UUID | None
    return_id: UUID | None
    kind: Kind
    status: Status
    receipt_seq: int | None = Field(description="Device number (qaror #12)")
    fm_terminal_id: str | None
    fm_receipt_seq: int | None = Field(description="Fiscal module number — separate from receipt_seq")
    fiscal_sign: str | None
    qr_url: str | None
    payment_form: Literal["cash", "card", "qr", "mixed"] | None
    delivery: Literal["printed", "electronic"]
    fiscal_at: str | None
    ofd_acked_at: str | None = Field(description="NULL — counted by the 48 h timer (18 §4.10)")
    sent_at: str | None
    offline_since: str | None
    attempts: int
    cash_register_id: UUID | None
    shift_id: UUID | None
    created_at: str


class FiscalReceiptPage(BaseModel):
    items: list[FiscalReceiptOut]
    next_cursor: str | None


class FiscalRetryOut(BaseModel):
    status: Literal["requeued"]


def fiscal_queries(request: Request) -> FiscalReceiptQueries:
    queries: FiscalReceiptQueries | None = getattr(request.app.state, "fiscal", None)
    if queries is None:
        raise RuntimeError("fiscal module is not configured (app.state.fiscal)")
    return queries


def _branches(scope: BranchScope) -> tuple[UUID, ...] | None:
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/fiscal-receipts", operation_id="sales_list_fiscal_receipts", response_model=FiscalReceiptPage)
async def list_fiscal_receipts(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanRead,
    sale_id: UUID | None = None,
    debt_payment_id: UUID | None = None,
    return_id: UUID | None = None,
    shift_id: UUID | None = None,
    kind: Kind | None = None,
    status: Status | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = ReceiptFilter(
        branch_ids=_branches(scope), sale_id=sale_id, return_id=return_id, debt_payment_id=debt_payment_id,
        shift_id=shift_id, kind=kind, status=status,
    )  # fmt: skip
    return await fiscal_queries(request).list_page(actor.tenant_id, actor.user_id, flt, cursor, limit)


@router.get(
    "/fiscal-receipts/{receipt_id}", operation_id="sales_get_fiscal_receipt", response_model=FiscalReceiptOut
)
async def get_fiscal_receipt(
    request: Request, receipt_id: UUID, actor: Actor, scope: Scope, _: CanRead
) -> dict[str, Any]:
    return await fiscal_queries(request).get(actor.tenant_id, actor.user_id, scope, receipt_id)


@router.post(
    "/fiscal-receipts/{receipt_id}/retry",
    operation_id="sales_retry_fiscal_receipt",
    response_model=FiscalRetryOut,
)
async def retry_fiscal_receipt(
    request: Request,
    receipt_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanRetry,
    body: FiscalRetryBody | None = None,
) -> dict[str, Any]:
    return await fiscal_queries(request).retry(
        actor.tenant_id, actor.user_id, scope, receipt_id, _ip(request)
    )
