"""Pure M12 report rules: date ranges (Asia/Tashkent), open receivable reconciliation, alert visibility."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.reports.domain.alerts import RULES, build_alerts
from app.modules.reports.domain.daily_summary import branch_summary, total_of
from app.modules.reports.domain.debts import DebtDoc, due_on_total, overdue_total, reconcile
from app.modules.reports.domain.periods import (
    DateRange,
    RangeError,
    business_today,
    checked_range,
    dashboard_range,
    day_bounds,
    month_range,
)

D = Decimal


def test_dashboard_ranges_today_week_month() -> None:
    friday = date(2026, 10, 16)
    assert dashboard_range("today", friday) == DateRange(friday, friday)
    assert dashboard_range("week", friday) == DateRange(date(2026, 10, 12), friday)  # Monday…today
    assert dashboard_range("month", friday) == DateRange(date(2026, 10, 1), friday)
    assert DateRange(date(2026, 10, 12), friday).previous() == DateRange(
        date(2026, 10, 7), date(2026, 10, 11)
    )


def test_checked_range_defaults_and_errors() -> None:
    today = date(2026, 10, 16)
    assert checked_range(None, None, today) == DateRange(today, today)
    assert checked_range(date(2026, 10, 1), None, today) == DateRange(date(2026, 10, 1), date(2026, 10, 1))
    with pytest.raises(RangeError) as inverted:
        checked_range(date(2026, 10, 2), date(2026, 10, 1), today)
    assert (inverted.value.field, inverted.value.message_key) == ("date_from", "validation.date_range")
    with pytest.raises(RangeError) as too_long:
        checked_range(date(2025, 1, 1), date(2026, 1, 3), today)
    assert too_long.value.message_key == "validation.date_range_too_long"
    assert month_range("2026-02") == DateRange(date(2026, 2, 1), date(2026, 2, 28))
    with pytest.raises(RangeError):
        month_range("2026-2")


def test_tashkent_day_boundaries() -> None:
    # 19:30 UTC is already the next day in Tashkent (UTC+5)
    assert business_today(datetime(2026, 10, 16, 19, 30, tzinfo=UTC)) == date(2026, 10, 17)
    start, end = day_bounds(DateRange(date(2026, 10, 17), date(2026, 10, 17)))
    assert start == datetime(2026, 10, 16, 19, 0, tzinfo=UTC) and end == datetime(
        2026, 10, 17, 19, 0, tzinfo=UTC
    )


def _doc(cp: object, amount: str, doc_day: int, due_day: int | None = None) -> DebtDoc:
    return DebtDoc(
        counterparty_id=cp,  # type: ignore[arg-type]
        branch_id=uuid4(),
        doc_type="sales",
        doc_id=uuid4(),
        doc_date=date(2026, 10, doc_day),
        due_date=None if due_day is None else date(2026, 10, due_day),
        amount=D(amount),
    )


def test_reconcile_consumes_unplaced_reductions_oldest_first() -> None:
    cp = uuid4()
    old, mid, new = _doc(cp, "10000.00", 1, 5), _doc(cp, "20000.00", 3), _doc(cp, "30000.00", 10, 20)
    # balance 35000 < 60000 of documents (a write-off reduced the balance): the oldest are closed first
    opened = reconcile([new, old, mid], D("35000.00"))
    # order: mid (no due date → doc_date 03.10), old (due 05.10), new (due 20.10)
    assert [(o.doc_id, o.open_amount) for o in opened] == [
        (old.doc_id, D("5000.00")),
        (new.doc_id, D("30000.00")),
    ]
    assert sum((o.open_amount for o in opened), D("0")) == D("35000.00")
    assert overdue_total(opened, date(2026, 10, 15)) == D("5000.00")
    assert due_on_total(opened, date(2026, 10, 20)) == D("30000.00")
    assert reconcile([old], D("0.00")) == [] and reconcile([old], D("-5.00")) == []


def test_acc12_effective_due_is_original_due_date() -> None:
    """ACC-12 / F6: overdue by ``COALESCE(due_date, doc_date)``; a customer promise never moves it."""
    cp = uuid4()
    late = _doc(cp, "7000.00", 1, 2)
    future = _doc(cp, "3000.00", 10, 30)
    opened = reconcile([late, future], D("10000.00"))
    assert [o.effective_due for o in opened] == [date(2026, 10, 2), date(2026, 10, 30)]
    assert overdue_total(opened, date(2026, 10, 17)) == D("7000.00")


def test_alerts_visibility_and_order() -> None:
    counts = {
        "low_stock": (2, None),
        "state_report_diff": (1, None),
        "pending_approvals": (0, None),
        "overdue_debts": (3, D("90000.00")),
    }
    everything = frozenset({"stock.view", "tax.vat.view", "reports.finance.view"})
    alerts = build_alerts(counts, everything, unrestricted=True)
    assert [a.type for a in alerts] == ["state_report_diff", "overdue_debts", "low_stock"]
    assert alerts[1].amount == D("90000.00") and alerts[1].route == RULES["overdue_debts"].route
    assert [a.type for a in build_alerts(counts, frozenset({"stock.view"}), unrestricted=True)] == [
        "low_stock"
    ]
    # tenant-wide alerts never reach a branch-restricted user
    assert "state_report_diff" not in [a.type for a in build_alerts(counts, everything, unrestricted=False)]


def test_total_of_sums_branches_and_recomputes_average() -> None:
    a = branch_summary(
        uuid4(), "A", gross_sales=D("36000"), receipts_count=2, returns_total=D("0"), revenue=D("32142.86"),
        cogs=D("24000"), expenses=D("1000"), other_income=D("0"), cash_on_hand=D("36000"), new_debts=D("0"),
        debt_payments=D("0"), overdue_debt_total=D("0"), low_stock_count=1,
    )  # fmt: skip
    b = branch_summary(
        uuid4(), "B", gross_sales=D("12000"), receipts_count=1, returns_total=D("2000"), revenue=D("8928.57"),
        cogs=D("6000"), expenses=D("0"), other_income=D("100"), cash_on_hand=D("10000"), new_debts=D("5000"),
        debt_payments=D("1000"), overdue_debt_total=D("700"), low_stock_count=1,
    )  # fmt: skip
    assert (a.avg_receipt, a.net_profit) == (D("18000.00"), D("7142.86"))
    total = total_of([a, b], uuid4(), low_stock_products=1)
    assert (total.sales_total, total.receipts_count, total.avg_receipt) == (D("46000.00"), 3, D("16000.00"))
    assert total.net_profit == a.net_profit + b.net_profit == D("10171.43")
    assert total.low_stock_count == 1  # distinct products, not a sum
