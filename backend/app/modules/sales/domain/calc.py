"""Receipt arithmetic of a POS sale (18 §4.1, §4.4, §4.5; 13 §2.1–§2.4, §5.3; qaror #26). Pure Python.

* :func:`check_line` — the server re-computation of ``line_total`` / ``vat_amount`` of one line
  (``line_total = ROUND_HALF_UP(qty × price − discount, 0)``, ``vat = ROUND_HALF_UP(line_total × r/(100+r),
  2)``);
* :func:`line_gross`, :func:`discount_pct` — ``ROUND_HALF_UP(qty × price, 0)`` and the server-side
  discount percent (``discount_amount / line_gross × 100``, 18 §4.4);
* :func:`allocate_last` / :func:`allocate_largest` — proportional split with the rounding rest on the last
  / the largest weight (13 §2.4 VAT by payment; 18 §4.5 mixed-receipt lines);
* :func:`fiscal_shares` — the first (non-debt) receipt of a mixed payment: per line amount, qty and VAT.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.money import HUNDRED, MONEY_EXP, QTY_EXP, line_total, money, qty, to_decimal, vat_from_gross

ZERO: Final = Decimal("0.00")
ONE_QTY: Final = Decimal("0.001")
PCT_EXP: Final = Decimal("0.01")
ALLOWED_VAT_RATES: Final = frozenset({Decimal("0.00"), Decimal("12.00")})


class CalcError(ValueError):
    """``field`` (relative to the line, e.g. ``line_total``) + ``message_key`` → ``422 VALIDATION_ERROR``."""

    def __init__(self, field: str, message_key: str) -> None:
        super().__init__(f"{field}: {message_key}")
        self.field = field
        self.message_key = message_key


def line_gross(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """``ROUND_HALF_UP(qty × price, 0)`` as money (18 §4.4)."""
    return line_total(quantity, unit_price)


def discount_pct(discount: Decimal, gross: Decimal) -> Decimal:
    if gross <= 0:
        return Decimal("0.00") if discount <= 0 else Decimal("100.00")
    return (to_decimal(discount) / gross * HUNDRED).quantize(PCT_EXP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class LineMath:
    gross: Decimal  # ROUND_HALF_UP(qty × price, 0)
    gross_vat: Decimal  # VAT of the list price (gross_9050 posting, 13 §2.1a)
    total: Decimal  # line_total — after discount, with VAT
    vat: Decimal  # vat_amount of line_total

    @property
    def net(self) -> Decimal:
        return money(self.total - self.vat)

    @property
    def list_net(self) -> Decimal:
        return money(self.gross - self.gross_vat)

    @property
    def discount_net(self) -> Decimal:
        """``(list_total − list_vat) − (net_total − net_vat)`` of this line (13 §2.1a row 1a)."""
        return money(self.list_net - self.net)


def check_line(
    quantity: Decimal,
    unit_price: Decimal,
    vat_rate: Decimal,
    discount: Decimal,
    sent_total: Decimal,
    sent_vat: Decimal,
) -> LineMath:
    """Server re-computation of one line; a mismatch with the device values is a ``CalcError``."""
    if quantity <= 0:
        raise CalcError("qty", "validation.greater_than")
    if unit_price < 0:
        raise CalcError("price", "validation.greater_than_equal")
    if vat_rate not in ALLOWED_VAT_RATES:
        raise CalcError("vat_rate", "validation.vat_rate")
    if discount < 0:
        raise CalcError("discount_amount", "validation.greater_than_equal")
    gross = line_gross(quantity, unit_price)
    if discount > to_decimal(quantity) * to_decimal(unit_price):
        raise CalcError("discount_amount", "validation.discount_exceeds_price")  # QT-M03-05
    total = line_total(quantity, unit_price, discount)
    if total != money(sent_total):
        raise CalcError("line_total", "validation.line_total_mismatch")
    vat = vat_from_gross(total, vat_rate)
    if vat != money(sent_vat):
        raise CalcError("vat_amount", "validation.vat_amount_mismatch")
    return LineMath(gross=gross, gross_vat=vat_from_gross(gross, vat_rate), total=total, vat=vat)


def _round(value: Decimal) -> Decimal:
    return value.quantize(MONEY_EXP, rounding=ROUND_HALF_UP)


def allocate_last(total: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    """``ROUND_HALF_UP(total × w / Σw, 2)`` each, the last one takes the rest (13 §2.4)."""
    if not weights:
        return []
    whole = sum(weights, ZERO)
    if whole == 0:
        return [ZERO for _ in weights[:-1]] + [money(total)]
    parts = [_round(to_decimal(total) * w / whole) for w in weights[:-1]]
    return [*parts, money(total - sum(parts, ZERO))]


def allocate_largest(total: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    """Proportional split; the rounding rest goes to the largest weight (ties — the later one, 18 §4.5)."""
    if not weights:
        return []
    whole = sum(weights, ZERO)
    if whole == 0:
        out = [ZERO for _ in weights]
        out[-1] = money(total)
        return out
    parts = [_round(to_decimal(total) * w / whole) for w in weights]
    biggest = max(range(len(weights)), key=lambda i: (weights[i], i))
    parts[biggest] = money(parts[biggest] + to_decimal(total) - sum(parts, ZERO))
    return parts


@dataclass(frozen=True, slots=True)
class FiscalShare:
    amount: Decimal
    qty: Decimal
    vat: Decimal


def fiscal_shares(
    totals: Sequence[Decimal], quantities: Sequence[Decimal], rates: Sequence[Decimal], non_debt: Decimal
) -> list[FiscalShare]:
    """18 §4.5: ``ratio = non_debt / total``; ``amt_i = ROUND_HALF_UP(line_total_i × ratio, 2)`` (rest to the
    largest line, ties — the larger line_no), ``qty_i = ROUND_HALF_UP(qty_i × ratio, 3)`` (≥ 0.001),
    ``vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)``. ``non_debt = total`` → the lines unchanged."""
    total = sum(totals, ZERO)
    if non_debt == total:
        return [
            FiscalShare(money(t), qty(q), vat_from_gross(t, r))
            for t, q, r in zip(totals, quantities, rates, strict=True)
        ]
    amounts = allocate_largest(non_debt, list(totals))
    ratio = to_decimal(non_debt) / total if total else Decimal(0)
    out: list[FiscalShare] = []
    for amount, quantity, rate in zip(amounts, quantities, rates, strict=True):
        share_qty = max((to_decimal(quantity) * ratio).quantize(QTY_EXP, rounding=ROUND_HALF_UP), ONE_QTY)
        out.append(FiscalShare(amount, share_qty, vat_from_gross(amount, rate)))
    return out


MARKING_MIN_LEN: Final = 18
MARKING_MAX_LEN: Final = 255
GS: Final = "\x1d"


def marking_code_valid(code: str) -> bool:
    """Local DataMatrix sanity check (18 §4.2 ``MARKING_CODE_INVALID``): 18–255 printable ASCII characters,
    GS (``\\x1d``) separators allowed inside, no surrounding whitespace. The CRPT check is ``verify``."""
    if not MARKING_MIN_LEN <= len(code) <= MARKING_MAX_LEN or code != code.strip() or code.startswith(GS):
        return False
    return all(ch == GS or 0x21 <= ord(ch) <= 0x7E for ch in code)
