"""Composition of the M12 reports module (read-only, 23 §1; D4 — SQL over registers and documents).

Public API for other modules:

* :func:`daily_summary` → :class:`SummaryService` — ``await svc.for_day(s, tenant_id, day, branch_ids)``
  returns :class:`DailySummary` (Telegram evening report, 21 §11 / US-M18-02; contract
  ``.claude-scratch/b4/contracts/daily-summary.md``). Call it inside your own tenant transaction.
* :func:`build_reports_service` → :class:`ReportsService` for ``app.state.reports`` (the REST endpoints).
"""

from __future__ import annotations

from app.core.db.session import Database
from app.modules.reports.application.reports import ReportsService
from app.modules.reports.application.summary import SummaryService
from app.modules.reports.domain.daily_summary import (
    BranchDaySummary,
    CashRegisterCash,
    DailySummary,
    DebtorDue,
)
from app.modules.reports.infrastructure.reports_sql import SqlReportsRepository

__all__ = [
    "BranchDaySummary",
    "CashRegisterCash",
    "DailySummary",
    "DebtorDue",
    "ReportsService",
    "SummaryService",
    "build_reports_service",
    "daily_summary",
]


def daily_summary() -> SummaryService:
    return SummaryService(SqlReportsRepository())


def build_reports_service(db: Database) -> ReportsService:
    return ReportsService(db.session_factory, SqlReportsRepository())
