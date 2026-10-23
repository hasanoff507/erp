"""Open receivable documents of a customer for the dashboard / daily summary (M08 figures). Pure Python.

The receivable register is ``debt_moves`` + ``debt_balances`` (13 §2.3, §2.13–§2.15). A debt document is a
posted credit sale or a receivable ``debt_openings`` row; its open part is its own moves (incl. storno) minus
the posted ``debt_payment_allocations`` that target it and the ``debt_adjustment`` part of its returns
(:class:`DebtDoc.amount`, computed in SQL). Anything the per-document figures cannot place (a write-off, an
adjustment entry) is reconciled to the counterparty balance **oldest first** — the same order as payment
allocation (13 §2.14: ``ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id``), so the sum of open
documents always equals ``debt_balances.balance``.

Due date of an open document (``effective_due``): ``COALESCE(due_date, doc_date)`` (20 #21 — the one
definition for aging, dashboard, alerts and Telegram, ACC-12 / F6). The customer's promise
(``counterparties.debt_due_date``) does **not** move it: a promise renegotiates collection, not age; it only
drives the ``debt_due_today`` reminder (debts daily check). A document is **overdue** on ``as_of`` when
``effective_due < as_of``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class DebtDoc:
    counterparty_id: UUID
    branch_id: UUID
    doc_type: str  # 'sales' | 'debt_openings'
    doc_id: UUID
    doc_date: date
    due_date: date | None
    amount: Decimal  # open part before reconciliation

    @property
    def key(self) -> date:
        return self.due_date or self.doc_date


@dataclass(frozen=True, slots=True)
class OpenDebt:
    counterparty_id: UUID
    branch_id: UUID
    doc_type: str
    doc_id: UUID
    effective_due: date
    open_amount: Decimal


def _order(doc: DebtDoc) -> tuple[date, date, str]:
    return (doc.key, doc.doc_date, str(doc.doc_id))


def reconcile(docs: Iterable[DebtDoc], balance: Decimal) -> list[OpenDebt]:
    """Open documents of ONE counterparty whose sum equals ``balance`` (≤ 0 → nothing is open).

    Excess document amounts are consumed oldest first; a balance larger than the documents (no document to
    place it on) stays unplaced — it is not attributed to a due date or a branch."""
    ordered = sorted((d for d in docs if d.amount > 0), key=_order)
    if balance <= 0:
        return []
    excess = sum((d.amount for d in ordered), ZERO) - balance
    out: list[OpenDebt] = []
    for doc in ordered:
        amount = doc.amount
        if excess > 0:
            taken = min(excess, amount)
            amount -= taken
            excess -= taken
        if amount <= 0:
            continue
        out.append(OpenDebt(doc.counterparty_id, doc.branch_id, doc.doc_type, doc.doc_id, doc.key, amount))
    return out


def overdue_total(open_docs: Sequence[OpenDebt], as_of: date) -> Decimal:
    return sum((d.open_amount for d in open_docs if d.effective_due < as_of), ZERO)


def due_on_total(open_docs: Sequence[OpenDebt], day: date) -> Decimal:
    return sum((d.open_amount for d in open_docs if d.effective_due == day), ZERO)
