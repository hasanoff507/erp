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
    "marking_alert",  # B5 marking: CRPT/duplicate-code problems (16 §7, B3 F-5)
    "marking_acceptance_due",  # B5 marking: M07 acceptance deadline due soon / overdue (qaror #63)
    "late_in_closed_period",  # B5 accounting: late POS event into a closed month (16 §3.4, QT-M11-14)
    "onec_agent_paired",  # B5 agent: Do'kon agenti paired / revoked / unpaired (33 §13.3, W-04/W-05/A-10)
    "onec_base_error",  # B5 agent: machine_hash change, rejected task (33 §13.3; 1C base errors — Bosqich 7)
]

EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "daily_report", "low_stock", "cash_variance", "over_limit_action", "state_report_diff",
        "offline_48h", "subscription_due", "subscription_grace", "debt_due_today", "debt_aging_60",
        "debt_limit_exceeded_offline", "expiry_soon", "card_settlement_mismatch",
        "recurring_expense_due",
        "marking_alert", "marking_acceptance_due",  # B5 marking
        "late_in_closed_period",  # B5 accounting
        "onec_agent_paired", "onec_base_error",  # B5 agent
    }
)  # fmt: skip

OUTBOX_KIND: Final = "telegram"  # outbox_jobs.kind of every recorded notification event
