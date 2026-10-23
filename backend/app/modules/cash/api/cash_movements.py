"""Cash movements — back-office (20 #52–#54; 18 §13.3). Tag ``cash`` (M16).

POS cash in/out is the ``cash_movement.created`` sync event; this REST is the back-office path (e.g.
recording a collection). ``POST``/``cancel`` need ``Idempotency-Key`` (17 §6).
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
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.cash.api.deps import cash_module, client_ip, require_any
from app.modules.cash.domain.movements import MovementInput

router = APIRouter(tags=["cash"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanView = Annotated[str, Depends(require_any("reports.sales.view", "cash.count.shift"))]
CanMove = Annotated[str, Depends(require_any("cash.deposit", "cash.withdraw"))]
Direction = Literal["in", "out"]
Reason = Literal["collection", "deposit", "owner_withdrawal", "other"]
Account = Literal["9430", "9390", "6310", "4010", "4730"]
Text = Annotated[str, StringConstraints(max_length=1000)]


class CashMovementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_register_id: UUID
    shift_id: UUID = Field(description="An open shift of the register")
    direction: Direction
    amount: MoneyStr = Field(description="> 0")
    reason: Reason = Field(description="collection/owner_withdrawal → out; deposit → in; other → both")
    account: Account | None = Field(default=None, description="Only reason=other; default out 9430, in 9390")
    employee_id: UUID | None = Field(default=None, description="Required when account=4730")
    counterparty_id: UUID | None = Field(
        default=None,
        description="owner_withdrawal: founder (not for sole_proprietor); other: account 6310/4010",
    )
    comment: Text | None = Field(default=None, description="Required for reason=other")
    doc_date: date


class CashMovementCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class CashMovementCreated(BaseModel):
    id: UUID
    status: Literal["posted", "draft"]
    amount: str
    approval_request_id: UUID | None = Field(
        default=None, description="202 only: cash_withdrawal_over_limit request (BO-16)"
    )


class CashMovementCancelled(BaseModel):
    id: UUID
    status: Literal["cancelled"]


class CashMovementOut(BaseModel):
    id: UUID
    number: str | None
    status: Literal["draft", "posted", "cancelled"]
    doc_date: str
    branch_id: UUID
    cash_register_id: UUID
    shift_id: UUID
    direction: Direction
    amount: str
    reason: Reason
    account: str | None
    counterparty_id: UUID | None
    employee_id: UUID | None
    comment: str | None
    created_by: UUID
    created_at: str
    posted_at: str | None
    cancelled_at: str | None
    cancel_reason: str | None
    device_id: UUID | None


class CashMovementPage(BaseModel):
    items: list[CashMovementOut]
    next_cursor: str | None


@router.get("/cash-movements", operation_id="cash_list_cash_movements", response_model=CashMovementPage)
async def list_cash_movements(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanView,
    cash_register_id: UUID | None = None,
    shift_id: UUID | None = None,
    direction: Direction | None = None,
    reason: Reason | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await cash_module(request).movements.list_page(
        actor,
        scope,
        cash_register_id=cash_register_id,
        shift_id=shift_id,
        direction=direction,
        reason=reason,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/cash-movements",
    operation_id="cash_create_cash_movement",
    response_model=CashMovementCreated,
    status_code=201,
    responses={
        202: {"model": CashMovementCreated, "description": "Over the cash.withdraw limit — APPROVAL_REQUIRED"}
    },
)
async def create_cash_movement(
    request: Request, response: Response, body: CashMovementIn, actor: Actor, scope: Scope, _: CanMove
) -> dict[str, Any]:
    movement = MovementInput(
        cash_register_id=body.cash_register_id,
        shift_id=body.shift_id,
        direction=body.direction,
        reason=body.reason,
        amount=Decimal(body.amount),
        account=body.account,
        counterparty_id=body.counterparty_id,
        employee_id=body.employee_id,
        comment=body.comment,
    )
    result, status = await cash_module(request).movements.create(
        actor, scope, movement, body.doc_date, client_ip(request)
    )
    response.status_code = status
    response.headers["Location"] = f"{request.url.path}/{result['id']}"
    return result


@router.post(
    "/cash-movements/{movement_id}/cancel",
    operation_id="cash_cancel_cash_movement",
    response_model=CashMovementCancelled,
)
async def cancel_cash_movement(
    request: Request, movement_id: UUID, body: CashMovementCancel, actor: Actor, scope: Scope, _: CanMove
) -> dict[str, Any]:
    return await cash_module(request).movements.cancel(
        actor, scope, movement_id, body.reason, client_ip(request)
    )
