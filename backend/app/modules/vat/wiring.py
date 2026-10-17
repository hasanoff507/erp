"""Composition of the VAT read module (M10): ``/reports/vat-summary``, ``/vat-moves`` (20 #1–#2)."""

from __future__ import annotations

from app.core.db.session import Database
from app.modules.accounting.wiring import ledger_poster
from app.modules.branches.wiring import turnover_rate_on
from app.modules.vat.application.tax_settlements import TaxSettlementService
from app.modules.vat.application.vat import VatService
from app.modules.vat.infrastructure.tax_settlements_sql import SqlTaxSettlementRepository
from app.modules.vat.infrastructure.vat_sql import SqlVatRepository

__all__ = ["TaxSettlementService", "VatService", "build_tax_settlement_service", "build_vat_service"]


def build_vat_service(db: Database) -> VatService:
    return VatService(db.session_factory, SqlVatRepository(), turnover_rate_on)


def build_tax_settlement_service(db: Database) -> TaxSettlementService:
    """``/tax-settlements`` (20 #8a–#8d, Bosqich 4) — published on ``app.state.tax_settlements``."""
    return TaxSettlementService(
        db.session_factory,
        SqlTaxSettlementRepository(),
        SqlVatRepository(),
        turnover_rate_on,
        ledger_poster(),
    )
