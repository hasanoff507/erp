"""Supplier payment rules (13 §2.16, §2.8; 19 §11; qaror #47) — pure Python.

* **Debt part / advance**: ``debt = min(amount, max(payable_balance, 0))`` closes payables
  (``Dt 6010``); ``advance = amount − debt`` is a prepayment (``Dt 4310``). ``debt_moves(payable)`` takes the
  full ``−amount`` (a negative payable balance = advance, offset by the next receipt — 13 §2.6).
* **Allocation** (``supplier_payment_allocations``): the debt part is spread over the supplier's open
  documents (posted credit ``goods_receipts`` and payable ``debt_openings``) oldest first —
  ``ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id`` (the 13 §2.14 order); a client may send its own
  split, which must sum to the debt part exactly and stay within each document's outstanding amount.
* **Deferred VAT credit** (13 §2.8/§2.16, VM 830): a receipt posted against a ``red``/``unknown`` e-invoice
  carries its input VAT on 4410 flagged ``vat_credit='deferred'`` and has no ``vat_moves``; a payment releases
  the credit proportionally — ``vat_i = ROUND_HALF_UP(invoice_vat × alloc_i / invoice_total, 2)`` (base
  likewise), the payment that closes the document takes the remainder; only ``vat_moves(input)`` are written.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from app.core.money import money
from app.modules.accounting.domain.entries import LedgerLine, VatMove

TargetType = Literal["goods_receipts", "debt_openings"]
Method = Literal["cash", "bank"]

ZERO: Final = Decimal("0.00")
SUPPLIERS: Final = "6010"
ADVANCES: Final = "4310"
CASH: Final = "5010"
BANK: Final = "5110"
TARGET_TYPES: Final = ("goods_receipts", "debt_openings")


@dataclass(frozen=True, slots=True)
class OpenDoc:
    """An open payable document of a supplier with its outstanding amount and deferred VAT state."""

    target_doc_type: str
    target_doc_id: UUID
    number: str | None
    doc_date: date
    due_date: date | None
    total: Decimal  # payable recognised at posting (invoice total incl. VAT)
    outstanding: Decimal  # total − returns − advance offset − posted allocations (≥ 0)
    einvoice_id: UUID | None = None
    risk_flag: str | None = None
    deferred_vat: Decimal = ZERO  # live 4410 ``vat_credit='deferred'`` of the receipt
    deferred_base: Decimal = ZERO  # Σ net of its taxed lines
    released_vat: Decimal = ZERO  # Σ vat_moves(input) already written for its e-invoice
    released_base: Decimal = ZERO

    @property
    def vat_pending(self) -> Decimal:
        return money(max(self.deferred_vat - self.released_vat, ZERO))


@dataclass(frozen=True, slots=True)
class Allocation:
    doc: OpenDoc
    amount: Decimal


@dataclass(frozen=True, slots=True)
class VatRelease:
    doc: OpenDoc
    base: Decimal
    vat: Decimal


def allocation_key(doc: OpenDoc) -> tuple[date, date, bytes]:
    """13 §2.14 order (shared with customer debts): due date (else doc date), doc date, doc id."""
    return (doc.due_date or doc.doc_date, doc.doc_date, doc.target_doc_id.bytes)


def debt_part(amount: Decimal, payable_balance: Decimal) -> Decimal:
    """The part of a payment that closes payables; the rest is an advance (13 §2.16)."""
    return money(min(amount, max(payable_balance, ZERO)))


def auto_allocate(docs: Sequence[OpenDoc], amount: Decimal) -> list[Allocation]:
    """Spread ``amount`` over ``docs`` oldest first (each up to its outstanding)."""
    left = money(amount)
    out: list[Allocation] = []
    for doc in sorted(docs, key=allocation_key):
        if left <= 0:
            break
        take = money(min(left, doc.outstanding))
        if take > 0:
            out.append(Allocation(doc, take))
            left -= take
    return out


def vat_release(alloc: Allocation) -> VatRelease | None:
    """Deferred input-VAT credit released by one allocation (13 §2.16); ``None`` when nothing is pending."""
    doc = alloc.doc
    pending_vat = doc.vat_pending
    if pending_vat <= 0 or doc.total <= 0:
        return None
    pending_base = money(max(doc.deferred_base - doc.released_base, ZERO))
    if alloc.amount >= doc.outstanding:  # this payment closes the document → the remainder
        return VatRelease(doc, pending_base, pending_vat)
    vat = money(min(doc.deferred_vat * alloc.amount / doc.total, pending_vat))
    base = money(min(doc.deferred_base * alloc.amount / doc.total, pending_base))
    if vat <= 0 and base <= 0:
        return None
    return VatRelease(doc, base, vat)


def payment_posting(
    *,
    method: str,
    allocated: Decimal,
    advance: Decimal,
    entry_date: date,
    branch_id: UUID,
    supplier_id: UUID,
    cash_register_id: UUID | None,
    shift_id: UUID | None,
    releases: Sequence[VatRelease],
) -> tuple[list[LedgerLine], list[VatMove]]:
    """``Dt 6010 / Kt 5010|5110 = allocated``, ``Dt 4310 / Kt 5010|5110 = advance`` + released VAT moves."""
    credit = CASH if method == "cash" else BANK
    analytics: dict[str, str] = {"counterparty_id": str(supplier_id)}
    if method == "cash" and cash_register_id is not None and shift_id is not None:
        analytics["cash_register_id"] = str(cash_register_id)
        analytics["shift_id"] = str(shift_id)
    ledger = [
        LedgerLine(entry_date, branch_id, SUPPLIERS, credit, money(allocated), analytics),
        LedgerLine(entry_date, branch_id, ADVANCES, credit, money(advance), analytics),
    ]
    vat = [VatMove(entry_date, "input", r.base, r.vat, r.doc.einvoice_id) for r in releases]
    return ledger, vat
