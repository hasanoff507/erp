"""SAQ job registry (23 §1: module ``tasks.py`` files are imported here)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.workers.jobs.system import noop, purge_login_attempts

FUNCTIONS: list[tuple[str, Callable[..., Awaitable[Any]]]] = [
    ("noop", noop),
    # cron jobs are enqueued onto the shared queue, so any regular worker may pick them up
    ("purge_login_attempts", purge_login_attempts),
]
