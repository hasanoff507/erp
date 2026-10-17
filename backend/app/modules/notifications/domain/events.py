"""Notification event kinds (20 #69 ``notification-settings`` kinds, US-M18-03). Pure Python.

Bosqich 2 only *records* events (``outbox_jobs(kind='telegram')``); sending — Bosqich 4.
"""

from __future__ import annotations

from typing import Final, Literal

EventKind = Literal[
    "daily_report",
    "low_stock",
    "cash_variance",
    "over_limit_action",
    "state_report_diff",
    "offline_48h",
    "subscription_due",
    "subscription_grace",
    "debt_due_today",
    "debt_aging_60",
    "debt_limit_exceeded_offline",
    "expiry_soon",
]

EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "daily_report", "low_stock", "cash_variance", "over_limit_action", "state_report_diff",
        "offline_48h", "subscription_due", "subscription_grace", "debt_due_today", "debt_aging_60",
        "debt_limit_exceeded_offline", "expiry_soon",
    }
)  # fmt: skip

OUTBOX_KIND: Final = "telegram"  # outbox_jobs.kind of every recorded notification event
