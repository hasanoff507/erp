"""Pure FIFO/AVECO math (13 §3.1–§3.2a, §5.3) — every 13 example as numbers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.inventory.domain.costing import (
    Allocation,
    AvecoValueError,
    AvgState,
    LotView,
    aveco_credit,
    aveco_debit,
    aveco_issue,
    empties_all,
    fifo_piece_costs,
    lot_unit_cost,
    pending_unit_cost,
    plan_issue,
    return_pieces,
    split_amount,
)

D = Decimal
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def lot(qty_left: str, unit_cost: str, minutes: int, blocked: str = "0.000") -> LotView:
    return LotView(uuid4(), T0 + timedelta(minutes=minutes), D(qty_left), D(blocked), D(unit_cost))


def test_13_3_2_fifo_example() -> None:
    """Receipts 100 × 8000 and 50 × 9000, sale 120 → COGS 980000.00, 30 × 9000 = 270000.00 left."""
    first, second = lot("100.000", "8000.0000", 0), lot("50.000", "9000.0000", 1)
    plan = plan_issue([second, first], D("120.000"))  # order of input is irrelevant: received_at, id
    assert [(p.id, q) for p, q in plan.pieces] == [(first.id, D("100.000")), (second.id, D("20.000"))]
    assert plan.uncovered == 0 and plan.covered == D("120.000")
    costs = fifo_piece_costs(plan, register_value=D("0"), last_out=empties_all([first, second], plan))
    assert costs == [D("800000.00"), D("180000.00")] and sum(costs) == D("980000.00")
    assert D("30.000") * second.unit_cost == D("270000.0000000")


def test_13_3_2_aveco_example() -> None:
    """avg after receipt 2 = 1250000/150 = 8333.3333; sale 120 → 999999.996 → 1000000.00; left 250000.00."""
    state = aveco_credit(
        AvgState(D("0.000"), D("0.0000"), D("0.00")), D("0.000"), D("100.000"), D("800000.00")
    )
    assert state == AvgState(D("100.000"), D("8000.0000"), D("800000.00"))
    state = aveco_credit(state, D("100.000"), D("50.000"), D("450000.00"))
    assert state == AvgState(D("150.000"), D("8333.3333"), D("1250000.00"))
    cost, state = aveco_issue(state, D("120.000"), D("120.000"), last_out=False)
    assert cost == D("1000000.00")
    assert state == AvgState(D("30.000"), D("8333.3333"), D("250000.00"))  # old value − COGS, not qty × avg
    cost, state = aveco_issue(state, D("30.000"), D("30.000"), last_out=True)
    assert (cost, state.total_value) == (
        D("250000.00"),
        D("0.00"),
    )  # 30 × 8333.3333 = 249999.999 → takes 250000.00


def test_aveco_negative_stock_avg_unchanged_value_zero_and_settlement_math() -> None:
    """13 §3.1: qty_after ≤ 0 → avg unchanged, total_value 0; the pending part never enters the value.
    Then 10 units for 100000.00 into −2: avg 10000.0000 (divisor = units in lots, 10), 2 settled at
    20000.00 → 80000.00 for the 8 units left (exact)."""
    state = AvgState(D("5.000"), D("8000.0000"), D("40000.00"))
    cost, state = aveco_issue(state, D("7.000"), D("5.000"), last_out=True)  # 5 covered, 2 pending
    assert (cost, state) == (D("40000.00"), AvgState(D("-2.000"), D("8000.0000"), D("0.00")))
    state = aveco_credit(state, D("0.000"), D("10.000"), D("100000.00"))
    assert state == AvgState(D("8.000"), D("10000.0000"), D("100000.00"))
    settle, state = aveco_issue(state, D("2.000"), D("2.000"), last_out=False)
    assert settle == D("20000.00") and state.total_value == D("80000.00")


def test_13_3_2a_aveco_return_at_original_cost() -> None:
    """30 left at 8333.3333 (250000.00); a receipt 10 × 12000 → avg 9250.0000; return 5 at the original
    8333.3333 (41666.67) → 411666.67 / 45 = 9148.1482."""
    state = AvgState(D("30.000"), D("8333.3333"), D("250000.00"))
    state = aveco_credit(state, D("30.000"), D("10.000"), D("120000.00"))
    assert state.avg_cost == D("9250.0000")
    returned = Decimal("41666.67")
    assert (D("5") * D("8333.3333")).quantize(D("0.01")) == returned
    state = aveco_credit(state, D("40.000"), D("5.000"), returned)
    assert state == AvgState(D("45.000"), D("9148.1482"), D("411666.67"))


def test_aveco_debit_inverts_a_receipt() -> None:
    state = AvgState(D("150.000"), D("8333.3333"), D("1250000.00"))
    assert aveco_debit(state, D("150.000"), D("50.000"), D("450000.00")) == AvgState(
        D("100.000"), D("8000.0000"), D("800000.00")
    )


def test_13_3_2a_fifo_return_pieces_reverse_order() -> None:
    a, b = uuid4(), uuid4()
    issued = [Allocation(a, D("100.000"), D("8000.0000")), Allocation(b, D("20.000"), D("9000.0000"))]
    assert return_pieces(issued, D("0"), D("5.000")) == [Allocation(b, D("5.000"), D("9000.0000"))]
    assert return_pieces(issued, D("5.000"), D("30.000")) == [
        Allocation(b, D("15.000"), D("9000.0000")),
        Allocation(a, D("15.000"), D("8000.0000")),
    ]
    with pytest.raises(ValueError, match="exceeds"):
        return_pieces(issued, D("100.000"), D("21.000"))


def test_blocked_qty_and_specific_lot_plans() -> None:
    old = lot("10.000", "100.0000", 0, blocked="4.000")
    new = lot("5.000", "200.0000", 1)
    plan = plan_issue([old, new], D("8.000"))
    assert [(p.id, q) for p, q in plan.pieces] == [(old.id, D("6.000")), (new.id, D("2.000"))]
    specific = plan_issue([old, new], D("7.000"), lot_id=old.id)
    assert (specific.covered, specific.uncovered) == (D("6.000"), D("1.000"))
    blocked = plan_issue([old, new], D("3.000"), lot_id=old.id, from_blocked=True)
    assert (blocked.covered, blocked.uncovered) == (D("3.000"), D("0.000"))
    short = plan_issue([new], D("7.000"))
    assert (short.covered, short.uncovered) == (D("5.000"), D("2.000"))
    assert not empties_all([old, new], plan)  # blocked units stay


def test_fifo_last_out_takes_the_residual() -> None:
    only = lot("3.000", "333.3333", 0)
    plan = plan_issue([only], D("3.000"))
    assert fifo_piece_costs(plan, register_value=D("1000.00"), last_out=True) == [D("1000.00")]
    assert fifo_piece_costs(plan, register_value=D("1000.00"), last_out=False) == [D("1000.00")]
    one = plan_issue([only], D("1.000"))
    assert fifo_piece_costs(one, register_value=D("1000.00"), last_out=False) == [D("333.33")]


def test_split_amount_sums_exactly() -> None:
    assert split_amount(D("1000000.00"), [D("100.000"), D("20.000")], D("8333.3333")) == [
        D("833333.33"), D("166666.67"),
    ]  # fmt: skip
    assert split_amount(D("0.00"), [], D("1")) == []


def test_pending_estimate_chain() -> None:
    assert pending_unit_cost(
        "fifo", avg_cost=D("7"), last_lot_cost=D("8000"), last_purchase_cost=D("9")
    ) == D("8000.0000")
    assert pending_unit_cost("fifo", avg_cost=None, last_lot_cost=None, last_purchase_cost=D("9")) == D(
        "9.0000"
    )
    assert pending_unit_cost(
        "aveco", avg_cost=D("8333.3333"), last_lot_cost=D("9000"), last_purchase_cost=None
    ) == D("8333.3333")
    assert pending_unit_cost("aveco", avg_cost=D("0"), last_lot_cost=None, last_purchase_cost=None) == D(
        "0.0000"
    )


def test_lot_unit_cost_and_allocation_json() -> None:
    assert lot_unit_cost(D("1000.00"), D("3.000")) == D("333.3333")
    with pytest.raises(ValueError, match="lot quantity"):
        lot_unit_cost(D("1"), D("0"))
    lot_id = uuid4()
    piece = Allocation(lot_id, D("2"), D("8000"))
    raw = piece.as_json()
    assert raw == {"lot_id": str(lot_id), "qty": "2.000", "unit_cost": "8000.0000", "pending": False}
    assert Allocation.from_json(raw) == Allocation(lot_id, D("2.000"), D("8000.0000"))
    assert Allocation.from_json({"lot_id": None, "qty": "1", "unit_cost": "0", "pending": True}).pending


def test_aveco_debit_refuses_a_negative_or_unitless_value() -> None:
    """ACC-01: A 10 × 100 + B 10 × 200, 10 issued at 150 → 10 left worth 1500.00; cancelling B (2000.00)
    would leave −500.00; a debit of every unit must take exactly the whole value."""
    state = AvgState(D("10.000"), D("150.0000"), D("1500.00"))
    with pytest.raises(AvecoValueError):
        aveco_debit(state, D("10.000"), D("10.000"), D("2000.00"))
    with pytest.raises(AvecoValueError):
        aveco_debit(state, D("10.000"), D("10.000"), D("1499.99"))
    assert aveco_debit(state, D("10.000"), D("10.000"), D("1500.00")) == AvgState(
        D("0.000"), D("150.0000"), D("0.00")
    )


def test_fifo_piece_that_empties_its_lot_takes_the_lot_remaining_value() -> None:
    """ACC-03: lot 1 unit left of 3 for 100.00 (two issued at 33.33) → the last piece costs 33.34;
    a negative remaining value falls back to ROUND(q × unit_cost, 2); last_out still wins."""
    a, b = lot("1.000", "33.3333", 0), lot("1.000", "50.0000", 1)
    plan = plan_issue([a, b], D("1.000"))
    assert fifo_piece_costs(
        plan, register_value=D("0"), last_out=False, lot_values={a.id: (D("33.34"), 3)}
    ) == [D("33.34")]
    assert fifo_piece_costs(
        plan, register_value=D("0"), last_out=False, lot_values={a.id: (D("-0.01"), 3)}
    ) == [D("33.33")]
    both = plan_issue([a, b], D("2.000"))
    assert fifo_piece_costs(
        both,
        register_value=D("83.35"),
        last_out=True,
        lot_values={a.id: (D("33.34"), 3), b.id: (D("50.00"), 1)},
    ) == [D("33.34"), D("50.01")]


def test_fifo_repriced_lot_ignores_its_stale_move_value() -> None:
    """A lot repriced by an AVECO→FIFO switch (13 §3.1, no moves written) still holds its old move
    value (12.00 for 1 unit at the new 15.0000): the exhausting piece costs ROUND(q × unit_cost) = 15.00."""
    a = lot("1.000", "15.0000", 0)
    plan = plan_issue([a], D("1.000"))
    assert fifo_piece_costs(
        plan, register_value=D("0"), last_out=False, lot_values={a.id: (D("12.00"), 2)}
    ) == [D("15.00")]
