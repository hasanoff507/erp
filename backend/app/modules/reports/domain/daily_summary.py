"""The day/period figures of one branch — the building block of ``GET /reports/dashboard`` (20 #17) and of the
Telegram evening report (21 §11, US-M18-02, QT-M18-02). Pure Python.

Formulas (one source of truth for both consumers):

* ``gross_sales`` = Σ ``sales.total_amount`` of posted sales (``doc_date`` in the range); ``returns_total`` =
  Σ ``return_lines.line_total`` of posted customer returns; ``sales_total = gross_sales − returns_total`` (20
  #18); ``avg_receipt = gross_sales ÷ receipts_count`` (an average *receipt*, so returns do not dilute it);
* ``revenue`` = net revenue excl. VAT ``(Kt−Dt 9020) − (Dt−Kt 9040) − (Dt−Kt 9050)``; ``cogs`` = Dt−Kt 9120
  (returns put cost back with ``Dt inv_acct / Kt 9120``); ``expenses`` = Dt−Kt 9410/9420/9430/9820 (posted
  expenses, write-offs, written-off debts, commissions, turnover tax); ``other_income`` = Kt−Dt 9390;
  ``net_profit = revenue − cogs − expenses + other_income`` (US-M15-03, 13 §1/§5.1 — the P&L accounts);
* ``cash_on_hand`` (M16) — drawer cash at the end of the range per register (:class:`CashRegisterCash`);
* ``new_debts`` — the ``debt`` payment part of posted sales; ``debt_payments`` — posted customer debt
  payments; ``overdue_debt_total`` — open receivable documents due before the day after the range
  (``domain.debts``);
* ``low_stock_count`` — products with a balance row at or below ``products.min_stock`` (US-M04-02, "now").
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def m2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def average(total: Decimal, count: int) -> Decimal:
    return ZERO if count <= 0 else m2(total / count)


@dataclass(frozen=True)
class CashRegisterCash:
    cash_register_id: UUID
    name: str
    branch_id: UUID
    cash_on_hand: Decimal


@dataclass(frozen=True)
class DebtorDue:
    counterparty_id: UUID
    name: str
    phone: str | None
    amount_due: Decimal
    due_date: date


@dataclass(frozen=True)
class BranchDaySummary:
    branch_id: UUID
    branch_name: str
    sales_total: Decimal = ZERO
    gross_sales: Decimal = ZERO
    receipts_count: int = 0
    avg_receipt: Decimal = ZERO
    returns_total: Decimal = ZERO
    revenue: Decimal = ZERO
    cogs: Decimal = ZERO
    expenses: Decimal = ZERO
    other_income: Decimal = ZERO
    net_profit: Decimal = ZERO
    cash_on_hand: Decimal = ZERO
    new_debts: Decimal = ZERO
    debt_payments: Decimal = ZERO
    overdue_debt_total: Decimal = ZERO
    low_stock_count: int = 0


@dataclass(frozen=True)
class DailySummary:
    tenant_id: UUID
    day: date
    branches: tuple[BranchDaySummary, ...]
    total: BranchDaySummary
    cash_registers: tuple[CashRegisterCash, ...] = ()
    debtors_due_tomorrow: tuple[DebtorDue, ...] = ()
    unsynced_devices: bool = False
    unsynced_device_count: int = 0


def branch_summary(
    branch_id: UUID,
    branch_name: str,
    *,
    gross_sales: Decimal,
    receipts_count: int,
    returns_total: Decimal,
    revenue: Decimal,
    cogs: Decimal,
    expenses: Decimal,
    other_income: Decimal,
    cash_on_hand: Decimal,
    new_debts: Decimal,
    debt_payments: Decimal,
    overdue_debt_total: Decimal,
    low_stock_count: int,
) -> BranchDaySummary:
    return BranchDaySummary(
        branch_id=branch_id,
        branch_name=branch_name,
        sales_total=m2(gross_sales - returns_total),
        gross_sales=m2(gross_sales),
        receipts_count=receipts_count,
        avg_receipt=average(gross_sales, receipts_count),
        returns_total=m2(returns_total),
        revenue=m2(revenue),
        cogs=m2(cogs),
        expenses=m2(expenses),
        other_income=m2(other_income),
        net_profit=m2(revenue - cogs - expenses + other_income),
        cash_on_hand=m2(cash_on_hand),
        new_debts=m2(new_debts),
        debt_payments=m2(debt_payments),
        overdue_debt_total=m2(overdue_debt_total),
        low_stock_count=low_stock_count,
    )


def total_of(rows: Sequence[BranchDaySummary], tenant_id: UUID, low_stock_products: int) -> BranchDaySummary:
    """Exact sums of the branch rows (``avg_receipt`` recomputed; ``low_stock_count`` = distinct products)."""

    def s(attr: str) -> Decimal:
        return sum((getattr(r, attr) for r in rows), ZERO)

    return branch_summary(
        tenant_id,
        "",
        gross_sales=s("gross_sales"),
        receipts_count=sum(r.receipts_count for r in rows),
        returns_total=s("returns_total"),
        revenue=s("revenue"),
        cogs=s("cogs"),
        expenses=s("expenses"),
        other_income=s("other_income"),
        cash_on_hand=s("cash_on_hand"),
        new_debts=s("new_debts"),
        debt_payments=s("debt_payments"),
        overdue_debt_total=s("overdue_debt_total"),
        low_stock_count=low_stock_products,
    )
