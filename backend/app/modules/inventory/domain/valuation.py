"""Valuation method rules (US-M04-05, 19 §17, 13 §3.1). Pure Python.

* The method in force on a date = the latest ``valuation_method_history.valid_from ≤ date``; a
  tenant without history uses AVECO (the signup default, 12 ``valuation_method_history``).
* ``PATCH`` rules: a change normally becomes a *pending* change effective next 1 January; it is
  applied immediately (``valid_from`` = this 1 January) when the tenant has no ``stock_moves`` in the
  current year; at most one change per calendar year; asking for the method already in force (with
  no pending change) or for the pending one is an idempotent ``200``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.modules.inventory.domain.costing import Method

DEFAULT_METHOD: Method = "aveco"


@dataclass(frozen=True, slots=True)
class MethodRow:
    valid_from: date
    method: Method


def method_on(history: Sequence[MethodRow], day: date) -> Method:
    current: Method = DEFAULT_METHOD
    for row in sorted(history, key=lambda r: r.valid_from):
        if row.valid_from <= day:
            current = row.method
    return current


def current_row(history: Sequence[MethodRow], day: date) -> MethodRow | None:
    rows = [r for r in history if r.valid_from <= day]
    return max(rows, key=lambda r: r.valid_from) if rows else None


def pending_row(history: Sequence[MethodRow], day: date) -> MethodRow | None:
    rows = [r for r in history if r.valid_from > day]
    return min(rows, key=lambda r: r.valid_from) if rows else None


Decision = Literal["noop", "immediate", "pending", "conflict"]


def decide_change(
    history: Sequence[MethodRow],
    today: date,
    requested: Method,
    *,
    changed_this_year: bool,
    moves_this_year: bool,
) -> Decision:
    """What ``PATCH /valuation-settings {method}`` does (19 §17).

    ``changed_this_year`` — an immediate change was already applied in this calendar year.
    """
    pending = pending_row(history, today)
    if pending is not None:
        return "noop" if pending.method == requested else "conflict"
    if method_on(history, today) == requested:
        return "noop"
    if changed_this_year:
        return "conflict"
    return "pending" if moves_this_year else "immediate"
