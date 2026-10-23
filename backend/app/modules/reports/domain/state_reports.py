"""State-report upload deadlines (20 #3, 11 §9; Monday–Friday, weekends only)."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def parse_report_period(value: str) -> date | None:
    if not PERIOD_RE.fullmatch(value):
        return None
    return date.fromisoformat(f"{value}-01")


def _add_weekdays(value: datetime, count: int) -> datetime:
    result = value.astimezone(TASHKENT)
    added = 0
    while added < count:
        result += timedelta(days=1)
        if result.weekday() < 5:
            added += 1
    return result


def state_report_deadline(tax_type: str, period: date, published_at: datetime) -> datetime:
    """min(five weekdays after publication, statutory next-month filing date).

    The filing date is the date specified by the accounting rules: the 20th for VAT and
    the 15th for turnover tax. The five-day deadline counts weekdays only, as directed
    for this implementation; no public-holiday calendar is applied.
    """
    next_year = period.year + (1 if period.month == 12 else 0)
    next_month_number = 1 if period.month == 12 else period.month + 1
    next_month = date(next_year, next_month_number, 1)
    filing_day = 20 if tax_type == "vat" else 15
    filing_deadline = datetime.combine(
        next_month.replace(day=filing_day), time.max, tzinfo=TASHKENT
    )
    return min(_add_weekdays(published_at, 5), filing_deadline)
