"""Worker registry (23 §4): cron jobs land on the shared queue, so every worker must know them."""

from __future__ import annotations

from app.workers.cron import CRON_JOBS
from app.workers.jobs import FUNCTIONS


def test_every_cron_job_is_registered_in_the_regular_worker() -> None:
    # SAQ names a cron job by its function's __qualname__ (saq.Worker.__init__)
    registered = dict(FUNCTIONS)
    assert len(registered) == len(FUNCTIONS), "duplicate job names"
    for cron in CRON_JOBS:
        name = cron.function.__qualname__
        assert registered.get(name) is cron.function, f"cron job {name!r} missing from FUNCTIONS"


def test_regular_and_scheduler_workers_share_the_function_registry() -> None:
    from app.workers import worker_settings

    worker = worker_settings.settings()
    scheduler = worker_settings.scheduler_settings()
    assert worker["functions"] is scheduler["functions"] is FUNCTIONS
    assert "cron_jobs" not in worker
