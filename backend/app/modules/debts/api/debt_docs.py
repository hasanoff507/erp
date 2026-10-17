"""Debt book REST (18 §12.1, §12.3–§12.6, §12.8; 20 #21). Tags ``debts`` (M08) and ``reports`` (debts aging).

Permissions (18 §12, 20 #21):

* ``GET /counterparties/{id}/debt-ledger`` — receivable: ``debts.create`` / ``debts.payment.accept`` /
  ``reports.sales.view``; payable («Men qarzdorman»): ``purchases.pay`` / ``reports.finance.view``;
* ``debt-payments`` — writes ``debts.payment.accept`` (``method='bank'`` only); reads +
  ``reports.sales.view``;
* ``debt-openings`` — writes ``stock.opening.manage`` / ``debts.limit.manage``; reads +
  ``reports.sales.view``;
* ``debt-writeoffs`` — writes ``debts.forgive`` (Owner); reads + ``reports.sales.view``;
* ``debt-doubtful-flags`` — ``debts.forgive``, otherwise ``403 DOUBTFUL_FLAG_REQUIRES_OWNER``;
* ``GET /reports/debts-aging`` — ``reports.finance.view`` / ``debts.approve``.

The debt ledger and the aging report honour the branch scope (SEC-01, 15 §2.4): a branch-restricted user sees
only documents of his branches (figures computed over them); an aging ``branch_id`` outside the scope →
``403 BRANCH_SCOPE_DENIED``.
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
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.money import MoneyStr
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.debts.api.counterparties import debts_module, granted, require_any
from app.modules.debts.application.documents import DocFilter, OpeningCreate, PaymentCreate, WriteoffCreate

router = APIRouter(tags=["debts"])
reports_router = APIRouter(tags=["reports"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Cursor = Annotated[str | None, Query(max_length=512)]
Limit = Annotated[int, Query(ge=1, le=200)]
Reason = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
Note = Annotated[str, StringConstraints(max_length=1000)]
Status = Literal["draft", "posted", "cancelled"]

LEDGER_RECEIVABLE = ("debts.create", "debts.payment.accept", "reports.sales.view")
LEDGER_PAYABLE = ("purchases.pay", "reports.finance.view")
CanLedger = Annotated[frozenset[str], Depends(require_any(*LEDGER_RECEIVABLE, *LEDGER_PAYABLE))]
CanPay = Annotated[frozenset[str], Depends(require_any("debts.payment.accept"))]
CanReadPayments = Annotated[
    frozenset[str], Depends(require_any("debts.payment.accept", "reports.sales.view"))
]
CanOpen = Annotated[frozenset[str], Depends(require_any("stock.opening.manage", "debts.limit.manage"))]
CanReadOpenings = Annotated[
    frozenset[str], Depends(require_any("stock.opening.manage", "debts.limit.manage", "reports.sales.view"))
]
CanForgive = Annotated[frozenset[str], Depends(require_any("debts.forgive"))]
CanReadWriteoffs = Annotated[frozenset[str], Depends(require_any("debts.forgive", "reports.sales.view"))]
CanAging = Annotated[frozenset[str], Depends(require_any("reports.finance.view", "debts.approve"))]


async def owner_only(request: Request, principal: Actor) -> None:
    """18 §12.6: only ``debts.forgive`` (the Owner) may set/remove a doubtful flag."""
    if not await granted(request, principal, ("debts.forgive",)):
        raise AppError(ErrorCode.DOUBTFUL_FLAG_REQUIRES_OWNER, params={"permission": "debts.forgive"})


Owner = Annotated[None, Depends(owner_only)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _location(request: Request, response: Response, body: dict[str, Any]) -> dict[str, Any]:
    response.headers["Location"] = f"{request.url.path}/{body['id']}"
    return body


# --- schemas --------------------------------------------------------------------------------------
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DebtAllocationOut(BaseModel):
    target_doc_type: Literal["sales", "debt_openings", "debt_writeoffs"]
    target_doc_id: UUID
    target_number: str | None
    target_doc_date: str | None
    amount: str


class DocOut(BaseModel):
    id: UUID
    number: str | None
    status: Status
    doc_date: str
    branch_id: UUID
    counterparty_id: UUID
    counterparty_name: str | None
    amount: str
    comment: str | None
    created_by: UUID
    created_at: str
    posted_at: str | None
    cancelled_at: str | None
    cancelled_by: UUID | None
    cancel_reason: str | None


class FiscalReceiptBrief(BaseModel):
    id: UUID
    status: str
    receipt_seq: int | None
    fm_receipt_seq: int | None
    ofd_acked_at: str | None


class DebtPaymentOut(DocOut):
    method: Literal["cash", "card", "uzqr", "click", "payme", "uzum", "bank"]
    unallocated_amount: str = Field(description="Offline overpayment held on 6310 (qaror #67)")
    cash_register_id: UUID | None
    shift_id: UUID | None
    receipt_seq: int | None
    terminal_ref: str | None
    provider_tx_id: str | None
    qr_type: str | None
    card_entry_mode: str | None
    card_type: str | None
    card_mask: str | None
    rrn: str | None
    promise_date: str | None
    device_id: UUID | None
    allocations: list[DebtAllocationOut]
    fiscal_receipt: FiscalReceiptBrief | None


class DebtPaymentPage(BaseModel):
    items: list[DebtPaymentOut]
    next_cursor: str | None


class DebtPaymentCreate(_Strict):
    counterparty_id: UUID
    branch_id: UUID
    amount: MoneyStr
    method: Annotated[str, StringConstraints(min_length=1, max_length=16)] = Field(
        description="Only 'bank' (qaror #67); other values → 422 validation.debt_payment_backoffice_bank_only"
    )
    doc_date: date
    promise_date: date | None = None
    comment: Note | None = None


class CancelBody(_Strict):
    reason: Reason


class NewCounterparty(_Strict):
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    phone: Annotated[str, StringConstraints(max_length=32)] | None = None
    kind: Literal["person", "company"] = "person"


class DebtOpeningOut(DocOut):
    direction: Literal["receivable", "payable"]
    due_date: str | None


class DebtOpeningPage(BaseModel):
    items: list[DebtOpeningOut]
    next_cursor: str | None


class DebtOpeningCreate(_Strict):
    counterparty_id: UUID | None = Field(default=None, description="Either counterparty_id or counterparty")
    counterparty: NewCounterparty | None = Field(
        default=None, description="{name, phone} of the paper book row"
    )
    amount: MoneyStr
    direction: Literal["receivable", "payable"] = "receivable"
    due_date: date | None = None
    doc_date: date | None = None
    branch_id: UUID | None = None
    comment: Note | None = None


class DebtWriteoffOut(DocOut):
    reason: str
    account_choice: Literal["9430", "4910"]
    tax_writeoff_basis: str | None
    approved_by: UUID | None
    allocations: list[DebtAllocationOut]


class DebtWriteoffPage(BaseModel):
    items: list[DebtWriteoffOut]
    next_cursor: str | None


class DebtWriteoffCreate(_Strict):
    counterparty_id: UUID
    amount: MoneyStr
    reason: Reason
    account_choice: Literal["9430", "4910"] = "9430"
    tax_writeoff_basis: (
        Literal["court", "bankruptcy", "liquidation", "death", "limitation", "none"] | None
    ) = None
    doc_date: date | None = None
    branch_id: UUID | None = None
    comment: Note | None = None


class DoubtfulFlagCreate(_Strict):
    counterparty_id: UUID
    reason: Reason


class DoubtfulFlagOut(BaseModel):
    id: UUID
    counterparty_id: UUID
    reason: str
    flagged_by: UUID
    flagged_at: str
    unflagged_at: str | None
    active: bool


class LedgerProduct(BaseModel):
    product_id: UUID
    name: str
    name_ru: str | None
    qty: str
    line_total: str


class LedgerAllocation(BaseModel):
    target_doc_type: str
    target_doc_id: UUID
    target_number: str | None
    amount: str


class LedgerEntry(BaseModel):
    id: UUID
    doc_type: str
    doc_id: UUID
    number: str | None
    doc_date: str | None
    amount: str = Field(description="Signed: + debt grows, − debt shrinks (net of storno)")
    direction: Literal["receivable", "payable"]
    kind: Literal["debt", "payment", "credit"]
    running_balance: str = Field(description="Balance after this row (rows are newest first)")
    due_date: str | None
    promise_date: str | None
    comment: str | None
    status: Literal["open", "partially_paid", "paid", "written_off"] | None
    open_amount: str | None
    created_by: UUID | None
    created_by_name: str | None
    paid_amount: str | None = Field(description="Debt payments: the money received (incl. 9390/6310 parts)")
    products: list[LedgerProduct]
    allocations: list[LedgerAllocation]


class LedgerFlag(BaseModel):
    id: UUID
    reason: str


class LedgerCounterparty(BaseModel):
    id: UUID
    name: str
    phone: str | None
    kind: str
    is_customer: bool
    is_supplier: bool
    credit_limit: str | None
    receivable_balance: str
    payable_balance: str
    debt_due_date: str | None
    doubtful_flag: LedgerFlag | None


class DebtLedgerOut(BaseModel):
    counterparty: LedgerCounterparty
    direction: Literal["receivable", "payable"]
    balance: str
    entries: list[LedgerEntry]
    next_cursor: str | None


class AgingBucket(BaseModel):
    bucket: Literal["0-30", "31-60", "60+"]
    count: int
    amount: str


class AgingSummary(BaseModel):
    total: str
    count: int
    buckets: list[AgingBucket]


class AgingRow(BaseModel):
    counterparty_id: UUID
    name: str
    phone: str | None
    balance: str
    credit_limit: str | None
    due_date: str | None
    overdue_since: str
    days_overdue: int
    bucket: Literal["0-30", "31-60", "60+"]
    promise_date: str | None
    open_docs: int
    limit_exceeded_offline: bool
    doubtful_flag: bool
    doubtful_flag_id: UUID | None
    last_payment_amount: str | None
    last_payment_date: str | None


class DebtsAgingOut(BaseModel):
    as_of: str
    direction: Literal["receivable", "payable"]
    summary: AgingSummary
    rows: list[AgingRow]


def _filter(
    counterparty_id: UUID | None,
    branch_id: UUID | None,
    status: Status | None,
    doc_date__gte: date | None,
    doc_date__lte: date | None,
) -> DocFilter:
    return DocFilter(
        counterparty_id=counterparty_id,
        branch_id=branch_id,
        status=status,
        doc_date__gte=doc_date__gte,
        doc_date__lte=doc_date__lte,
    )


# --- debt ledger (18 §12.1) -----------------------------------------------------------------------
@router.get(
    "/counterparties/{counterparty_id}/debt-ledger",
    operation_id="debts_get_counterparty_debt_ledger",
    response_model=DebtLedgerOut,
)
async def get_debt_ledger(
    request: Request,
    counterparty_id: UUID,
    actor: Actor,
    scope: Scope,
    grants: CanLedger,
    direction: Literal["receivable", "payable"] = "receivable",
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    needed = LEDGER_RECEIVABLE if direction == "receivable" else LEDGER_PAYABLE
    if not grants & set(needed):
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": needed[0], "any_of": list(needed)})
    return await debts_module(request).ledger.ledger(actor, scope, counterparty_id, direction, cursor, limit)


# --- debt payments (18 §12.3, §12.5a) -------------------------------------------------------------
@router.post(
    "/debt-payments", operation_id="debts_create_debt_payment", response_model=DebtPaymentOut, status_code=201
)
async def create_debt_payment(
    request: Request, response: Response, body: DebtPaymentCreate, actor: Actor, scope: Scope, _: CanPay
) -> dict[str, Any]:
    data = PaymentCreate(
        counterparty_id=body.counterparty_id,
        branch_id=body.branch_id,
        amount=Decimal(body.amount),
        method=body.method,
        doc_date=body.doc_date,
        promise_date=body.promise_date,
        comment=body.comment,
    )
    created = await debts_module(request).documents.create_payment(actor, scope, data, _ip(request))
    return _location(request, response, created)


@router.get("/debt-payments", operation_id="debts_list_debt_payments", response_model=DebtPaymentPage)
async def list_debt_payments(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanReadPayments,
    counterparty_id: UUID | None = None,
    branch_id: UUID | None = None,
    status: Status | None = None,
    doc_date__gte: date | None = None,
    doc_date__lte: date | None = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    flt = _filter(counterparty_id, branch_id, status, doc_date__gte, doc_date__lte)
    return await debts_module(request).documents.page_payments(actor, scope, flt, cursor, limit)


@router.get("/debt-payments/{doc_id}", operation_id="debts_get_debt_payment", response_model=DebtPaymentOut)
async def get_debt_payment(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanReadPayments
) -> dict[str, Any]:
    return await debts_module(request).documents.get_payment(actor, scope, doc_id)


@router.post(
    "/debt-payments/{doc_id}/post", operation_id="debts_post_debt_payment", response_model=DebtPaymentOut
)
async def post_debt_payment(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanPay
) -> dict[str, Any]:
    return await debts_module(request).documents.post_payment(actor, scope, doc_id, _ip(request))


@router.post(
    "/debt-payments/{doc_id}/cancel", operation_id="debts_cancel_debt_payment", response_model=DebtPaymentOut
)
async def cancel_debt_payment(
    request: Request, doc_id: UUID, body: CancelBody, actor: Actor, scope: Scope, _: CanPay
) -> dict[str, Any]:
    return await debts_module(request).documents.cancel_payment(
        actor, scope, doc_id, body.reason, _ip(request)
    )


# --- debt openings (18 §12.4, §12.5a) -------------------------------------------------------------
@router.post(
    "/debt-openings", operation_id="debts_create_debt_opening", response_model=DebtOpeningOut, status_code=201
)
async def create_debt_opening(
    request: Request, response: Response, body: DebtOpeningCreate, actor: Actor, scope: Scope, _: CanOpen
) -> dict[str, Any]:
    data = OpeningCreate(
        amount=Decimal(body.amount),
        direction=body.direction,
        counterparty_id=body.counterparty_id,
        new_counterparty=body.counterparty.model_dump() if body.counterparty else None,
        due_date=body.due_date,
        doc_date=body.doc_date,
        branch_id=body.branch_id,
        comment=body.comment,
    )
    created = await debts_module(request).documents.create_opening(actor, scope, data, _ip(request))
    return _location(request, response, created)


@router.get("/debt-openings", operation_id="debts_list_debt_openings", response_model=DebtOpeningPage)
async def list_debt_openings(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanReadOpenings,
    counterparty_id: UUID | None = None,
    branch_id: UUID | None = None,
    status: Status | None = None,
    direction: Literal["receivable", "payable"] | None = None,
    doc_date__gte: date | None = None,
    doc_date__lte: date | None = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    flt = _filter(counterparty_id, branch_id, status, doc_date__gte, doc_date__lte)
    flt = DocFilter(**{**flt.__dict__, "direction": direction}) if direction else flt
    return await debts_module(request).documents.page_openings(actor, scope, flt, cursor, limit)


@router.get("/debt-openings/{doc_id}", operation_id="debts_get_debt_opening", response_model=DebtOpeningOut)
async def get_debt_opening(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanReadOpenings
) -> dict[str, Any]:
    return await debts_module(request).documents.get_opening(actor, scope, doc_id)


@router.post(
    "/debt-openings/{doc_id}/post", operation_id="debts_post_debt_opening", response_model=DebtOpeningOut
)
async def post_debt_opening(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanOpen
) -> dict[str, Any]:
    return await debts_module(request).documents.post_opening(actor, scope, doc_id, _ip(request))


@router.post(
    "/debt-openings/{doc_id}/cancel", operation_id="debts_cancel_debt_opening", response_model=DebtOpeningOut
)
async def cancel_debt_opening(
    request: Request, doc_id: UUID, body: CancelBody, actor: Actor, scope: Scope, _: CanOpen
) -> dict[str, Any]:
    return await debts_module(request).documents.cancel_opening(
        actor, scope, doc_id, body.reason, _ip(request)
    )


# --- debt write-offs (18 §12.5, §12.5a) -----------------------------------------------------------
@router.post(
    "/debt-writeoffs",
    operation_id="debts_create_debt_writeoff",
    response_model=DebtWriteoffOut,
    status_code=201,
)
async def create_debt_writeoff(
    request: Request, response: Response, body: DebtWriteoffCreate, actor: Actor, scope: Scope, _: CanForgive
) -> dict[str, Any]:
    data = WriteoffCreate(
        counterparty_id=body.counterparty_id,
        amount=Decimal(body.amount),
        reason=body.reason,
        account_choice=body.account_choice,
        tax_writeoff_basis=body.tax_writeoff_basis,
        doc_date=body.doc_date,
        branch_id=body.branch_id,
        comment=body.comment,
    )
    created = await debts_module(request).documents.create_writeoff(actor, scope, data, _ip(request))
    return _location(request, response, created)


@router.get("/debt-writeoffs", operation_id="debts_list_debt_writeoffs", response_model=DebtWriteoffPage)
async def list_debt_writeoffs(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanReadWriteoffs,
    counterparty_id: UUID | None = None,
    branch_id: UUID | None = None,
    status: Status | None = None,
    doc_date__gte: date | None = None,
    doc_date__lte: date | None = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> dict[str, Any]:
    flt = _filter(counterparty_id, branch_id, status, doc_date__gte, doc_date__lte)
    return await debts_module(request).documents.page_writeoffs(actor, scope, flt, cursor, limit)


@router.get(
    "/debt-writeoffs/{doc_id}", operation_id="debts_get_debt_writeoff", response_model=DebtWriteoffOut
)
async def get_debt_writeoff(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanReadWriteoffs
) -> dict[str, Any]:
    return await debts_module(request).documents.get_writeoff(actor, scope, doc_id)


@router.post(
    "/debt-writeoffs/{doc_id}/post", operation_id="debts_post_debt_writeoff", response_model=DebtWriteoffOut
)
async def post_debt_writeoff(
    request: Request, doc_id: UUID, actor: Actor, scope: Scope, _: CanForgive
) -> dict[str, Any]:
    return await debts_module(request).documents.post_writeoff(actor, scope, doc_id, _ip(request))


@router.post(
    "/debt-writeoffs/{doc_id}/cancel",
    operation_id="debts_cancel_debt_writeoff",
    response_model=DebtWriteoffOut,
)
async def cancel_debt_writeoff(
    request: Request, doc_id: UUID, body: CancelBody, actor: Actor, scope: Scope, _: CanForgive
) -> dict[str, Any]:
    return await debts_module(request).documents.cancel_writeoff(
        actor, scope, doc_id, body.reason, _ip(request)
    )


# --- doubtful flags (18 §12.6) --------------------------------------------------------------------
@router.post(
    "/debt-doubtful-flags",
    operation_id="debts_create_debt_doubtful_flag",
    response_model=DoubtfulFlagOut,
    status_code=201,
)
async def create_doubtful_flag(
    request: Request, response: Response, body: DoubtfulFlagCreate, actor: Actor, _: Owner
) -> dict[str, Any]:
    created = await debts_module(request).documents.flag(
        actor, body.counterparty_id, body.reason, _ip(request)
    )
    return _location(request, response, created)


@router.post(
    "/debt-doubtful-flags/{flag_id}/unflag",
    operation_id="debts_unflag_debt_doubtful_flag",
    response_model=DoubtfulFlagOut,
)
async def unflag_doubtful_flag(request: Request, flag_id: UUID, actor: Actor, _: Owner) -> dict[str, Any]:
    return await debts_module(request).documents.unflag(actor, flag_id, _ip(request))


# --- debts aging (20 #21 = 18 §12.8) -------------------------------------------------------------
@reports_router.get(
    "/reports/debts-aging", operation_id="reports_get_debts_aging", response_model=DebtsAgingOut
)
async def get_debts_aging(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanAging,
    direction: Literal["receivable", "payable"] = "receivable",
    as_of: date | None = None,
    branch_id: UUID | None = None,
    bucket: Literal["0-30", "31-60", "60+"] | None = None,
    limit_exceeded_offline: bool | None = None,
) -> dict[str, Any]:
    return await debts_module(request).ledger.aging(
        actor,
        scope,
        direction=direction,
        as_of=as_of,
        branch_id=branch_id,
        bucket=bucket,
        limit_exceeded_offline=limit_exceeded_offline,
    )
