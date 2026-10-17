"""Offline sync rules (16 §2–§3, §8; 18 §2). Pure Python.

* event types — the final list of 16 §2; Bosqich 4 types are refused until their module lands;
* the permission each event needs from its ``actor_user_id`` (15 §2.1, 18/19 per event);
* ``retryable`` (16 §3.4): only a dependency that may still arrive, or a server fault, is retried;
* clock skew clamp (16 §8) and the ``devices.outbox_*`` arithmetic (16 §3.1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

EVENT_TYPES: Final = frozenset(
    {
        "shift.opened", "shift.closed", "sale.created", "sale.draft_voided", "receipt.reprinted",
        "return.created", "debt_payment.created", "cash_movement.created", "counterparty.created",
        "transfer.sent", "transfer.received", "stock_count.line_recorded", "expense.created",
    }
)  # fmt: skip
# 16 §2 types whose posting module is a later stage: refused, non-retryable, until a handler exists
LATER_STAGE_TYPES: Final[frozenset[str]] = frozenset()

# permission of the actor (who pressed the button, 16 §2) — None: the handler decides (e.g. deposit/withdraw)
EVENT_PERMISSIONS: Final[dict[str, str | None]] = {
    "shift.opened": "shift.open",
    "shift.closed": "shift.close",
    "sale.created": "sales.create",
    "sale.draft_voided": "sales.void",
    "receipt.reprinted": "sales.create",
    "return.created": "returns.create",
    "cash_movement.created": None,
    "debt_payment.created": "debts.payment.accept",
    "counterparty.created": "debts.create",
    "expense.created": None,  # POS cash expense: the handler checks cash.withdraw + limit (18 §13.2)
    "transfer.sent": "transfer.create",
    "transfer.received": "transfer.receive",
    "stock_count.line_recorded": "stock.count.create",
}

# 16 §3.3/§3.4: the device keeps retrying these automatically; everything else needs a human
RETRYABLE_CODES: Final = frozenset(
    {
        "SALE_NOT_FOUND",
        "DEPENDENCY_NOT_SYNCED",
        "TRANSFER_COST_PENDING",
        "PAYMENT_NOT_CONFIRMED",
        "INTERNAL_ERROR",
    }
)

# sync_exceptions kinds that M18 announces (16 §5, 15 §2.3) → notification event kind (20 #69)
NOTIFY_KINDS: Final[dict[str, str]] = {
    "debt_limit_exceeded_offline": "debt_limit_exceeded_offline",
    "approval_limit_exceeded_offline": "over_limit_action",
    "actor_unverified": "over_limit_action",
}

# 16 §5 — the CHECK list of app.sync_exceptions.kind
EXCEPTION_KINDS: Final = frozenset(
    {
        "price_mismatch", "archived_product", "stock_negative", "debt_limit_exceeded_offline",
        "approval_limit_exceeded_offline", "receipt_seq_conflict", "debt_overpayment_offline",
        "debt_allocation_mismatch", "late_in_closed_period", "cost_unknown", "count_late_move",
        "card_result_mismatch", "card_orphan_transaction", "actor_unverified", "late_in_closed_shift",
    }
)  # fmt: skip


def is_retryable(code: str) -> bool:
    return code in RETRYABLE_CODES


@dataclass(frozen=True, slots=True)
class Clamp:
    effective: datetime
    clamped: bool


def clamp_created_at(created_at: datetime, received_at: datetime, *, window_s: int, skew_s: int) -> Clamp:
    """16 §8: ``clamp(created_at, received_at − OFFLINE_CLAMP_WINDOW, received_at + CLOCK_SKEW_WARN_S)``."""
    low = received_at - timedelta(seconds=window_s)
    high = received_at + timedelta(seconds=skew_s)
    effective = min(max(created_at, low), high)
    return Clamp(effective, effective != created_at)


@dataclass(frozen=True, slots=True)
class OutboxReport:
    pending_count: int
    oldest_pending_at: datetime | None


def outbox_report(
    pending_count: int, oldest_pending_created_at: datetime | None, rejected_created_at: Iterable[datetime]
) -> OutboxReport:
    """16 §3.1: the device's not-sent part + the events rejected in this request (raw device clock)."""
    rejected = list(rejected_created_at)
    candidates = [*rejected, *([oldest_pending_created_at] if oldest_pending_created_at else [])]
    return OutboxReport(pending_count + len(rejected), min(candidates) if candidates else None)


def actor_was_active(status: str, membership_changed_at: datetime, event_at: datetime) -> bool:
    """14 §4.3: the actor's membership was active at ``created_at``. Memberships keep no history, so a
    ``blocked`` membership counts as active for events created before its last change (conservative:
    the block happened after the sale the cashier already made)."""
    if status == "active":
        return True
    return status == "blocked" and membership_changed_at > event_at
