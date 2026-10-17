"""Composition of the VAT read module (M10): ``/reports/vat-summary``, ``/vat-moves`` (20 #1–#2)."""

from __future__ import annotations

from app.core.db.session import Database
from app.modules.branches.wiring import turnover_rate_on
from app.modules.vat.application.vat import VatService
from app.modules.vat.infrastructure.vat_sql import SqlVatRepository

__all__ = ["VatService", "build_vat_service"]


def build_vat_service(db: Database) -> VatService:
    return VatService(db.session_factory, SqlVatRepository(), turnover_rate_on)
