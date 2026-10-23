"""Month closing — ``period_closings`` (13 §5.1, §5.5; 20 #14–#16; qaror #23, #69). Pure Python.

* A period is a calendar month (``period_closings.period`` = its first day, API ``"YYYY-MM"``).
* Closing is **oldest-first**: the only month that may be closed is the one right after the last closed
  month; with nothing closed yet — the month of the first accounting activity (earliest ledger line or
  ``go_live_date − 1``). Anything else → ``409 PERIOD_CLOSE_OUT_OF_ORDER``; a month ≤ the last closed one →
  ``409 PERIOD_ALREADY_CLOSED``; a month that has not ended yet (its last day ≥ today, Tashkent) →
  ``422 validation.period_not_ended``. A closed month is never reopened.
* Readiness (``GET /period-closings/{period}/readiness``): ``ready = (blockers = [])``; blockers
  ``recost_pending``, ``fiscal_pending``, ``devices_unsynced``; warnings never block.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final

from app.modules.accounting.domain.calendar import month_start, next_month, period_label

BLOCKERS: Final = ("recost_pending", "fiscal_pending", "devices_unsynced")
WARNINGS: Final = (
    "tax_settlement_missing",
    "tax_settlement_stale",
    "opening_0000_nonzero",
    "open_shifts",
    "drafts_in_period",
    "devices_not_synced_after_period_end",
    "ledger_stock_mismatch",
)


def parse_period(raw: str) -> date | None:
    """``"YYYY-MM"`` → first day of the month; ``None`` when malformed."""
    parts = raw.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2 or not (parts[0] + parts[1]).isdigit():
        return None
    try:
        return date(int(parts[0]), int(parts[1]), 1)
    except ValueError:
        return None


def period_end(period: date) -> date:
    return period.replace(day=calendar.monthrange(period.year, period.month)[1])


def expected_period(last_closed: date | None, first_activity: date | None) -> date | None:
    """The only month ``POST /period-closings`` accepts now (``None`` = no activity yet: any ended month)."""
    if last_closed is not None:
        return next_month(last_closed)
    return None if first_activity is None else month_start(first_activity)


@dataclass(frozen=True, slots=True)
class CloseVerdict:
    code: str | None  # None = may close; else ErrorCode name / validation key
    expected: date | None = None


def close_verdict(
    period: date, *, today: date, last_closed: date | None, first_activity: date | None
) -> CloseVerdict:
    if last_closed is not None and period <= month_start(last_closed):
        return CloseVerdict("PERIOD_ALREADY_CLOSED")
    expected = expected_period(last_closed, first_activity)
    if expected is not None and period != expected:
        return CloseVerdict("PERIOD_CLOSE_OUT_OF_ORDER", expected)
    if period_end(period) >= today:
        return CloseVerdict("validation.period_not_ended")
    return CloseVerdict(None)


@dataclass(frozen=True, slots=True)
class UnsyncedDevice:
    device_id: str
    cash_register_name: str | None
    outbox_pending_count: int
    outbox_oldest_pending_at: str | None


@dataclass(frozen=True, slots=True)
class StaleSettlement:
    id: str
    tax_kind: str
    branch_id: str | None
    amount: Decimal
    current_amount: Decimal


@dataclass(frozen=True, slots=True)
class StockMismatch:
    account: str
    ledger_balance: Decimal
    stock_value: Decimal

    @property
    def difference(self) -> Decimal:
        return self.ledger_balance - self.stock_value


@dataclass(slots=True)
class Readiness:
    period: date
    pending_recost_jobs: int = 0
    pending_fiscal_receipts: int = 0
    unsynced_devices: list[UnsyncedDevice] = field(default_factory=list)
    tax_settlement_missing: bool = False
    stale_tax_settlements: list[StaleSettlement] = field(default_factory=list)
    opening_0000_balance: Decimal = Decimal("0.00")
    open_shifts: int = 0
    drafts_in_period: int = 0
    devices_not_synced: int = 0
    ledger_stock_mismatches: list[StockMismatch] = field(default_factory=list)

    @property
    def blockers(self) -> list[str]:
        flags = {
            "recost_pending": self.pending_recost_jobs > 0,
            "fiscal_pending": self.pending_fiscal_receipts > 0,
            "devices_unsynced": bool(self.unsynced_devices),
        }
        return [b for b in BLOCKERS if flags[b]]

    @property
    def warnings(self) -> list[str]:
        flags = {
            "tax_settlement_missing": self.tax_settlement_missing,
            "tax_settlement_stale": bool(self.stale_tax_settlements),
            "opening_0000_nonzero": self.opening_0000_balance != 0,
            "open_shifts": self.open_shifts > 0,
            "drafts_in_period": self.drafts_in_period > 0,
            "devices_not_synced_after_period_end": self.devices_not_synced > 0,
            "ledger_stock_mismatch": bool(self.ledger_stock_mismatches),
        }
        return [w for w in WARNINGS if flags[w]]

    @property
    def ready(self) -> bool:
        return not self.blockers

    @property
    def label(self) -> str:
        return period_label(self.period)
