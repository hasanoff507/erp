"""SAQ job registry (23 §1: module ``tasks.py`` files are imported here)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.modules.imports.tasks import import_jobs_commit, import_jobs_validate  # catalog/import slice
from app.workers.jobs.system import (
    noop,
    purge_idempotency_keys,
    purge_idempotency_keys_fanout,
    purge_login_attempts,
)

FUNCTIONS: list[tuple[str, Callable[..., Awaitable[Any]]]] = [
    ("noop", noop),
    # cron jobs are enqueued onto the shared queue, so any regular worker may pick them up
    ("purge_login_attempts", purge_login_attempts),
    ("purge_idempotency_keys_fanout", purge_idempotency_keys_fanout),
    # per-tenant jobs (first argument tenant_id, 23 §4)
    ("purge_idempotency_keys", purge_idempotency_keys),
    # --- Bosqich 1 module jobs (catalog/import slice appends below this line) ---
    ("import_jobs_validate", import_jobs_validate),
    ("import_jobs_commit", import_jobs_commit),
]
