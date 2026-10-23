"""Debt register primitive (11 §7, 13 §5.2, 23 §2.1) — used inside other modules' posting transactions.

Every method runs in the **caller's** ``tenant_transaction`` (the posting service of goods receipts,
supplier returns, later sales/returns/debt payments). Lock order (23 §2.1): the caller locks its
``stock_balances`` rows first; :meth:`DebtRegister.post` / :meth:`DebtRegister.reverse` then lock the
``debt_balances`` rows they touch, sorted by ``counterparty_id`` — so two documents for the same
counterparty serialise instead of deadlocking.

Usage (inside a posting service)::

    register = debt_register()                      # app.modules.debts.wiring
    await register.post(s, tenant_id, [
        DebtMoveInput(supplier_id, "payable", money(total), "goods_receipts", receipt_id),
    ])
    ...
    await register.reverse(s, tenant_id, "goods_receipts", receipt_id)   # on cancel (storno)
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.money import money
from app.modules.debts.application.ports import DebtRegisterRepository
from app.modules.debts.domain.register import (
    DIRECTIONS,
    ZERO,
    BalanceKey,
    DebtMove,
    DebtMoveInput,
    Direction,
    lock_order,
    net_deltas,
    pending_reversals,
)


class DebtRegister:
    def __init__(self, repo: DebtRegisterRepository) -> None:
        self._repo = repo

    async def lock(
        self, s: AsyncSession, tenant_id: UUID, keys: Iterable[BalanceKey]
    ) -> dict[BalanceKey, Decimal]:
        """``INSERT … ON CONFLICT DO NOTHING`` + ``SELECT … FOR UPDATE`` in lock order; current balances.

        Call it early when the caller must check a balance before writing (e.g. a credit limit,
        13 §2.16 overpay policy); :meth:`post` locks by itself otherwise.
        """
        ordered = lock_order(keys)
        if not ordered:
            return {}
        return await self._repo.lock_balances(s, tenant_id, ordered)

    async def post(self, s: AsyncSession, tenant_id: UUID, moves: Sequence[DebtMoveInput]) -> list[DebtMove]:
        """Append ``debt_moves`` (signed 2-dp amounts) and move ``debt_balances`` by the same amounts."""
        lines = [self._checked(m) for m in moves]
        lines = [m for m in lines if m.amount != ZERO]
        if not lines:
            return []
        await self.lock(s, tenant_id, ((m.counterparty_id, m.direction) for m in lines))
        written = await self._repo.insert_moves(s, tenant_id, [(uuid7(), m, None) for m in lines])
        await self._repo.add_to_balances(
            s, tenant_id, net_deltas((m.counterparty_id, m.direction, m.amount) for m in lines)
        )
        return written

    async def reverse(self, s: AsyncSession, tenant_id: UUID, doc_type: str, doc_id: UUID) -> list[DebtMove]:
        """Storno of a document (13 §5.2): one negated row per original row, ``reversal_of_id`` set.

        Idempotent — rows that already have a storno row are skipped (a repeated cancel writes nothing).
        """
        originals = pending_reversals(await self._repo.moves_of_doc(s, doc_type, doc_id))
        if not originals:
            return []
        await self.lock(s, tenant_id, ((m.counterparty_id, m.direction) for m in originals))
        rows = [
            (
                uuid7(),
                DebtMoveInput(
                    counterparty_id=m.counterparty_id,
                    direction=m.direction,
                    amount=-m.amount,
                    doc_type=m.doc_type,
                    doc_id=m.doc_id,
                    due_date=m.due_date,
                    limit_exceeded=m.limit_exceeded,
                ),
                m.id,
            )
            for m in originals
        ]
        written = await self._repo.insert_moves(s, tenant_id, rows)
        await self._repo.add_to_balances(
            s, tenant_id, net_deltas((m.counterparty_id, m.direction, -m.amount) for m in originals)
        )
        return written

    async def balances(self, s: AsyncSession, counterparty_id: UUID) -> dict[Direction, Decimal]:
        """``{receivable, payable}`` from ``debt_balances`` (``0.00`` when there is no row); no lock."""
        found = await self._repo.balances(s, counterparty_id)
        return {d: money(found.get(d, ZERO)) for d in DIRECTIONS}

    @staticmethod
    def _checked(move: DebtMoveInput) -> DebtMoveInput:
        if move.direction not in DIRECTIONS:
            raise ValueError(f"unknown debt direction {move.direction!r}")
        if not move.doc_type:
            raise ValueError("doc_type is required")
        amount = money(move.amount)
        if amount != move.amount:
            raise ValueError(f"debt amount must have at most 2 decimal places: {move.amount}")
        return replace(move, amount=amount)
