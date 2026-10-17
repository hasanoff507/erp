"""Composition of the debts module (23 §1 ``wiring.py``).

Public entry points for other modules (purchasing — goods receipts, supplier returns; later sales,
returns, debt payments): :func:`debt_register` (the ``debt_moves``/``debt_balances`` primitive, run
inside the caller's posting transaction) and :func:`counterparty_directory` (active supplier/customer
checks). Domain types: ``DebtMoveInput``, ``DebtMove``, ``Direction``, ``Counterparty``.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.debts.application.counterparties import CounterpartyDirectory, CounterpartyService
from app.modules.debts.application.module import DebtsModule
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.counterparties import Counterparty
from app.modules.debts.domain.register import DebtMove, DebtMoveInput, Direction
from app.modules.debts.infrastructure.repositories import SqlCounterpartyRepository, SqlDebtRegisterRepository
from app.modules.integrations.einvoice.application.ports import EInvoicePort
from app.modules.integrations.einvoice.wiring import einvoice_port

__all__ = [
    "Counterparty",
    "CounterpartyDirectory",
    "DebtMove",
    "DebtMoveInput",
    "DebtRegister",
    "DebtsModule",
    "Direction",
    "build_debts_module",
    "counterparty_directory",
    "debt_register",
]


def debt_register() -> DebtRegister:
    return DebtRegister(SqlDebtRegisterRepository())


def counterparty_directory() -> CounterpartyDirectory:
    return CounterpartyDirectory(SqlCounterpartyRepository())


def build_debts_module(
    settings: Settings, db: Database, *, einvoice: EInvoicePort | None = None
) -> DebtsModule:
    port = einvoice or einvoice_port(settings)
    register = debt_register()
    return DebtsModule(
        counterparties=CounterpartyService(db.session_factory, SqlCounterpartyRepository(), register, port),
        directory=counterparty_directory(),
        register=register,
        einvoice=port,
    )
