"""Goods receipt amounts and posting rules (13 §2.6, §2.6a, §2.7, §2.8, §4.1, §4.3, §5.3) — pure Python.

Amounts (19 §8): ``lines[].cost`` is the unit cost **without VAT** (4 dp). Per line
``net = ROUND_HALF_UP(qty × cost, 2)``, ``vat = ROUND_HALF_UP(net × vat_rate / 100, 2)``
(``receipt_lines.vat_amount``); document totals are the sums of the rounded lines (13 §5.3).

Posting (:func:`receipt_posting`), ``credit`` = ``6010`` (credit purchase) or ``5110`` (paid at once,
13 §2.8 — bank only in Bosqich 2):

* ``kind='gratuitous'`` (13 §2.6a): per line ``Dt inv_acct / Kt 8530 = net``; no VAT, no debt.
* VAT regime: per line ``Dt inv_acct / Kt credit = net`` (lot amount = net); one
  ``Dt 4410 / Kt credit = Σ vat`` (always — the liability is recognised at the full invoice amount) +
  ``vat_moves(input, base = Σ net of taxed lines, vat = Σ vat)``. While the linked e-invoice is
  ``red``/``unknown`` and the receipt is unpaid (13 §2.8, VM 830) only the VAT *credit* waits for the
  supplier payment: the 4410 line carries ``vat_credit='deferred'`` and no ``vat_moves`` row is written.
* Turnover regime (13 §4.3): per line ``Dt inv_acct / Kt credit = net + vat`` (lot amount incl. VAT),
  no 4410, no ``vat_moves``.
* Credit purchase: ``debt_moves`` payable ``+ Σ (net + vat)`` (= the Kt 6010 of this posting, also while
  the VAT credit is deferred); supplier advance (4310 debit balance, 13 §2.6/§2.16, qaror #47):
  ``Dt 6010 / Kt 4310 = min(advance, Σ Kt 6010 of this posting)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from app.core.money import money
from app.modules.accounting.domain.entries import LedgerLine, VatMove

Regime = Literal["vat", "turnover"]
ReceiptKind = Literal["purchase", "gratuitous"]

ZERO: Final = Decimal("0.00")
ZERO_QTY: Final = Decimal("0.000")
HUNDRED: Final = Decimal("100")
MAX_LINES: Final = 1000
SUPPLIERS: Final = "6010"
BANK: Final = "5110"
INPUT_VAT: Final = "4410"
ADVANCES: Final = "4310"
GRATUITOUS: Final = "8530"
DEFERRED_RISK_FLAGS: Final = frozenset({"red", "unknown"})
DISCREPANCY_REASONS: Final = ("short", "excess", "damaged", "wrong_item", "other")
ALLOWED_VAT_RATES: Final = (Decimal("0.00"), Decimal("12.00"))


def line_net(qty: Decimal, cost: Decimal) -> Decimal:
    return money(qty * cost)


def line_vat(net: Decimal, vat_rate: Decimal) -> Decimal:
    return money(net * vat_rate / HUNDRED)


@dataclass(frozen=True, slots=True)
class ReceiptLine:
    id: UUID
    line_no: int
    product_id: UUID
    qty: Decimal
    cost: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    vat_exemption_code: str | None = None
    expiry_date: date | None = None
    discrepancy_reason: str | None = None
    product_name: str | None = None
    unit_code: str | None = None
    is_marked: bool = False
    marking_group_code: str | None = None
    marking_deadline: str | None = None  # platform.marking_product_groups.acceptance_deadline
    marking_codes: tuple[str, ...] = ()
    lot_id: UUID | None = None
    lot_qty_left: Decimal | None = None
    returned_qty: Decimal = ZERO_QTY

    @property
    def net(self) -> Decimal:
        return line_net(self.qty, self.cost)

    @property
    def total(self) -> Decimal:
        return self.net + self.vat_amount


@dataclass(frozen=True, slots=True)
class GoodsReceipt:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    supplier_id: UUID
    supplier_name: str | None
    supplier_stir: str | None
    po_id: UUID | None
    warehouse_id: UUID
    paid_immediately: bool
    kind: str
    source: str
    einvoice_id: UUID | None
    einvoice_risk_flag: str | None
    ettn_ref: str | None
    poa_id: UUID | None
    poa_number: str | None
    comment: str | None
    created_by: UUID
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    lines: tuple[ReceiptLine, ...] = field(default_factory=tuple)
    line_count: int = 0
    net_total: Decimal = ZERO
    vat_total: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return self.net_total + self.vat_total


def vat_deferred(risk_flag: str | None, *, paid_immediately: bool) -> bool:
    """13 §2.8 / VM 830: the input-VAT credit (``vat_moves``) of a ``red``/``unknown`` e-invoice waits
    for the payment; the ``Dt 4410`` line itself is posted, flagged ``vat_credit='deferred'``.

    A receipt paid at once (``paid_immediately``) *is* paid — the credit is taken at posting.
    No linked e-invoice (manual receipt) → recorded at posting.
    """
    return risk_flag in DEFERRED_RISK_FLAGS and not paid_immediately


def lot_amount(line: ReceiptLine, *, regime: Regime, kind: str) -> Decimal:
    """Value of the new lot: net, or net + VAT in the turnover regime (13 §4.3); gifts at net (2.6a)."""
    if kind == "gratuitous" or regime == "vat":
        return line.net
    return line.total


@dataclass(frozen=True, slots=True)
class ReceiptPosting:
    ledger: list[LedgerLine]
    vat: list[VatMove]
    payable: Decimal  # debt_moves(payable) amount, 0 → none
    advance_offset: Decimal


def receipt_posting(
    lines: Sequence[tuple[ReceiptLine, UUID]],
    *,
    regime: Regime,
    kind: str,
    paid_immediately: bool,
    risk_flag: str | None,
    advance: Decimal,
    entry_date: date,
    branch_id: UUID,
    inv_acct: str,
    supplier_id: UUID,
    warehouse_id: UUID,
    einvoice_id: UUID | None = None,
) -> ReceiptPosting:
    """The ledger lines, VAT moves and payable of a receipt; ``lines`` = (line, its new lot id)."""
    supplier = str(supplier_id)
    ledger: list[LedgerLine] = []

    def stock_line(line: ReceiptLine, lot_id: UUID, credit: str, amount: Decimal) -> LedgerLine:
        analytics = {
            "product_id": str(line.product_id),
            "warehouse_id": str(warehouse_id),
            "counterparty_id": supplier,
            "line_id": str(line.id),
            "lot_id": str(lot_id),
        }
        return LedgerLine(entry_date, branch_id, inv_acct, credit, amount, analytics)

    if kind == "gratuitous":
        for line, lot_id in lines:
            ledger.append(stock_line(line, lot_id, GRATUITOUS, line.net))
        return ReceiptPosting(ledger, [], ZERO, ZERO)

    credit = BANK if paid_immediately else SUPPLIERS
    vat_lines: list[VatMove] = []
    if regime == "turnover":
        for line, lot_id in lines:
            ledger.append(stock_line(line, lot_id, credit, line.total))
    else:
        for line, lot_id in lines:
            ledger.append(stock_line(line, lot_id, credit, line.net))
        vat_total = money(sum((ln.vat_amount for ln, _ in lines), ZERO))
        if vat_total > 0:
            deferred = vat_deferred(risk_flag, paid_immediately=paid_immediately)
            analytics: dict[str, str] = {"tax_type": "vat", "counterparty_id": supplier}
            if einvoice_id is not None:
                analytics["einvoice_id"] = str(einvoice_id)
            if deferred:
                analytics["vat_credit"] = "deferred"
            ledger.append(LedgerLine(entry_date, branch_id, INPUT_VAT, credit, vat_total, analytics))
            if not deferred:
                base = money(sum((ln.net for ln, _ in lines if ln.vat_amount > 0), ZERO))
                vat_lines.append(VatMove(entry_date, "input", base, vat_total, einvoice_id))
    if paid_immediately:
        return ReceiptPosting(ledger, vat_lines, ZERO, ZERO)
    gross = money(sum((ln.total for ln, _ in lines), ZERO))
    credited = money(sum((x.amount for x in ledger if x.account_kt == SUPPLIERS), ZERO))
    offset = money(max(min(advance, credited), ZERO))
    if offset > 0:
        ledger.append(
            LedgerLine(entry_date, branch_id, SUPPLIERS, ADVANCES, offset, {"counterparty_id": supplier})
        )
    return ReceiptPosting(ledger, vat_lines, gross, offset)


def remaining_by_product(ordered: dict[UUID, Decimal], received: dict[UUID, Decimal]) -> dict[UUID, Decimal]:
    """PO quantity still expected per product (ordered − already received in posted receipts, ≥ 0)."""
    out = {p: max(q - received.get(p, ZERO_QTY), ZERO_QTY) for p, q in ordered.items()}
    return out


def discrepant_products(lines: Sequence[tuple[UUID, Decimal]], remaining: dict[UUID, Decimal]) -> set[UUID]:
    """Products whose received quantity (Σ over the receipt's lines) differs from what the PO still
    expects — their lines need ``discrepancy_reason`` (19 §8, QT-M07-02). Products not on the PO
    (expected 0) are discrepant too."""
    got: dict[UUID, Decimal] = {}
    for product_id, quantity in lines:
        got[product_id] = got.get(product_id, ZERO_QTY) + quantity
    return {p for p, q in got.items() if q != remaining.get(p, ZERO_QTY)}
