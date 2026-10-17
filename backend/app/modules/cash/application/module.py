"""The cash module facade published on ``app.state.cash`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.cash.application.movements import CashMovementService
from app.modules.cash.application.shifts import ShiftService


@dataclass(slots=True)
class CashModule:
    shifts: ShiftService
    movements: CashMovementService
