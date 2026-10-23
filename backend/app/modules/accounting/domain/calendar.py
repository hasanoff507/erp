"""Business calendar (16 §8, 13 §5.1): Asia/Tashkent dates and accounting periods. Pure Python.

Asia/Tashkent is UTC+5 all year (no DST), so a fixed offset is exact. A *period* is a calendar
month identified by its first day (``period_closings.period``, ``vat_moves.period``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Final

TASHKENT: Final = timezone(timedelta(hours=5), "Asia/Tashkent")


def business_date(at: datetime) -> date:
    """The Tashkent calendar date of an aware instant."""
    if at.tzinfo is None:
        raise ValueError("business_date() needs an aware datetime")
    return at.astimezone(TASHKENT).date()


def business_today(now: datetime | None = None) -> date:
    return business_date(now or datetime.now(UTC))


def day_start(day: date) -> datetime:
    """00:00 Tashkent of ``day`` as an aware instant."""
    return datetime.combine(day, time.min, tzinfo=TASHKENT)


def day_end(day: date) -> datetime:
    """The last microsecond of ``day`` in Tashkent (``day_start(day + 1) - 1 µs``)."""
    return day_start(day + timedelta(days=1)) - timedelta(microseconds=1)


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month(day: date) -> date:
    first = month_start(day)
    return date(first.year + 1, 1, 1) if first.month == 12 else date(first.year, first.month + 1, 1)


def period_label(day: date) -> str:
    """``"YYYY-MM"`` — the ``correction_of_period`` / ``PERIOD_CLOSED`` params format."""
    return f"{day.year:04d}-{day.month:02d}"


def year_start(day: date) -> date:
    return date(day.year, 1, 1)


def is_closed(day: date, last_closed_period: date | None) -> bool:
    """Closing is oldest-first (13 §5.1), so ``day`` is closed iff its month ≤ the latest closed month."""
    return last_closed_period is not None and month_start(day) <= month_start(last_closed_period)


def first_open_date(day: date, last_closed_period: date | None) -> date:
    """``day`` itself when its period is open, else the 1st day of the first open period (13 §5.1/§5.2)."""
    if not is_closed(day, last_closed_period):
        return day
    assert last_closed_period is not None
    return next_month(last_closed_period)
