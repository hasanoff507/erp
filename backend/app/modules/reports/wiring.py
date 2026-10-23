"""Composition of the M12 reports module (read-only, 23 §1; D4 — SQL over registers and documents).

Public API for other modules:

* :func:`daily_summary` → :class:`SummaryService` — ``await svc.for_day(s, tenant_id, day, branch_ids)``
  returns :class:`DailySummary` (Telegram evening report, 21 §11 / US-M18-02; contract
  ``.claude-scratch/b4/contracts/daily-summary.md``). Call it inside your own tenant transaction.
* :func:`build_reports_service` → :class:`ReportsService` for ``app.state.reports`` (the REST endpoints).
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import Database
from app.modules.attachments.application.service import AttachmentService
from app.modules.reports.application.accounting_reports import AccountingReportsService
from app.modules.reports.application.reports import AlertSource, ReportsService
from app.modules.reports.application.state_reports import StateReportsService
from app.modules.reports.application.summary import SummaryService
from app.modules.reports.domain.daily_summary import (
    BranchDaySummary,
    CashRegisterCash,
    DailySummary,
    DebtorDue,
)
from app.modules.reports.infrastructure.accounting_sql import SqlAccountingReports
from app.modules.reports.infrastructure.reports_sql import SqlReportsRepository
from app.modules.reports.infrastructure.state_reports_sql import SqlStateReportsRepository

__all__ = [
    "AccountingReportsService",
    "BranchDaySummary",
    "CashRegisterCash",
    "DailySummary",
    "DebtorDue",
    "ReportsService",
    "StateReportsService",
    "SummaryService",
    "build_accounting_reports_service",
    "build_reports_service",
    "build_state_reports_service",
    "daily_summary",
]


def daily_summary() -> SummaryService:
    return SummaryService(SqlReportsRepository())


def _alert_sources() -> list[AlertSource]:
    """BO-02 counts published by b5-fiscal / b5-edocs (contracts/accounting.md), when present."""
    sources: list[AlertSource] = []
    fiscal = getattr(importlib.import_module("app.modules.integrations.fiscal.wiring"), "fiscal_alerts", None)
    if fiscal is not None:  # contracts/fiscal.md §2: fiscal_alerts(s, *, at, branch_ids) -> FiscalAlerts

        async def fiscal_counts(
            s: AsyncSession, tenant_id: UUID, branch_ids: tuple[UUID, ...] | None
        ) -> Mapping[str, int]:
            del tenant_id
            found = await fiscal(s, at=datetime.now(UTC), branch_ids=branch_ids)
            return {"fiscal_unacked": int(found.fiscal_unacked)}

        sources.append(fiscal_counts)
    einvoice = getattr(
        importlib.import_module("app.modules.integrations.einvoice.wiring"), "einvoice_alerts", None
    )
    if einvoice is not None:

        async def edocs(
            s: AsyncSession, tenant_id: UUID, branch_ids: tuple[UUID, ...] | None
        ) -> Mapping[str, int]:
            del tenant_id, branch_ids  # contracts/edocs.md §5c: einvoice_alerts(s) -> {kind: count}
            found = await einvoice(s)
            return {"einvoices_awaiting_signature": int(found.get("incoming_awaiting_signature", 0))}

        sources.append(edocs)
    return sources


def build_reports_service(db: Database) -> ReportsService:
    return ReportsService(db.session_factory, SqlReportsRepository(), _alert_sources())


def build_accounting_reports_service(db: Database) -> AccountingReportsService:
    """M11 statements (20 #11, #13, #20a) — published on ``app.state.accounting_reports`` (B5)."""
    return AccountingReportsService(db.session_factory, SqlAccountingReports())


def build_state_reports_service(db: Database, attachments: AttachmentService) -> StateReportsService:
    """BO-10 upload and report history (20 #3, #5–#6)."""
    return StateReportsService(db.session_factory, SqlStateReportsRepository(), attachments)
