"""Composition of the accounting module (23 §1 ``wiring.py``).

Public posting toolkit for every posting service (other modules import it from here):

* :func:`ledger_poster` → :class:`LedgerPoster` — ``post`` / ``reverse_document`` /
  ``reverse_entries`` / ``assert_period_open`` / ``first_open_date`` (13 §5.1–§5.3);
* :class:`LedgerLine`, :class:`VatMove` — the values a posting writes;
* business calendar helpers (Asia/Tashkent): :func:`business_today`, :func:`business_date`, …
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.accounting.application.journal import JournalService
from app.modules.accounting.application.module import AccountingModule
from app.modules.accounting.application.ports import StoredEntry
from app.modules.accounting.application.posting import LedgerPoster, Posted, period_closed_error
from app.modules.accounting.domain.calendar import (
    TASHKENT,
    business_date,
    business_today,
    day_end,
    day_start,
    month_start,
    period_label,
)
from app.modules.accounting.domain.entries import LedgerLine, PostingError, VatMove
from app.modules.accounting.infrastructure.repositories import SqlLedgerRepository

__all__ = [
    "TASHKENT",
    "AccountingModule",
    "LedgerLine",
    "LedgerPoster",
    "Posted",
    "PostingError",
    "StoredEntry",
    "VatMove",
    "build_accounting_module",
    "business_date",
    "business_today",
    "day_end",
    "day_start",
    "ledger_poster",
    "month_start",
    "period_closed_error",
    "period_label",
]


def ledger_poster() -> LedgerPoster:
    return LedgerPoster(SqlLedgerRepository())


def build_accounting_module(settings: Settings, db: Database) -> AccountingModule:
    """B5 services (adjustments, closings) are attached by :mod:`app.modules.accounting.assembly` — this
    module is imported by every posting service and must not import other modules' wiring."""
    del settings
    repo = SqlLedgerRepository()
    return AccountingModule(journal=JournalService(db.session_factory, repo), poster=LedgerPoster(repo))
