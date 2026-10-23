"""The inventory module facade published on ``app.state.inventory`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.inventory.application.openings import StockOpeningService
from app.modules.inventory.application.queries import StockQueryService
from app.modules.inventory.application.recost import RecostService
from app.modules.inventory.application.stock import StockService
from app.modules.inventory.application.stock_counts import StockCountService
from app.modules.inventory.application.stock_settings import StockSettingsService
from app.modules.inventory.application.transfers import TransferService
from app.modules.inventory.application.valuation import ValuationService
from app.modules.inventory.application.write_offs import WriteOffService


@dataclass(slots=True)
class InventoryModule:
    stock: StockService
    queries: StockQueryService
    valuation: ValuationService
    recost: RecostService
    openings: StockOpeningService
    transfers: TransferService
    stock_counts: StockCountService
    write_offs: WriteOffService
    stock_settings: StockSettingsService
