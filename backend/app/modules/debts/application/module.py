"""The debts module facade published on ``app.state.debts`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.debts.application.counterparties import CounterpartyDirectory, CounterpartyService
from app.modules.debts.application.documents import DebtDocumentService
from app.modules.debts.application.ledger import DebtLedgerQueries
from app.modules.debts.application.register import DebtRegister
from app.modules.integrations.einvoice.application.ports import EInvoicePort


@dataclass(slots=True)
class DebtsModule:
    counterparties: CounterpartyService
    directory: CounterpartyDirectory
    register: DebtRegister
    einvoice: EInvoicePort  # the STIR-lookup adapter (tests swap/flip the fake through it)
    documents: DebtDocumentService  # debt-payments (bank) / debt-openings / debt-writeoffs / doubtful flags
    ledger: DebtLedgerQueries  # debt-ledger + reports/debts-aging
