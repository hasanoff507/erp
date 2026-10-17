"""Card terminal REST (18 §16a; endpoint index #42–#46). Tag ``card_terminals``.

* ``POST /card-terminal-transactions`` — upsert by ``id`` (= ``attempt_id``); ``purchase`` —
  ``sales.create`` or ``debts.payment.accept``, ``refund`` — ``returns.create``, ``void`` — ``sales.void``
  or ``returns.create``;
  ``result.resolved_by='manager'`` additionally needs ``card_manual_approval`` (or the caller's own
  ``card.manual_entry.approve``).
* ``GET /card-terminal-transactions/{id}`` — ``sales.create`` / ``returns.create`` / ``debts.payment.accept``.
* ``GET /card-terminals`` — ``cash_register.manage`` or ``sales.create`` (own register); ``POST``/``PATCH`` —
  ``cash_register.manage``.
* ``POST /card-terminal-settlements`` — ``shift.close``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.money import MoneyStr, money
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.access.application.approval_gate import ApprovalRefIn
from app.modules.integrations.card_terminal.application.contracts import SettlementInput
from app.modules.integrations.card_terminal.application.module import CardTerminalModule
from app.modules.integrations.card_terminal.application.ports import TerminalFilter
from app.modules.integrations.card_terminal.application.schemas import CardResultIn
from app.modules.integrations.card_terminal.application.terminals import TerminalPatch
from app.modules.integrations.card_terminal.application.transactions import (
    APPROVE_PERMISSION,
    KIND_PERMISSIONS,
    READ_PERMISSIONS,
    RecordInput,
)

router = APIRouter(tags=["card_terminals"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanManage = Annotated[PermissionGrant, Depends(require_permission("cash_register.manage"))]
CanCloseShift = Annotated[PermissionGrant, Depends(require_permission("shift.close"))]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Code = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{2,40}$")]
Tid = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{1,16}$")]
Mid = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{1,20}$")]
LocalId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Host = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")]
Adapter = Literal["agent_ecr", "cloud", "android_intent", "softpos", "fake"]
TerminalStatus = Literal["active", "disabled", "archived"]
HealthStatus = Literal["online", "busy", "offline", "error", "unknown"]


def card_module(request: Request) -> CardTerminalModule:
    module: CardTerminalModule | None = getattr(request.app.state, "card_terminal", None)
    if module is None:
        raise RuntimeError("card terminal module is not wired (app.state.card_terminal)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _holds(request: Request, principal: Principal, code: str) -> bool:
    if not principal.has_scope(code.split(".", 1)[0]):
        return False
    return bool(await auth_gateway(request).permission_limits(principal, code))


async def _require_any(request: Request, principal: Principal, codes: tuple[str, ...]) -> None:
    for code in codes:
        if await _holds(request, principal, code):
            return
    raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": codes[0], "any_of": list(codes)})


# --- schemas ---------------------------------------------------------------------------------------


class CardApprovalRef(BaseModel):
    """``ApprovalRef`` (18 §2.4)."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["local_pin", "remote_request"]
    approved_by: UUID | None = None
    pin_verified_locally: bool | None = None
    approval_request_id: UUID | None = None


class CardTxIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(description="attempt_id (UUIDv7) given by the device before calling the terminal")
    card_terminal_id: UUID
    cash_register_id: UUID | None = None
    shift_id: UUID | None = None
    kind: Literal["purchase", "refund", "void"]
    original_transaction_id: UUID | None = None
    amount: MoneyStr
    client_event_id: UUID | None = None
    requested_at: datetime
    status: Literal["pending", "approved", "declined", "unknown", "voided"] | None = None
    result: CardResultIn | None = None
    card_manual_approval: CardApprovalRef | None = None


class CardTxOut(BaseModel):
    id: UUID
    card_terminal_id: UUID
    status: Literal["pending", "approved", "declined", "unknown", "voided"]
    kind: Literal["purchase", "refund", "void"]
    amount: str
    approved_amount: str | None
    approval_code: str | None
    rrn: str | None
    card_mask: str | None
    card_scheme: str | None
    card_type: str | None
    card_type_source: str | None
    tid: str | None
    decline_code: str | None
    decline_message: str | None
    doc_type: str | None
    doc_id: UUID | None
    resolved_by: Literal["auto", "status_query", "manager"] | None
    updated_at: str | None


class CardTerminalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    cash_register_id: UUID | None = None
    name: Name
    vendor: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{2,32}$")]
    model: Annotated[str, StringConstraints(max_length=100)] | None = None
    adapter: Adapter
    driver: Code
    agent_id: UUID | None = None
    local_id: LocalId | None = None
    host: Host | None = None
    port: Annotated[int, Field(ge=1, le=65535)] | None = None
    vendor_terminal_ref: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    tid: Tid | None = None
    mid: Mid | None = None
    acquirer_counterparty_id: UUID | None = None
    status: TerminalStatus = "active"
    is_default: bool = False


class CardTerminalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    model: Annotated[str, StringConstraints(max_length=100)] | None = None
    cash_register_id: UUID | None = None
    agent_id: UUID | None = None
    local_id: LocalId | None = None
    host: Host | None = None
    port: Annotated[int, Field(ge=1, le=65535)] | None = None
    vendor_terminal_ref: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    tid: Tid | None = None
    mid: Mid | None = None
    acquirer_counterparty_id: UUID | None = None
    status: TerminalStatus | None = None
    is_default: bool | None = None
    version: int


