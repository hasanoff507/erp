"""Purchase order receipt progress (19 §10, 11 §8) — pure domain."""

from __future__ import annotations

from decimal import Decimal

from app.core.db.base import uuid7
from app.modules.purchasing.domain.purchase_orders import (
    PoLine,
    ReceivedLine,
    line_amount,
    received_lines,
    status_after_receipts,
)

A, B, C = uuid7(), uuid7(), uuid7()
LINES = (
    PoLine(id=uuid7(), line_no=1, product_id=A, qty=Decimal("50.000"), price=Decimal("12000.0000")),
    PoLine(id=uuid7(), line_no=2, product_id=B, qty=Decimal("10.000"), price=None),
)


def test_status_after_receipts() -> None:
    assert status_after_receipts(LINES, {}) == "sent"
    assert status_after_receipts(LINES, {A: Decimal("0.000")}) == "sent"
    assert status_after_receipts(LINES, {A: Decimal("48.000")}) == "partially_received"
    assert status_after_receipts(LINES, {A: Decimal("50.000")}) == "partially_received"
    assert status_after_receipts(LINES, {A: Decimal("50.000"), B: Decimal("10.000")}) == "closed"
    assert status_after_receipts(LINES, {A: Decimal("51.000"), B: Decimal("12.500")}) == "closed"  # excess
    assert status_after_receipts(LINES, {C: Decimal("1.000")}) == "partially_received"  # wrong item only
    assert status_after_receipts((), {}) == "sent"


def test_received_lines_lists_ordered_then_extras() -> None:
    got = received_lines(LINES, {A: Decimal("48.000"), C: Decimal("2.000")})
    assert got == [
        ReceivedLine(A, Decimal("50.000"), Decimal("48.000")),
        ReceivedLine(B, Decimal("10.000"), Decimal("0.000")),
        ReceivedLine(C, Decimal("0.000"), Decimal("2.000")),
    ]


def test_line_amount() -> None:
    assert line_amount(Decimal("2.500"), Decimal("1000.0000")) == Decimal("2500")
    assert line_amount(Decimal("1.000"), None) is None
