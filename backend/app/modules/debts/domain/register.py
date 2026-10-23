"""Debt register rules (11 §7 ``debt_moves``/``debt_balances``, 13 §5.2, 23 §2.1) — pure Python.

``direction``: ``receivable`` — the counterparty owes us; ``payable`` — we owe the counterparty.
``amount`` is signed: ``+`` increases the debt in that direction, ``−`` decreases it. A negative
``payable`` balance is a supplier advance (13 §2.16, qaror #47). Storno rows carry the negated
amount and ``reversal_of_id`` of the original row (13 §5.2) — rows are never updated.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

Direction = Literal["receivable", "payable"]
DIRECTIONS: Final[tuple[Direction, ...]] = ("receivable", "payable")
ZERO: Final = Decimal("0.00")

BalanceKey = tuple[UUID, Direction]


@dataclass(frozen=True, slots=True)
class DebtMoveInput:
    """One register line a posting service asks for (amount already rounded to 2 dp by the caller)."""

    counterparty_id: UUID
    direction: Direction
    amount: Decimal
    doc_type: str  # document table name (11 §7: ``goods_receipts``, ``supplier_returns``, ``sales`` …)
    doc_id: UUID
    due_date: date | None = None
    limit_exceeded: bool = False


@dataclass(frozen=True, slots=True)
class DebtMove:
    id: UUID
    counterparty_id: UUID
    direction: Direction
    amount: Decimal
    due_date: date | None
    limit_exceeded: bool
    doc_type: str
    doc_id: UUID
    reversal_of_id: UUID | None
    created_at: datetime


def lock_order(keys: Iterable[BalanceKey]) -> list[BalanceKey]:
    """Deadlock-free lock order of ``debt_balances`` rows: ``counterparty_id``, then direction (23 §2.1)."""
    return sorted(set(keys), key=lambda key: (key[0].bytes, key[1]))


def net_deltas(moves: Iterable[tuple[UUID, Direction, Decimal]]) -> dict[BalanceKey, Decimal]:
    deltas: dict[BalanceKey, Decimal] = {}
    for counterparty_id, direction, amount in moves:
        key = (counterparty_id, direction)
        deltas[key] = deltas.get(key, ZERO) + amount
    return deltas


def pending_reversals(moves: Iterable[DebtMove]) -> list[DebtMove]:
    """Original rows of a document that have no storno row yet (a second cancel is a no-op)."""
    rows = list(moves)
    reversed_ids = {m.reversal_of_id for m in rows if m.reversal_of_id is not None}
    return [m for m in rows if m.reversal_of_id is None and m.id not in reversed_ids]
