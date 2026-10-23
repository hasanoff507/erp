"""Composition of the debts module (23 §1 ``wiring.py``).

Public entry points for other modules (purchasing — goods receipts, supplier returns; sales, returns):
:func:`debt_register` (the ``debt_moves``/``debt_balances`` primitive, run inside the caller's posting
transaction) and :func:`counterparty_directory` (active supplier/customer checks). Domain types:
``DebtMoveInput``, ``DebtMove``, ``Direction``, ``Counterparty``.

Bosqich 4 (M08 debt book):

* :func:`sync_handlers` — ``debt_payment.created`` (18 §12.2) and ``counterparty.created`` (18 §11.1) for
  ``/sync/push``;
* :func:`open_debt_docs_reader` — the 16 §1 ``customers[].open_debt_docs[]`` rows for ``/sync/pull``;
* :func:`debt_daily_check` — the daily ``debt_due_today`` / ``debt_aging_60`` events (cron, ``tasks.py``);
* ``build_debts_module`` → ``app.state.debts`` (counterparties, debt documents, ledger, aging).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.accounting.wiring import ledger_poster
from app.modules.debts.application.counterparties import CounterpartyDirectory, CounterpartyService
from app.modules.debts.application.daily_check import DebtDailyCheck
from app.modules.debts.application.documents import DebtDocumentService
from app.modules.debts.application.ledger import DebtLedgerQueries
from app.modules.debts.application.module import DebtsModule
from app.modules.debts.application.open_docs import OpenDebtDocsReader
from app.modules.debts.application.payments import DebtPaymentHandler, DebtPaymentPostingService, HandlerDeps
from app.modules.debts.application.quick_customer import CounterpartyCreatedHandler
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.counterparties import Counterparty
from app.modules.debts.domain.register import DebtMove, DebtMoveInput, Direction
from app.modules.debts.infrastructure.docs_sql import SqlDebtDocsRepository
from app.modules.debts.infrastructure.repositories import SqlCounterpartyRepository, SqlDebtRegisterRepository
from app.modules.integrations.card_terminal.wiring import card_payments
from app.modules.integrations.einvoice.application.ports import EInvoicePort
from app.modules.integrations.fiscal.wiring import fiscal_service
from app.modules.notifications.wiring import event_recorder
from app.modules.sync.application.handlers import SyncEventHandler

__all__ = [
    "Counterparty",
    "CounterpartyDirectory",
    "DebtMove",
    "DebtMoveInput",
    "DebtRegister",
    "DebtsModule",
    "Direction",
    "OpenDebtDocsReader",
    "build_debts_module",
    "counterparty_directory",
    "debt_daily_check",
    "debt_register",
    "open_debt_docs_reader",
    "sync_handlers",
]


def debt_register() -> DebtRegister:
    return DebtRegister(SqlDebtRegisterRepository())


def counterparty_directory() -> CounterpartyDirectory:
    return CounterpartyDirectory(SqlCounterpartyRepository())


def debt_payment_posting() -> DebtPaymentPostingService:
    return DebtPaymentPostingService(SqlDebtDocsRepository(), debt_register(), ledger_poster())


def open_debt_docs_reader() -> OpenDebtDocsReader:
    """``await reader.for_customers(s, counterparty_ids)`` → ``{id: [OpenDebtDoc JSON]}`` (16 §1)."""
    return OpenDebtDocsReader(SqlDebtDocsRepository())


def debt_daily_check() -> DebtDailyCheck:
    return DebtDailyCheck(SqlDebtDocsRepository(), event_recorder())


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, SyncEventHandler]:
    from app.modules.cash.wiring import shift_guard  # cash.wiring imports this module (debt_register)

    del db
    repo = SqlDebtDocsRepository()
    deps = HandlerDeps(
        repo=repo,
        posting=DebtPaymentPostingService(repo, debt_register(), ledger_poster()),
        directory=counterparty_directory(),
        fiscal=fiscal_service(settings),
        fiscal_provider=settings.fiscal_provider,
        shifts=shift_guard(),
        cards=card_payments(settings),
        events=event_recorder(),
    )
    return {
        "debt_payment.created": DebtPaymentHandler(deps),
        "counterparty.created": CounterpartyCreatedHandler(SqlCounterpartyRepository()),
    }


def build_debts_module(
    settings: Settings, db: Database, *, einvoice: EInvoicePort | None = None
) -> DebtsModule:
    # lazy: einvoice.wiring imports debts.wiring (debt_register) — no import cycle at module load
    from app.modules.integrations.einvoice.wiring import einvoice_port

    port = einvoice or einvoice_port(settings)
    register = debt_register()
    repo = SqlDebtDocsRepository()
    cps = SqlCounterpartyRepository()
    poster = ledger_poster()
    return DebtsModule(
        counterparties=CounterpartyService(db.session_factory, cps, register, port),
        directory=counterparty_directory(),
        register=register,
        einvoice=port,
        documents=DebtDocumentService(
            db.session_factory,
            repo,
            cps,
            counterparty_directory(),
            register,
            poster,
            DebtPaymentPostingService(repo, register, poster),
        ),
        ledger=DebtLedgerQueries(db.session_factory, repo, cps, register),
    )


async def open_debt_docs(
    s: AsyncSession, counterparty_ids: Sequence[UUID]
) -> dict[UUID, list[dict[str, Any]]]:
    """Shortcut of :func:`open_debt_docs_reader` for ``/sync/pull`` (16 §1)."""
    return await open_debt_docs_reader().for_customers(s, counterparty_ids)
