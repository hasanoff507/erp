"""The purchasing module facade published on ``app.state.purchasing`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.purchasing.application.goods_receipts import GoodsReceiptService
from app.modules.purchasing.application.po_receipts import PurchaseOrderReceipts
from app.modules.purchasing.application.purchase_orders import PurchaseOrderService
from app.modules.purchasing.application.supplier_returns import SupplierReturnService


@dataclass(slots=True)
class PurchasingModule:
    purchase_orders: PurchaseOrderService
    po_receipts: PurchaseOrderReceipts  # PO ↔ goods receipt link (assert open, refresh status)
    goods_receipts: GoodsReceiptService
    supplier_returns: SupplierReturnService
