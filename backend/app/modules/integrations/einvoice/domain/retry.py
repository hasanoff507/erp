"""Outbox retry policy of the e-invoice operator jobs (21 §0 formula, §2/§3 numbers). Pure Python.

``next_run_at = now + min(cap, base × 2^(attempts − 1)) + jitter`` after the ``attempts``-th failed
try (``attempts ≥ 1``): 1, 2, 4, 8, 16, 32 minutes, then 60 minutes each — ``base = 1 min``,
``factor = 2``, ``cap = 1 h``; the 24th failed try is final (``failed``, dead letter, ≈ 18 h in
total). ``jitter`` is ``0 … 10 %`` of the delay so retried jobs of one outage do not arrive together.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

BASE_S: Final = 60
CAP_S: Final = 3600
MAX_ATTEMPTS: Final = 24
JITTER_SHARE: Final = 0.1


def backoff_seconds(attempts: int) -> int:
    """Delay (without jitter) after the ``attempts``-th failed try."""
    if attempts < 1:
        raise ValueError("attempts counts the tries made so far (≥ 1)")
    delay: int = BASE_S << min(attempts - 1, 16)
    return min(CAP_S, delay)


def exhausted(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS


def retry_delay(attempts: int, unit_random: float) -> timedelta:
    """Backoff + jitter after the ``attempts``-th failed try; ``unit_random`` ∈ [0, 1) — the jitter draw
    (injected so tests are deterministic). The outbox adds it to the database ``now()`` — the same clock
    the claim (``next_run_at <= now()``) compares with."""
    delay = backoff_seconds(attempts)
    return timedelta(seconds=delay + delay * JITTER_SHARE * min(max(unit_random, 0.0), 1.0))


def next_run_at(now: datetime, attempts: int, unit_random: float) -> datetime:
    return now + retry_delay(attempts, unit_random)
