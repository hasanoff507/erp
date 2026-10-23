"""Pure expense rules (13 §2.17, §2.26; US-M15-02)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.expenses.domain.expenses import (
    Violation,
    add_period,
    cash_refs_violations,
    credit_account,
    crosses_tax_boundary,
    first_due_date,
    format_amount,
    reminder_text,
    roll_forward,
    tax_type_violation,
)


def test_13_2_17_credit_account_by_source() -> None:
    assert credit_account("cash") == "5010"
    assert credit_account("bank") == "5110"
    assert credit_account("card") == "5110"  # corporate card pays from the bank account, 5710 is inbound only
    with pytest.raises(ValueError, match="unknown"):
        credit_account("click")


def test_qt_m15_06_tax_type_iff_6410() -> None:
    assert tax_type_violation("6410", None) == Violation("tax_type", "validation.required")
    assert tax_type_violation("6410", "vat") is None
    assert tax_type_violation("9410", "vat") == Violation("tax_type", "validation.must_be_null")
    assert tax_type_violation("9430", None) is None


@pytest.mark.parametrize("tax_type", ["pit", "social", "property", "land", "other"])
def test_acc08_unaccrued_tax_type_refused_on_6410(tax_type: str) -> None:
    """ACC-08 / F5: only VAT and turnover are accrued to Kt 6410 in MVP; the rest are expenses."""
    assert tax_type_violation("6410", tax_type) == Violation("tax_type", "validation.tax_type_not_accrued")
    assert tax_type_violation("6410", "turnover") is None


def test_cash_refs() -> None:
    assert [v.field for v in cash_refs_violations("cash", None, None)] == ["cash_register_id", "shift_id"]
    assert cash_refs_violations("cash", 1, 2) == []
    assert [v.message_key for v in cash_refs_violations("bank", 1, None)] == ["validation.must_be_null"]


def test_tax_boundary() -> None:
    assert crosses_tax_boundary("9410", "6410") and crosses_tax_boundary("6410", "9430")
    assert not crosses_tax_boundary("9410", "9420") and not crosses_tax_boundary("6410", "6410")


def test_qt_m15_02_reminder_text() -> None:
    assert reminder_text("Ijara", Decimal("3000000.00")) == "Ijara to'lash vaqti: 3 000 000 so'm"
    assert format_amount(Decimal("1500.50")) == "1 500,50"
    assert format_amount(Decimal("999.00")) == "999"


@pytest.mark.parametrize(
    ("today", "day", "expected"),
    [
        (date(2026, 10, 3), 5, date(2026, 10, 5)),
        (date(2026, 10, 5), 5, date(2026, 10, 5)),
        (date(2026, 10, 6), 5, date(2026, 11, 5)),
        (date(2026, 12, 20), 5, date(2027, 1, 5)),
    ],
)
def test_first_due_date(today: date, day: int, expected: date) -> None:
    assert first_due_date(today, day) == expected


def test_periods_and_roll_forward() -> None:
    assert add_period(date(2026, 11, 28), "month", 28) == date(2026, 12, 28)
    assert add_period(date(2026, 11, 10), "quarter", 10) == date(2027, 2, 10)
    assert add_period(date(2026, 2, 28), "year", 28) == date(2027, 2, 28)
    assert roll_forward(date(2026, 1, 5), "month", 5, date(2026, 4, 6)) == date(2026, 5, 5)
    assert roll_forward(date(2026, 5, 5), "month", 5, date(2026, 4, 6)) == date(2026, 5, 5)
