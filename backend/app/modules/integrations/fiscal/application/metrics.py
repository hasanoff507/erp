"""Fiscal metrics (G-08 / 23 §8 / 25 §5): OFD send outcomes and store-agent fiscal results."""

from __future__ import annotations

from prometheus_client import Counter

from app.core.telemetry import REGISTRY

OFD_SEND = Counter(
    "erp_fiscal_ofd_send_total",
    "Server-side fiscalization attempts (ofd_send) by outcome (done/retry/failed/skipped)",
    ["outcome"],
    registry=REGISTRY,
)
AGENT_RESULTS = Counter(
    "erp_fiscal_agent_results_total",
    "Store-agent fiscal task results applied, by kind (fiscal.status/resend_unsent/zreport)",
    ["kind"],
    registry=REGISTRY,
)
OFD_ACKS = Counter(
    "erp_fiscal_ofd_acks_total",
    "Receipts acknowledged by the OFD, by source (provider/agent)",
    ["source"],
    registry=REGISTRY,
)
