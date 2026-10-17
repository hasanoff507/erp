"""Expenses — back-office REST (20 #41–#51, M15). Tag ``expenses``.

POS cash expenses arrive as the ``expense.created`` sync event (18 §13.2). Writes need
``Idempotency-Key`` (17 §6).
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
from app.modules.expenses.application.expenses import ExpenseInput, invalid
from app.modules.expenses.application.module import ExpensesModule

router = APIRouter(tags=["expenses"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanCreate = Annotated[PermissionGrant, Depends(require_permission("expenses.create"))]
Source = Literal["cash", "bank", "card"]
Status = Literal["draft", "posted", "cancelled"]
Account = Literal["9410", "9420", "9430", "6410"]
TaxType = Literal["vat", "turnover", "pit", "social", "property", "land", "other"]
Period = Literal["month", "quarter", "year"]
Text = Annotated[str, StringConstraints(max_length=1000)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=50)]
RuleName = Annotated[str, StringConstraints(max_length=100)]
Reason = Annotated[str, StringConstraints(min_length=3, max_length=500)]
Day = Annotated[int, Field(ge=1, le=28)]


def _module(request: Request) -> ExpensesModule:
    module: ExpensesModule | None = getattr(request.app.state, "expenses", None)
    if module is None:
        raise RuntimeError("expenses module is not configured (app.state.expenses)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _positive(field: str, value: str) -> Decimal:
    amount = Decimal(value)
    if amount <= 0:
        raise invalid(field, "validation.greater_than")
    return amount


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- schemas ---------------------------------------------------------------------------------------
class ExpenseCreate(_In):
    doc_date: date = Field(description="Not in the future; closed period → 409 PERIOD_CLOSED")
    branch_id: UUID | None = Field(
        default=None, description="Default: X-Branch-Id (or the member's only branch)"
    )
    category_id: UUID
    amount: MoneyStr = Field(description="> 0")
    source: Source
    cash_register_id: UUID | None = Field(default=None, description="source=cash only (required)")
    shift_id: UUID | None = Field(default=None, description="source=cash only (required, open shift)")
    attachment_id: UUID | None = None
    comment: Text | None = None
    recurring_rule_id: UUID | None = None
    tax_type: TaxType | None = Field(default=None, description="Required iff the category account is 6410")


class ExpenseOut(BaseModel):
    id: UUID
    number: str | None
    branch_id: UUID
    doc_date: str
    status: Status
    category_id: UUID
    category_name: str
    account: str = Field(description="Dt account: posted → the ledger's, draft → category default_account")
    amount: str
    source: Source
    tax_type: str | None
    cash_register_id: UUID | None
    shift_id: UUID | None
    attachment_id: UUID | None
    recurring_rule_id: UUID | None
    comment: str | None
    created_by: UUID
    created_at: str | None
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None
    device_id: UUID | None
    approval_request_id: UUID | None
    approval_status: str | None = Field(description="Latest expense_over_limit request: pending/approved/…")


class ExpenseTotals(BaseModel):
    posted: str
    draft: str


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    next_cursor: str | None
    totals: ExpenseTotals


class ExpensePosted(BaseModel):
    id: UUID
    status: Literal["posted", "draft"]
    number: str | None = None
    posted_at: str | None = None
    approval_request_id: UUID | None = Field(default=None, description="202 only: expense_over_limit request")


class ExpenseCancel(_In):
    reason: Reason


class ExpenseCancelled(BaseModel):
    id: UUID
    status: Literal["cancelled"]
    cancelled_at: str | None


class ExpenseCategoryItem(BaseModel):
    id: UUID
    code: str | None
    name: str
    default_account: Account
    source_ref: str | None
    is_system: bool
    archived_at: str | None
    version: int


class CategoryList(BaseModel):
    items: list[ExpenseCategoryItem]


class ExpenseCategoryCreateIn(_In):
    name: Name
    default_account: Account


class ExpenseCategoryUpdateIn(_In):
    name: Name | None = None
    default_account: Account | None = Field(default=None, description="Never crosses 94xx ↔ 6410")
    archived: bool | None = None
    version: int = Field(ge=1)


class RuleOut(BaseModel):
    id: UUID
    name: str | None
    branch_id: UUID
    category_id: UUID
    amount: str
    period: Period
    day_of_month: int
    source: Source
    cash_register_id: UUID | None
    next_due_date: str
    last_triggered_at: str | None
    is_active: bool
    is_due: bool = Field(description="Active and next_due_date ≤ today — BO-17 reminder banner")
    version: int


class RulePage(BaseModel):
    items: list[RuleOut]
    total: int
    page: int
    size: int


class RuleCreate(_In):
    name: RuleName | None = None
    category_id: UUID
    amount: MoneyStr
    day_of_month: Day
    period: Period
    source: Source
    cash_register_id: UUID | None = Field(default=None, description="Required for source=cash")
    branch_id: UUID | None = Field(default=None, description="Default: X-Branch-Id")


class RuleUpdate(_In):
    name: RuleName | None = None
    amount: MoneyStr | None = None
    day_of_month: Day | None = None
    is_active: bool | None = None
    version: int = Field(ge=1)


class RuleConfirm(_In):
    amount_override: MoneyStr | None = None


class RuleConfirmed(BaseModel):
    expense_id: UUID
    status: Literal["posted", "draft"]
    approval_request_id: UUID | None = Field(default=None, description="202 only")


# --- expenses --------------------------------------------------------------------------------------
@router.get("/expenses", operation_id="expenses_list_expenses", response_model=ExpensePage)
async def list_expenses(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanCreate,
    category_id: UUID | None = None,
    branch_id: UUID | None = None,
    source: Source | None = None,
    status: Status | None = None,
    doc_date__gte: date | None = None,
    doc_date__lte: date | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _module(request).expenses.list_page(
        actor,
        scope,
        branch_id=branch_id,
        category_id=category_id,
        source=source,
        status=status,
        date_from=doc_date__gte,
        date_to=doc_date__lte,
        cursor=cursor,
        limit=limit,
    )


@router.post("/expenses", operation_id="expenses_create_expense", response_model=ExpenseOut, status_code=201)
async def create_expense(
    request: Request, response: Response, body: ExpenseCreate, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    inp = ExpenseInput(
        doc_date=body.doc_date,
        category_id=body.category_id,
        amount=_positive("amount", body.amount),
        source=body.source,
        branch_id=body.branch_id,
        cash_register_id=body.cash_register_id,
        shift_id=body.shift_id,
        attachment_id=body.attachment_id,
        comment=body.comment,
        recurring_rule_id=body.recurring_rule_id,
        tax_type=body.tax_type,
    )
    created = await _module(request).expenses.create(actor, scope, inp, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.post(
    "/expenses/{expense_id}/post",
    operation_id="expenses_post_expense",
    response_model=ExpensePosted,
    responses={
        202: {"model": ExpensePosted, "description": "Over the expenses.approve limit — APPROVAL_REQUIRED"}
    },
)
async def post_expense(
    request: Request, response: Response, expense_id: UUID, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    outcome = await _module(request).expenses.post(actor, scope, expense_id, _ip(request))
    response.status_code = outcome.status
    return outcome.body


@router.post(
    "/expenses/{expense_id}/cancel", operation_id="expenses_cancel_expense", response_model=ExpenseCancelled
)
async def cancel_expense(
    request: Request, expense_id: UUID, body: ExpenseCancel, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    return await _module(request).expenses.cancel(actor, scope, expense_id, body.reason, _ip(request))


# --- categories ------------------------------------------------------------------------------------
@router.get("/expense-categories", operation_id="expenses_list_categories", response_model=CategoryList)
async def list_categories(request: Request, actor: Actor, include_archived: bool = True) -> dict[str, Any]:
    return await _module(request).categories.list(actor, include_archived=include_archived)


@router.post(
    "/expense-categories",
    operation_id="expenses_create_category",
    response_model=ExpenseCategoryItem,
    status_code=201,
)
async def create_category(
    request: Request, response: Response, body: ExpenseCategoryCreateIn, actor: Actor, _: CanCreate
) -> dict[str, Any]:
    created = await _module(request).categories.create(actor, body.name, body.default_account, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.patch(
    "/expense-categories/{category_id}",
    operation_id="expenses_update_category",
    response_model=ExpenseCategoryItem,
)
async def update_category(
    request: Request, category_id: UUID, body: ExpenseCategoryUpdateIn, actor: Actor, _: CanCreate
) -> dict[str, Any]:
    changes = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    for key in ("name", "default_account", "archived"):
        if key in changes and changes[key] is None:
            raise invalid(key, "validation.required")
    return await _module(request).categories.update(actor, category_id, body.version, changes, _ip(request))


# --- recurring -------------------------------------------------------------------------------------
@router.get("/recurring-expenses", operation_id="expenses_list_recurring", response_model=RulePage)
async def list_recurring(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanCreate,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _module(request).recurring.list_page(actor, scope, is_active=is_active, page=page, size=size)


@router.post(
    "/recurring-expenses", operation_id="expenses_create_recurring", response_model=RuleOut, status_code=201
)
async def create_recurring(
    request: Request, response: Response, body: RuleCreate, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    _positive("amount", body.amount)
    created = await _module(request).recurring.create(actor, scope, body.model_dump(), _ip(request))
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.patch(
    "/recurring-expenses/{rule_id}", operation_id="expenses_update_recurring", response_model=RuleOut
)
async def update_recurring(
    request: Request, rule_id: UUID, body: RuleUpdate, actor: Actor, scope: Scope, _: CanCreate
) -> dict[str, Any]:
    changes = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    for key in ("amount", "day_of_month", "is_active"):
        if key in changes and changes[key] is None:
            raise invalid(key, "validation.required")
    if changes.get("amount") is not None:
        _positive("amount", changes["amount"])
    return await _module(request).recurring.update(actor, scope, rule_id, body.version, changes, _ip(request))


@router.post(
    "/recurring-expenses/{rule_id}/confirm",
    operation_id="expenses_confirm_recurring",
    response_model=RuleConfirmed,
    status_code=201,
    responses={
        202: {"model": RuleConfirmed, "description": "Over the expenses.approve limit — APPROVAL_REQUIRED"}
    },
)
async def confirm_recurring(
    request: Request,
    response: Response,
    rule_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanCreate,
    body: RuleConfirm | None = None,
) -> dict[str, Any]:
    override = None
    if body is not None and body.amount_override is not None:
        override = _positive("amount_override", body.amount_override)
    result, status = await _module(request).recurring.confirm(actor, scope, rule_id, override, _ip(request))
    response.status_code = status
    return result
