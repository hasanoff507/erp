"""BO-02 «Diqqat talab qiladi» and the topbar bell (06 §1.9) — one list, ``GET /reports/dashboard`` →
``alerts[]``.

Each alert type has a fixed severity, a target screen (route of 07) and the permissions that make it visible
(any of them; empty = the dashboard permission ``reports.sales.view`` is enough). Tenant-wide alerts (no
branch dimension) are shown only to users whose branch scope is unrestricted (SEC-11). Pure Python.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

Severity = Literal["info", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class AlertRule:
    severity: Severity
    route: str
    requires: tuple[str, ...] = ()
    tenant_wide: bool = False


# order = display order (most urgent first)
RULES: Final[Mapping[str, AlertRule]] = {
    "fiscal_unacked": AlertRule("critical", "/app/settings/branches"),
    "state_report_diff": AlertRule(
        "critical", "/app/tax/reconciliation", ("tax.compare.review", "tax.vat.view"), tenant_wide=True
    ),
    "unsynced_devices": AlertRule("warning", "/app/settings/users?tab=devices"),
    "cash_variance": AlertRule("warning", "/app/reports?report=cash-history"),
    "overdue_debts": AlertRule("warning", "/app/debts", ("debts.payment.accept", "reports.finance.view")),
    "low_stock": AlertRule("warning", "/app/warehouse/stock?lowStockOnly=1", ("stock.view",)),
    "expiring_lots": AlertRule("warning", "/app/warehouse/stock?expiringWithinDays=7", ("stock.view",)),
    "sync_exceptions": AlertRule(
        "warning",
        "/app/settings/tenant?tab=sync-exceptions",
        ("settings.tenant", "accounting.post"),
        tenant_wide=True,
    ),
    "pending_approvals": AlertRule("info", "/app/approvals"),
    "einvoices_awaiting_signature": AlertRule("info", "/app/einvoices", ("einvoice.sign",), tenant_wide=True),
}


@dataclass(frozen=True, slots=True)
class Alert:
    type: str
    severity: Severity
    message_key: str
    count: int
    amount: Decimal | None
    route: str


def visible(rule: AlertRule, granted: frozenset[str], unrestricted: bool) -> bool:
    if rule.tenant_wide and not unrestricted:
        return False
    return not rule.requires or any(code in granted for code in rule.requires)


def build_alerts(
    counts: Mapping[str, tuple[int, Decimal | None]], granted: frozenset[str], unrestricted: bool
) -> list[Alert]:
    """Alerts with ``count > 0`` the caller may see, in :data:`RULES` order."""
    out: list[Alert] = []
    for kind, rule in RULES.items():
        count, amount = counts.get(kind, (0, None))
        if count <= 0 or not visible(rule, granted, unrestricted):
            continue
        out.append(Alert(kind, rule.severity, f"reports.alerts.{kind}", count, amount, rule.route))
    return out
