"""``expense.created`` — POS-14 «Xarajat» (18 §13.2; 16 §2): cash expense, offline too.

Validated with Pydantic (``extra="forbid"`` → ``VALIDATION_ERROR``) and posted inside the per-event
transaction opened by the sync module.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, validation_details
from app.core.money import MoneyStr
from app.modules.access.application.approval_gate import ApprovalRefIn
from app.modules.accounting.wiring import business_date
from app.modules.expenses.application.expenses import ExpenseInput, ExpenseService, invalid
from app.modules.sync.application.handlers import EventContext, HandlerResult

Text = Annotated[str, StringConstraints(max_length=1000)]
TaxType = Literal["vat", "turnover", "pit", "social", "property", "land", "other"]


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


class ExpenseCreatedPayload(_Payload):
    """18 §13.2 — exactly these fields."""

    id: UUID
    doc_date: date  # accepted for the contract, ignored: the server uses business_date(created_at) (SYNC-02)
    branch_id: UUID
    cash_register_id: UUID
    shift_id: UUID
    category_id: UUID
    amount: MoneyStr
    comment: Text | None = None
    tax_type: TaxType | None = None
    approval: ApprovalRefPayload | None = None


def parse(payload: Mapping[str, Any]) -> ExpenseCreatedPayload:
    try:
        return ExpenseCreatedPayload.model_validate(dict(payload))
    except ValidationError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, details=validation_details(exc.errors())) from None


class ExpenseSyncHandlers:
    def __init__(self, expenses: ExpenseService) -> None:
        self._expenses = expenses

    async def expense_created(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        body = parse(payload)
        amount = Decimal(body.amount)
        if amount <= 0:
            raise invalid("amount", "validation.greater_than")
        posted = await self._expenses.from_event(
            s,
            ctx,
            body.id,
            ExpenseInput(
                # SYNC-02 / F8: like cash movements and debt payments, the day is the Tashkent date of the
                # (clamped) event time; the device value is ignored — rejecting would lose a cash expense.
                doc_date=business_date(ctx.created_at),
                category_id=body.category_id,
                amount=amount,
                source="cash",
                branch_id=body.branch_id,
                cash_register_id=body.cash_register_id,
                shift_id=body.shift_id,
                comment=body.comment,
                tax_type=body.tax_type,
            ),
            None if body.approval is None else body.approval.to_ref(),
        )
        return HandlerResult(server=posted.body, sync_exceptions=posted.sync_exceptions)
