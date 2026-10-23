"""Composition of the inventory module (23 §1 ``wiring.py``).

Public stock toolkit for every stock document (goods receipts, supplier returns, transfers, stock
counts, write-offs; sales/returns in Bosqich 3) — import it from here:

* :func:`stock_service` → :class:`StockService` — ``lock(s, tenant_id, keys)`` → :class:`StockTxn`
  with ``receive`` / ``issue`` / ``return_to_lots`` / ``block`` / ``reverse_receipt`` /
  ``reverse_issue`` / ``live_allocations`` / ``inv_acct`` / ``last_purchase_cost`` / ``cost_line``;
  ``after_commit(txn)`` enqueues recost jobs; ``queue_recost`` (Bosqich 3 late-sync trigger);
* :class:`CostPosting`, :class:`IssueResult`, :class:`ReceiveResult`, :class:`Allocation`;
* pure helpers: :func:`return_pieces` (13 §3.2a), :func:`cost_analytics` / :func:`cost_line_key`
  (the cost-line analytics contract), :func:`expected_count_qty` (13 X-02);
* :func:`product_cost_reader` — ``current_cost`` for the catalog list (19 §1);
* stock documents (19 §13–§15): :func:`transfer_service` (e-TTN outbox via
  ``integrations.einvoice``), :func:`stock_count_service`, :func:`write_off_service`; offline sync
  payload validators — :func:`parse_transfer_sent`, :func:`parse_transfer_received`,
  :func:`parse_line_recorded`; :func:`sync_handlers` — the ``/sync/push`` handlers of these events.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.accounting.wiring import ledger_poster
from app.modules.integrations.einvoice.wiring import ETTN_SEND_JOB, ettn_auto_send
from app.modules.integrations.marking.wiring import marking_hooks
from app.modules.inventory.application.module import InventoryModule
from app.modules.inventory.application.openings import (
    OpeningImportAdapter,
    OpeningLineInput,
    StockOpeningService,
)
from app.modules.inventory.application.ports import JobEnqueuer, Key
from app.modules.inventory.application.queries import ProductCostReader, StockNotifier, StockQueryService
from app.modules.inventory.application.recost import RecostService
from app.modules.inventory.application.stock import (
    RECOST_JOB,
    CostPosting,
    IssueResult,
    ReceiveResult,
    StockService,
    StockTxn,
)
from app.modules.inventory.application.stock_counts import StockCountService
from app.modules.inventory.application.stock_settings import StockSettingsService
from app.modules.inventory.application.sync_events import InventorySyncDeps, InventorySyncHandlers
from app.modules.inventory.application.transfers import OutboxConfig, TransferService
from app.modules.inventory.application.valuation import ValuationService
from app.modules.inventory.application.write_offs import WriteOffService
from app.modules.inventory.domain.analytics import cost_analytics, cost_line_key
from app.modules.inventory.domain.costing import Allocation, return_pieces
from app.modules.inventory.domain.counts import expected_count_qty
from app.modules.inventory.domain.stock_counts import EVENT_LINE_RECORDED, parse_line_recorded
from app.modules.inventory.domain.transfers import (
    EVENT_TRANSFER_RECEIVED,
    EVENT_TRANSFER_SENT,
    EventPayloadError,
    parse_transfer_received,
    parse_transfer_sent,
)
from app.modules.inventory.infrastructure.counts_sql import SqlCountRepository
from app.modules.inventory.infrastructure.docs_sql import SqlOpeningRepository, SqlStockQueryRepository
from app.modules.inventory.infrastructure.queue import SaqEnqueuer
from app.modules.inventory.infrastructure.recost_sql import SqlRecostRepository
from app.modules.inventory.infrastructure.stock_settings_sql import SqlStockSettingsRepository
from app.modules.inventory.infrastructure.stock_sql import SqlStockRepository
from app.modules.inventory.infrastructure.sync_events_sql import SqlInventorySyncRepository
from app.modules.inventory.infrastructure.transfers_sql import SqlTransferRepository
from app.modules.inventory.infrastructure.write_offs_sql import SqlWriteOffRepository
from app.modules.notifications.wiring import event_recorder
from app.modules.pricing.wiring import current_price_reader
from app.modules.sync.application.handlers import SyncEventHandler

__all__ = [
    "EVENT_LINE_RECORDED",
    "EVENT_TRANSFER_RECEIVED",
    "EVENT_TRANSFER_SENT",
    "RECOST_JOB",
    "Allocation",
    "CostPosting",
    "EventPayloadError",
    "InventoryModule",
    "IssueResult",
    "Key",
    "OpeningLineInput",
    "ProductCostReader",
    "ReceiveResult",
    "StockOpeningService",
    "StockService",
    "StockTxn",
    "build_inventory_module",
    "cost_analytics",
    "cost_line_key",
    "expected_count_qty",
    "opening_import_port",
    "opening_service",
    "parse_line_recorded",
    "parse_transfer_received",
    "parse_transfer_sent",
    "product_cost_reader",
    "recost_service",
    "return_pieces",
    "stock_count_service",
    "stock_notifier",
    "stock_service",
    "sync_handlers",
    "transfer_service",
    "valuation_service",
    "write_off_service",
]


def _queue(settings: Settings | None) -> JobEnqueuer | None:
    if settings is None:
        return None
    return SaqEnqueuer(settings.redis_url.get_secret_value(), settings.queue_name)


def valuation_service(session_factory: async_sessionmaker[AsyncSession] | None = None) -> ValuationService:
    return ValuationService(session_factory, SqlStockRepository())


def stock_service(settings: Settings | None = None, *, queue: JobEnqueuer | None = None) -> StockService:
    """The stock toolkit; with ``settings`` recost jobs are enqueued to SAQ after commit."""
    return StockService(
        SqlStockRepository(),
        SqlRecostRepository(),
        ledger_poster(),
        valuation_service(),
        queue or _queue(settings),
    )


def recost_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings | None = None
) -> RecostService:
    return RecostService(
        session_factory, SqlRecostRepository(), SqlStockRepository(), stock_service(settings), ledger_poster()
    )


def opening_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings | None = None
) -> StockOpeningService:
    return StockOpeningService(
        session_factory,
        SqlOpeningRepository(),
        SqlStockRepository(),
        stock_service(settings),
        ledger_poster(),
    )


def opening_import_port(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings | None = None
) -> OpeningImportAdapter:
    """The ``opening_stock`` import port (composed in ``imports.wiring``)."""
    return OpeningImportAdapter(opening_service(session_factory, settings), SqlStockRepository())


def stock_notifier() -> StockNotifier:
    return StockNotifier(SqlStockRepository(), SqlStockQueryRepository(), event_recorder())


def product_cost_reader() -> ProductCostReader:
    return ProductCostReader(SqlStockRepository(), SqlStockQueryRepository())


def transfer_service(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings | None = None,
    *,
    queue: JobEnqueuer | None = None,
) -> TransferService:
    """Transfers (19 §13); with ``settings`` the e-TTN job is enqueued after a vehicle ``post`` and the
    fake operator auto-sends (27 B2)."""
    return TransferService(
        session_factory,
        SqlTransferRepository(),
        SqlStockRepository(),
        stock_service(settings, queue=queue),
        ledger_poster(),
        queue or _queue(settings),
        OutboxConfig(auto_send=settings is not None and ettn_auto_send(settings), job=ETTN_SEND_JOB),
    )


def stock_count_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings | None = None
) -> StockCountService:
    return StockCountService(
        session_factory, SqlCountRepository(), SqlStockRepository(), stock_service(settings), ledger_poster()
    )


def write_off_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings | None = None
) -> WriteOffService:
    return WriteOffService(
        session_factory,
        SqlWriteOffRepository(),
        SqlStockRepository(),
        stock_service(settings),
        ledger_poster(),
        current_price_reader(),
        event_recorder(),
        marking_hooks(),
    )


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, SyncEventHandler]:
    """``transfer.sent`` / ``transfer.received`` / ``stock_count.line_recorded`` for ``/sync/push``
    (PLAN contract 1; Bosqich 3) — posted through the same transfer / stock-count services as REST."""
    sf = db.session_factory
    queue = _queue(settings)
    return InventorySyncHandlers(
        InventorySyncDeps(
            transfers=transfer_service(sf, settings, queue=queue),
            transfer_docs=SqlTransferRepository(),
            counts=stock_count_service(sf, settings),
            count_docs=SqlCountRepository(),
            stock_repo=SqlStockRepository(),
            stock=stock_service(settings, queue=queue),
            poster=ledger_poster(),
            sync_repo=SqlInventorySyncRepository(),
            queue=queue,
            outbox=OutboxConfig(auto_send=ettn_auto_send(settings), job=ETTN_SEND_JOB),
        )
    ).handlers()


def build_inventory_module(settings: Settings, db: Database) -> InventoryModule:
    sf = db.session_factory
    return InventoryModule(
        stock=stock_service(settings),
        queries=StockQueryService(sf, SqlStockRepository(), SqlStockQueryRepository()),
        valuation=valuation_service(sf),
        recost=recost_service(sf, settings),
        openings=opening_service(sf, settings),
        transfers=transfer_service(sf, settings),
        stock_counts=stock_count_service(sf, settings),
        write_offs=write_off_service(sf, settings),
        stock_settings=StockSettingsService(sf, SqlStockSettingsRepository()),
    )
