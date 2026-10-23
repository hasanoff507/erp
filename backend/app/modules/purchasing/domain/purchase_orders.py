"""Purchase order state machine and receipt progress (11 §8, 19 §10) — pure Python.

``draft → sent → partially_received → closed``; ``draft | sent | partially_received → cancelled``.
The status is a **stored** column: ``GoodsReceiptPostingService`` recomputes it in the receipt's
post/cancel transaction from the posted ``receipt_lines`` linked by ``goods_receipts.po_id``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

PoStatus = Literal["draft", "sent", "partially_received", "closed", "cancelled"]
PO_STATUSES: Final[tuple[PoStatus, ...]] = ("draft", "sent", "partially_received", "closed", "cancelled")
EDITABLE: Final[frozenset[str]] = frozenset({"draft", "sent"})  # PATCH (19 §10)
CANCELLABLE: Final[frozenset[str]] = frozenset({"draft", "sent", "partially_received"})
RECEIVABLE: Final[frozenset[str]] = frozenset({"sent", "partially_received"})  # goods receipts (19 §8)
RECEIPT_DRIVEN: Final[frozenset[str]] = frozenset({"sent", "partially_received", "closed"})
MAX_LINES: Final = 1000
ZERO_QTY: Final = Decimal("0.000")


@dataclass(frozen=True, slots=True)
class PoLine:
    id: UUID
    line_no: int
    product_id: UUID
    qty: Decimal
    price: Decimal | None
    product_name: str | None = None
    unit_code: str | None = None


@dataclass(frozen=True, slots=True)
class PurchaseOrder:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    supplier_id: UUID
    supplier_name: str | None
    supplier_stir: str | None
    warehouse_id: UUID
    created_by: UUID
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None  # purchase_orders.posted_at — when the order left draft
    cancelled_at: datetime | None
    cancelled_by: UUID | None
    cancel_reason: str | None
    comment: str | None
    total: Decimal | None = None
    line_count: int = 0
    lines: tuple[PoLine, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReceivedLine:
    product_id: UUID
    ordered_qty: Decimal
    received_qty: Decimal


def ordered_by_product(lines: Iterable[PoLine]) -> dict[UUID, Decimal]:
    out: dict[UUID, Decimal] = {}
    for line in lines:
        out[line.product_id] = out.get(line.product_id, ZERO_QTY) + line.qty
    return out


def received_lines(lines: Sequence[PoLine], received: Mapping[UUID, Decimal]) -> list[ReceivedLine]:
    """19 §10 ``received_lines``: ordered products (PO line order), then received extras (ordered 0)."""
    ordered = ordered_by_product(lines)
    out = [ReceivedLine(p, q, received.get(p, ZERO_QTY)) for p, q in ordered.items()]
    out += [ReceivedLine(p, ZERO_QTY, q) for p, q in received.items() if p not in ordered and q != 0]
    return out


def status_after_receipts(lines: Sequence[PoLine], received: Mapping[UUID, Decimal]) -> PoStatus:
    """``closed`` when every ordered product is fully received, ``partially_received`` when anything was
    received, ``sent`` otherwise (a cancelled receipt can move a PO back)."""
    ordered = ordered_by_product(lines)
    if ordered and all(received.get(p, ZERO_QTY) >= q for p, q in ordered.items()):
        return "closed"
    if any(q > 0 for q in received.values()):
        return "partially_received"
    return "sent"


def line_amount(qty: Decimal, price: Decimal | None) -> Decimal | None:
    return None if price is None else qty * price