class CardTerminalOut(BaseModel):
    id: UUID
    branch_id: UUID
    cash_register_id: UUID | None
    name: str
    vendor: str
    model: str | None
    adapter: Adapter
    driver: str
    agent_id: UUID | None
    local_id: str | None
    host: str | None
    port: int | None
    vendor_terminal_ref: str | None
    tid: str | None
    mid: str | None
    acquirer_counterparty_id: UUID | None
    status: TerminalStatus
    is_default: bool
    capabilities: dict[str, bool]
    health_status: HealthStatus
    health_checked_at: str | None
    version: int


class CardTerminalPage(BaseModel):
    items: list[CardTerminalOut]
    total: int
    page: int
    size: int


class CardSettlementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    card_terminal_id: UUID
    shift_id: UUID | None = None
    batch_no: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    business_date: date
    settled_at: datetime
    purchase_count: Annotated[int, Field(ge=0)]
    purchase_total: MoneyStr
    refund_count: Annotated[int, Field(ge=0)] = 0
    refund_total: MoneyStr = "0.00"
    status: Literal["failed"] | None = Field(
        default=None, description="'failed' — the terminal could not settle; otherwise the server computes it"
    )
    terminal_response: dict[str, Any] = Field(default_factory=dict)


class CardSettlementOut(BaseModel):
    id: UUID
    card_terminal_id: UUID
    status: Literal["matched", "mismatch", "failed"]
    net_total: str
    expected_total: str
    variance: str


# --- transactions ----------------------------------------------------------------------------------


@router.post(
    "/card-terminal-transactions",
    operation_id="card_terminals_record_transaction",
    response_model=CardTxOut,
    status_code=201,
    responses={200: {"model": CardTxOut, "description": "Already recorded (replay or forward update)"}},
)
async def record_card_transaction(
    request: Request, response: Response, body: CardTxIn, actor: Actor, scope: Scope
) -> dict[str, Any]:
    await _require_any(request, actor, KIND_PERMISSIONS[body.kind])
    approval = None
    if body.card_manual_approval is not None:
        a = body.card_manual_approval
        approval = ApprovalRefIn(a.mode, a.approved_by, a.pin_verified_locally, a.approval_request_id)
    data = RecordInput(
        id=body.id, card_terminal_id=body.card_terminal_id, cash_register_id=body.cash_register_id,
        shift_id=body.shift_id, kind=body.kind, original_transaction_id=body.original_transaction_id,
        amount=Decimal(body.amount), client_event_id=body.client_event_id, requested_at=body.requested_at,
        status=body.status, result=body.result, card_manual_approval=approval,
    )  # fmt: skip
    may_approve = await _holds(request, actor, APPROVE_PERMISSION)
    result, status = await card_module(request).transactions.record(
        actor, scope, data, may_approve=may_approve, ip=_ip(request)
    )
    response.status_code = status
    return result


@router.get(
    "/card-terminal-transactions/{tx_id}",
    operation_id="card_terminals_get_transaction",
    response_model=CardTxOut,
)
async def get_card_transaction(request: Request, tx_id: UUID, actor: Actor, scope: Scope) -> dict[str, Any]:
    await _require_any(request, actor, READ_PERMISSIONS)
    return await card_module(request).transactions.get(actor, scope, tx_id)


# --- terminals -------------------------------------------------------------------------------------


@router.get("/card-terminals", operation_id="card_terminals_list_terminals", response_model=CardTerminalPage)
async def list_card_terminals(
    request: Request,
    actor: Actor,
    scope: Scope,
    branch_id: UUID | None = None,
    cash_register_id: UUID | None = None,
    status: TerminalStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    can_manage = await _holds(request, actor, "cash_register.manage")
    if not can_manage:
        await _require_any(request, actor, ("cash_register.manage", "sales.create"))
    flt = TerminalFilter(scope.allowed, branch_id or scope.current, cash_register_id, status)
    return await card_module(request).terminals.list_page(
        actor, scope, flt, page, size, can_manage=can_manage
    )


@router.post(
    "/card-terminals",
    operation_id="card_terminals_create_terminal",
    response_model=CardTerminalOut,
    status_code=201,
)
async def create_card_terminal(
    request: Request, response: Response, body: CardTerminalCreate, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    created = await card_module(request).terminals.create(actor, scope, body.model_dump(), _ip(request))
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{created['id']}"
    return created


@router.patch(
    "/card-terminals/{terminal_id}",
    operation_id="card_terminals_update_terminal",
    response_model=CardTerminalOut,
)
async def update_card_terminal(
    request: Request, terminal_id: UUID, body: CardTerminalUpdate, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    fields = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    patch = TerminalPatch(version=body.version, fields=fields)
    return await card_module(request).terminals.update(actor, scope, terminal_id, patch, _ip(request))


# --- settlements -----------------------------------------------------------------------------------


@router.post(
    "/card-terminal-settlements",
    operation_id="card_terminals_record_settlement",
    response_model=CardSettlementOut,
    status_code=201,
)
async def record_card_settlement(
    request: Request, body: CardSettlementIn, actor: Actor, scope: Scope, _: CanCloseShift
) -> dict[str, Any]:
    item = SettlementInput(
        id=body.id, card_terminal_id=body.card_terminal_id, shift_id=body.shift_id, batch_no=body.batch_no,
        business_date=body.business_date, settled_at=body.settled_at, purchase_count=body.purchase_count,
        purchase_total=money(body.purchase_total), refund_count=body.refund_count,
        refund_total=money(body.refund_total), failed=body.status == "failed",
        terminal_response=body.terminal_response,
    )  # fmt: skip
    return await card_module(request).settlements.record(actor, scope, item, _ip(request))
