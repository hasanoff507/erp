"""Payload schemas of the debt-book POS events (18 §11.1 ``counterparty.created``, §12.2
``debt_payment.created``).

``extra="forbid"`` everywhere; money/qty are decimal strings. :func:`parse` turns a Pydantic failure into
``422 VALIDATION_ERROR`` with ``details[]`` (field path + ``validation.<type>``), like the sales payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, validation_details
from app.core.money import MoneyStr, QtyStr

PositiveMoney = Annotated[str, StringConstraints(pattern=r"^\d{1,16}\.\d{2}$")]
Rate2 = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{2}$")]
ShortText = Annotated[str, StringConstraints(max_length=1000)]
PosMethod = Literal["cash", "card", "uzqr", "click", "payme", "uzum"]
ManualReason = Literal["standalone_terminal", "terminal_offline", "terminal_error", "unknown_result"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalRefPayload(_Strict):
    """18 §2.4 ``ApprovalRef`` (only ``card_manual_approval`` uses it on a debt payment)."""

    mode: Literal["local_pin", "remote_request"]
    approved_by: UUID | None = None
    pin_verified_locally: bool | None = None
    approval_request_id: UUID | None = None


class AllocationPayload(_Strict):
    target_doc_type: Literal["sales", "debt_openings", "debt_writeoffs"]
    target_doc_id: UUID
    amount: PositiveMoney


class FiscalLinePayload(_Strict):
    sale_id: UUID | None = None
    sale_line_id: UUID | None = None
    product_id: UUID | None = None
    qty: QtyStr
    amount: PositiveMoney
    vat_rate: Rate2
    vat_amount: MoneyStr
    marking_code: Annotated[str, StringConstraints(max_length=512)] | None = None


class DebtPaymentCreatedPayload(_Strict):
    """18 §12.2 — POS only (``bank`` is the back-office REST path, §12.3)."""

    id: UUID
    counterparty_id: UUID
    branch_id: UUID
    cash_register_id: UUID
    shift_id: UUID
    receipt_seq: int = Field(gt=0)
    is_offline: bool
    offline_since: str | None = None
    amount: PositiveMoney
    method: PosMethod
    terminal_ref: Annotated[str, StringConstraints(max_length=64)] | None = None
    # never sent by the device (18 §4.1/§12.2) — accepted by the schema only to answer 422 with the right key
    card_type: str | None = None
    card_type_source: str | None = None
    card_mask: str | None = None
    rrn: str | None = None
    approval_code: str | None = None
    card_scheme: str | None = None
    card_terminal_transaction_id: UUID | None = None
    card_entry_mode: Literal["integrated", "manual"] | None = None
    card_result: dict[str, Any] | None = None
    manual_reason: ManualReason | None = None
    card_manual_approval: ApprovalRefPayload | None = None
    qr_type: Literal["static", "dynamic"] | None = None
    checkout_ref: UUID | None = None
    provider_tx_id: Annotated[str, StringConstraints(max_length=128)] | None = None
    promise_date: date | None = None
    comment: ShortText | None = None
    allocations: list[AllocationPayload] = Field(max_length=500)
    fiscal_lines: list[FiscalLinePayload] = Field(min_length=1, max_length=2000)
    fiscal_result: dict[str, Any] | None = None


class CounterpartyCreatedPayload(_Strict):
    """18 §11.1 — the POS quick customer (name + phone)."""

    id: UUID
    kind: Literal["person", "company"] = "person"
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    phone: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    notify_consent: bool = False


def parse[M: BaseModel](model: type[M], payload: Mapping[str, Any]) -> M:
    try:
        return model.model_validate(dict(payload))
    except ValidationError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, details=validation_details(exc.errors())) from None
