"""SAQ job registry (23 §1: module ``tasks.py`` files are imported here)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.modules.cash.tasks import approval_requests_expire
from app.modules.imports.tasks import import_jobs_commit, import_jobs_validate  # catalog/import slice
from app.modules.integrations.card_terminal.tasks import card_orphan_sweep
from app.modules.integrations.einvoice.tasks import einvoice_ettn_send, einvoice_ettn_sweep
from app.modules.integrations.fiscal.tasks import fiscal_ofd_send, fiscal_ofd_sweep, fiscal_unacked_monitor
from app.modules.inventory.tasks import inventory_daily, inventory_recost, inventory_recost_sweep
from app.workers.jobs.approvals import approval_requests_expire_fanout
from app.workers.jobs.card import card_orphan_sweep_fanout
from app.workers.jobs.einvoice import einvoice_ettn_sweep_fanout
from app.workers.jobs.fiscal import fiscal_ofd_sweep_fanout, fiscal_unacked_monitor_fanout
from app.workers.jobs.inventory import inventory_daily_fanout, inventory_recost_sweep_fanout
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
    # --- Bosqich 2: inventory (recost, daily notifications/valuation switch) ---
    ("inventory_daily_fanout", inventory_daily_fanout),
    ("inventory_recost_sweep_fanout", inventory_recost_sweep_fanout),
    ("inventory_recost", inventory_recost),
    ("inventory_recost_sweep", inventory_recost_sweep),
    ("inventory_daily", inventory_daily),
    # --- Bosqich 2: e-TTN outbox (transfers, 21 §3) ---
    ("einvoice_ettn_sweep_fanout", einvoice_ettn_sweep_fanout),
    ("einvoice_ettn_send", einvoice_ettn_send),
    ("einvoice_ettn_sweep", einvoice_ettn_sweep),
    # --- B3 sales/fiscal jobs ---
    ("fiscal_ofd_sweep_fanout", fiscal_ofd_sweep_fanout),
    ("fiscal_unacked_monitor_fanout", fiscal_unacked_monitor_fanout),
    ("fiscal_ofd_send", fiscal_ofd_send),
    ("fiscal_ofd_sweep", fiscal_ofd_sweep),
    ("fiscal_unacked_monitor", fiscal_unacked_monitor),
    # --- B3 cash jobs ---
    ("approval_requests_expire_fanout", approval_requests_expire_fanout),
    ("approval_requests_expire", approval_requests_expire),
    # --- B3 card jobs ---
    ("card_orphan_sweep_fanout", card_orphan_sweep_fanout),
    ("card_orphan_sweep", card_orphan_sweep),
    # --- B3 sync jobs ---
    # --- B3 device-auth jobs ---
]
