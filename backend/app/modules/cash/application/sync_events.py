"""``/sync/push`` handlers of the cash module (18 §3.1, §3.2, §13.1; 16 §3.1).

Each handler validates its payload (Pydantic, ``extra="forbid"`` → ``VALIDATION_ERROR``) and posts through
the services inside the per-event transaction opened by the sync module.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, validation_details
from app.core.money import MoneyStr
from app.modules.access.application.approval_gate import ApprovalRefIn
from app.modules.cash.application.movements import CashMovementService
from app.modules.cash.application.shifts import CloseInput, OpenInput, ShiftService
from app.modules.cash.domain.movements import MovementInput
from app.modules.sync.application.handlers import EventContext, HandlerResult

Text = Annotated[str, StringConstraints(max_length=1000)]


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalRefPayload(_Payload):
    """``ApprovalRef`` (18 §2.4)."""

    mode: Literal["local_pin", "remote_request"]
    approved_by: UUID | None = None
    pin_verified_locally: bool | None = None
    approval_request_id: UUID | None = None

    def to_ref(self) -> ApprovalRefIn:
        return ApprovalRefIn(
            mode=self.mode,
            approved_by=self.approved_by,
            pin_verified_locally=self.pin_verified_locally,
            approval_request_id=self.approval_request_id,
        )


class ShiftOpenedPayload(_Payload):
    id: UUID
    cash_register_id: UUID
    shift_no: int = Field(gt=0, le=2_000_000_000)
    opening_cash: MoneyStr
    comment: Text | None = None


class ShiftClosedPayload(_Payload):
    shift_id: UUID
    counted_cash: MoneyStr
    counted_card_total: MoneyStr | None = None
    card_settlements: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    variance_note: Text | None = None


class CashMovementPayload(_Payload):
    id: UUID
    cash_register_id: UUID
    shift_id: UUID
    direction: Literal["in", "out"]
    reason: Literal["collection", "deposit", "owner_withdrawal", "other"]
    account: Literal["9430", "9390", "6310", "4010", "4730"] | None = None
    counterparty_id: UUID | None = None
    employee_id: UUID | None = None
    amount: MoneyStr
    comment: Text | None = None
    approval: ApprovalRefPayload | None = None


def parse[T: BaseModel](model: type[T], payload: Mapping[str, Any]) -> T:
    try:
        return model.model_validate(dict(payload))
    except ValidationError as exc:
        details = validation_details(exc.errors())
        raise AppError(ErrorCode.VALIDATION_ERROR, details=details) from None


def _non_negative(field: str, value: Decimal) -> None:
    if value < 0:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=validation_details([{"loc": (field,), "type": "greater_than_equal"}]),
        )


class CashSyncHandlers:
    def __init__(self, shifts: ShiftService, movements: CashMovementService) -> None:
        self._shifts = shifts
        self._movements = movements

    async def shift_opened(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        body = parse(ShiftOpenedPayload, payload)
        opening = Decimal(body.opening_cash)
        _non_negative("opening_cash", opening)
        server = await self._shifts.open(
            s, ctx, OpenInput(body.id, body.cash_register_id, body.shift_no, opening, body.comment)
        )
        return HandlerResult(server=server)

    async def shift_closed(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        body = parse(ShiftClosedPayload, payload)
        counted = Decimal(body.counted_cash)
        _non_negative("counted_cash", counted)
        card_total = None if body.counted_card_total is None else Decimal(body.counted_card_total)
        if card_total is not None:
            _non_negative("counted_card_total", card_total)
        result = await self._shifts.close(
            s, ctx, CloseInput(body.shift_id, counted, card_total, body.card_settlements, body.variance_note)
        )
        return HandlerResult(
            server=result.server,
            sync_exceptions=tuple(result.sync_exceptions),
            after_commit=tuple(result.after_commit),
        )

    async def cash_movement_created(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        body = parse(CashMovementPayload, payload)
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
        posted = await self._movements.from_event(
            s, ctx, body.id, movement, None if body.approval is None else body.approval.to_ref()
        )
        return HandlerResult(server=posted.body, sync_exceptions=posted.sync_exceptions)
