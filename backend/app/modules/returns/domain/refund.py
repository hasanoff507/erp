"""Refund arithmetic of a POS return (18 §7.1, 13 §2.5, §3.2a). Pure Python.

* :func:`refund_line` — ``ROUND_HALF_UP(sale_line.line_total × ret_qty / sale_line.qty, 0)``; the line's last
  return takes the rest (``line_total − Σ earlier refund_line``), so a fully returned line refunds exactly
  its ``line_total``;
* :func:`split_refund` — ``debt_part = min(return_amount, open_debt_of_sale)`` (``Kt 4010``, no receipt),
  ``money_part`` = the rest (``refund_method``, the ``kind='return'`` receipt).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from app.core.money import line_total, money, to_decimal

ZERO: Final = Decimal("0.00")
# the "no limit" value of a returns.approve check — only an unlimited approver covers it (expired goods,
# qaror #48: the approver must be a Manager/Owner); fits doc_approvals.requested_value NUMERIC(18,4)
UNLIMITED_ONLY: Final = Decimal("99999999999999.9999")


def refund_line(
    sale_total: Decimal,
    sale_qty: Decimal,
    ret_qty: Decimal,
    returned_qty: Decimal,
    refunded: Decimal,
) -> Decimal:
    """Refund of ``ret_qty`` of a sale line; ``returned_qty`` (refunded ``refunded``) went back already."""
    if ret_qty <= 0 or returned_qty + ret_qty > sale_qty:
        raise ValueError("return quantity outside the sold quantity")
    if returned_qty + ret_qty == sale_qty:
        return money(to_decimal(sale_total) - refunded)
    return line_total(Decimal(1), to_decimal(sale_total) * ret_qty / sale_qty)


@dataclass(frozen=True, slots=True)
class RefundSplit:
    debt_part: Decimal
    money_part: Decimal


def split_refund(return_amount: Decimal, open_debt: Decimal, refund_method: str) -> RefundSplit:
    """13 §2.5: the sale's open debt shrinks first; ``debt_adjustment`` puts everything on the account."""
    if refund_method == "debt_adjustment":
        return RefundSplit(money(return_amount), ZERO)
    debt_part = money(min(return_amount, max(open_debt, ZERO)))
    return RefundSplit(debt_part, money(return_amount - debt_part))
