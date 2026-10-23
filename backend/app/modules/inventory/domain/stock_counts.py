"""Stock counts (19 §14, 13 §2.11, X-02, qaror #53). Pure Python.

Posting a count line (13 §2.11): ``diff = counted − expected`` (``expected`` —
:func:`inventory.domain.counts.expected_count_qty`):

* ``diff < 0`` (kamomad) → issue ``−diff`` with the cost line ``Dt 4730`` (``responsible_user_id``
  given, analytics ``employee_id``) or ``Dt 5910`` / ``Kt inv_acct`` at the balance cost (FIFO/AVECO);
* ``diff > 0`` (ortiqcha) → a new lot (``source_doc_type='stock_counts'``) at the current value —
  :func:`surplus_unit_cost` — and ``Dt inv_acct / Kt 9390``.

The offline ``stock_count.line_recorded`` payload (19 §14) is validated here for Bosqich 3.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from app.core.money import price, qty, to_decimal
from app.modules.inventory.domain.transfers import EventPayloadError

STATUSES: Final = ("counting", "review", "posted", "cancelled")
EMPLOYEE_ACCOUNT: Final = "4730"
SHORTAGE_ACCOUNT: Final = "5910"
SURPLUS_ACCOUNT: Final = "9390"
EVENT_LINE_RECORDED: Final = "stock_count.line_recorded"
ZERO_QTY: Final = Decimal("0.000")


def shortage_account(responsible_user_id: UUID | None) -> str:
    """13 §2.11: ``4730`` with a materially responsible person, else ``5910``."""
    return EMPLOYEE_ACCOUNT if responsible_user_id is not None else SHORTAGE_ACCOUNT


def surplus_unit_cost(
    last_purchase_cost: Decimal | None, balance_qty: Decimal, balance_value: Decimal
) -> Decimal:
    """13 §2.11 "joriy qiymat": the latest ``goods_receipts`` lot cost, else ``avg_costs.avg_cost``
    (both inside ``last_purchase_cost``), else the register average ``value / qty`` (FIFO tenants have
    no ``avg_costs`` row), else ``0`` (no value known — the lot enters at zero, no ledger line)."""
    if last_purchase_cost is not None and last_purchase_cost > 0:
        return price(last_purchase_cost)
    if balance_qty > 0 and balance_value > 0:
        return price(balance_value / balance_qty)
    return Decimal("0.0000")


@dataclass(frozen=True, slots=True)
class LineRecordedEvent:
    count_id: UUID
    product_id: UUID | None
    counted: Decimal
    barcode: str | None
    recorded_at: datetime


def parse_line_recorded(raw: Mapping[str, Any]) -> LineRecordedEvent:
    """Validate ``stock_count.line_recorded`` (19 §14; permission ``stock.count.create``):
    ``{count_id, product_id, counted (absolute, 3 dp), barcode?, recorded_at}``; ``product_id`` may be
    absent when only an unknown barcode was scanned (accepted with ``BARCODE_NOT_IN_CATALOG`` warning)."""
    try:
        count_id = UUID(str(raw["count_id"]))
    except (KeyError, ValueError):
        raise EventPayloadError("count_id", "validation.uuid") from None
    product_raw = raw.get("product_id")
    barcode = raw.get("barcode")
    if barcode is not None and (not isinstance(barcode, str) or not 1 <= len(barcode) <= 64):
        raise EventPayloadError("barcode", "validation.string")
    product_id: UUID | None = None
    if product_raw is not None:
        try:
            product_id = UUID(str(product_raw))
        except ValueError:
            raise EventPayloadError("product_id", "validation.uuid") from None
    elif barcode is None:
        raise EventPayloadError("product_id", "validation.required")
    counted_raw = raw.get("counted")
    if not isinstance(counted_raw, str):
        raise EventPayloadError("counted", "validation.decimal_string")
    try:
        counted = to_decimal(counted_raw)
    except ValueError:
        raise EventPayloadError("counted", "validation.decimal_string") from None
    if counted < 0 or counted != qty(counted):
        raise EventPayloadError("counted", "validation.non_negative")
    try:
        recorded_at = datetime.fromisoformat(str(raw["recorded_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        raise EventPayloadError("recorded_at", "validation.datetime") from None
    if recorded_at.tzinfo is None:
        raise EventPayloadError("recorded_at", "validation.datetime")
    return LineRecordedEvent(count_id, product_id, qty(counted), barcode, recorded_at.astimezone(UTC))
