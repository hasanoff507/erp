"""BO-14 «Sinxron istisnolari» — ``GET /sync-exceptions``, ``POST /sync-exceptions/{id}/review``
(20 #40f/#40g). Tag ``branches`` (17 §11: M13a/M14 tenant settings). Permission ``settings.tenant``
**or** ``accounting.post``."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.sync.application.module import SyncModule
from app.modules.sync.application.ports import ExceptionFilter

router = APIRouter(tags=["branches"])

REVIEW_PERMISSIONS = ("settings.tenant", "accounting.post")


async def can_review(
    request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
) -> Principal:
    """20 #40f/#40g: ``settings.tenant`` or ``accounting.post`` (token scope first, then the live grants)."""
    gateway = auth_gateway(request)
    for code in REVIEW_PERMISSIONS:
        if principal.has_scope(code.split(".", 1)[0]) and await gateway.permission_limits(principal, code):
            return principal
    raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": " | ".join(REVIEW_PERMISSIONS)})


Reviewer = Annotated[Principal, Depends(can_review)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Note = Annotated[str, StringConstraints(min_length=1, max_length=500, strip_whitespace=True)]

ExceptionKind = Literal[
    "price_mismatch", "archived_product", "stock_negative", "debt_limit_exceeded_offline",
    "approval_limit_exceeded_offline", "receipt_seq_conflict", "debt_overpayment_offline",
    "debt_allocation_mismatch", "late_in_closed_period", "cost_unknown", "count_late_move",
    "card_result_mismatch", "card_orphan_transaction", "actor_unverified", "late_in_closed_shift",
]  # fmt: skip


def _module(request: Request) -> SyncModule:
    module: SyncModule | None = getattr(request.app.state, "sync", None)
    if module is None:
        raise RuntimeError("sync module is not configured (app.state.sync)")
    return module


class SyncExceptionOut(BaseModel):
    id: UUID
    kind: ExceptionKind
    device_id: UUID | None
    branch_id: UUID | None
    client_event_id: UUID | None
    doc_type: str | None
    doc_id: UUID | None
    details: dict[str, Any]
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: UUID | None
    review_note: str | None


class SyncExceptionPage(BaseModel):
    items: list[SyncExceptionOut]
    next_cursor: str | None


class SyncExceptionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_note: Note


class SyncExceptionReviewed(BaseModel):
    id: UUID
    reviewed_at: datetime
    reviewed_by: UUID
    review_note: str


@router.get(
    "/sync-exceptions", operation_id="branches_list_sync_exceptions", response_model=SyncExceptionPage
)
async def list_sync_exceptions(
    request: Request,
    actor: Reviewer,
    scope: Scope,
    reviewed: bool | None = None,
    branch_id: UUID | None = None,
    device_id: UUID | None = None,
    created_at__gte: AwareDatetime | None = None,
    created_at__lte: AwareDatetime | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = ExceptionFilter(reviewed, branch_id, device_id, created_at__gte, created_at__lte)
    return await _module(request).exceptions.page(actor, scope, flt, cursor, limit)


@router.post(
    "/sync-exceptions/{exception_id}/review",
    operation_id="branches_review_sync_exception",
    response_model=SyncExceptionReviewed,
)
async def review_sync_exception(
    request: Request, exception_id: UUID, body: SyncExceptionReview, actor: Reviewer, scope: Scope
) -> dict[str, Any]:
    ip = request.client.host if request.client else None
    return await _module(request).exceptions.review(actor, scope, exception_id, body.review_note, ip)
