"""The pricing module facade published on ``app.state.pricing`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.pricing.application.price_changes import PriceChangeService


@dataclass(slots=True)
class PricingModule:
    price_changes: PriceChangeService
