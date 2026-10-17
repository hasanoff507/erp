"""Composition of the catalog module (23 §1 ``wiring.py``).

Other modules (imports, later sales/inventory) import **only** from here or
from ``catalog.application``/``catalog.domain`` — never ``catalog.infrastructure``.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.catalog.application.categories import CategoryService
from app.modules.catalog.application.module import CatalogModule
from app.modules.catalog.application.mxik import MxikService
from app.modules.catalog.application.ports import CatalogRepository, MxikCatalogPort
from app.modules.catalog.application.products import ProductService
from app.modules.catalog.infrastructure.mxik import FakeMxikAdapter, RedisMxikCache, TasnifMxikAdapter
from app.modules.catalog.infrastructure.repositories import SqlCatalogRepository
from app.modules.inventory.wiring import product_cost_reader
from app.modules.pricing.wiring import current_price_reader

__all__ = ["CatalogModule", "build_catalog_module", "build_mxik_port", "catalog_repository"]

_HARDENED = frozenset({"staging", "prod"})


def catalog_repository() -> CatalogRepository:
    return SqlCatalogRepository()


def build_mxik_port(settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> MxikCatalogPort:
    if settings.mxik_provider == "fake":
        if settings.environment in _HARDENED:
            raise RuntimeError("ERP_MXIK_PROVIDER=fake is a dev/test flag (qaror #34)")
        return FakeMxikAdapter()
    return TasnifMxikAdapter(settings.mxik_base_url, timeout_s=settings.mxik_timeout_s, transport=transport)


def build_catalog_module(
    settings: Settings,
    db: Database,
    redis: Callable[[], Redis],
    *,
    mxik_port: MxikCatalogPort | None = None,
) -> CatalogModule:
    repo = catalog_repository()
    cache = RedisMxikCache(redis, fresh_s=settings.mxik_cache_fresh_s, ttl_s=settings.mxik_cache_ttl_s)
    mxik = MxikService(
        mxik_port or build_mxik_port(settings),
        cache,
        retry_base_s=settings.mxik_retry_base_s,
        retry_cap_s=settings.mxik_retry_cap_s,
        max_attempts=settings.mxik_max_attempts,
    )
    return CatalogModule(
        products=ProductService(db.session_factory, repo, current_price_reader(), product_cost_reader()),
        categories=CategoryService(db.session_factory, repo),
        mxik=mxik,
    )
