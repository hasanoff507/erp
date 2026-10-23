"""Quantity allocation and cost math for FIFO / AVECO (13 §3.1–§3.2a, §5.3). Pure Python.

Model
-----
* **Lots track quantities FIFO for both methods** (13 §3.1, 11 §7): an issue always takes
  ``qty_left − blocked_qty`` from the oldest lots (``ORDER BY received_at, id``) or from one lot the
  caller names. Only the *valuation* differs:

  - **FIFO**: cost of a piece = ``ROUND_HALF_UP(piece_qty × lot.unit_cost, 2)``;
  - **AVECO**: cost = ``ROUND_HALF_UP(qty × avg_cost, 2)``, ``total_value −= cost`` (13 §3.1); the
    value is tracked as *old value − COGS*, never ``qty × avg``; the unit cost reported for every
    piece is the ``avg_cost`` used.

* **Last unit out takes the residual value.** When an issue leaves no units at all in the lots of
  ``(warehouse, product)`` (``Σ qty_left = 0`` afterwards — so nothing blocked either), the covered
  part costs exactly the remaining register value (FIFO: ``stock_balances.value``; AVECO:
  ``total_value``) — the last piece absorbs the tiyin rounding residue. So the inventory account is
  exactly ``0.00`` whenever the stock is empty (13 §3.1 "qty_after ≤ 0 → total_value = 0").

* **AVECO receipt** (any positive movement into lots — receipt, return, cancelled issue)::

      total_value' = total_value + amount
      L'           = Σ qty_left (physical units in lots) + qty
      avg_cost'    = ROUND_HALF_UP(total_value' / L', 4)          (NUMERIC(18,4), 13 §5.3)

  ``L`` (units in lots) rather than the balance qty is the divisor: while issues are *pending*
  (negative stock) ``total_value`` holds only the physical units' value (``0`` when none), so
  receiving 10 units for ``100 000.00`` into a balance of ``−2`` gives ``avg_cost' = 10 000.0000``
  (not 100 000 / 8). The 2 pending units are then settled from the new stock at that cost:
  ``total_value = 100 000.00 − 20 000.00 = 80 000.00`` for the 8 remaining units — exact.

* **Negative stock** (13 §3.1, 16 §5): the uncovered remainder of an issue becomes a *pending*
  piece ``{lot_id: null, qty, unit_cost, pending: true}`` costed at an estimate (see
  :func:`pending_unit_cost`); it is settled — re-costed from real lots — as soon as stock arrives.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.core.money import money, price, qty, to_decimal

Method = Literal["fifo", "aveco"]
ZERO_QTY = Decimal("0.000")
ZERO_MONEY = Decimal("0.00")
ZERO_PRICE = Decimal("0.0000")


@dataclass(frozen=True, slots=True)
class Allocation:
    """One piece of an issue; the JSON shape of ``sale_lines`` / ``transfer_lines.lot_allocations``."""

    lot_id: UUID | None
    qty: Decimal
    unit_cost: Decimal
    pending: bool = False

    def as_json(self) -> dict[str, Any]:
        return {
            "lot_id": str(self.lot_id) if self.lot_id else None,
            "qty": format(qty(self.qty), "f"),
            "unit_cost": format(price(self.unit_cost), "f"),
            "pending": self.pending,
        }

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> Allocation:
        lot = raw.get("lot_id")
        return cls(
            lot_id=UUID(str(lot)) if lot else None,
            qty=qty(to_decimal(str(raw["qty"]))),
            unit_cost=price(to_decimal(str(raw["unit_cost"]))),
            pending=bool(raw.get("pending", False)),
        )


@dataclass(frozen=True, slots=True)
class LotView:
    id: UUID
    received_at: datetime
    qty_left: Decimal
    blocked_qty: Decimal
    unit_cost: Decimal

    @property
    def available(self) -> Decimal:
        return self.qty_left - self.blocked_qty


@dataclass(frozen=True, slots=True)
class AvgState:
    """``avg_costs`` row: ``qty`` = balance qty (may be negative), ``total_value`` = physical value."""

    qty: Decimal
    avg_cost: Decimal
    total_value: Decimal


@dataclass(frozen=True, slots=True)
class IssuePlan:
    pieces: list[tuple[LotView, Decimal]]
    uncovered: Decimal

    @property
    def covered(self) -> Decimal:
        return sum((q for _, q in self.pieces), ZERO_QTY)


def fifo_order(lots: Sequence[LotView]) -> list[LotView]:
    return sorted(lots, key=lambda lot: (lot.received_at, lot.id.int))


def plan_issue(
    lots: Sequence[LotView], quantity: Decimal, *, lot_id: UUID | None = None, from_blocked: bool = False
) -> IssuePlan:
    """Which lots give ``quantity`` (both methods); ``uncovered`` is what the lots cannot give.

    * no ``lot_id``: FIFO over ``qty_left − blocked_qty > 0``;
    * ``lot_id``: only that lot — its free part, or its *blocked* part with ``from_blocked=True``
      (``expired_return`` write-off, 13 §2.5).
    """
    if quantity <= 0:
        raise ValueError("issue quantity must be > 0")
    if lot_id is not None:
        lot = next((x for x in lots if x.id == lot_id), None)
        avail = ZERO_QTY if lot is None else (lot.blocked_qty if from_blocked else lot.available)
        take = min(quantity, max(avail, ZERO_QTY))
        pieces = [(lot, take)] if lot is not None and take > 0 else []
        return IssuePlan(pieces, quantity - take)
    if from_blocked:
        raise ValueError("from_blocked needs an explicit lot_id")
    need = quantity
    pieces = []
    for lot in fifo_order(lots):
        if need <= 0:
            break
        if lot.available <= 0:
            continue
        take = min(need, lot.available)
        pieces.append((lot, take))
        need -= take
    return IssuePlan(pieces, need)


def empties_all(lots: Sequence[LotView], plan: IssuePlan) -> bool:
    """After the plan, are there no units left in any lot (free or blocked)?"""
    taken: dict[UUID, Decimal] = {}
    for lot, q in plan.pieces:
        taken[lot.id] = taken.get(lot.id, ZERO_QTY) + q
    return bool(plan.pieces) and all(lot.qty_left - taken.get(lot.id, ZERO_QTY) == 0 for lot in lots)


def fifo_piece_costs(
    plan: IssuePlan,
    *,
    register_value: Decimal,
    last_out: bool,
    lot_values: Mapping[UUID, tuple[Decimal, int]] | None = None,
) -> list[Decimal]:
    """FIFO cost of every piece (13 §3.1).

    A piece that empties its lot (``qty_left − q = 0``) costs the lot's remaining value
    (``lot_values[lot.id]`` = (Σ ``cost_amount`` of the lot's live moves, their count)) — the tiyin
    rounding residue leaves with the lot. The remaining value is used only while it differs from
    ``ROUND(q × unit_cost, 2)`` by no more than rounding can explain (0.01 per move plus the 4-dp unit
    cost of the receipt): a lot repriced by an AVECO→FIFO switch (no moves written) or a negative value
    falls back to ``ROUND(q × unit_cost, 2)``. Then, with ``last_out``, the last piece takes the residual
    register value.
    """
    values = lot_values or {}
    costs: list[Decimal] = []
    for lot, q in plan.pieces:
        entry = values.get(lot.id)
        nominal = money(q * lot.unit_cost)
        if lot.qty_left - q == 0 and entry is not None and entry[0] >= 0:
            remaining, moves = entry
            tolerance = Decimal("0.01") * moves + q * Decimal("0.0001")
            costs.append(money(remaining) if abs(remaining - nominal) <= tolerance else nominal)
        else:
            costs.append(nominal)
    if last_out and costs:
        residual = money(register_value) - sum(costs[:-1], ZERO_MONEY)
        if residual >= 0:
            costs[-1] = residual
    return costs


def split_amount(total: Decimal, quantities: Sequence[Decimal], unit_cost: Decimal) -> list[Decimal]:
    """Split ``total`` over pieces as ``ROUND(q × unit_cost, 2)``; the last piece takes the remainder."""
    if not quantities:
        return []
    parts = [money(q * unit_cost) for q in quantities[:-1]]
    parts.append(money(total) - sum(parts, ZERO_MONEY))
    return parts


def aveco_issue(
    state: AvgState, quantity: Decimal, covered: Decimal, *, last_out: bool
) -> tuple[Decimal, AvgState]:
    """AVECO cost of the *covered* part of an issue of ``quantity`` and the new state (13 §3.1).

    The pending (uncovered) part is costed separately at an estimate and never enters
    ``total_value``; ``avg_cost`` never changes on an issue.
    """
    if covered <= 0:
        cost = ZERO_MONEY
    elif last_out:
        cost = money(state.total_value)
    else:
        cost = money(covered * state.avg_cost)
    return cost, AvgState(state.qty - quantity, state.avg_cost, money(state.total_value - cost))


def aveco_credit(state: AvgState, lot_units_before: Decimal, quantity: Decimal, amount: Decimal) -> AvgState:
    """Units enter the lots at ``amount`` (receipt, return at original cost, cancelled issue)."""
    value = money(state.total_value + amount)
    units = lot_units_before + quantity
    avg = price(value / units) if units > 0 else state.avg_cost
    return AvgState(state.qty + quantity, avg, value)


class AvecoValueError(ValueError):
    """A cancelled receipt would leave AVECO ``total_value < 0`` (or value without units) — its value
    is already mixed into issued COGS (13 §3.1 → ``409 LOT_ALREADY_CONSUMED``)."""


def aveco_debit(state: AvgState, lot_units_before: Decimal, quantity: Decimal, amount: Decimal) -> AvgState:
    """Units leave the lots at a fixed ``amount`` (a cancelled receipt): the inverse of a credit.

    Raises :class:`AvecoValueError` when the value would go below 0, or stay ≠ 0 with no units left.
    """
    value = money(state.total_value - amount)
    units = lot_units_before - quantity
    if value < 0 or (units == 0 and value != 0):
        raise AvecoValueError(f"aveco total_value {value} for {units} units after the debit")
    avg = price(value / units) if units > 0 else state.avg_cost
    return AvgState(state.qty - quantity, avg, value)


def pending_unit_cost(
    method: Method,
    *,
    avg_cost: Decimal | None,
    last_lot_cost: Decimal | None,
    last_purchase_cost: Decimal | None,
) -> Decimal:
    """Estimate for a pending piece (13 §3.1): last lot cost → ``last_purchase_cost`` → ``0``.

    For AVECO the current ``avg_cost`` (when > 0) comes first — it is the AVECO "last known cost".
    ``0`` means *cost unknown* — the caller records ``sync_exceptions(kind='cost_unknown')``.
    """
    candidates = [avg_cost] if method == "aveco" else []
    candidates += [last_lot_cost, last_purchase_cost]
    for value in candidates:
        if value is not None and value > 0:
            return price(value)
    return ZERO_PRICE


def return_pieces(
    issued: Sequence[Allocation], already_returned: Decimal, quantity: Decimal
) -> list[Allocation]:
    """13 §3.2a: give ``quantity`` back to the original pieces in *reverse* allocation order, at
    their original unit cost, skipping what earlier returns of the same line already took."""
    if quantity <= 0:
        raise ValueError("return quantity must be > 0")
    skip, need = already_returned, quantity
    out: list[Allocation] = []
    for piece in reversed(issued):
        left = piece.qty
        skipped = min(left, skip)
        skip -= skipped
        left -= skipped
        take = min(left, need)
        if take > 0:
            out.append(Allocation(piece.lot_id, take, piece.unit_cost, piece.pending))
            need -= take
        if need == 0:
            break
    if need > 0:
        raise ValueError("return quantity exceeds what the line issued")
    return out


def lot_unit_cost(amount: Decimal, quantity: Decimal) -> Decimal:
    """``stock_lots.unit_cost`` (4 dp) from a line total; the amount itself stays the move's value."""
    if quantity <= 0:
        raise ValueError("lot quantity must be > 0")
    return price(amount / quantity)
