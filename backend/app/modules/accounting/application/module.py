"""The accounting module facade published on ``app.state.accounting`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.accounting.application.journal import JournalService
from app.modules.accounting.application.posting import LedgerPoster


@dataclass(slots=True)
class AccountingModule:
    journal: JournalService
    poster: LedgerPoster
