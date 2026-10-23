"""Delivery policy of the M18 Telegram notifications (21 §11, 20 #66–#71, 07 BO-20). Pure Python.

* who may receive a kind — :data:`AUDIENCE` (the permission a recipient needs besides ``telegram.link``);
* defaults of ``notification_settings`` (a kind without a row is enabled; ``daily_report`` at 21:00 Tashkent);
* the retry policy of ``outbox_jobs(kind='telegram')`` deliveries (21 §11: base 10 s, ×2, cap 5 min, 10
  tries);
* the link code alphabet (Telegram deep-link ``start`` parameter: ``[A-Za-z0-9_-]{1,64}``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Final

LINK_PERMISSION: Final = "telegram.link"
MANAGE_PERMISSION: Final = "notifications.manage"

# BO-20 / 20 #69 order of the kinds (GET /notification-settings always lists every kind in this order)
KIND_ORDER: Final[tuple[str, ...]] = (
    "daily_report", "low_stock", "expiry_soon", "cash_variance", "over_limit_action", "state_report_diff",
    "offline_48h", "subscription_due", "subscription_grace", "debt_due_today", "debt_aging_60",
    "debt_limit_exceeded_offline", "card_settlement_mismatch", "recurring_expense_due",
)  # fmt: skip

# the permission (15 §2.1) a linked user needs to receive the kind — the data in the message is what that
# permission shows on screen; a kind missing here is delivered to nobody (fail closed)
AUDIENCE: Final[dict[str, str]] = {
    "daily_report": "reports.finance.view",  # net profit (M15) is a financial report
    "low_stock": "stock.view",  # US-M04-02: the manager
    "expiry_soon": "stock.view",  # US-M04-06: owner/manager
    "cash_variance": "reports.finance.view",
    "over_limit_action": "reports.finance.view",
    "card_settlement_mismatch": "reports.finance.view",
    "debt_due_today": "reports.finance.view",
    "debt_aging_60": "reports.finance.view",
    "debt_limit_exceeded_offline": "reports.finance.view",
    "offline_48h": "reports.sales.view",
    "state_report_diff": "tax.compare.review",
    "subscription_due": "billing.manage",
    "subscription_grace": "billing.manage",
    "recurring_expense_due": "expenses.create",  # US-M15-02 reminder (never auto-paid)
}

DAILY_REPORT: Final = "daily_report"
DEFAULT_DAILY_TIME: Final = time(21, 0)  # 07 BO-20 default 21:00 (Asia/Tashkent)
TASHKENT: Final = timezone(timedelta(hours=5), "Asia/Tashkent")  # UTC+5 all year, no DST

# 21 §11 retry: base=10 s, factor=2, cap=5 min, max_attempts=10; jitter 0…10 % (21 §0 formula)
RETRY_BASE_S: Final = 10
RETRY_CAP_S: Final = 300
MAX_ATTEMPTS: Final = 10
JITTER_SHARE: Final = 0.1
EVENT_MAX_AGE: Final = timedelta(hours=24)  # an event older than this when first processed is dropped

_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
LINK_CODE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def parse_hhmm(value: str) -> time | None:
    """``"HH:mm"`` → :class:`time`; ``None`` when the format is wrong."""
    match = _TIME.match(value)
    return time(int(match.group(1)), int(match.group(2))) if match else None


def format_hhmm(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def local_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(TASHKENT)


def daily_report_due(now_local: datetime, at: time) -> bool:
    """The report of ``now_local.date()`` is due once the configured time has come (same calendar day)."""
    return now_local.time().replace(second=0, microsecond=0) >= at


def backoff_seconds(attempts: int) -> int:
    """Delay (without jitter) after the ``attempts``-th failed try (≥ 1): 10, 20, 40 … 300 s."""
    if attempts < 1:
        raise ValueError("attempts counts the tries made so far (>= 1)")
    return int(min(RETRY_CAP_S, RETRY_BASE_S << min(attempts - 1, 16)))


def retry_delay(attempts: int, unit_random: float, retry_after_s: int | None = None) -> timedelta:
    """Backoff + jitter; a Telegram ``429 retry_after`` is honoured when it is longer."""
    base = backoff_seconds(attempts)
    delay = base + base * JITTER_SHARE * min(max(unit_random, 0.0), 1.0)
    if retry_after_s is not None and retry_after_s > delay:
        delay = float(retry_after_s)
    return timedelta(seconds=delay)


def exhausted(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS
