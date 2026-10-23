"""Composition of the returns module (23 §1): the ``return.created`` sync handler, ``GET /returns``."""

from __future__ import annotations

from collections.abc import Mapping

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.returns.application.queries import ReturnQueries
from app.modules.returns.application.return_posting import ReturnPostingHandler
from app.modules.returns.infrastructure.returns_sql import SqlReturnsRepository
from app.modules.sales.wiring import posting_deps
from app.modules.sync.application.handlers import SyncEventHandler

__all__ = ["ReturnQueries", "build_returns_queries", "return_handler", "sync_handlers"]


def return_handler(settings: Settings) -> ReturnPostingHandler:
    return ReturnPostingHandler(posting_deps(settings), SqlReturnsRepository())


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, SyncEventHandler]:
    del db
    return {"return.created": return_handler(settings)}


def build_returns_queries(db: Database) -> ReturnQueries:
    return ReturnQueries(db.session_factory, SqlReturnsRepository())
