"""Supplier payments (19 §11). Tag ``purchasing`` (M07, M08). Permission ``purchases.pay`` for every route.

``POST`` is one-step (created ``posted``); ``cancel`` is a storno. Every write needs ``Idempotency-Key``.
``GET /supplier-payments/open-documents`` feeds the BO-04 allocation table (oldest first).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.money import MoneyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.purchasing.api.purchase_orders import SupplierRef
from app.modules.purchasing.application.purchase_orders import scope_branches
from app.modules.purchasing.application.supplier_payments import (
    AllocationInput,
    PaymentInput,
    SupplierPaymentService,
)
from app.modules.purchasing.application.supplier_payments_ports import PaymentFilter

router = APIRouter(tags=["purchasing"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanPay = Annotated[PermissionGrant, Depends(require_permission("purchases.pay"))]
TargetType = Literal["goods_receipts", "debt_openings"]
Method = Literal["cash", "bank"]


class AllocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_doc_type: TargetType
    target_doc_id: UUID
    amount: MoneyStr = Field(description="> 0, ≤ the document's outstanding amount")


class PaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID
    amount: MoneyStr = Field(description="> 0; above the payable debt → advance 4310 (qaror #47)")
    method: Method
    doc_date: date
    cash_register_id: UUID | None = Field(default=None, description="Required for method=cash")
    shift_id: UUID | None = Field(default=None, description="method=cash: an open shift of that register")
    allocations: list[AllocationIn] | None = Field(
        default=None,
        max_length=1000,
        description="Omitted → the server allocates the debt part oldest first; given → Σ = the debt part",
    )
    comment: Annotated[str, StringConstraints(max_length=1000)] | None = None


class PaymentCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class SupplierPaymentAllocationOut(BaseModel):
    target_doc_type: TargetType
    target_doc_id: UUID
    target_number: str | None
    target_doc_date: str | None
    amount: str
    vat_credit_unlocked: str = Field(description="Deferred input VAT of the target released by this payment")


class VatUnlocked(BaseModel):
    einvoice_id: UUID | None
    vat_amount: str


class PaymentWarning(BaseModel):
    code: Literal["SUPPLIER_OVERPAY_ADVANCE"]
    params: dict[str, str]


class PaymentOut(BaseModel):
    id: UUID
    number: str | None
    status: Literal["draft", "posted", "cancelled"]
    doc_date: str
    branch_id: UUID
    supplier_id: UUID
    supplier: SupplierRef
    method: Method
    amount: str
    cash_register_id: UUID | None
    shift_id: UUID | None
    allocations: list[SupplierPaymentAllocationOut]
    advance_amount: str = Field(description="amount − Σ allocations → Dt 4310 (13 §2.16)")
    vat_credit_unlocked: list[VatUnlocked]
    comment: str | None
    created_by: UUID
    created_by_name: str | None
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None


class PaymentCreated(PaymentOut):
    warnings: list[PaymentWarning]


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    next_cursor: str | None


class OpenDocOut(BaseModel):
    target_doc_type: TargetType
    target_doc_id: UUID
    number: str | None
    doc_date: str
    due_date: str | None
    total: str
    outstanding: str
    einvoice_id: UUID | None
    einvoice_risk_flag: Literal["green", "red", "unknown"] | None
    vat_pending: str = Field(description="Deferred input-VAT credit not released yet (13 §2.8)")


class OpenDocsOut(BaseModel):
    supplier_id: UUID
    payable_balance: str = Field(description="debt_balances(payable); negative = advance paid")
    advance_balance: str
    items: list[OpenDocOut]


def service(request: Request) -> SupplierPaymentService:
    found: SupplierPaymentService | None = getattr(request.app.state, "supplier_payments", None)
    if found is None:
        raise RuntimeError("supplier payments are not configured (app.state.supplier_payments)")
    return found


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get(
    "/supplier-payments/open-documents",
    operation_id="purchasing_list_supplier_open_documents",
    response_model=OpenDocsOut,
)
async def list_open_documents(request: Request, actor: Actor, _: CanPay, supplier_id: UUID) -> dict[str, Any]:
    return await service(request).open_documents(actor, supplier_id)


@router.get(
    "/supplier-payments", operation_id="purchasing_list_supplier_payments", response_model=PaymentPage
)
async def list_supplier_payments(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanPay,
    supplier_id: UUID | None = None,
    status: Literal["posted", "cancelled"] | None = None,
    method: Method | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = PaymentFilter(
        branch_ids=scope_branches(scope),
        supplier_id=supplier_id,
        status=status,
        method=method,
        date_from=date_from,
        date_to=date_to,
    )
    return await service(request).list_page(actor, flt, cursor, limit)


@router.post(
    "/supplier-payments",
    operation_id="purchasing_create_supplier_payment",
    response_model=PaymentCreated,
    status_code=201,
)
async def create_supplier_payment(
    request: Request, response: Response, body: PaymentIn, actor: Actor, scope: Scope, _: CanPay
) -> dict[str, Any]:
    data = PaymentInput(
        supplier_id=body.supplier_id,
        amount=Decimal(body.amount),
        method=body.method,
        doc_date=body.doc_date,
        cash_register_id=body.cash_register_id,
        shift_id=body.shift_id,
        allocations=None
        if body.allocations is None
        else [
            AllocationInput(a.target_doc_type, a.target_doc_id, Decimal(a.amount)) for a in body.allocations
        ],
        comment=body.comment,
    )
    created = await service(request).create(actor, scope, data, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.get(
    "/supplier-payments/{payment_id}",
    operation_id="purchasing_get_supplier_payment",
    response_model=PaymentOut,
)
async def get_supplier_payment(
    request: Request, payment_id: UUID, actor: Actor, scope: Scope, _: CanPay
) -> dict[str, Any]:
    return await service(request).get(actor, scope, payment_id)


@router.post(
    "/supplier-payments/{payment_id}/cancel",
    operation_id="purchasing_cancel_supplier_payment",
    response_model=PaymentOut,
)
async def cancel_supplier_payment(
    request: Request, payment_id: UUID, body: PaymentCancel, actor: Actor, scope: Scope, _: CanPay
) -> dict[str, Any]:
    return await service(request).cancel(actor, scope, payment_id, body.reason, _ip(request))
