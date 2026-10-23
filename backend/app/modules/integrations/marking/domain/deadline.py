"""Acceptance deadline of marked goods (ownership transfer notice, 21 §4 SLA; qaror #63). Pure Python.

``platform.marking_product_groups.acceptance_deadline``:

* ``72_hours`` — water/beverages (VM 631), medicines (VM 149), vegetable oil pilot (VM 23): the notice is due
  72 hours after ownership passes;
* ``3_business_days`` — every other group (VM 833 66–67-band): due at the end (24:00 Asia/Tashkent) of the
  third business day after the day ownership passes.

Conservative choices (the deadline is never later than the legal one): ownership passes at 00:00 Tashkent
of the earliest known date (receipt ``doc_date`` / e-invoice or e-TTN dispatch date); a business day is
Monday–Friday and public holidays are NOT skipped; when a receipt mixes groups the strictest (earliest)
deadline applies. Internal transfers have no deadline (no ownership transfer — VM 833 66–67, 26 #117).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Final, Literal

TASHKENT: Final = timezone(timedelta(hours=5), "Asia/Tashkent")  # UTC+5 all year, no DST
DeadlineKind = Literal["72_hours", "3_business_days"]
KINDS: Final[frozenset[str]] = frozenset({"72_hours", "3_business_days"})
BUSINESS_DAYS: Final = 3
# M18 warning before the deadline (21 §4 "muddat yaqinlashsa"): 24 h before for 72 h groups, one business day
# (24 h) for the others — the monitor warns once per stage
DUE_SOON: Final = timedelta(hours=24)


def ownership_start(doc_date: date, shipped_on: date | None = None) -> datetime:
    """00:00 Tashkent of the earliest known transfer date."""
    day = min(doc_date, shipped_on) if shipped_on is not None else doc_date
    return datetime.combine(day, time.min, tzinfo=TASHKENT)


def add_business_days(day: date, n: int) -> date:
    """The ``n``-th Monday–Friday day after ``day`` (``day`` itself is not counted)."""
    current, left = day, n
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def due_at(kind: str, start: datetime) -> datetime:
    if kind == "72_hours":
        return start + timedelta(hours=72)
    if kind == "3_business_days":
        last = add_business_days(start.astimezone(TASHKENT).date(), BUSINESS_DAYS)
        return datetime.combine(last + timedelta(days=1), time.min, tzinfo=TASHKENT)
    raise ValueError(f"unknown acceptance_deadline {kind!r}")


def strictest(kinds: set[str], start: datetime) -> tuple[DeadlineKind, datetime]:
    """The earliest deadline of the groups present (72 h ≤ 3 business days in practice, but computed)."""
    known = [k for k in kinds if k in KINDS] or ["3_business_days"]
    best = min(known, key=lambda k: (due_at(k, start), k != "72_hours"))
    return ("72_hours" if best == "72_hours" else "3_business_days"), due_at(best, start)


AcceptanceStage = Literal["pending", "due_soon", "overdue"]


def stage(due: datetime, now: datetime) -> AcceptanceStage:
    if now >= due:
        return "overdue"
    if now >= due - DUE_SOON:
        return "due_soon"
    return "pending"
