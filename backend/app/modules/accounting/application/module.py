"""The accounting module facade published on ``app.state.accounting`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.accounting.application.adjustments import LedgerAdjustmentService
from app.modules.accounting.application.closings import PeriodClosingService
from app.modules.accounting.application.journal import JournalService
from app.modules.accounting.application.posting import LedgerPoster


@dataclass(slots=True)
class AccountingModule:
    journal: JournalService
    poster: LedgerPoster
    adjustments: LedgerAdjustmentService | None = None  # B5-T14 (20 #10–#10b)
    closings: PeriodClosingService | None = None  # B5-T13 (20 #14–#16)
