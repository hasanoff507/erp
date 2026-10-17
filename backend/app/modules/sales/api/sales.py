"""Receipt search (18 §4.8; POS-05, BO-09). Tag ``sales`` (M01). Read-only — sales come from ``/sync/push``.

Permission: ``sales.create`` (POS-05, own branches) or ``reports.sales.view`` (BO-09); branch scope applies.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.sales.application.ports import SaleFilter
from app.modules.sales.application.queries import scope_branches
from app.modules.sales.wiring import SalesModule

router = APIRouter(tags=["sales"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Status = Literal["draft", "posted", "cancelled"]


def require_any(*codes: str) -> Callable[..., Awaitable[frozenset[str]]]:
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


CanRead = Annotated[frozenset[str], Depends(require_any("sales.create", "reports.sales.view"))]


class SalePaymentSummary(BaseModel):
    method: str
    amount: str


class SaleListItem(BaseModel):
    id: UUID
    number: str | None
    temp_number: str | None
    doc_date: str
    status: Status
    total_amount: str
    payments_summary: list[SalePaymentSummary]
    counterparty_id: UUID | None
    is_offline: bool
    has_returns: bool
    shift_id: UUID
    cash_register_id: UUID
    branch_id: UUID
    created_at: str


class SalePage(BaseModel):
    items: list[SaleListItem]
    next_cursor: str | None


class SaleLineOut(BaseModel):
    id: UUID
    sale_line_id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    unit_code: str
    qty: str
    returned_qty: str = Field(description="Derived: Σ posted return_lines.qty of this line")
    price: str
    discount_amount: str
    discount_pct: str | None
    discount_source: str | None
    discount_rule_id: UUID | None
    vat_rate: str
    vat_exemption_code: str | None
    vat_amount: str
    line_total: str
    marking_code: str | None
    settled_amount: str


class SalePaymentOut(BaseModel):
    id: UUID
    method: str
    amount: str
    card_entry_mode: Literal["integrated", "manual"] | None
    manual_reason: str | None
    card_type: str | None
    card_mask: str | None
    rrn: str | None
    approval_code: str | None
    card_scheme: str | None
    terminal_ref: str | None
    qr_type: Literal["static", "dynamic"] | None
    provider_tx_id: str | None
    due_date: str | None


class SaleFiscalOut(BaseModel):
    id: UUID
    kind: str
    status: str
    receipt_seq: int | None
    fm_receipt_seq: int | None
    fiscal_sign: str | None
    qr_url: str | None
    payment_form: str | None
    ofd_acked_at: str | None


class SaleOut(BaseModel):
    id: UUID
    number: str | None
    temp_number: str | None
    doc_date: str
    status: Status
    branch_id: UUID
    shift_id: UUID
    cash_register_id: UUID
    counterparty_id: UUID | None
    total_amount: str | None
    is_offline: bool
    debt_limit_exceeded: bool
    created_by: UUID
    created_at: str
    posted_at: str | None
    device_id: UUID | None
    comment: str | None
    lines: list[SaleLineOut]
    payments: list[SalePaymentOut]
    fiscal_receipts: list[SaleFiscalOut]


def sales_module(request: Request) -> SalesModule:
    module: SalesModule | None = getattr(request.app.state, "sales", None)
    if module is None:
        raise RuntimeError("sales module is not configured (app.state.sales)")
    return module


@router.get("/sales", operation_id="sales_list_sales", response_model=SalePage)
async def list_sales(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanRead,
    number: Annotated[str | None, Query(max_length=64)] = None,
    fiscal_receipt_seq: Annotated[int | None, Query(ge=1)] = None,
    shift_id: UUID | None = None,
    counterparty_id: UUID | None = None,
    doc_date_gte: Annotated[date | None, Query(alias="doc_date__gte")] = None,
    doc_date_lte: Annotated[date | None, Query(alias="doc_date__lte")] = None,
    status: Status | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = SaleFilter(
        branch_ids=scope_branches(scope), number=number, fiscal_receipt_seq=fiscal_receipt_seq,
        shift_id=shift_id,
        counterparty_id=counterparty_id, date_from=doc_date_gte, date_to=doc_date_lte, status=status,
    )  # fmt: skip
    return await sales_module(request).queries.list_page(actor.tenant_id, actor.user_id, flt, cursor, limit)


@router.get("/sales/{sale_id}", operation_id="sales_get_sale", response_model=SaleOut)
async def get_sale(request: Request, sale_id: UUID, actor: Actor, scope: Scope, _: CanRead) -> dict[str, Any]:
    return await sales_module(request).queries.get(actor.tenant_id, actor.user_id, scope, sale_id)
