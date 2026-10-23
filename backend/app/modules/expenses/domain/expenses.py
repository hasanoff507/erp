"""Expense rules (M15; 13 §2.17, §2.26; 20 #41–#51; 18 §13.2). Pure Python.

* :func:`credit_account` — ``source`` → Kt (``cash`` → 5010, ``bank``/``card`` → 5110, qaror #42/#49);
* :func:`tax_type_violation` — ``tax_type`` is mandatory for a ``6410`` category (tax payment to the budget,
  not an expense) and forbidden for every other category (QT-M15-06); on 6410 only the taxes accrued
  to Kt 6410 in MVP (``vat``, ``turnover``) are accepted (ACC-08, F5);
* :func:`crosses_tax_boundary` — a category's ``default_account`` never moves between 94xx and 6410;
* recurring rules: :func:`first_due_date`, :func:`add_period`, :func:`roll_forward`;
* :func:`reminder_text` — the US-M15-02 reminder ("Ijara to'lash vaqti: 3 000 000 so'm").
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

Source = Literal["cash", "bank", "card"]
Period = Literal["month", "quarter", "year"]

TAX_ACCOUNT: Final = "6410"
EXPENSE_ACCOUNTS: Final = frozenset({"9410", "9420", "9430"})
CATEGORY_ACCOUNTS: Final = frozenset({*EXPENSE_ACCOUNTS, TAX_ACCOUNT})
TAX_TYPES: Final = ("vat", "turnover", "pit", "social", "property", "land", "other")
# ACC-08 / F5: only these taxes are ever accrued to Kt 6410 in MVP (VAT at the sale, turnover via
# ``tax_settlements``); paying any other tax "to 6410" would leave a debit balance nothing offsets.
ACCRUED_TAX_TYPES: Final = frozenset({"vat", "turnover"})
SOURCES: Final = ("cash", "bank", "card")
PERIODS: Final = ("month", "quarter", "year")
_MONTHS: Final[dict[str, int]] = {"month": 1, "quarter": 3, "year": 12}
CASH_ACCOUNT: Final = "5010"
BANK_ACCOUNT: Final = "5110"


@dataclass(frozen=True, slots=True)
class Violation:
    field: str
    message_key: str


def credit_account(source: str) -> str:
    """13 §2.17: cash → 5010; bank and the tenant's corporate card → 5110 (5710 is inbound only)."""
    if source == "cash":
        return CASH_ACCOUNT
    if source in ("bank", "card"):
        return BANK_ACCOUNT
    raise ValueError(f"unknown expense source {source!r}")


def tax_type_violation(default_account: str, tax_type: str | None) -> Violation | None:
    """``tax_type`` ⇔ category account 6410 (13 §2.26, 20 #42)."""
    if default_account == TAX_ACCOUNT and tax_type is None:
        return Violation("tax_type", "validation.required")
    if default_account != TAX_ACCOUNT and tax_type is not None:
        return Violation("tax_type", "validation.must_be_null")
    if default_account == TAX_ACCOUNT and tax_type not in ACCRUED_TAX_TYPES:
        # property/land/other → «Davr soliqlari» (9430); social/JShDS → payroll 9410/9420 (qaror #52)
        return Violation("tax_type", "validation.tax_type_not_accrued")
    return None


def cash_refs_violations(
    source: str, cash_register_id: object | None, shift_id: object | None
) -> list[Violation]:
    """``source=cash`` needs the register and its open shift; other sources must not carry them."""
    out: list[Violation] = []
    if source == "cash":
        if cash_register_id is None:
            out.append(Violation("cash_register_id", "validation.required"))
        if shift_id is None:
            out.append(Violation("shift_id", "validation.required"))
    else:
        if cash_register_id is not None:
            out.append(Violation("cash_register_id", "validation.must_be_null"))
        if shift_id is not None:
            out.append(Violation("shift_id", "validation.must_be_null"))
    return out


def crosses_tax_boundary(old: str, new: str) -> bool:
    """A 94xx category never becomes a tax payment (6410) or back (drafts/reports would change meaning)."""
    return (old == TAX_ACCOUNT) != (new == TAX_ACCOUNT)


# --- recurring rules (US-M15-02) -----------------------------------------------------------------
def add_months(day: date, months: int, day_of_month: int) -> date:
    total = day.year * 12 + (day.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, min(day_of_month, monthrange(year, month)[1]))


def add_period(due: date, period: str, day_of_month: int) -> date:
    return add_months(due, _MONTHS[period], day_of_month)


def first_due_date(today: date, day_of_month: int) -> date:
    """The first ``day_of_month`` on or after ``today`` (this month or the next)."""
    this_month = date(today.year, today.month, day_of_month)
    return this_month if this_month >= today else add_months(today, 1, day_of_month)


def roll_forward(due: date, period: str, day_of_month: int, today: date) -> date:
    """Advance ``due`` by whole periods until it is on or after ``today`` (re-activated rule)."""
    while due < today:
        due = add_period(due, period, day_of_month)
    return due


def format_amount(amount: Decimal) -> str:
    """``3000000.00`` → ``3 000 000``; tiyin kept only when non-zero (``1500.50`` → ``1 500,50``)."""
    value = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, frac = divmod(value, 1)
    grouped = f"{int(whole):,}".replace(",", " ")
    if frac == 0:
        return grouped
    return f"{grouped},{format(frac, 'f')[2:]}"


def reminder_text(label: str, amount: Decimal) -> str:
    """US-M15-02 / QT-M15-02: ``"Ijara to'lash vaqti: 3 000 000 so'm"``."""
    return f"{label} to'lash vaqti: {format_amount(amount)} so'm"
