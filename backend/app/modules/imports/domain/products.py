"""``products`` import rows (US-M04-04, 19 §6, 11 §10) — pure parsing/validation, no I/O.

Template columns (03 US-M04-04):
``name;name_ru;barcode;unit_code;mxik_code;vat_rate;price;category;is_marked``.
Errors are row/field level, codes from the 17 §15 catalog, ``message`` is a ``validation.*`` i18n key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final

TEMPLATE_COLUMNS: Final[tuple[str, ...]] = (
    "name",
    "name_ru",
    "barcode",
    "unit_code",
    "mxik_code",
    "vat_rate",
    "price",
    "category",
    "is_marked",
)
REQUIRED_COLUMNS: Final = frozenset({"name", "unit_code", "vat_rate"})
SUPPORTED_KINDS: Final = frozenset({"products"})
ALL_KINDS: Final = frozenset({"products", "opening_stock", "opening_debts"})

_MXIK_RE: Final = re.compile(r"^[0-9]{17}$")
_BARCODE_RE: Final = re.compile(r"^[0-9A-Za-z\-.$/+%]{1,64}$")
_DECIMAL_RE: Final = re.compile(r"^\d{1,14}(\.\d{1,4})?$")
_VAT_RATES: Final = {Decimal("12.00"), Decimal("0.00")}
_TRUE: Final = frozenset({"1", "true", "ha", "yes", "y", "да", "x", "✓"})
_FALSE: Final = frozenset({"", "0", "false", "yo'q", "yoq", "no", "n", "нет"})
NAME_MAX: Final = 255
DEFAULT_MARKING_GROUP: Final = "general"


@dataclass(frozen=True, slots=True)
class RowError:
    row: int
    field: str
    code: str
    message: str

    def as_json(self) -> dict[str, Any]:
        return {"row": self.row, "field": self.field, "code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class ProductRow:
    row: int
    name: str
    name_ru: str | None
    barcode: str | None
    unit_code: str
    mxik_code: str | None
    vat_rate: Decimal
    price: Decimal | None
    category: str | None
    is_marked: bool


def cell_text(value: Any, column: str) -> str:
    """Spreadsheet cell → text. Numeric MXIK cells lose their leading zeros in Excel: pad back to 17."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        return f"{value:017d}" if column == "mxik_code" and 0 < len(str(value)) <= 17 else str(value)
    return str(value).strip()


def parse_product_row(
    row: int, raw: dict[str, str], unit_codes: set[str]
) -> tuple[ProductRow | None, list[RowError]]:
    errors: list[RowError] = []

    def err(field: str, message: str, code: str = "VALIDATION_ERROR") -> None:
        errors.append(RowError(row, field, code, message))

    name = raw.get("name", "").strip()
    if not name:
        err("name", "validation.required")
    elif len(name) > NAME_MAX:
        err("name", "validation.max_length")
    name_ru = raw.get("name_ru", "").strip() or None
    if name_ru is not None and len(name_ru) > NAME_MAX:
        err("name_ru", "validation.max_length")

    barcode = raw.get("barcode", "").strip() or None
    if barcode is not None and not _BARCODE_RE.match(barcode):
        err("barcode", "validation.barcode_format")

    unit_code = raw.get("unit_code", "").strip().lower()
    if not unit_code:
        err("unit_code", "validation.required")
    elif unit_code not in unit_codes:
        err("unit_code", "validation.unit_not_found")

    mxik = raw.get("mxik_code", "").strip() or None
    if mxik is not None and not _MXIK_RE.match(mxik):
        err("mxik_code", "validation.mxik_format", "MXIK_CODE_INVALID")

    vat_rate: Decimal | None = None
    vat_raw = raw.get("vat_rate", "").strip().rstrip("%").strip()
    if not vat_raw:
        err("vat_rate", "validation.required")
    else:
        try:
            vat_rate = Decimal(vat_raw).quantize(Decimal("0.01"))
        except InvalidOperation:
            vat_rate = None
        if vat_rate not in _VAT_RATES:
            err("vat_rate", "validation.vat_rate_not_allowed")
            vat_rate = None

    price: Decimal | None = None
    price_raw = raw.get("price", "").strip()
    if price_raw:
        if not _DECIMAL_RE.match(price_raw):
            err("price", "validation.decimal_format")
        else:
            price = Decimal(price_raw).quantize(Decimal("0.0001"))
            if price <= 0:
                err("price", "validation.positive")
                price = None

    category = raw.get("category", "").strip() or None
    if category is not None and len(category) > NAME_MAX:
        err("category", "validation.max_length")

    marked_raw = raw.get("is_marked", "").strip().lower()
    is_marked = marked_raw in _TRUE
    if not is_marked and marked_raw not in _FALSE:
        err("is_marked", "validation.boolean")

    if errors or vat_rate is None:
        return None, errors
    return (
        ProductRow(row, name, name_ru, barcode, unit_code, mxik, vat_rate, price, category, is_marked),
        errors,
    )


def template_csv(kind: str) -> str:
    if kind != "products":
        raise ValueError(kind)
    return ";".join(TEMPLATE_COLUMNS) + "\r\n"
