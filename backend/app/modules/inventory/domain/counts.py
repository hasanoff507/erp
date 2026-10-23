"""Expected quantity of a stock-count line (13 X-02, qaror #53). Pure Python — for the stock-counts posting.

``expected = snapshot_qty(started_at) + Σ stock_moves.qty (started_at < moved_at ≤ counted_at)``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal


def expected_count_qty(
    snapshot_qty: Decimal,
    moves: Iterable[tuple[datetime, Decimal]],
    *,
    started_at: datetime,
    counted_at: datetime,
) -> Decimal:
    """``moves`` = ``(moved_at, signed qty)`` of the line's (warehouse, product)."""
    return snapshot_qty + sum((q for at, q in moves if started_at < at <= counted_at), Decimal("0.000"))
