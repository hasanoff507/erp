"""E-TTN documents (19 §20; tag ``transfers``). Reads — ``stock.view``; sign / submit-signed —
``einvoice.sign``;
register-manual — ``transfer.create``; accept / reject — ``purchases.receive`` (incoming) or
``transfer.receive``
(internal) **and** ``einvoice.sign``. Every write needs ``Idempotency-Key``."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.integrations.einvoice.api.deps import (
    ChallengeId,
    EmptyBody,
    Pkcs7,
    Queued,
    Reason,
    SignChallenge,
    SubmitSigned,
    client_ip,
    edocs,
    require,
)

router = APIRouter(tags=["transfers"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanSign = Annotated[PermissionGrant, Depends(require_permission("einvoice.sign"))]
CanTransfer = Annotated[PermissionGrant, Depends(require_permission("transfer.create"))]
EttnStatus = Literal[
    "pending_signature", "sending", "registered", "received", "accepted", "rejected", "cancelled", "failed"
]


class EttnOut(BaseModel):
    id: UUID
    direction: Literal["in", "out"]
    transport_type: Literal["warehouse_to_warehouse", "seller_to_buyer", "other"]
    status: EttnStatus
    operator_doc_id: str | None
    transfer_id: UUID | None
    einvoice_id: UUID | None
    counterparty_id: UUID | None
    receipt_id: UUID | None
    doc_date: date | None
    signed_at: str | None
    last_error: str | None
    created_at: str


class EttnDetail(EttnOut):
    payload: dict[str, Any]


class EttnPage(BaseModel):
    items: list[EttnOut]
    next_cursor: str | None


class Sending(BaseModel):
    id: UUID
    status: Literal["sending"]
    signed_at: str


class ManualIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_doc_id: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    doc_date: date


class AcceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: ChallengeId
    signature_pkcs7: Pkcs7 = Field(description="base64 attached PKCS#7 over the sign-challenge?action= hash")


class RejectIn(AcceptIn):
    reason: Reason


@router.get("/ettn-documents", operation_id="transfers_list_ettn_documents", response_model=EttnPage)
async def list_ettn_documents(
    request: Request,
    actor: Actor,
    _: CanView,
    direction: Literal["in", "out"] | None = None,
    status: EttnStatus | None = None,
    transfer_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await edocs(request).ettn.list_page(
        actor, direction=direction, status=status, transfer_id=transfer_id, cursor=cursor, limit=limit
    )


@router.get(
    "/ettn-documents/{ettn_id}", operation_id="transfers_get_ettn_document", response_model=EttnDetail
)
async def get_ettn_document(request: Request, ettn_id: UUID, actor: Actor, _: CanView) -> dict[str, Any]:
    return await edocs(request).ettn.get(actor, ettn_id)


@router.post(
    "/ettn-documents/{ettn_id}/sign-challenge",
    operation_id="transfers_ettn_sign_challenge",
    response_model=SignChallenge,
)
async def ettn_sign_challenge(
    request: Request,
    ettn_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanSign,
    action: Literal["accept", "reject"] | None = None,
    body: EmptyBody | None = None,
) -> dict[str, Any]:
    return await edocs(request).ettn.sign_challenge(actor, scope, ettn_id, action)


@router.post(
    "/ettn-documents/{ettn_id}/submit-signed",
    operation_id="transfers_ettn_submit_signed",
    response_model=Sending,
    status_code=202,
)
async def ettn_submit_signed(
    request: Request, ettn_id: UUID, body: SubmitSigned, actor: Actor, scope: Scope, _: CanSign
) -> dict[str, Any]:
    return await edocs(request).ettn.submit_signed(
        actor, scope, ettn_id, body.challenge_id, body.signature_pkcs7, client_ip(request)
    )


@router.post(
    "/ettn-documents/{ettn_id}/register-manual",
    operation_id="transfers_register_ettn_manual",
    response_model=EttnOut,
)
async def register_ettn_manual(
    request: Request, ettn_id: UUID, body: ManualIn, actor: Actor, scope: Scope, _: CanTransfer
) -> dict[str, Any]:
    return await edocs(request).ettn.register_manual(
        actor, scope, ettn_id, body.operator_doc_id, body.doc_date, client_ip(request)
    )


async def _receive_permission(request: Request, actor: Principal, ettn_id: UUID) -> None:
    direction = await edocs(request).ettn.direction_of(actor, ettn_id)
    await require(request, actor, "purchases.receive" if direction == "in" else "transfer.receive")


@router.post(
    "/ettn-documents/{ettn_id}/accept",
    operation_id="transfers_accept_ettn",
    response_model=Queued,
    status_code=202,
)
async def accept_ettn(
    request: Request, ettn_id: UUID, body: AcceptIn, actor: Actor, scope: Scope, _: CanSign
) -> dict[str, Any]:
    await _receive_permission(request, actor, ettn_id)
    return await edocs(request).ettn.respond(
        actor, scope, ettn_id, "accept", body.challenge_id, body.signature_pkcs7, None, client_ip(request)
    )


@router.post(
    "/ettn-documents/{ettn_id}/reject",
    operation_id="transfers_reject_ettn",
    response_model=Queued,
    status_code=202,
)
async def reject_ettn(
    request: Request, ettn_id: UUID, body: RejectIn, actor: Actor, scope: Scope, _: CanSign
) -> dict[str, Any]:
    await _receive_permission(request, actor, ettn_id)
    return await edocs(request).ettn.respond(
        actor,
        scope,
        ettn_id,
        "reject",
        body.challenge_id,
        body.signature_pkcs7,
        body.reason,
        client_ip(request),
    )
