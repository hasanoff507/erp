"""Notification event kinds (20 #69 ``notification-settings`` kinds, US-M18-03). Pure Python.

Modules *record* events (``outbox_jobs(kind='telegram')``); the M18 sender delivers them (Bosqich 4).
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
    "card_settlement_mismatch",
    "recurring_expense_due",  # US-M15-02 (b4-expenses)
]

EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "daily_report", "low_stock", "cash_variance", "over_limit_action", "state_report_diff",
        "offline_48h", "subscription_due", "subscription_grace", "debt_due_today", "debt_aging_60",
        "debt_limit_exceeded_offline", "expiry_soon", "card_settlement_mismatch",
        "recurring_expense_due",
    }
)  # fmt: skip

OUTBOX_KIND: Final = "telegram"  # outbox_jobs.kind of every recorded notification event
