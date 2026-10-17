"""``opening_stock`` import rows (US-M04-04, 19 §6, 11 §10) — pure parsing/validation, no I/O.

Template ``barcode;qty;unit_cost;expiry_date`` (19 §6). ``qty`` > 0 (≤ 3 dp), ``unit_cost`` ≥ 0
(≤ 4 dp, the cost per unit without VAT for a VAT payer), ``expiry_date`` optional ``YYYY-MM-DD``.
The barcode → product lookup happens in the service (catalog).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from app.modules.imports.domain.products import RowError

TEMPLATE_COLUMNS: Final[tuple[str, ...]] = ("barcode", "qty", "unit_cost", "expiry_date")
REQUIRED_COLUMNS: Final = frozenset({"barcode", "qty", "unit_cost"})

_QTY_RE: Final = re.compile(r"^\d{1,15}(\.\d{1,3})?$")
_COST_RE: Final = re.compile(r"^\d{1,14}(\.\d{1,4})?$")
_DATE_RE: Final = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T]00:00(?::00)?)?$")


@dataclass(frozen=True, slots=True)
class OpeningStockRow:
    row: int
    barcode: str
    qty: Decimal
    unit_cost: Decimal
    expiry_date: date | None


def parse_opening_row(row: int, raw: dict[str, str]) -> tuple[OpeningStockRow | None, list[RowError]]:
    errors: list[RowError] = []

    def err(field: str, message: str, code: str = "VALIDATION_ERROR") -> None:
        errors.append(RowError(row, field, code, message))

    barcode = raw.get("barcode", "").strip()
    if not barcode:
        err("barcode", "validation.required")

    quantity: Decimal | None = None
    qty_raw = raw.get("qty", "").strip().replace(",", ".")
    if not qty_raw:
        err("qty", "validation.required")
    elif not _QTY_RE.match(qty_raw):
        err("qty", "validation.decimal_format")
    else:
        quantity = Decimal(qty_raw).quantize(Decimal("0.001"))
        if quantity <= 0:
            err("qty", "validation.positive")
            quantity = None

    cost: Decimal | None = None
    cost_raw = raw.get("unit_cost", "").strip().replace(",", ".")
    if not cost_raw:
        err("unit_cost", "validation.required")
    elif not _COST_RE.match(cost_raw):
        err("unit_cost", "validation.decimal_format")
    else:
        cost = Decimal(cost_raw).quantize(Decimal("0.0001"))

    expiry: date | None = None
    expiry_raw = raw.get("expiry_date", "").strip()
    if expiry_raw:
        match = _DATE_RE.match(expiry_raw)
        try:
            expiry = date.fromisoformat(match.group(1)) if match else None
        except ValueError:
            expiry = None
        if expiry is None:
            err("expiry_date", "validation.date_format")

    if errors or quantity is None or cost is None:
        return None, errors
    return OpeningStockRow(row, barcode, quantity, cost, expiry), errors


def opening_template_csv() -> str:
    return ";".join(TEMPLATE_COLUMNS) + "\r\n"
