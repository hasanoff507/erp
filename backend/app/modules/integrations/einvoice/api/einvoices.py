"""E-invoices (19 §19 incoming — tag ``purchasing``; 18 §14a outgoing — tag ``sales``).

Reads: incoming — ``purchases.post``; outgoing — ``einvoice.sign`` or ``purchases.post``. Risk flag, accept,
reject — ``purchases.post``; sign-challenge / submit-signed / send / cancel — ``einvoice.sign``; create /
from-receipt — ``einvoice.create``. Every write needs ``Idempotency-Key``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import PercentStr, PriceStr, QtyStr
from app.core.permissions import PermissionGrant, require_permission
from app.modules.integrations.einvoice.api.deps import (
    EmptyBody,
    Queued,
    Reason,
    SignChallenge,
    SubmitSigned,
    client_ip,
    edocs,
    require,
    require_any,
)
from app.modules.integrations.einvoice.application.einvoices import OutInput, OutLineInput

router = APIRouter()

Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanPost = Annotated[PermissionGrant, Depends(require_permission("purchases.post"))]
CanSign = Annotated[PermissionGrant, Depends(require_permission("einvoice.sign"))]
CanCreate = Annotated[PermissionGrant, Depends(require_permission("einvoice.create"))]
CanRead = Annotated[str, Depends(require_any("purchases.post", "einvoice.sign"))]
Direction = Literal["in", "out"]
Status = Literal["draft", "received", "signed", "sent", "accepted", "rejected", "cancelled"]
RiskFlag = Literal["green", "red", "unknown"]
Name = Annotated[str, StringConstraints(min_length=1, max_length=500)]
Short = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class CounterpartyRef(BaseModel):
    id: UUID
    name: str | None
    stir: str | None


class EInvoiceOut(BaseModel):
    id: UUID
    direction: Direction
    operator: Literal["faktura", "didox"]
    operator_doc_id: str | None
    counterparty_id: UUID
    counterparty: CounterpartyRef
    status: Status
    risk_flag: RiskFlag
    factura_type: Literal["standard", "additional", "corrected"]
    related_einvoice_id: UUID | None
    related_doc_type: Literal["sales", "goods_receipts", "supplier_returns"] | None
    related_doc_id: UUID | None
    number: str | None
    doc_date: date | None
    total_amount: str | None
    vat_amount: str | None
    signed_at: str | None
    signed_by: UUID | None
    last_error: str | None = Field(
        description="The operator error of the newest send/accept job (retry/failed)"
    )
    created_at: str
    updated_at: str


class EInvoiceDetail(EInvoiceOut):
    payload: dict[str, Any] = Field(
        description="Requisites and lines (MXIK, qty, net_amount, VAT, marking codes)"
    )


class EInvoicePage(BaseModel):
    items: list[EInvoiceOut]
    next_cursor: str | None


class RiskFlagIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_flag: Literal["green", "red"]
    note: Reason


class RiskFlagOut(BaseModel):
    id: UUID
    risk_flag: Literal["green", "red"]
    vat_released: str = Field(description="Input VAT written to vat_moves by this change (13 §2.8)")


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class Signed(BaseModel):
    id: UUID
    status: Literal["signed"]
    signed_at: str


class OutLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    qty: QtyStr
    price: PriceStr = Field(description="Unit price WITHOUT VAT, 4 dp")
    vat_rate: PercentStr = Field(description='"12.00" / "0.00"')
    product_id: UUID | None = None
    mxik: Annotated[str, StringConstraints(pattern=r"^[0-9]{17}$")] | None = None
    unit_code: Short | None = None


class EInvoiceCreate(BaseModel):
    """18 §14a ``POST /einvoices`` (outgoing). With ``related_doc_id`` (a posted sale) the lines default to
    the
    receipt less returns and may not exceed it."""

    model_config = ConfigDict(extra="forbid")

    direction: Literal["out"] = "out"
    counterparty_id: UUID
    related_doc_type: Literal["sales"] | None = None
    related_doc_id: UUID | None = None
    doc_date: date | None = None
    lines: list[OutLineIn] | None = Field(default=None, min_length=1, max_length=1000)


class FromReceiptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_id: UUID
    counterparty_id: UUID


class CancelOut(BaseModel):
    id: UUID
    status: Literal["cancelled"]


@router.get(
    "/einvoices", operation_id="purchasing_list_einvoices", response_model=EInvoicePage, tags=["purchasing"]
)
async def list_einvoices(
    request: Request,
    actor: Actor,
    granted: CanRead,
    direction: Direction | None = None,
    status: Status | None = None,
    risk_flag: RiskFlag | None = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    if direction != "out" and granted != "purchases.post":
        await require(request, actor, "purchases.post")  # incoming e-invoices — Buxgalter (19 §19)
    return await edocs(request).einvoices.list_page(
        actor, direction=direction, status=status, risk_flag=risk_flag, cursor=cursor, limit=limit
    )


@router.get(
    "/einvoices/{einvoice_id}",
    operation_id="purchasing_get_einvoice",
    response_model=EInvoiceDetail,
    tags=["purchasing"],
)
async def get_einvoice(request: Request, einvoice_id: UUID, actor: Actor, granted: CanRead) -> dict[str, Any]:
    body: dict[str, Any] = await edocs(request).einvoices.get(actor, einvoice_id)
    if body["direction"] == "in" and granted != "purchases.post":
        await require(request, actor, "purchases.post")
    return body


@router.patch(
    "/einvoices/{einvoice_id}/risk-flag",
    operation_id="purchasing_set_einvoice_risk_flag",
    response_model=RiskFlagOut,
    tags=["purchasing"],
)
async def set_risk_flag(
    request: Request, einvoice_id: UUID, body: RiskFlagIn, actor: Actor, _: CanPost
) -> dict[str, Any]:
    return await edocs(request).einvoices.set_risk_flag(
        actor, einvoice_id, body.risk_flag, body.note, client_ip(request)
    )


@router.post(
    "/einvoices/{einvoice_id}/accept",
    operation_id="purchasing_accept_einvoice",
    response_model=Queued,
    status_code=202,
    tags=["purchasing"],
)
async def accept_einvoice(
    request: Request, einvoice_id: UUID, actor: Actor, _: CanPost, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await edocs(request).einvoices.accept(actor, einvoice_id, client_ip(request))


@router.post(
    "/einvoices/{einvoice_id}/reject",
    operation_id="purchasing_reject_einvoice",
    response_model=Queued,
    status_code=202,
    tags=["purchasing"],
)
async def reject_einvoice(
    request: Request, einvoice_id: UUID, body: RejectIn, actor: Actor, _: CanPost
) -> dict[str, Any]:
    return await edocs(request).einvoices.reject(actor, einvoice_id, body.reason, client_ip(request))


@router.post(
    "/einvoices/{einvoice_id}/sign-challenge",
    operation_id="purchasing_einvoice_sign_challenge",
    response_model=SignChallenge,
    tags=["purchasing"],
)
async def einvoice_sign_challenge(
    request: Request, einvoice_id: UUID, actor: Actor, _: CanSign, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await edocs(request).einvoices.sign_challenge(actor, einvoice_id)


@router.post(
    "/einvoices/{einvoice_id}/submit-signed",
    operation_id="purchasing_einvoice_submit_signed",
    response_model=Signed,
    tags=["purchasing"],
)
async def einvoice_submit_signed(
    request: Request, einvoice_id: UUID, body: SubmitSigned, actor: Actor, _: CanSign
) -> dict[str, Any]:
    return await edocs(request).einvoices.submit_signed(
        actor, einvoice_id, body.challenge_id, body.signature_pkcs7, client_ip(request)
    )


@router.post(
    "/einvoices",
    operation_id="sales_create_einvoice",
    response_model=EInvoiceDetail,
    status_code=201,
    tags=["sales"],
)
async def create_einvoice(
    request: Request, body: EInvoiceCreate, actor: Actor, _: CanCreate
) -> dict[str, Any]:
    data = OutInput(
        counterparty_id=body.counterparty_id,
        doc_date=body.doc_date,
        related_doc_type=body.related_doc_type,
        related_doc_id=body.related_doc_id,
        lines=None
        if body.lines is None
        else [
            OutLineInput(
                name=ln.name,
                qty=Decimal(ln.qty),
                price=Decimal(ln.price),
                vat_rate=Decimal(ln.vat_rate),
                product_id=ln.product_id,
                mxik=ln.mxik,
                unit_code=ln.unit_code,
            )
            for ln in body.lines
        ],
    )
    return await edocs(request).einvoices.create_out(actor, data, client_ip(request))


@router.post(
    "/einvoices/from-receipt",
    operation_id="sales_create_einvoice_from_receipt",
    response_model=EInvoiceDetail,
    status_code=201,
    tags=["sales"],
)
async def create_einvoice_from_receipt(
    request: Request, body: FromReceiptIn, actor: Actor, _: CanCreate
) -> dict[str, Any]:
    return await edocs(request).einvoices.from_receipt(
        actor, body.sale_id, body.counterparty_id, client_ip(request)
    )


@router.post(
    "/einvoices/{einvoice_id}/send",
    operation_id="sales_send_einvoice",
    response_model=Queued,
    status_code=202,
    tags=["sales"],
)
async def send_einvoice(
    request: Request, einvoice_id: UUID, actor: Actor, _: CanSign, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await edocs(request).einvoices.send(actor, einvoice_id, client_ip(request))


@router.post(
    "/einvoices/{einvoice_id}/cancel",
    operation_id="sales_cancel_einvoice",
    response_model=CancelOut,
    tags=["sales"],
)
async def cancel_einvoice(
    request: Request, einvoice_id: UUID, body: RejectIn, actor: Actor, _: CanSign
) -> dict[str, Any]:
    return await edocs(request).einvoices.cancel(actor, einvoice_id, body.reason, client_ip(request))
