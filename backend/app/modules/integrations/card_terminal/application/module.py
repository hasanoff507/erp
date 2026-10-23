"""The card slice facade published on ``app.state.card_terminal`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.integrations.card_terminal.application.orphans import OrphanSweep
from app.modules.integrations.card_terminal.application.settlements import SettlementService
from app.modules.integrations.card_terminal.application.terminals import CardTerminalService
from app.modules.integrations.card_terminal.application.transactions import CardTransactionService


@dataclass(slots=True)
class CardTerminalModule:
    terminals: CardTerminalService
    transactions: CardTransactionService
    settlements: SettlementService
    orphans: OrphanSweep
