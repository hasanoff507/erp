"""Marking rules: ``MARKING_PRECHECK`` decisions (18 §15, qaror #62) and the outbox retry policy (21 §4).
Pure Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

PrecheckMode = Literal["off", "warn", "block"]
DEFAULT_MODE: Final[PrecheckMode] = "warn"  # qaror #62
WARNING: Final = "MARKING_PRECHECK_WARNING"

# CRPT answers mapped to the 18 §15 reasons (``already_sold`` / ``expired`` / ``not_found``) + local ones
INVALID_REASONS: Final = frozenset(
    {"already_sold", "expired", "not_found", "written_off", "returned_to_supplier", "not_owner"}
)

# outbox_jobs kinds of the CRPT API (12 outbox_jobs CHECK; 21 §0)
VERIFY: Final = "marking_verify"
ACCEPT: Final = "marking_accept"
SUPPLIER_RETURN: Final = "marking_supplier_return"
WRITEOFF: Final = "marking_writeoff"
JOB_KINDS: Final = (VERIFY, ACCEPT, SUPPLIER_RETURN, WRITEOFF)

# 21 §4: base = 1 min, cap = 30 min (+ 0…10 % jitter, 21 §0 formula). ``marking_verify`` (the later check of
# offline-sold codes) gives up after 24 tries (≈ 9 h); the ownership notices keep retrying inside the group
# deadline window and become a dead letter (``failed`` + audit + M18) only once it is a day past ``due_at``.
BASE_S: Final = 60
CAP_S: Final = 1800
JITTER_SHARE: Final = 0.1
VERIFY_MAX_ATTEMPTS: Final = 24
NOTICE_GRACE: Final = timedelta(hours=24)
NOTICE_MAX_ATTEMPTS: Final = 400  # hard stop (≈ 8 days at the cap) when a job carries no due_at


def mode_of(raw: object) -> PrecheckMode:
    modes: dict[object, PrecheckMode] = {"off": "off", "warn": "warn", "block": "block"}
    return modes.get(raw, DEFAULT_MODE)


@dataclass(frozen=True, slots=True)
class Decision:
    """What ``POST /marking-codes/verify`` answers for a CRPT result (18 §15 table)."""

    outcome: Literal["ok", "warn", "fail", "unavailable"]
    audit: bool  # ``marking.precheck_failed`` (warn mode only)


def decide(mode: PrecheckMode, valid: bool | None) -> Decision:
    """``valid``: CRPT says valid (``True``), invalid (``False``) or did not answer (``None``)."""
    if valid is True:
        return Decision("ok", False)
    if mode == "block":
        return Decision("fail" if valid is False else "unavailable", False)
    if mode == "warn":
        return Decision("warn", True)
    return Decision("ok", False)  # off: the POS does not call; an explicit call just reports


def backoff_seconds(attempts: int) -> int:
    if attempts < 1:
        raise ValueError("attempts counts the tries made so far (≥ 1)")
    return min(CAP_S, BASE_S << min(attempts - 1, 16))


def retry_delay(attempts: int, unit_random: float) -> timedelta:
    delay = backoff_seconds(attempts)
    return timedelta(seconds=delay + delay * JITTER_SHARE * min(max(unit_random, 0.0), 1.0))


def exhausted(kind: str, attempts: int, now: datetime, due: datetime | None) -> bool:
    if kind == VERIFY:
        return attempts >= VERIFY_MAX_ATTEMPTS
    if due is not None:
        return now >= due + NOTICE_GRACE
    return attempts >= NOTICE_MAX_ATTEMPTS
