"""Composition of the imports module (23 §1 ``wiring.py``).

``import_jobs`` spans modules (products → catalog + pricing; later
opening_stock → inventory, opening_debts → debts), so it lives in its own
module and reaches the others only through their ``wiring``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.catalog.wiring import catalog_repository
from app.modules.imports.application.ports import JobEnqueuer
from app.modules.imports.application.service import ImportLimits, ImportService
from app.modules.imports.infrastructure.queue import SaqEnqueuer
from app.modules.imports.infrastructure.repositories import SqlImportJobRepository
from app.modules.imports.infrastructure.storage import FilesystemStorage
from app.modules.pricing.wiring import price_change_service

__all__ = ["ImportService", "build_import_service"]


def build_import_service(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    queue: JobEnqueuer | None = None,
) -> ImportService:
    return ImportService(
        session_factory,
        SqlImportJobRepository(),
        FilesystemStorage(settings.file_storage_dir),
        queue or SaqEnqueuer(settings.redis_url.get_secret_value(), settings.queue_name),
        catalog_repository(),
        price_change_service(session_factory),
        ImportLimits(max_bytes=settings.import_max_bytes, max_rows=settings.import_max_rows),
    )


def build_imports_module(settings: Settings, db: Database) -> ImportService:
    return build_import_service(settings, db.session_factory)
