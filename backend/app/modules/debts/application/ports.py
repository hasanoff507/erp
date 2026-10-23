"""Ports of the debts application layer (implemented in ``debts.infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.debts.domain.counterparties import Counterparty
from app.modules.debts.domain.register import BalanceKey, DebtMove, DebtMoveInput, Direction


@dataclass(frozen=True, slots=True)
class CounterpartyFilter:
    search: str | None = None
    search_digits: str | None = None
    kind: str | None = None
    is_supplier: bool | None = None
    is_customer: bool | None = None
    archived: bool = False


@dataclass(frozen=True, slots=True)
class CounterpartyListRow:
    counterparty: Counterparty
    receivable_balance: Decimal
    payable_balance: Decimal


class CounterpartyRepository(Protocol):
    async def get(
        self, s: AsyncSession, counterparty_id: UUID, *, lock: bool = False
    ) -> Counterparty | None: ...
    async def list_page(
        self, s: AsyncSession, flt: CounterpartyFilter, offset: int, limit: int
    ) -> tuple[list[CounterpartyListRow], int]: ...
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def update(
        self, s: AsyncSession, counterparty_id: UUID, version: int, values: Mapping[str, Any]
    ) -> bool: ...
    async def set_archived(self, s: AsyncSession, counterparty_id: UUID, archived: bool) -> None: ...
    async def find_by_stir(self, s: AsyncSession, stir: str) -> UUID | None: ...


class DebtRegisterRepository(Protocol):
    async def lock_balances(
        self, s: AsyncSession, tenant_id: UUID, keys: Sequence[BalanceKey]
    ) -> dict[BalanceKey, Decimal]: ...
    async def insert_moves(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[tuple[UUID, DebtMoveInput, UUID | None]]
    ) -> list[DebtMove]: ...
    async def add_to_balances(
        self, s: AsyncSession, tenant_id: UUID, deltas: Mapping[BalanceKey, Decimal]
    ) -> None: ...
    async def moves_of_doc(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> list[DebtMove]: ...
    async def balances(self, s: AsyncSession, counterparty_id: UUID) -> dict[Direction, Decimal]: ...
