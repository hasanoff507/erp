"""Composition of the card-terminal slice (23 §1 ``wiring.py``; qaror #71).

Public entry points: :func:`card_payments` (the :class:`CardPayments` contract used inside document
postings — sales, returns, shift close), :func:`build_card_terminal_module` (REST services on
``app.state.card_terminal``), :func:`orphan_sweep` (cron job) and :func:`fake_card_terminal` /
:func:`uzqr_port` (the B3 adapters).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.access.wiring import approval_gate
from app.modules.integrations.card_terminal.application.contracts import CardPayments
from app.modules.integrations.card_terminal.application.module import CardTerminalModule
from app.modules.integrations.card_terminal.application.orphans import OrphanSweep
from app.modules.integrations.card_terminal.application.payments import CardPaymentsService
from app.modules.integrations.card_terminal.application.settlements import SettlementService, SettlementWriter
from app.modules.integrations.card_terminal.application.terminals import CardTerminalService
from app.modules.integrations.card_terminal.application.transactions import CardTransactionService
from app.modules.integrations.card_terminal.application.uzqr import UzqrPort
from app.modules.integrations.card_terminal.infrastructure.fake import FakeCardTerminalAdapter
from app.modules.integrations.card_terminal.infrastructure.sql import SqlCardRepository
from app.modules.integrations.card_terminal.infrastructure.uzqr_stub import UzqrStubAdapter
from app.modules.notifications.wiring import event_recorder

CARD_ORPHAN_SWEEP_JOB = "card_orphan_sweep"  # SAQ job: one tenant's orphan approved purchases (23 §4)

__all__ = [
    "CARD_ORPHAN_SWEEP_JOB",
    "CardPayments",
    "CardTerminalModule",
    "FakeCardTerminalAdapter",
    "build_card_terminal_module",
    "card_payments",
    "fake_card_terminal",
    "orphan_sweep",
    "uzqr_port",
]


def _settlement_writer(repo: SqlCardRepository) -> SettlementWriter:
    return SettlementWriter(repo, event_recorder())


def card_payments(settings: Settings | None = None) -> CardPayments:
    """Card rules for document postings — call inside the caller's transaction."""
    repo = SqlCardRepository()
    return CardPaymentsService(repo, approval_gate(), _settlement_writer(repo))


def build_card_terminal_module(settings: Settings, db: Database) -> CardTerminalModule:
    repo = SqlCardRepository()
    return CardTerminalModule(
        terminals=CardTerminalService(
            db.session_factory,
            repo,
            fake_allowed=settings.card_fake_terminals and settings.environment != "prod",
        ),
        transactions=CardTransactionService(db.session_factory, repo, approval_gate()),
        settlements=SettlementService(db.session_factory, repo, _settlement_writer(repo)),
        orphans=OrphanSweep(db.session_factory, repo),
    )


def orphan_sweep(session_factory: async_sessionmaker[AsyncSession]) -> OrphanSweep:
    return OrphanSweep(session_factory, SqlCardRepository())


def fake_card_terminal(settings: Settings) -> FakeCardTerminalAdapter:
    """The B3 terminal emulator (tests, dev agent emulator); never in prod (21 §9.4)."""
    if settings.environment == "prod":
        raise RuntimeError("FakeCardTerminalAdapter is not allowed in prod (21 §9.4)")
    return FakeCardTerminalAdapter()


def uzqr_port(settings: Settings) -> UzqrPort:
    """Dynamic UzQR — stub until Bosqich 5 (21 §9.1, 26 #49)."""
    return UzqrStubAdapter()
