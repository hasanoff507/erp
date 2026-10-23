"""Composition of the B5 accounting services that depend on other modules (20 #10–#16) — published on
``app.state.accounting`` by ``app.main`` (B5 accounting anchor).

Kept out of ``accounting/wiring.py``: that module is imported by every posting service, so it must not import
other modules' wiring (``debts`` for the 4010/6010 register, ``vat`` for B5-T16, ``integrations.fiscal`` for
``fiscal_readiness``).
"""

from __future__ import annotations

import importlib
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import Database
from app.modules.accounting.application.adjustments import LedgerAdjustmentService
from app.modules.accounting.application.closings import PeriodClosingService
from app.modules.accounting.application.module import AccountingModule
from app.modules.accounting.application.ports import FiscalReadinessReader, TaxReadiness
from app.modules.accounting.domain.calendar import period_label
from app.modules.accounting.infrastructure.adjustments_sql import SqlAdjustmentRepository
from app.modules.accounting.infrastructure.closings_sql import SqlClosingRepository, SqlFiscalReadiness
from app.modules.debts.wiring import debt_register
from app.modules.vat.wiring import build_tax_settlement_service


class _FiscalReadiness:
    """b5-fiscal ``fiscal_readiness(s, "YYYY-MM") -> FiscalReadiness`` (contracts/fiscal.md §1): its
    ``pending_fiscal_receipts`` (not fiscalised + fiscalised but not OFD-acknowledged) is the blocker."""

    def __init__(self, reader: Any) -> None:
        self._reader = reader

    async def __call__(self, s: AsyncSession, tenant_id: UUID, period: date) -> int:
        del tenant_id
        result = await self._reader(s, period_label(period))
        return int(result.pending_fiscal_receipts)


def fiscal_readiness_reader() -> FiscalReadinessReader:
    """b5-fiscal ``fiscal_readiness`` (PLAN contract 4) when published, else the accounting SQL fallback
    (status ``pending``/``sent``/``failed``, contracts/accounting.md)."""
    fiscal = importlib.import_module("app.modules.integrations.fiscal.wiring")
    reader = getattr(fiscal, "fiscal_readiness", None)
    return _FiscalReadiness(reader) if reader is not None else SqlFiscalReadiness()


class _TaxReadiness:
    """``vat`` module (B5-T16) — imported lazily: ``vat.wiring`` imports this module."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._service: Any = None

    async def __call__(self, s: AsyncSession, tenant_id: UUID, period: date) -> TaxReadiness:
        if self._service is None:
            self._service = build_tax_settlement_service(self._db)
        result: TaxReadiness = await self._service.readiness(s, tenant_id, period)
        return result


def attach_b5_services(module: AccountingModule, db: Database) -> None:
    module.adjustments = LedgerAdjustmentService(
        db.session_factory, SqlAdjustmentRepository(), module.poster, debt_register()
    )
    module.closings = PeriodClosingService(
        db.session_factory, SqlClosingRepository(), fiscal_readiness_reader(), _TaxReadiness(db)
    )
