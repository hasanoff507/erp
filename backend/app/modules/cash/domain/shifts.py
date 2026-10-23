"""Shift close: expected cash, variance posting and the Z-report (18 §3.2, 13 §2.19 + X-01, US-M16-02/03).

* ``expected_cash = opening_cash + Σ cash_moves(shift_id, method='cash')`` — the opening cash is never a
  ``cash_moves`` row (X-01);
* ``variance = counted_cash − expected_cash``; ``≠ 0`` needs a ``variance_note``;
* variance posting (``doc_type='shifts'``): shortage Dt 4730 / Kt 5010 (``employee_id`` = the cashier who
  opened the shift), overage Dt 5010 / Kt 9390. Pure Python.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

ZERO: Final = Decimal("0.00")
PAYMENT_METHODS: Final[tuple[str, ...]] = ("cash", "card", "uzqr", "click", "payme", "uzum", "debt")


def m2(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def expected_cash(opening_cash: Decimal, cash_moves_total: Decimal) -> Decimal:
    return (opening_cash + cash_moves_total).quantize(Decimal("0.01"))


@dataclass(frozen=True, slots=True)
class VarianceEntry:
    account_dt: str
    account_kt: str
    amount: Decimal
    analytics: dict[str, Any]


def variance_entry(
    variance: Decimal, *, cashier_id: UUID, cash_register_id: UUID, shift_id: UUID
) -> VarianceEntry | None:
    """13 §2.19: shortage → Dt 4730 / Kt 5010 (employee analytics); overage → Dt 5010 / Kt 9390."""
    cash = {"cash_register_id": str(cash_register_id), "shift_id": str(shift_id)}
    if variance < 0:
        return VarianceEntry("4730", "5010", -variance, {**cash, "employee_id": str(cashier_id)})
    if variance > 0:
        return VarianceEntry("5010", "9390", variance, cash)
    return None


def variance_correction(
    before: Decimal, after: Decimal, *, cashier_id: UUID, cash_register_id: UUID, shift_id: UUID
) -> list[VarianceEntry]:
    """Lines that turn the posted variance ``before`` into ``after`` (late document, ACC-01, 13 X-01).

    Shortage part (4730) and overage part (9390) are corrected separately, so a correction that crosses
    zero both clears one side and books the other.
    """
    cash = {
        "cash_register_id": str(cash_register_id),
        "shift_id": str(shift_id),
        "correction": "late_document",
    }
    out: list[VarianceEntry] = []
    d_short = max(-after, ZERO) - max(-before, ZERO)
    if d_short > 0:
        out.append(VarianceEntry("4730", "5010", d_short, {**cash, "employee_id": str(cashier_id)}))
    elif d_short < 0:
        out.append(VarianceEntry("5010", "4730", -d_short, {**cash, "employee_id": str(cashier_id)}))
    d_over = max(after, ZERO) - max(before, ZERO)
    if d_over > 0:
        out.append(VarianceEntry("5010", "9390", d_over, cash))
    elif d_over < 0:
        out.append(VarianceEntry("9390", "5010", -d_over, cash))
    return out


@dataclass(frozen=True, slots=True)
class SettlementRow:
    card_terminal_id: UUID
    net_total: Decimal
    expected_total: Decimal
    variance: Decimal
    status: str


@dataclass(frozen=True, slots=True)
class ShiftTotals:
    """Register facts of one shift (posted documents only)."""

    totals_by_method: Mapping[str, Decimal]
    card_integrated: Decimal
    card_manual: Decimal
    vat_total: Decimal
    discount_total: Decimal
    returns_total: Decimal
    sales_count: int
    returns_count: int
    voided_count: int
    cash_in: Decimal
    cash_out: Decimal
    cash_moves_total: Decimal
    settlements: Sequence[SettlementRow] = field(default_factory=tuple)


def z_report(totals: ShiftTotals, *, expected: Decimal, counted: Decimal | None) -> dict[str, Any]:
    """The ``z_report`` object of 18 §3.2 (money as strings)."""
    return {
        "expected_cash": m2(expected),
        "counted_cash": None if counted is None else m2(counted),
        "variance": None if counted is None else m2(counted - expected),
        "totals_by_method": {k: m2(totals.totals_by_method.get(k, ZERO)) for k in PAYMENT_METHODS},
        "card_split": {"integrated": m2(totals.card_integrated), "manual": m2(totals.card_manual)},
        "card_settlements": [
            {
                "card_terminal_id": str(st.card_terminal_id),
                "net_total": m2(st.net_total),
                "expected_total": m2(st.expected_total),
                "variance": m2(st.variance),
                "status": st.status,
            }
            for st in totals.settlements
        ],
        "vat_total": m2(totals.vat_total),
        "discount_total": m2(totals.discount_total),
        "returns_total": m2(totals.returns_total),
        "sales_count": totals.sales_count,
        "returns_count": totals.returns_count,
    }


def running_totals(totals: ShiftTotals, *, expected: Decimal) -> dict[str, Any]:
    """``running_totals`` of an open shift (18 §3.3 ``GET /shifts/{id}``)."""
    return {
        "totals_by_method": {k: m2(totals.totals_by_method.get(k, ZERO)) for k in PAYMENT_METHODS},
        "sales_count": totals.sales_count,
        "voided_count": totals.voided_count,
        "returns_total": m2(totals.returns_total),
        "cash_in": m2(totals.cash_in),
        "cash_out": m2(totals.cash_out),
        "expected_cash": m2(expected),
    }
