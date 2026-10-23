"""The catalog module facade published on ``app.state.catalog`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.catalog.application.categories import CategoryService
from app.modules.catalog.application.mxik import MxikService
from app.modules.catalog.application.products import ProductService


@dataclass(slots=True)
class CatalogModule:
    products: ProductService
    categories: CategoryService
    mxik: MxikService
