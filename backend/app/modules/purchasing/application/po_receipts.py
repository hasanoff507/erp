"""Purchase order ↔ goods receipt link (19 §8, §10; 11 §8; QT-M07-07) — for ``GoodsReceiptPostingService``.

Both methods run in the **caller's** transaction (receipt create/post/cancel)::

    # 409 PURCHASE_ORDER_CLOSED unless sent/partially_received
    po = await purchasing.po_receipts.assert_open_for_receipt(s, po_id)
    defaults = {line.product_id: (line.qty, line.price) for line in po.lines}
    ...  # write the receipt, post it
    await purchasing.po_receipts.refresh_status(s, po_id)  # same transaction as the post/cancel
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.purchasing.application.ports import PurchaseOrderRepository
from app.modules.purchasing.application.purchase_orders import not_found
from app.modules.purchasing.domain.purchase_orders import (
    RECEIPT_DRIVEN,
    RECEIVABLE,
    PoStatus,
    PurchaseOrder,
    status_after_receipts,
)


class PurchaseOrderReceipts:
    def __init__(self, repo: PurchaseOrderRepository) -> None:
        self._repo = repo

    async def assert_open_for_receipt(
        self, s: AsyncSession, po_id: UUID, *, lock: bool = False
    ) -> PurchaseOrder:
        """The PO (with ``lines``: product, qty, price) if it accepts receipts, else an error.

        ``404 NOT_FOUND{resource:purchase_order}`` (also another tenant's id — RLS);
        ``409 PURCHASE_ORDER_CLOSED`` unless ``status ∈ (sent, partially_received)`` — draft, closed
        and cancelled orders take no receipts (19 §8, QT-M07-07). ``lock=True`` holds the PO row
        ``FOR UPDATE`` (use it in the post transaction before :meth:`refresh_status`).
        """
        po = await self._repo.get(s, po_id, lock=lock)
        if po is None:
            raise not_found()
        if po.status not in RECEIVABLE:
            raise AppError(
                ErrorCode.PURCHASE_ORDER_CLOSED,
                params={"po_id": str(po_id), "actual_status": po.status},
            )
        return po

    async def received_qty(self, s: AsyncSession, po_id: UUID) -> dict[UUID, Decimal]:
        """Σ ``receipt_lines.qty`` per product over **posted** receipts with ``goods_receipts.po_id``."""
        return await self._repo.received_qty(s, po_id)

    async def refresh_status(self, s: AsyncSession, po_id: UUID) -> PoStatus | str:
        """Recompute and store the PO status after a receipt post/cancel (19 §10 — stored column).

        ``closed`` when every ordered product's posted received qty ≥ ordered qty,
        ``partially_received`` when anything was received, ``sent`` otherwise. ``draft``/``cancelled``
        orders are left as they are. Locks the PO row; returns the (possibly unchanged) status.
        """
        po = await self._repo.get(s, po_id, lock=True)
        if po is None:
            raise not_found()
        if po.status not in RECEIPT_DRIVEN:
            return po.status
        status = status_after_receipts(po.lines, await self._repo.received_qty(s, po_id))
        if status != po.status:
            await self._repo.update(s, po_id, {"status": status})
        return status
