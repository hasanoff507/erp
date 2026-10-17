"""Approval queue (BO-16) — 18 §9. Tag ``approvals`` (M13).

Online only (18 §9.6). Writes need ``Idempotency-Key``. ``approve`` is a PIN step-up of the approver
(``PIN_INVALID``). Who sees/decides what follows 15 §2.3 (kind → approver permission + limit).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.access.application.approvals import ApprovalRequestService, NewRequest

router = APIRouter(tags=["approvals"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Kind = Literal[
    "discount_over_limit",
    "return_over_limit",
    "return_no_receipt",
    "debt_over_limit",
    "cash_withdrawal_over_limit",
    "price_change",
    "expense_over_limit",
    "write_off_over_limit",
    "card_manual_entry",
]
Status = Literal["pending", "approved", "rejected", "expired", "consumed"]
DocType = Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,64}$")]


class ApprovalRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    context: dict[str, Any] = Field(
        description="Snapshot; the value in amount (so'm) or requested_pct (discount), decimal string",
        max_length=50,
    )
    linked_doc_type: DocType | None = None
    linked_doc_id: UUID | None = None


class ApprovalRequestCreated(BaseModel):
    id: UUID
    kind: Kind
    status: Literal["pending"]
    expires_at: str


class ApprovalRequestOut(BaseModel):
    id: UUID
    branch_id: UUID
    kind: Kind
    permission_code: str
    requested_value: str | None
    context: dict[str, Any]
    linked_doc_type: str | None
    linked_doc_id: UUID | None
    device_id: UUID | None
    status: Status
    requested_by: UUID
    requested_by_name: str | None
    requested_at: str
    expires_at: str
    resolved_by: UUID | None
    resolved_at: str | None
    reject_reason: str | None
    consumed_at: str | None


class ApprovalRequestPage(BaseModel):
    items: list[ApprovalRequestOut]
    next_cursor: str | None


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: Annotated[str, StringConstraints(pattern=r"^[0-9]{4,6}$")]


class ApproveOut(BaseModel):
    id: UUID
    status: Literal["approved"]
    resolved_by: UUID
    resolved_at: str


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class RejectOut(BaseModel):
    id: UUID
    status: Literal["rejected"]


def approvals(request: Request) -> ApprovalRequestService:
    service: ApprovalRequestService | None = getattr(request.app.state, "approvals", None)
    if service is None:
        raise RuntimeError("approvals are not configured (app.state.approvals)")
    return service


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/approval-requests",
    operation_id="approvals_create_request",
    response_model=ApprovalRequestCreated,
    status_code=201,
)
async def create_request(
    request: Request, body: ApprovalRequestIn, actor: Actor, scope: Scope
) -> dict[str, Any]:
    return await approvals(request).create(
        actor,
        scope,
        NewRequest(body.kind, body.context, body.linked_doc_type, body.linked_doc_id),
        _ip(request),
    )


@router.get("/approval-requests", operation_id="approvals_list_requests", response_model=ApprovalRequestPage)
async def list_requests(
    request: Request,
    actor: Actor,
    scope: Scope,
    status: Status | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await approvals(request).list_page(actor, scope, status, cursor, limit)


@router.get(
    "/approval-requests/{request_id}", operation_id="approvals_get_request", response_model=ApprovalRequestOut
)
async def get_request(request: Request, request_id: UUID, actor: Actor, scope: Scope) -> dict[str, Any]:
    return await approvals(request).get(actor, scope, request_id)


@router.post(
    "/approval-requests/{request_id}/approve",
    operation_id="approvals_approve_request",
    response_model=ApproveOut,
)
async def approve_request(
    request: Request, request_id: UUID, body: ApproveIn, actor: Actor, scope: Scope
) -> dict[str, Any]:
    return await approvals(request).approve(actor, scope, request_id, body.pin, _ip(request))


@router.post(
    "/approval-requests/{request_id}/reject",
    operation_id="approvals_reject_request",
    response_model=RejectOut,
)
async def reject_request(
    request: Request, request_id: UUID, body: RejectIn, actor: Actor, scope: Scope
) -> dict[str, Any]:
    return await approvals(request).reject(actor, scope, request_id, body.reason, _ip(request))
