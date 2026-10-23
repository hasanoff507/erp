"""Powers of attorney — e-ishonchnoma (19 §8a; tag ``purchasing``). Create / cancel — ``purchases.create``;
reads — ``purchases.create`` or ``purchases.receive`` or ``purchases.post``; sign-challenge / submit-signed —
``einvoice.sign``. Every write needs ``Idempotency-Key``."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.integrations.einvoice.api.deps import (
    EmptyBody,
    Reason,
    SignChallenge,
    SubmitSigned,
    client_ip,
    edocs,
    require_any,
)
from app.modules.integrations.einvoice.application.poa import PoaInput

router = APIRouter(tags=["purchasing"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanCreate = Annotated[PermissionGrant, Depends(require_permission("purchases.create"))]
CanSign = Annotated[PermissionGrant, Depends(require_permission("einvoice.sign"))]
CanRead = Annotated[str, Depends(require_any("purchases.create", "purchases.receive", "purchases.post"))]
PoaStatus = Literal[
    "draft", "pending_signature", "sending", "sent", "accepted", "rejected", "cancelled", "failed"
]


class PoaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_order_id: UUID | None = None
    supplier_id: UUID
    employee_user_id: UUID
    doc_date: date
    valid_from: date | None = None
    valid_to: date | None = None


class SupplierRef(BaseModel):
    id: UUID
    name: str | None
    stir: str | None


class PoaOut(BaseModel):
    id: UUID
    branch_id: UUID
    purchase_order_id: UUID | None
    supplier_id: UUID
    supplier: SupplierRef
    employee_user_id: UUID
    employee_name: str | None
    doc_date: date
    valid_from: date
    valid_to: date
    number: str | None
    operator_doc_id: str | None
    status: PoaStatus
    last_error: str | None
    signed_at: str | None
    sent_at: str | None
    responded_at: str | None
    reject_reason: str | None
    created_at: str
    version: int


class PoaPage(BaseModel):
    items: list[PoaOut]
    next_cursor: str | None


class PoaState(BaseModel):
    id: UUID
    status: Literal["sending", "cancelled"]


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


@router.post(
    "/powers-of-attorney",
    operation_id="purchasing_create_power_of_attorney",
    response_model=PoaOut,
    status_code=201,
)
async def create_power_of_attorney(
    request: Request, response: Response, body: PoaIn, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    data = PoaInput(
        supplier_id=body.supplier_id,
        employee_user_id=body.employee_user_id,
        doc_date=body.doc_date,
        purchase_order_id=body.purchase_order_id,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
    )
    created: dict[str, Any] = await edocs(request).poa.create(actor, scope, data, client_ip(request))
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.get("/powers-of-attorney", operation_id="purchasing_list_powers_of_attorney", response_model=PoaPage)
async def list_powers_of_attorney(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanRead,
    purchase_order_id: UUID | None = None,
    supplier_id: UUID | None = None,
    status: PoaStatus | None = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await edocs(request).poa.list_page(
        actor,
        scope,
        purchase_order_id=purchase_order_id,
        supplier_id=supplier_id,
        status=status,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/powers-of-attorney/{poa_id}", operation_id="purchasing_get_power_of_attorney", response_model=PoaOut
)
async def get_power_of_attorney(
    request: Request, poa_id: UUID, actor: Actor, scope: Scope, _: CanRead
) -> dict[str, Any]:
    return await edocs(request).poa.get(actor, scope, poa_id)


@router.post(
    "/powers-of-attorney/{poa_id}/sign-challenge",
    operation_id="purchasing_poa_sign_challenge",
    response_model=SignChallenge,
)
async def poa_sign_challenge(
    request: Request, poa_id: UUID, actor: Actor, scope: Scope, _: CanSign, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await edocs(request).poa.sign_challenge(actor, scope, poa_id)


@router.post(
    "/powers-of-attorney/{poa_id}/submit-signed",
    operation_id="purchasing_poa_submit_signed",
    response_model=PoaState,
    status_code=202,
)
async def poa_submit_signed(
    request: Request, poa_id: UUID, body: SubmitSigned, actor: Actor, scope: Scope, _: CanSign
) -> dict[str, Any]:
    return await edocs(request).poa.submit_signed(
        actor, scope, poa_id, body.challenge_id, body.signature_pkcs7, client_ip(request)
    )


@router.post(
    "/powers-of-attorney/{poa_id}/cancel",
    operation_id="purchasing_cancel_power_of_attorney",
    response_model=PoaState,
)
async def cancel_power_of_attorney(
    request: Request, poa_id: UUID, body: CancelIn, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    return await edocs(request).poa.cancel(actor, scope, poa_id, body.reason, client_ip(request))
