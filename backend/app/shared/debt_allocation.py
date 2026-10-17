"""Debt payment allocation and ``debt_settlement`` receipt lines (18 §12.2, 13 §2.14, 16 §1; qaror #45, #67).

ONE formula for the server posting and the offline POS: the TS twin is ``@shared/lib/debt-allocation``
(web/packages/shared/lib/src/debt-allocation); both read ``shared/debt-allocation-vectors.json`` in their
test suites (32 §6.3). Pure Python — imports only ``app.core.money``.

**Allocation order.** First the open remainders of ``sales`` and ``debt_openings``
``ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id``; then ``debt_writeoffs`` (written-off debt that
comes back — ``Kt 9390``), oldest first (``ORDER BY doc_date, doc_id``). Each target takes
``min(rest, open_amount)``; what is left is ``unallocated_amount`` (offline overpayment — ``Kt 6310``).

**Receipt lines** (one ``debt_settlement`` receipt per payment; ``FiscalPolicy.debt_receipt_split='single'``).
A line returned against the sale (``returned_qty`` / ``returned_amount`` — posted ``return_lines``, 13 §2.5)
only keeps its remainder: ``eff_total_i = max(line_total_i − returned_amount_i, 0)``,
``eff_qty_i = qty_i − returned_qty_i``; lines with ``eff_total_i = 0`` are skipped. For every sale
allocation ``a`` (``total = Σ eff_total_i``, ``room_i = max(eff_total_i − settled_amount_i, 0)``,
``goods = min(a, Σ room_i)``):

* ``goods = Σ room_i`` — the payment closes the sale: ``amt_i = room_i``;
* otherwise ``amt_i = min(ROUND_HALF_UP(eff_total_i × goods / total, 2), room_i)``, the rounding rest goes to
  the largest ``eff_total`` (ties — the larger line number) within its room;
* ``qty_i = max(R3(eff_qty_i × (settled_i + amt_i) / eff_total_i) − R3(eff_qty_i × settled_i / eff_total_i),
  0.001)`` (``R3`` = ROUND_HALF_UP to 3 decimals) — the quantities of one line's receipts telescope to
  exactly ``eff_qty_i``; the receipt that closes the line gets
  ``eff_qty_i − R3(eff_qty_i × settled_i / eff_total_i)``;
* ``vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)`` (qaror #26); the marking code only on a line the receipt
  closes (``amt_i = room_i``); lines with ``amt_i = 0`` are left out.

``debt_openings`` / ``debt_writeoffs`` allocations, ``unallocated_amount`` and a sale allocation above the
sale's
fiscal room go to ONE general line without goods (``sale_id``/``sale_line_id``/``product_id`` null,
``qty = 1.000``, ``vat_rate = 0.00``) — the receipt total always equals the money received.

**Reconcile to the balance** (:func:`reconcile_to_balance`, 13 §2.14): the open sales and openings of a
customer are trimmed oldest first (allocation order) by ``excess = Σ open − max(balance, 0)`` — a credit on
the account without a document (a ``debt_adjustment`` return of a sale with no open debt) closes the oldest
debt; write-offs are never trimmed. Invariant: ``Σ reconciled open(sales + openings) == max(balance, 0)``
whenever ``balance ≤ Σ open``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final, Literal

from app.core.money import money, money_str, percent_str, qty, qty_str, to_decimal, vat_from_gross

TargetType = Literal["sales", "debt_openings", "debt_writeoffs"]
TARGET_TYPES: Final[tuple[str, ...]] = ("sales", "debt_openings", "debt_writeoffs")
ZERO: Final = Decimal("0.00")
MIN_QTY: Final = Decimal("0.001")
GENERAL_QTY: Final = Decimal("1.000")
GENERAL_RATE: Final = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class OpenLine:
    """A sale line of an open sale (16 §1 ``open_debt_docs[].lines[]`` — the fields the formula needs)."""

    sale_line_id: str
    product_id: str | None
    qty: Decimal
    line_total: Decimal
    vat_rate: Decimal
    settled_amount: Decimal
    marking_code: str | None = None
    returned_qty: Decimal = Decimal("0.000")  # Σ posted return_lines.qty of this sale line (ACC-01)
    returned_amount: Decimal = Decimal("0.00")  # Σ posted return_lines.line_total of this sale line

    @property
    def eff_total(self) -> Decimal:
        return max(money(self.line_total) - money(self.returned_amount), ZERO)

    @property
    def eff_qty(self) -> Decimal:
        return max(qty(self.qty) - qty(self.returned_qty), Decimal("0.000"))


@dataclass(frozen=True, slots=True)
class OpenDoc:
    doc_type: str  # sales | debt_openings | debt_writeoffs
    doc_id: str  # lowercase UUID text (UUIDv7 — text order = byte order)
    doc_date: str  # ISO date
    due_date: str | None
    open_amount: Decimal
    lines: tuple[OpenLine, ...] = ()


@dataclass(frozen=True, slots=True)
class Allocation:
    target_doc_type: str
    target_doc_id: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class FiscalLine:
    sale_id: str | None
    sale_line_id: str | None
    product_id: str | None
    qty: Decimal
    amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    marking_code: str | None


@dataclass(frozen=True, slots=True)
class AllocationResult:
    allocations: tuple[Allocation, ...]
    unallocated_amount: Decimal
    fiscal_lines: tuple[FiscalLine, ...] = field(default_factory=tuple)

    @property
    def allocated(self) -> Decimal:
        return money(sum((a.amount for a in self.allocations), ZERO))

    def amount_for(self, doc_type: str) -> Decimal:
        return money(sum((a.amount for a in self.allocations if a.target_doc_type == doc_type), ZERO))

    def settled_by_line(self) -> dict[str, Decimal]:
        """``sale_line_id`` → amount this receipt fiscalizes (the ``sale_lines.settled_amount`` increment)."""
        out: dict[str, Decimal] = {}
        for ln in self.fiscal_lines:
            if ln.sale_line_id is not None:
                out[ln.sale_line_id] = out.get(ln.sale_line_id, ZERO) + ln.amount
        return out


def allocation_order(docs: Sequence[OpenDoc]) -> list[OpenDoc]:
    """Debts first (sales + openings by ``COALESCE(due_date, doc_date), doc_date, doc_id``), then
    write-offs."""
    debts = [d for d in docs if d.doc_type != "debt_writeoffs"]
    written_off = [d for d in docs if d.doc_type == "debt_writeoffs"]
    debts.sort(key=lambda d: (d.due_date or d.doc_date, d.doc_date, d.doc_id))
    written_off.sort(key=lambda d: (d.doc_date, d.doc_id))
    return [*debts, *written_off]


def allocate(amount: Decimal, docs: Sequence[OpenDoc], *, fiscal: bool = True) -> AllocationResult:
    """Allocate ``amount`` over the open documents; ``fiscal=False`` skips the receipt lines (bank
    payment)."""
    amount = money(amount)
    if amount <= 0:
        raise ValueError("payment amount must be positive")
    for doc in docs:
        if doc.doc_type not in TARGET_TYPES:
            raise ValueError(f"unknown target doc_type {doc.doc_type!r}")
    rest = amount
    allocations: list[Allocation] = []
    lines: list[FiscalLine] = []
    general = ZERO
    for doc in allocation_order(docs):
        if rest <= 0:
            break
        open_amount = money(doc.open_amount)
        if open_amount <= 0:
            continue
        take = min(rest, open_amount)
        rest = money(rest - take)
        allocations.append(Allocation(doc.doc_type, doc.doc_id, take))
        if doc.doc_type == "sales" and fiscal:
            goods_lines, excess = _sale_lines(doc, take)
            lines.extend(goods_lines)
            general += excess
        else:
            general += take
    general = money(general + rest)
    if fiscal and general > 0:
        lines.append(FiscalLine(None, None, None, GENERAL_QTY, general, GENERAL_RATE, ZERO, None))
    return AllocationResult(tuple(allocations), rest, tuple(lines) if fiscal else ())


def _sale_lines(doc: OpenDoc, alloc: Decimal) -> tuple[list[FiscalLine], Decimal]:
    src = [ln for ln in doc.lines if ln.eff_total > 0]
    totals = [ln.eff_total for ln in src]
    total = sum(totals, ZERO)
    rooms = [max(t - money(ln.settled_amount), ZERO) for ln, t in zip(src, totals, strict=True)]
    room = sum(rooms, ZERO)
    goods = min(alloc, room)
    excess = money(alloc - goods)
    if goods <= 0 or total <= 0:
        return [], money(alloc)
    if goods == room:
        amounts = list(rooms)
    else:
        amounts = [min(_round(t * goods / total, 2), r) for t, r in zip(totals, rooms, strict=True)]
        diff = goods - sum(amounts, ZERO)
        order = sorted(range(len(src)), key=lambda i: (-totals[i], -i))
        for i in order:
            if diff == 0:
                break
            step = min(diff, rooms[i] - amounts[i]) if diff > 0 else -min(-diff, amounts[i])
            amounts[i] += step
            diff -= step
    out: list[FiscalLine] = []
    for ln, eff_total, room_i, amt in zip(src, totals, rooms, amounts, strict=True):
        if amt <= 0:
            continue
        closes = amt == room_i
        settled = money(ln.settled_amount)
        q = _qty_telescoped(ln.eff_qty, settled, amt, eff_total)
        out.append(
            FiscalLine(
                sale_id=doc.doc_id,
                sale_line_id=ln.sale_line_id,
                product_id=ln.product_id,
                qty=q,
                amount=money(amt),
                vat_rate=to_decimal(ln.vat_rate),
                vat_amount=vat_from_gross(amt, ln.vat_rate),
                marking_code=ln.marking_code if closes else None,
            )
        )
    return out, excess


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _qty_telescoped(eff_qty: Decimal, settled: Decimal, amt: Decimal, eff_total: Decimal) -> Decimal:
    """ACC-10: the quantity telescopes over the cumulative ``settled_amount`` — the receipts of one line sum
    to exactly ``eff_qty`` (the closing receipt takes the rest)."""
    if eff_total <= 0:
        return MIN_QTY
    before = _round(eff_qty * min(settled, eff_total) / eff_total, 3)
    after = _round(eff_qty * min(settled + amt, eff_total) / eff_total, 3)
    return max(after - before, MIN_QTY)


def reconcile_to_balance(docs: Sequence[OpenDoc], balance: Decimal) -> list[OpenDoc]:
    """ACC-02: trim the open sales/openings oldest first so that their Σ equals ``max(balance, 0)``.

    ``balance`` is the customer's ``debt_balances`` receivable. Write-offs are never trimmed; when
    ``Σ open ≤ balance`` nothing changes. The input order is kept; a trimmed document may end at ``0.00``."""
    target = max(money(balance), ZERO)
    debts = [d for d in allocation_order(docs) if d.doc_type != "debt_writeoffs" and money(d.open_amount) > 0]
    excess = money(sum((money(d.open_amount) for d in debts), ZERO) - target)
    if excess <= 0:
        return list(docs)
    trimmed: dict[tuple[str, str], Decimal] = {}
    for d in debts:
        if excess <= 0:
            break
        cut = min(excess, money(d.open_amount))
        trimmed[(d.doc_type, d.doc_id)] = money(money(d.open_amount) - cut)
        excess = money(excess - cut)
    return [
        replace(d, open_amount=trimmed[(d.doc_type, d.doc_id)]) if (d.doc_type, d.doc_id) in trimmed else d
        for d in docs
    ]


# --- JSON boundary (16 §1 open_debt_docs rows, 18 §12.2 payload, shared vectors) ------------------------
def open_doc_from_json(raw: Mapping[str, Any]) -> OpenDoc:
    return OpenDoc(
        doc_type=str(raw["doc_type"]),
        doc_id=str(raw["doc_id"]).lower(),
        doc_date=str(raw["doc_date"]),
        due_date=None if raw.get("due_date") is None else str(raw["due_date"]),
        open_amount=to_decimal(raw["open_amount"]),
        lines=tuple(
            OpenLine(
                sale_line_id=str(ln["sale_line_id"]).lower(),
                product_id=None if ln.get("product_id") is None else str(ln["product_id"]).lower(),
                qty=to_decimal(ln["qty"]),
                line_total=to_decimal(ln["line_total"]),
                vat_rate=to_decimal(ln["vat_rate"]),
                settled_amount=to_decimal(ln.get("settled_amount") or "0.00"),
                marking_code=ln.get("marking_code"),
                returned_qty=to_decimal(ln.get("returned_qty") or "0.000"),
                returned_amount=to_decimal(ln.get("returned_amount") or "0.00"),
            )
            for ln in raw.get("lines") or ()
        ),
    )


def allocation_json(a: Allocation) -> dict[str, str]:
    return {
        "target_doc_type": a.target_doc_type,
        "target_doc_id": a.target_doc_id,
        "amount": money_str(a.amount),
    }


def fiscal_line_json(ln: FiscalLine) -> dict[str, Any]:
    return {
        "sale_id": ln.sale_id,
        "sale_line_id": ln.sale_line_id,
        "product_id": ln.product_id,
        "qty": qty_str(ln.qty),
        "amount": money_str(ln.amount),
        "vat_rate": percent_str(ln.vat_rate),
        "vat_amount": money_str(ln.vat_amount),
        "marking_code": ln.marking_code,
    }


def result_json(result: AllocationResult) -> dict[str, Any]:
    return {
        "allocations": [allocation_json(a) for a in result.allocations],
        "unallocated_amount": money_str(result.unallocated_amount),
        "fiscal_lines": [fiscal_line_json(ln) for ln in result.fiscal_lines],
    }


def allocate_json(amount: str, docs: Sequence[Mapping[str, Any]], *, fiscal: bool = True) -> dict[str, Any]:
    """String in / string out — the shape of the shared vectors and of the POS twin."""
    return result_json(allocate(to_decimal(amount), [open_doc_from_json(d) for d in docs], fiscal=fiscal))
