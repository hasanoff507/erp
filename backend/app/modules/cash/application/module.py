"""The cash module facade published on ``app.state.cash`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.cash.application.bank_import import BankStatementImportService
from app.modules.cash.application.bank_settlements import BankSettlementService
from app.modules.cash.application.movements import CashMovementService
from app.modules.cash.application.shifts import ShiftService


@dataclass(slots=True)
class CashModule:
    shifts: ShiftService
    movements: CashMovementService
    # --- B4 bank (BO-24, 20 #55a–#55h) ---
    bank_settlements: BankSettlementService | None = None
    bank_imports: BankStatementImportService | None = None
