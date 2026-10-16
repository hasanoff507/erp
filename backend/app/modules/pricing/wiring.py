"""Composition of the pricing module (23 §1 ``wiring.py``).

Public entry points for other modules: :func:`build_pricing_module`,
:func:`price_change_service` (catalog import posts initial prices through it),
:func:`current_price_reader` (``current_price`` of the catalog list, 19 §1)
and the pure price resolution in ``pricing.domain.resolution`` (POS, Bosqich 3).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import Database
from app.modules.pricing.application.current_prices import CurrentPriceReader
from app.modules.pricing.application.module import PricingModule
from app.modules.pricing.application.price_changes import PriceChangeService
from app.modules.pricing.domain.resolution import PriceRecord, effective_price, effective_record
from app.modules.pricing.infrastructure.repositories import SqlPricingRepository

__all__ = [
    "CurrentPriceReader",
    "PriceRecord",
    "PricingModule",
    "build_pricing_module",
    "current_price_reader",
    "effective_price",
    "effective_record",
    "price_change_service",
]


def price_change_service(session_factory: async_sessionmaker[AsyncSession]) -> PriceChangeService:
    return PriceChangeService(session_factory, SqlPricingRepository())


def current_price_reader() -> CurrentPriceReader:
    return CurrentPriceReader(SqlPricingRepository())


def build_pricing_module(db: Database) -> PricingModule:
    return PricingModule(price_changes=price_change_service(db.session_factory))
