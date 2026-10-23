"""Pure rules of month closing (13 §5.1), manual adjustments (13 §2.23) and the balance sheet (20 #13)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.accounting.domain.adjustments import (
    AdjustmentInvalidError,
    balance_needs,
    checked_adjustment,
    debt_effects,
)
from app.modules.accounting.domain.closing import Readiness, close_verdict, parse_period
from app.modules.reports.domain.statements import balance_sheet

D = Decimal


def test_parse_period() -> None:
    assert parse_period("2026-10") == date(2026, 10, 1)
    assert (
        parse_period("2026-13") is None and parse_period("26-10") is None and parse_period("2026-1a") is None
    )


@pytest.mark.parametrize(
    ("period", "last", "first", "code"),
    [
        (date(2026, 9, 1), date(2026, 9, 1), None, "PERIOD_ALREADY_CLOSED"),
        (date(2026, 8, 1), date(2026, 9, 1), None, "PERIOD_ALREADY_CLOSED"),
        (date(2026, 11, 1), date(2026, 9, 1), None, "PERIOD_CLOSE_OUT_OF_ORDER"),  # QT-M11-14: 2026-10 open
        (date(2026, 10, 1), date(2026, 9, 1), None, None),
        (date(2026, 9, 1), None, date(2026, 8, 31), "PERIOD_CLOSE_OUT_OF_ORDER"),
        (date(2026, 8, 1), None, date(2026, 8, 31), None),
        (date(2026, 12, 1), date(2026, 11, 1), None, "validation.period_not_ended"),
    ],
)
def test_close_verdict(period: date, last: date | None, first: date | None, code: str | None) -> None:
    assert close_verdict(period, today=date(2026, 12, 3), last_closed=last, first_activity=first).code == code


def test_readiness_blockers_and_warnings() -> None:
    r = Readiness(date(2026, 10, 1), pending_recost_jobs=1, opening_0000_balance=D("-5.00"))
    assert r.blockers == ["recost_pending"] and r.warnings == ["opening_0000_nonzero"] and not r.ready
    assert Readiness(date(2026, 10, 1), open_shifts=1).ready


def _adj(**kw: object) -> object:
    base: dict[str, object] = {
        "branch_id": uuid4(), "doc_date": date(2026, 10, 5), "account_dt": "9430", "account_kt": "5010",
        "amount": "10.00", "comment": "x", "analytics": None, "correction_of_period": None,
        "today": date(2026, 10, 18), "go_live_date": date(2026, 6, 1),
    }  # fmt: skip
    base.update(kw)
    return checked_adjustment(**base)  # type: ignore[arg-type]


def test_checked_adjustment_rules() -> None:
    with pytest.raises(AdjustmentInvalidError) as exc:
        _adj(account_dt="2910", account_kt="2910", amount="0.00", comment=" ")
    keys = {(p.field, p.key) for p in exc.value.problems}
    assert ("account_dt", "validation.account_register_managed") in keys
    assert ("account_kt", "validation.same_account") in keys
    assert ("amount", "validation.positive") in keys and ("comment", "validation.required") in keys
    ok = _adj(account_dt="5010", account_kt="0000", doc_date=date(2026, 5, 31))
    assert ok.amount == D("10.00")  # type: ignore[attr-defined]


def test_debt_effects_and_balance_needs() -> None:
    assert [(e.direction, e.amount) for e in debt_effects("6310", "4010", D("5"))] == [
        ("receivable", D("-5"))
    ]
    assert [(e.direction, e.amount) for e in debt_effects("6010", "5110", D("5"))] == [("payable", D("-5"))]
    assert [n.what for n in balance_needs("6310", "4010", D("5"))] == ["receivable", "advance_6310"]


def test_balance_sheet_balances_with_unresolved_0000() -> None:
    sheet = balance_sheet({"2920": D("1000"), "4010": D("300"), "0000": D("-1300")})
    assert sheet.total_assets == sheet.total_liabilities_and_equity == D("1300")
    assert sheet.warnings == ["opening_0000_nonzero"]
    profit = balance_sheet({"5010": D("82"), "6410": D("-12"), "9020": D("-100"), "9420": D("30")})
    assert profit.equity == [("9910", D("70"))] and profit.liabilities == [("6410", D("12"))]
