"""Turnover-tax category/rate in force on a date (US-M14-04, 13 §4.3, QT-M14-03/04/05). Pure Python.

The category history is ``branch_tax_settings`` (``valid_from`` rows); a change
applies from its ``valid_from`` only — earlier periods keep the old category.
Rates come from the global ``platform.turnover_tax_rates`` (``code``, ``valid_from``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

SOLE_PROPRIETOR: Final = "sole_proprietor"


@dataclass(frozen=True, slots=True)
class TaxSetting:
    valid_from: date
    settlement_category: str
    activity_type: str


@dataclass(frozen=True, slots=True)
class RateRow:
    valid_from: date
    rate_pct: Decimal


@dataclass(frozen=True, slots=True)
class TurnoverRate:
    on_date: date
    settlement_category: str
    activity_type: str
    rate_code: str
    rate_pct: Decimal | None  # None — no platform rate row in force


def setting_in_force(history: Iterable[TaxSetting], on: date) -> TaxSetting | None:
    """The row with the greatest ``valid_from`` ≤ ``on``."""
    best: TaxSetting | None = None
    for row in history:
        if row.valid_from <= on and (best is None or row.valid_from > best.valid_from):
            best = row
    return best


def turnover_rate_code(settlement_category: str, activity_type: str, legal_form: str | None = None) -> str:
    """13 §4.3: YaTT → ``sole_proprietor``; retail → ``retail_<category>``; other activity → ``general``.

    (The tobacco share of the base uses ``tobacco`` by product group — that split belongs to the
    turnover-tax settlement, not to the branch.)
    """
    if legal_form == SOLE_PROPRIETOR:
        return SOLE_PROPRIETOR
    if activity_type == "retail":
        return f"retail_{settlement_category}"
    return "general"


def rate_in_force(rates: Iterable[RateRow], on: date) -> Decimal | None:
    best: RateRow | None = None
    for row in rates:
        if row.valid_from <= on and (best is None or row.valid_from > best.valid_from):
            best = row
    return None if best is None else best.rate_pct
