"""Composition of the purchasing module (23 §1 ``wiring.py``).

Public entry points: :func:`build_purchasing_module` and :func:`purchase_order_receipts` (the PO ↔
goods receipt link: ``assert_open_for_receipt`` / ``refresh_status``). Goods receipts and supplier
returns post through the stock toolkit (``inventory.wiring.stock_service``), the ledger poster
(``accounting.wiring``) and the debt register (``debts.wiring``) in one transaction.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.accounting.wiring import ledger_poster
from app.modules.debts.wiring import counterparty_directory, debt_register
from app.modules.inventory.wiring import stock_service
from app.modules.purchasing.application.goods_receipts import GoodsReceiptService
from app.modules.purchasing.application.module import PurchasingModule
from app.modules.purchasing.application.po_receipts import PurchaseOrderReceipts
from app.modules.purchasing.application.purchase_orders import PurchaseOrderService
from app.modules.purchasing.application.supplier_returns import SupplierReturnService
from app.modules.purchasing.infrastructure.receipts_sql import (
    SqlGoodsReceiptRepository,
    SqlSupplierReturnRepository,
)
from app.modules.purchasing.infrastructure.repositories import SqlPurchaseOrderRepository

__all__ = [
    "PurchaseOrderReceipts",
    "PurchasingModule",
    "build_purchasing_module",
    "purchase_order_receipts",
]


def purchase_order_receipts() -> PurchaseOrderReceipts:
    return PurchaseOrderReceipts(SqlPurchaseOrderRepository())


def build_purchasing_module(settings: Settings, db: Database) -> PurchasingModule:
    repo = SqlPurchaseOrderRepository()
    po_receipts = PurchaseOrderReceipts(repo)
    stock = stock_service(settings)
    receipts = SqlGoodsReceiptRepository()
    return PurchasingModule(
        purchase_orders=PurchaseOrderService(db.session_factory, repo, counterparty_directory()),
        po_receipts=po_receipts,
        goods_receipts=GoodsReceiptService(
            db.session_factory,
            receipts,
            repo,
            po_receipts,
            counterparty_directory(),
            stock,
            ledger_poster(),
            debt_register(),
        ),
        supplier_returns=SupplierReturnService(
            db.session_factory,
            SqlSupplierReturnRepository(),
            receipts,
            stock,
            ledger_poster(),
            debt_register(),
        ),
    )
