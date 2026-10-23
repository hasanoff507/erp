"""Report date ranges (20 #12, #17–#19). Pure Python.

All report days are Asia/Tashkent business days (UTC+5, no DST — 16 §8): document dates (``doc_date``,
``entry_date``) are already Tashkent dates; register timestamps are cut at Tashkent midnight by the
infrastructure (:func:`day_bounds`).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Final, Literal

TASHKENT: Final = timezone(timedelta(hours=5), "Asia/Tashkent")
MAX_RANGE_DAYS: Final = 366

DashboardPeriod = Literal["today", "week", "month"]


class RangeError(ValueError):
    """An invalid report range — the API maps it to ``VALIDATION_ERROR`` (``field``, ``message_key``)."""

    def __init__(self, field: str, message_key: str) -> None:
        super().__init__(f"{field}: {message_key}")
        self.field = field
        self.message_key = message_key


@dataclass(frozen=True, slots=True)
class DateRange:
    """Inclusive ``[date_from, date_to]`` of Tashkent business days."""

    date_from: date
    date_to: date

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    def previous(self) -> DateRange:
        """The range of the same length that ends the day before this one starts ("kecha bilan")."""
        end = self.date_from - timedelta(days=1)
        return DateRange(end - timedelta(days=self.days - 1), end)

    def each_day(self) -> list[date]:
        return [self.date_from + timedelta(days=i) for i in range(self.days)]


def business_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(TASHKENT).date()


def day_bounds(rng: DateRange) -> tuple[datetime, datetime]:
    """``[start, end)`` aware instants of a range: 00:00 Tashkent of ``date_from`` … of ``date_to + 1``."""
    start = datetime.combine(rng.date_from, time.min, tzinfo=TASHKENT)
    end = datetime.combine(rng.date_to + timedelta(days=1), time.min, tzinfo=TASHKENT)
    return start, end


def checked_range(date_from: date | None, date_to: date | None, today: date) -> DateRange:
    """``date_from``/``date_to`` default to ``today``; the range must be ordered and ≤ 366 days."""
    start = date_from or date_to or today
    end = date_to or (date_from if date_from is not None else today)
    if start > end:
        raise RangeError("date_from", "validation.date_range")
    rng = DateRange(start, end)
    if rng.days > MAX_RANGE_DAYS:
        raise RangeError("date_to", "validation.date_range_too_long")
    return rng


def month_range(period: str) -> DateRange:
    """``"YYYY-MM"`` → the whole calendar month."""
    try:
        year_raw, month_raw = period.split("-")
        if len(year_raw) != 4 or len(month_raw) != 2:
            raise ValueError(period)
        first = date(int(year_raw), int(month_raw), 1)
    except ValueError:
        raise RangeError("period", "validation.period_format") from None
    return DateRange(first, first.replace(day=calendar.monthrange(first.year, first.month)[1]))


def dashboard_range(period: DashboardPeriod, today: date) -> DateRange:
    """BO-02 «Bugun / Hafta / Oy»: today; the calendar week so far (Monday…today); the month so far."""
    if period == "today":
        return DateRange(today, today)
    if period == "week":
        return DateRange(today - timedelta(days=today.weekday()), today)
    return DateRange(today.replace(day=1), today)
