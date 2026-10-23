"""Fiscal rules (21 §1, 18 §4.5/§4.10, 16 §6/§8, qaror #43/#64). Pure Python.

* :func:`payment_form` — ``fiscal_receipts.payment_form`` from the payment methods of a receipt;
* 48 h timer: :data:`OFFLINE_WARN_HOURS`, :data:`OFFLINE_BLOCK_HOURS`, :func:`offline_stage`;
* :func:`effective_created_at` — the server clamp of a device timestamp (16 §8, QT-OFFLINE48-02);
* :func:`ofd_backoff` — the ``ofd_send`` retry policy of the server-side providers (21 §1);
* :func:`qr_url` — the OFD check link format.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Final, Literal

PaymentForm = Literal["cash", "card", "qr", "mixed"]
QR_METHODS: Final = frozenset({"uzqr", "click", "payme", "uzum"})
FM_STATES: Final = ("ok", "locked", "ack_overdue", "memory_full", "unknown")

OFFLINE_WARN_HOURS: Final = (24, 40, 46)
OFFLINE_BLOCK_HOURS: Final = 48
OFFLINE_STAGES: Final = (*OFFLINE_WARN_HOURS, OFFLINE_BLOCK_HOURS)

# 16 §8: effective_created_at = clamp(created_at, received_at − 7 days, received_at + 300 s)
OFFLINE_CLAMP_WINDOW: Final = timedelta(days=7)
CLOCK_SKEW_WARN: Final = timedelta(seconds=300)

# 21 §1 partner cloud: base 30 s, factor 2, cap 15 min; from 40 h of the oldest unacked receipt — every 2 min;
# the job never stops inside the 48 h window (no attempts limit for transient errors)
OFD_BASE_S: Final = 30
OFD_CAP_S: Final = 15 * 60
OFD_LATE_S: Final = 120
OFD_LATE_AFTER: Final = timedelta(hours=40)

OFD_CHECK_URL: Final = "https://ofd.soliq.uz/check"


def payment_method_form(method: str) -> PaymentForm | None:
    if method == "cash":
        return "cash"
    if method == "card":
        return "card"
    if method in QR_METHODS:
        return "qr"
    return None  # debt is not a fiscal payment form


def payment_form(methods: Iterable[str]) -> PaymentForm:
    """cash / card (always card for card payments) / qr (uzqr, click, payme, uzum) / mixed (several forms).

    ``debt`` parts are not on the receipt (18 §4.5). An empty set is a programming error."""
    forms = {f for f in (payment_method_form(m) for m in methods) if f is not None}
    if not forms:
        raise ValueError("a fiscal receipt needs at least one non-debt payment")
    if len(forms) > 1:
        return "mixed"
    return next(iter(forms))


def effective_created_at(created_at: datetime, received_at: datetime) -> datetime:
    """16 §8: the device clock clamped into ``[received_at − 7 d, received_at + 300 s]``."""
    low, high = received_at - OFFLINE_CLAMP_WINDOW, received_at + CLOCK_SKEW_WARN
    return min(max(created_at, low), high)


def was_clamped(created_at: datetime, received_at: datetime) -> bool:
    return effective_created_at(created_at, received_at) != created_at


def offline_age(oldest_unacked_at: datetime | None, at: datetime) -> timedelta | None:
    return None if oldest_unacked_at is None else max(at - oldest_unacked_at, timedelta(0))


def offline_stage(oldest_unacked_at: datetime | None, at: datetime) -> int | None:
    """The highest reached stage (24 / 40 / 46 / 48) of the register's timer at ``at``; ``None`` < 24 h."""
    age = offline_age(oldest_unacked_at, at)
    if age is None:
        return None
    reached = [h for h in OFFLINE_STAGES if age >= timedelta(hours=h)]
    return reached[-1] if reached else None


def is_blocked(oldest_unacked_at: datetime | None, at: datetime) -> bool:
    """48 h rule (qaror #43): a new fiscal receipt is refused when the oldest unacked one is ≥ 48 h old."""
    return offline_stage(oldest_unacked_at, at) == OFFLINE_BLOCK_HOURS


def ofd_backoff(attempts: int, *, late: bool) -> timedelta:
    """Delay after the ``attempts``-th failed try (≥ 1)."""
    if attempts < 1:
        raise ValueError("attempts counts the tries made so far (≥ 1)")
    if late:
        return timedelta(seconds=OFD_LATE_S)
    return timedelta(seconds=min(OFD_CAP_S, OFD_BASE_S << min(attempts - 1, 16)))


def qr_url(terminal_id: str, fm_receipt_seq: int, fiscal_at: datetime, fiscal_sign: str) -> str:
    """``https://ofd.soliq.uz/check?t={TerminalID}&r={ReceiptSeq}&c={YYYYMMDDHHMMSS}&s={FiscalSign}``."""
    return f"{OFD_CHECK_URL}?t={terminal_id}&r={fm_receipt_seq}&c={fiscal_at:%Y%m%d%H%M%S}&s={fiscal_sign}"
