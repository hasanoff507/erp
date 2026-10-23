"""Composition of the sales module (23 §1 ``wiring.py``).

* :func:`sync_handlers` — ``sale.created``, ``sale.draft_voided``, ``receipt.reprinted`` for ``/sync/push``
  (contract: ``app.modules.sync.application.handlers``);
* :func:`build_sales_module` — ``app.state.sales`` (``GET /sales``) and ``app.state.fiscal``
  (``/fiscal-receipts``) of the REST API.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.access.wiring import approval_gate
from app.modules.accounting.wiring import ledger_poster
from app.modules.cash.wiring import shift_guard
from app.modules.debts.wiring import debt_register
from app.modules.integrations.card_terminal.wiring import card_payments
from app.modules.integrations.einvoice.wiring import einvoice_hooks
from app.modules.integrations.fiscal.wiring import (
    FiscalReceiptQueries,
    fiscal_receipt_queries,
    fiscal_service,
)
from app.modules.integrations.marking.wiring import marking_hooks
from app.modules.inventory.wiring import stock_service
from app.modules.sales.application.audit_events import DraftVoidedHandler, ReceiptReprintedHandler
from app.modules.sales.application.queries import SaleQueries
from app.modules.sales.application.sale_posting import Deps, SalePostingHandler
from app.modules.sales.infrastructure.sales_sql import SqlSalesRepository
from app.modules.sync.application.handlers import SyncEventHandler

__all__ = ["SalesModule", "build_sales_module", "posting_deps", "sale_handler", "sync_handlers"]


@dataclass(frozen=True, slots=True)
class SalesModule:
    queries: SaleQueries
    fiscal: FiscalReceiptQueries


def posting_deps(settings: Settings) -> Deps:
    """The collaborators of the sale posting (returns reuse the same set)."""
    return Deps(
        repo=SqlSalesRepository(),
        stock=stock_service(settings),
        poster=ledger_poster(),
        debts=debt_register(),
        fiscal=fiscal_service(settings),
        fiscal_provider=settings.fiscal_provider,
        shifts=shift_guard(),
        approvals=approval_gate(),
        cards=card_payments(settings),
        marking=marking_hooks(),
        einvoices=einvoice_hooks(),
    )


def sale_handler(settings: Settings) -> SalePostingHandler:
    return SalePostingHandler(posting_deps(settings))


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, SyncEventHandler]:
    del db
    repo = SqlSalesRepository()
    return {
        "sale.created": sale_handler(settings),
        "sale.draft_voided": DraftVoidedHandler(repo),
        "receipt.reprinted": ReceiptReprintedHandler(repo),
    }


def build_sales_module(settings: Settings, db: Database) -> SalesModule:
    sf = db.session_factory
    return SalesModule(
        queries=SaleQueries(sf, SqlSalesRepository()), fiscal=fiscal_receipt_queries(sf, settings)
    )
