"""Transfers (19 §13). Tag ``transfers`` (17 §11, M06)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import QtyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.inventory.application.module import InventoryModule
from app.modules.inventory.application.transfers import ReceiveLineInput, TransferFilter, TransferLineInput

router = APIRouter(tags=["transfers"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanCreate = Annotated[PermissionGrant, Depends(require_permission("transfer.create"))]
CanReceive = Annotated[PermissionGrant, Depends(require_permission("transfer.receive"))]
Text = Annotated[str, StringConstraints(max_length=1000)]
Short = Annotated[str, StringConstraints(max_length=64, strip_whitespace=True)]

TransferStatus = Literal["draft", "posted", "sent", "received", "discrepancy", "cancelled"]
EttnStatus = Literal[
    "pending_signature", "sending", "registered", "received", "accepted", "rejected", "cancelled", "failed"
]


def _module(request: Request) -> InventoryModule:
    module: InventoryModule | None = getattr(request.app.state, "inventory", None)
    if module is None:
        raise RuntimeError("inventory module is not configured (app.state.inventory)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --- schemas -------------------------------------------------------------------------------------
class TransferLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    qty_sent: QtyStr


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_warehouse_id: UUID
    to_warehouse_id: UUID
    doc_date: date
    transport_mode: Literal["vehicle", "on_foot_or_public"] = "vehicle"
    vehicle_plate: Short | None = Field(
        default=None, description="e-TTN rekviziti; vehicle bo'lsa post'da shart"
    )
    driver_name: Annotated[str, StringConstraints(max_length=255)] | None = None
    comment: Text | None = None
    lines: list[TransferLineIn] = Field(min_length=1, max_length=1000)


class ReceiveLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transfer_line_id: UUID
    qty_received: QtyStr


class TransferReceive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[ReceiveLineIn] = Field(min_length=1, max_length=1000)


class TransferCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LotAllocationOut(BaseModel):
    lot_id: UUID | None
    qty: str
    unit_cost: str
    pending: bool


class TransferLineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    qty_sent: str
    qty_received: str | None
    unit_cost: str | None = Field(description="Weighted average of the allocations (4 dp), set on send")
    lot_allocations: list[LotAllocationOut]


class EttnOut(BaseModel):
    id: UUID
    status: EttnStatus
    operator_doc_id: str | None


class TransferOut(BaseModel):
    id: UUID
    number: str | None
    status: TransferStatus
    doc_date: date
    branch_id: UUID
    from_branch_id: UUID
    to_branch_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    transport_mode: Literal["vehicle", "on_foot_or_public"]
    vehicle_plate: str | None
    driver_name: str | None
    ettn_ref: str | None
    ettn: EttnOut | None
    is_overdue: bool = Field(
        description="status=sent longer than settings.transfer_overdue_hours (QT-M06-05)"
    )
    comment: str | None
    created_by: UUID
    created_at: str | None
    posted_at: str | None
    sent_at: str | None
    sent_by: UUID | None
    received_at: str | None
    received_by: UUID | None
    cancelled_at: str | None
    cancel_reason: str | None
    lines: list[TransferLineOut]
    warnings: list[str] = Field(description="e.g. ETTN_CANCEL_IN_OPERATOR on cancel")


class TransferPage(BaseModel):
    items: list[TransferOut]
    next_cursor: str | None


# --- routes --------------------------------------------------------------------------------------
@router.post(
    "/transfers", operation_id="transfers_create_transfer", response_model=TransferOut, status_code=201
)
async def create_transfer(
    request: Request, response: Response, body: TransferCreate, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    doc = await _module(request).transfers.create(
        actor,
        scope,
        from_warehouse_id=body.from_warehouse_id,
        to_warehouse_id=body.to_warehouse_id,
        doc_date=body.doc_date,
        transport_mode=body.transport_mode,
        vehicle_plate=body.vehicle_plate,
        driver_name=body.driver_name,
        comment=body.comment,
        lines=[TransferLineInput(ln.product_id, Decimal(ln.qty_sent)) for ln in body.lines],
        ip=_ip(request),
    )
    response.headers["Location"] = f"{request.url.path}/{doc['id']}"
    return doc


@router.get("/transfers", operation_id="transfers_list_transfers", response_model=TransferPage)
async def list_transfers(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    status: TransferStatus | None = None,
    ettn_status: EttnStatus | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = TransferFilter(status=status, ettn_status=ettn_status, date_from=date_from, date_to=date_to)
    return await _module(request).transfers.page(actor, scope, flt, cursor, limit)


@router.get("/transfers/{doc_id}", operation_id="transfers_get_transfer", response_model=TransferOut)
async def get_transfer(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanView
) -> dict[str, Any]:
    return await _module(request).transfers.get(actor, scope, doc_id)


@router.post("/transfers/{doc_id}/post", operation_id="transfers_post_transfer", response_model=TransferOut)
async def post_transfer(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanCreate, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await _module(request).transfers.post(actor, scope, doc_id, _ip(request))


@router.post("/transfers/{doc_id}/send", operation_id="transfers_send_transfer", response_model=TransferOut)
async def send_transfer(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanCreate, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await _module(request).transfers.send(actor, scope, doc_id, _ip(request))


@router.post(
    "/transfers/{doc_id}/receive", operation_id="transfers_receive_transfer", response_model=TransferOut
)
async def receive_transfer(
    request: Request, doc_id: UUID, body: TransferReceive, actor: Actor, scope: Scope, _: CanReceive
) -> dict[str, Any]:
    lines = [ReceiveLineInput(ln.transfer_line_id, Decimal(ln.qty_received)) for ln in body.lines]
    return await _module(request).transfers.receive(actor, scope, doc_id, lines, _ip(request))


@router.post(
    "/transfers/{doc_id}/cancel", operation_id="transfers_cancel_transfer", response_model=TransferOut
)
async def cancel_transfer(
    request: Request, doc_id: UUID, body: TransferCancel, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    return await _module(request).transfers.cancel(actor, scope, doc_id, body.reason, _ip(request))
