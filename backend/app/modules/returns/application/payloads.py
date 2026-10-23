"""``return.created`` payload (18 §7.1) — ``extra="forbid"``."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.money import QtyStr
from app.modules.sales.application.payloads import (
    ApprovalRefPayload,
    ManualReason,
    Price4,
    Rate2,
    ShortText,
)

RefundMethod = Literal["cash", "card", "uzqr", "click", "payme", "uzum", "debt_adjustment"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RefundCardPayload(_Strict):
    card_entry_mode: Literal["integrated", "manual"]
    card_result: dict[str, Any] | None = None
    # derived by the server from card_result (integrated) / always NULL (manual) — any value → 422
    card_type: str | None = None
    card_type_source: str | None = None
    card_mask: str | None = None
    rrn: str | None = None
    approval_code: str | None = None
    card_scheme: str | None = None
    terminal_ref: str | None = None
    manual_reason: ManualReason | None = None
    card_manual_approval: ApprovalRefPayload | None = None


class ReturnLinePayload(_Strict):
    sale_line_id: UUID | None = None
    product_id: UUID
    qty: QtyStr
    price: Price4
    vat_rate: Rate2
    vat_exemption_code: Annotated[str, StringConstraints(max_length=64)] | None = None
    marking_code: Annotated[str, StringConstraints(max_length=512)] | None = None
    restock: bool = True


class ReturnCreatedPayload(_Strict):
    id: UUID
    branch_id: UUID
    shift_id: UUID
    cash_register_id: UUID
    receipt_seq: int | None = Field(default=None, gt=0)
    fiscal_result: dict[str, Any] | None = None
    sale_id: UUID | None = None
    counterparty_id: UUID | None = None
    is_offline: bool
    offline_since: str | None = None
    temp_number: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    lines: list[ReturnLinePayload] = Field(min_length=1, max_length=500)
    reason: Literal["defective", "wrong_item", "customer_changed_mind", "other"]
    refund_method: RefundMethod
    refund_card: RefundCardPayload | None = None
    approval: ApprovalRefPayload | None = None
    comment: ShortText | None = None
