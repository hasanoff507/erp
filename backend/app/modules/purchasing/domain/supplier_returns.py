"""Supplier return amounts and posting rules (13 §2.20, §3.2, §4.3, §5.3) — pure Python.

Per returned line (from one lot of one receipt line):

* ``cost`` = the receipt line's unit cost (without VAT);
* ``vat_amount`` = the line's share of the receipt line VAT:
  ``ROUND_HALF_UP(line_vat × qty / line_qty, 2)``; the return that completes the receipt line takes
  the remainder (``line_vat − Σ earlier shares``), so the shares never exceed the line VAT;
* ``invoice`` (settlement value with the supplier, without recoverable VAT):
  VAT regime → ``ROUND_HALF_UP(qty × cost, 2)``; turnover regime of the receipt (VAT sits in the
  lot cost, 13 §4.3) → ``ROUND_HALF_UP(qty × cost, 2) + vat_amount``;
* ``book`` = the issue cost of the returned units (FIFO — the lot cost; AVECO — ``qty × avg_cost``).

Ledger (13 §2.20): ``Dt 6010 / Kt inv_acct = min(invoice, book)``; ``invoice > book`` →
``Dt 6010 / Kt 9390 = invoice − book``; ``invoice < book`` → ``Dt 9430 / Kt inv_acct = book −
invoice``. Both ``Kt inv_acct`` lines carry the cost-line analytics key of the returned line, so
their sum equals ``−Σ stock_moves.cost_amount`` of the line (= ``book``), which is what recost
compares (13 §3.3; a specific-lot issue is never pending, so recost has nothing to change).
Row 2 (``Dt 6010 / Kt 4410``, VAT) and the negative ``vat_moves`` are **not** written here — they
come with the supplier's additional (negative) e-invoice (``supplier_return.vat_adjusted``, Bosqich 5).
``debt_moves`` payable ``−Σ invoice``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from app.core.money import money
from app.modules.accounting.domain.entries import LedgerLine

ZERO: Final = Decimal("0.00")
ZERO_QTY: Final = Decimal("0.000")
SUPPLIERS: Final = "6010"
OTHER_INCOME: Final = "9390"
OTHER_EXPENSE: Final = "9430"
RETURN_REASONS: Final = ("expired", "damaged", "excess", "other")
MAX_LINES: Final = 1000
REVERSE_SALE_MONTHS: Final = 12


@dataclass(frozen=True, slots=True)
class ReturnLine:
    id: UUID
    line_no: int
    receipt_line_id: UUID
    lot_id: UUID
    product_id: UUID
    qty: Decimal
    cost: Decimal
    vat_amount: Decimal
    product_name: str | None = None
    unit_code: str | None = None
    marking_codes: tuple[str, ...] = ()
    is_marked: bool = False

    @property
    def net(self) -> Decimal:
        return money(self.qty * self.cost)


@dataclass(frozen=True, slots=True)
class SupplierReturn:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    supplier_id: UUID
    supplier_name: str | None
    supplier_stir: str | None
    receipt_id: UUID
    receipt_number: str | None
    receipt_doc_date: date
    warehouse_id: UUID
    reason: str
    comment: str | None
    created_by: UUID
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    receipt_regime: str = "vat"  # tax regime in force on the receipt's doc_date (13 §4.3)
    vat_adjusted: bool = False  # row 2 written on the supplier's accepted additional EHF (13 §2.20)
    lines: tuple[ReturnLine, ...] = field(default_factory=tuple)
    line_count: int = 0
    net_total: Decimal = ZERO
    vat_total: Decimal = ZERO

    @property
    def invoice_total(self) -> Decimal:
        return self.net_total + self.vat_total if self.receipt_regime == "turnover" else self.net_total


def vat_share(
    line_vat: Decimal, line_qty: Decimal, qty: Decimal, earlier_qty: Decimal, earlier_vat: Decimal
) -> Decimal:
    """VAT of ``qty`` units of a receipt line; the return completing the line takes the remainder."""
    if earlier_qty + qty >= line_qty:
        return money(max(line_vat - earlier_vat, ZERO))
    return money(line_vat * qty / line_qty)


def invoice_amount(qty: Decimal, cost: Decimal, vat_amount: Decimal, *, regime: str) -> Decimal:
    net = money(qty * cost)
    return net + vat_amount if regime == "turnover" else net


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    last = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28, 31, 30, 31, 30, 31,
            31, 30, 31, 30, 31][month - 1]  # fmt: skip
    return date(year, month, min(day.day, last))


def reverse_sale_required(receipt_date: date, return_date: date) -> bool:
    """13 §2.20: a return more than 12 months after the receipt is a reverse sale, not a return."""
    return add_months(receipt_date, REVERSE_SALE_MONTHS) < return_date


def return_entries(
    *,
    invoice: Decimal,
    book: Decimal,
    inv_acct: str,
    entry_date: date,
    branch_id: UUID,
    cost_analytics: Mapping[str, Any],
    supplier_id: UUID,
) -> list[LedgerLine]:
    """The ledger lines of one returned line (13 §2.20 rows 1, 3a, 3b); zero amounts left out."""
    supplier = {"counterparty_id": str(supplier_id)}
    main = min(invoice, book)
    out = [LedgerLine(entry_date, branch_id, SUPPLIERS, inv_acct, main, {**cost_analytics})]
    if invoice > book:
        out.append(LedgerLine(entry_date, branch_id, SUPPLIERS, OTHER_INCOME, invoice - book, supplier))
    elif invoice < book:
        out.append(
            LedgerLine(entry_date, branch_id, OTHER_EXPENSE, inv_acct, book - invoice, {**cost_analytics})
        )
    return [x for x in out if x.amount > 0]
