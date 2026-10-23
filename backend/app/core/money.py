"""Money / quantity / price rules (01 #26, 17 §3, 32 §3).

All arithmetic is ``Decimal`` with ROUND_HALF_UP; floats are rejected. The API
transports amounts as decimal strings, never JSON numbers.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Final

from pydantic import StringConstraints

MONEY_EXP: Final = Decimal("0.01")  # NUMERIC(18,2)
QTY_EXP: Final = Decimal("0.001")  # NUMERIC(18,3)
PRICE_EXP: Final = Decimal("0.0001")  # NUMERIC(18,4)
PERCENT_EXP: Final = Decimal("0.01")  # NUMERIC(5,2)
WHOLE_SUM: Final = Decimal("1")
HUNDRED: Final = Decimal("100")

DecimalInput = Decimal | str | int

# Pydantic field types for API schemas (32 §3.2: str, not Decimal)
MoneyStr = Annotated[str, StringConstraints(pattern=r"^-?\d{1,16}\.\d{2}$")]
QtyStr = Annotated[str, StringConstraints(pattern=r"^-?\d{1,15}\.\d{3}$")]
PriceStr = Annotated[str, StringConstraints(pattern=r"^-?\d{1,14}\.\d{4}$")]
PercentStr = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{2}$")]


def to_decimal(value: DecimalInput) -> Decimal:
    if isinstance(value, bool | float):  # bool is an int subclass
        raise TypeError("float/bool cannot be used for money or quantities (32 §3.2)")
    if isinstance(value, Decimal):
        result = value
    else:
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"not a finite decimal: {value!r}")
    return result


def _round(value: DecimalInput, exp: Decimal) -> Decimal:
    return to_decimal(value).quantize(exp, rounding=ROUND_HALF_UP)


def money(value: DecimalInput) -> Decimal:
    return _round(value, MONEY_EXP)


def qty(value: DecimalInput) -> Decimal:
    return _round(value, QTY_EXP)


def price(value: DecimalInput) -> Decimal:
    return _round(value, PRICE_EXP)


def percent(value: DecimalInput) -> Decimal:
    return _round(value, PERCENT_EXP)


def line_total(quantity: DecimalInput, unit_price: DecimalInput, discount: DecimalInput = "0") -> Decimal:
    """Receipt line total: ROUND_HALF_UP(qty × unit_price − discount, 0), kept as NUMERIC(18,2)."""
    raw = to_decimal(quantity) * to_decimal(unit_price) - to_decimal(discount)
    return raw.quantize(WHOLE_SUM, rounding=ROUND_HALF_UP).quantize(MONEY_EXP)


def vat_from_gross(amount: DecimalInput, rate_pct: DecimalInput) -> Decimal:
    """VAT included in a gross amount: ROUND_HALF_UP(amount × r / (100 + r), 2)."""
    rate = to_decimal(rate_pct)
    if rate < 0:
        raise ValueError("VAT rate cannot be negative")
    return money(to_decimal(amount) * rate / (HUNDRED + rate))


def to_tiyin(amount: DecimalInput) -> int:
    """Money → integer tiyin at the FiscalPort/CardTerminalPort boundary (01 #26)."""
    value = to_decimal(amount)
    if value != money(value):
        raise ValueError(f"amount has more than 2 decimal places: {value}")
    return int(value * HUNDRED)


def from_tiyin(tiyin: int) -> Decimal:
    if isinstance(tiyin, bool) or not isinstance(tiyin, int):
        raise TypeError("tiyin must be an int")
    return (Decimal(tiyin) / HUNDRED).quantize(MONEY_EXP)


def money_str(value: DecimalInput) -> str:
    return format(money(value), "f")


def qty_str(value: DecimalInput) -> str:
    return format(qty(value), "f")


def price_str(value: DecimalInput) -> str:
    return format(price(value), "f")


def percent_str(value: DecimalInput) -> str:
    return format(percent(value), "f")
