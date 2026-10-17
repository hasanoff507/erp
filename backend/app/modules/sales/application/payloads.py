"""Payload schemas of the POS sale events (18 §4.1, §5, §6) — ``extra="forbid"`` everywhere.

Money/qty travel as decimal strings; the field formats follow 18 §2.3 (``Money`` 2 dp, ``Qty`` 3 dp,
``price`` 4 dp, ``vat_rate``/percent 2 dp). :func:`parse` turns a Pydantic failure into
``422 VALIDATION_ERROR`` with ``details[]`` (field path + ``validation.<type>``).
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

Price4 = Annotated[str, StringConstraints(pattern=r"^\d{1,14}\.\d{4}$")]
Rate2 = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{2}$")]
PositiveMoney = Annotated[str, StringConstraints(pattern=r"^\d{1,16}\.\d{2}$")]
ShortText = Annotated[str, StringConstraints(max_length=1000)]
Code = Annotated[str, StringConstraints(min_length=1, max_length=64)]
Method = Literal["cash", "card", "uzqr", "click", "payme", "uzum", "debt"]
CardEntryMode = Literal["integrated", "manual"]
ManualReason = Literal["standalone_terminal", "terminal_offline", "terminal_error", "unknown_result"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalRefPayload(_Strict):
    """18 §2.4 ``ApprovalRef``."""

    mode: Literal["local_pin", "remote_request"]
    approved_by: UUID | None = None
    pin_verified_locally: bool | None = None
    approval_request_id: UUID | None = None


class SaleLinePayload(_Strict):
    id: UUID
    product_id: UUID
    unit_code: Code
    qty: QtyStr
    price: Price4
    vat_rate: Rate2
    vat_exemption_code: Annotated[str, StringConstraints(max_length=64)] | None = None
    discount_pct: Rate2 | None = None
    discount_amount: PositiveMoney | None = None
    discount_source: Literal["manual", "standing_customer", "rule"] | None = None
    discount_rule_id: UUID | None = None
    discount_approval: ApprovalRefPayload | None = None
    marking_code: Annotated[str, StringConstraints(max_length=512)] | None = None
    marking_offline: bool | None = None
    line_total: MoneyStr
    vat_amount: MoneyStr


class SalePaymentPayload(_Strict):
    method: Method
    amount: PositiveMoney
    card_entry_mode: CardEntryMode | None = None
    card_result: dict[str, Any] | None = None
    terminal_ref: Annotated[str, StringConstraints(max_length=64)] | None = None
    # never sent by the device (18 §4.1) — accepted by the schema only to answer 422 with the right key
    card_type: str | None = None
    card_type_source: str | None = None
    card_mask: str | None = None
    rrn: str | None = None
    approval_code: str | None = None
    card_scheme: str | None = None
    card_terminal_transaction_id: UUID | None = None
    manual_reason: ManualReason | None = None
    card_manual_approval: ApprovalRefPayload | None = None
    qr_type: Literal["static", "dynamic"] | None = None
    checkout_ref: UUID | None = None
    provider_tx_id: Annotated[str, StringConstraints(max_length=128)] | None = None
    due_date: date | None = None
    debt_approval: ApprovalRefPayload | None = None


class SaleCreatedPayload(_Strict):
    id: UUID
    branch_id: UUID
    cash_register_id: UUID
    shift_id: UUID
    receipt_seq: int | None = Field(default=None, gt=0)
    credit_receipt_seq: int | None = Field(default=None, gt=0)
    fiscal_result: dict[str, Any] | None = None
    delivery: Literal["printed", "electronic"] = "printed"
    delivery_reason: Literal["printer_failure", "customer_request"] | None = None
    temp_number: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    doc_date: date
    counterparty_id: UUID | None = None
    lines: list[SaleLinePayload] = Field(min_length=1, max_length=500)
    payments: list[SalePaymentPayload] = Field(min_length=1, max_length=20)
    comment: ShortText | None = None
    is_offline: bool
    offline_since: str | None = None


class DraftVoidedPayload(_Strict):
    draft_ref: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    voided_lines: list[dict[str, Any]] | None = Field(default=None, max_length=500)
    reason: ShortText | None = None


class ReceiptReprintedPayload(_Strict):
    fiscal_receipt_id: UUID
    sale_id: UUID | None = None
    reason: ShortText | None = None


def parse[M: BaseModel](model: type[M], payload: Mapping[str, Any]) -> M:
    try:
        return model.model_validate(dict(payload))
    except ValidationError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, details=validation_details(exc.errors())) from None
