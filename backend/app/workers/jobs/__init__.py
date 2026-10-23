"""SAQ job registry (23 §1: module ``tasks.py`` files are imported here)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.modules.cash.tasks import approval_requests_expire
from app.modules.debts.tasks import debts_daily
from app.modules.expenses.tasks import expenses_recurring_remind
from app.modules.imports.tasks import import_jobs_commit, import_jobs_validate  # catalog/import slice
from app.modules.integrations.card_terminal.tasks import (
    card_orphan_sweep,
    card_settlement_sweep,
    card_status_sweep,
)
from app.modules.integrations.einvoice.tasks import (
    einvoice_doc_send,
    einvoice_doc_sweep,
    einvoice_ettn_send,
    einvoice_ettn_sweep,
    einvoice_poll,
)
from app.modules.integrations.fiscal.tasks import (
    fiscal_ack_poll,
    fiscal_agent_status,
    fiscal_ofd_send,
    fiscal_ofd_sweep,
    fiscal_unacked_monitor,
)
from app.modules.integrations.marking.tasks import (  # B5 marking
    marking_acceptance_monitor,
    marking_outbox_run,
    marking_outbox_sweep,
)
from app.modules.integrations.payments.tasks import payments_checkout_expire  # B5 payments
from app.modules.inventory.tasks import inventory_daily, inventory_recost, inventory_recost_sweep
from app.modules.notifications.tasks import notifications_daily_report, notifications_telegram_sweep
from app.modules.onec_integration.tasks import onec_lease_sweeper
from app.workers.jobs.agent import onec_lease_sweeper_fanout
from app.workers.jobs.approvals import approval_requests_expire_fanout
from app.workers.jobs.card import card_orphan_sweep_fanout
from app.workers.jobs.debts import debts_daily_fanout
from app.workers.jobs.devices import card_settlement_sweep_fanout, card_status_sweep_fanout
from app.workers.jobs.einvoice import (
    einvoice_doc_sweep_fanout,
    einvoice_ettn_sweep_fanout,
    einvoice_poll_fanout,
)
from app.workers.jobs.expenses import expenses_recurring_remind_fanout
from app.workers.jobs.fiscal import (
    fiscal_ack_poll_fanout,
    fiscal_agent_status_fanout,
    fiscal_ofd_sweep_fanout,
    fiscal_unacked_monitor_fanout,
)
from app.workers.jobs.inventory import inventory_daily_fanout, inventory_recost_sweep_fanout
from app.workers.jobs.marking import marking_acceptance_monitor_fanout, marking_outbox_sweep_fanout
from app.workers.jobs.payments import payments_checkout_expire_fanout
from app.workers.jobs.system import (
    noop,
    purge_idempotency_keys,
    purge_idempotency_keys_fanout,
    purge_login_attempts,
)
from app.workers.jobs.telegram import notifications_daily_report_fanout, notifications_telegram_sweep_fanout

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
    # --- B4 debts jobs ---
    ("debts_daily_fanout", debts_daily_fanout),
    ("debts_daily", debts_daily),
    # --- B4 expenses jobs ---
    ("expenses_recurring_remind_fanout", expenses_recurring_remind_fanout),
    ("expenses_recurring_remind", expenses_recurring_remind),
    # --- B4 bank jobs ---
    # --- B4 reports jobs ---
    # --- B4 telegram jobs ---
    ("notifications_telegram_sweep_fanout", notifications_telegram_sweep_fanout),
    ("notifications_daily_report_fanout", notifications_daily_report_fanout),
    ("notifications_telegram_sweep", notifications_telegram_sweep),
    ("notifications_daily_report", notifications_daily_report),
    # --- B5 agent-auth jobs ---
    # --- B5 agent jobs ---
    ("onec_lease_sweeper_fanout", onec_lease_sweeper_fanout),
    ("onec_lease_sweeper", onec_lease_sweeper),
    # --- B5 fiscal jobs ---
    ("fiscal_agent_status_fanout", fiscal_agent_status_fanout),
    ("fiscal_ack_poll_fanout", fiscal_ack_poll_fanout),
    ("fiscal_agent_status", fiscal_agent_status),
    ("fiscal_ack_poll", fiscal_ack_poll),
    # --- B5 edocs jobs ---
    ("einvoice_doc_sweep_fanout", einvoice_doc_sweep_fanout),
    ("einvoice_poll_fanout", einvoice_poll_fanout),
    ("einvoice_doc_send", einvoice_doc_send),
    ("einvoice_doc_sweep", einvoice_doc_sweep),
    ("einvoice_poll", einvoice_poll),
    # --- B5 marking jobs ---
    ("marking_outbox_sweep_fanout", marking_outbox_sweep_fanout),
    ("marking_acceptance_monitor_fanout", marking_acceptance_monitor_fanout),
    ("marking_outbox_run", marking_outbox_run),
    ("marking_outbox_sweep", marking_outbox_sweep),
    ("marking_acceptance_monitor", marking_acceptance_monitor),
    # --- B5 payments jobs ---
    ("payments_checkout_expire_fanout", payments_checkout_expire_fanout),
    ("payments_checkout_expire", payments_checkout_expire),
    # --- B5 accounting jobs ---
    # --- B5 devices jobs ---
    ("card_status_sweep_fanout", card_status_sweep_fanout),
    ("card_settlement_sweep_fanout", card_settlement_sweep_fanout),
    ("card_status_sweep", card_status_sweep),
    ("card_settlement_sweep", card_settlement_sweep),
]
