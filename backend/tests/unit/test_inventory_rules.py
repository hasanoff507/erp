"""Valuation PATCH rules (19 §17), the cost-line analytics contract (13 §3.3), X-02 expected qty and the
``opening_stock`` import row parser (19 §6) — pure functions."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.imports.domain.opening_stock import opening_template_csv, parse_opening_row
from app.modules.inventory.domain.analytics import cost_analytics, cost_line_key
from app.modules.inventory.domain.counts import expected_count_qty
from app.modules.inventory.domain.valuation import (
    MethodRow,
    current_row,
    decide_change,
    method_on,
    pending_row,
)

TODAY = date(2026, 10, 17)
HISTORY = [MethodRow(date(2026, 1, 1), "aveco")]


def test_method_on_and_rows() -> None:
    assert method_on([], TODAY) == "aveco"  # signup default
    history = [*HISTORY, MethodRow(date(2027, 1, 1), "fifo")]
    assert method_on(history, TODAY) == "aveco" and method_on(history, date(2027, 1, 1)) == "fifo"
    assert current_row(history, TODAY) == HISTORY[0]
    assert pending_row(history, TODAY) == MethodRow(date(2027, 1, 1), "fifo")


@pytest.mark.parametrize(
    ("requested", "changed", "moves", "history", "expected"),
    [
        ("aveco", False, True, HISTORY, "noop"),  # same method → idempotent 200
        ("fifo", False, False, HISTORY, "immediate"),  # no stock_moves this year
        ("fifo", False, True, HISTORY, "pending"),  # → next 1 January
        ("fifo", True, False, HISTORY, "conflict"),  # one change per calendar year
        ("fifo", False, True, [*HISTORY, MethodRow(date(2027, 1, 1), "fifo")], "noop"),  # repeat pending
        ("aveco", False, True, [*HISTORY, MethodRow(date(2027, 1, 1), "fifo")], "conflict"),
    ],
)
def test_decide_change(
    requested: str, changed: bool, moves: bool, history: list[MethodRow], expected: str
) -> None:
    assert (
        decide_change(history, TODAY, requested, changed_this_year=changed, moves_this_year=moves) == expected
    )  # type: ignore[arg-type]


def test_cost_line_contract() -> None:
    p, w, ln, lot = uuid4(), uuid4(), uuid4(), uuid4()
    key = cost_line_key(product_id=p, warehouse_id=w, line_id=ln)
    analytics = cost_analytics(
        product_id=p, warehouse_id=w, line_id=ln, lot_ids=[lot, None, lot], extra={"employee_id": "e"}
    )
    assert analytics == {**key, "lot_ids": [str(lot)], "employee_id": "e"}
    assert key == {"stock_cost": True, "product_id": str(p), "warehouse_id": str(w), "line_id": str(ln)}
    with pytest.raises(ValueError, match="reserved"):
        cost_analytics(product_id=p, warehouse_id=w, line_id=ln, extra={"recost_job_id": "x"})


def test_x02_expected_count_qty() -> None:
    """13 X-02: snapshot 10 at T0, 2 sold at T1; counted at T2 > T1 → expected 8; at T0 < T2 < T1 → 10."""
    t0 = datetime(2026, 10, 1, 9, tzinfo=UTC)
    t1 = t0 + timedelta(hours=2)
    moves = [(t1, Decimal("-2.000"))]
    assert expected_count_qty(
        Decimal("10.000"), moves, started_at=t0, counted_at=t1 + timedelta(hours=1)
    ) == Decimal("8.000")
    assert expected_count_qty(
        Decimal("10.000"), moves, started_at=t0, counted_at=t0 + timedelta(hours=1)
    ) == Decimal("10.000")
    assert expected_count_qty(
        Decimal("10.000"), [(t0, Decimal("5"))], started_at=t0, counted_at=t1
    ) == Decimal("10.000")


def test_opening_stock_row_parser() -> None:
    assert opening_template_csv().strip() == "barcode;qty;unit_cost;expiry_date"
    row, errors = parse_opening_row(
        2, {"barcode": "4870001", "qty": "12", "unit_cost": "6500,5", "expiry_date": "2027-01-31"}
    )
    assert errors == [] and row is not None
    assert (row.qty, row.unit_cost, row.expiry_date) == (
        Decimal("12.000"),
        Decimal("6500.5000"),
        date(2027, 1, 31),
    )
    excel_date, _ = parse_opening_row(
        3, {"barcode": "1", "qty": "1", "unit_cost": "0", "expiry_date": "2027-02-01 00:00:00"}
    )
    assert excel_date is not None and excel_date.expiry_date == date(2027, 2, 1)
    bad, errors = parse_opening_row(
        4, {"barcode": "", "qty": "0", "unit_cost": "-1", "expiry_date": "31.01.2027"}
    )
    assert bad is None
    assert [(e.field, e.message) for e in errors] == [
        ("barcode", "validation.required"),
        ("qty", "validation.positive"),
        ("unit_cost", "validation.decimal_format"),
        ("expiry_date", "validation.date_format"),
    ]
