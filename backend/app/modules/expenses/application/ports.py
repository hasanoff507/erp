"""Ports of the expenses application layer (23 §1)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.domain.approvals import UserGrant
from app.modules.expenses.domain.categories import ExpenseCategoryTemplate


class ExpenseCategoryStore(Protocol):
    async def insert_system_categories(
        self, session: AsyncSession, tenant_id: UUID, categories: Iterable[ExpenseCategoryTemplate]
    ) -> None: ...


class GrantSource(Protocol):
    """``access.wiring.permission_grants()``: live grants + the ``approval_requests`` insert."""

    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant: ...

    async def insert_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...


@dataclass(frozen=True, slots=True)
class CategoryRow:
    id: UUID
    code: str | None
    name: str
    default_account: str
    source_ref: str | None
    is_system: bool
    archived_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class ExpenseRow:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    category_id: UUID
    category_name: str
    category_account: str
    posted_account: str | None  # Dt account of the posted ledger line (None for a draft)
    amount: Decimal
    source: str
    tax_type: str | None
    cash_register_id: UUID | None
    shift_id: UUID | None
    attachment_id: UUID | None
    recurring_rule_id: UUID | None
    comment: str | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    device_id: UUID | None
    approval_request_id: UUID | None
    approval_status: str | None
    approval_requested_value: Decimal | None


@dataclass(frozen=True, slots=True)
class ExpenseFilter:
    branch_ids: tuple[UUID, ...] | None  # None = every branch
    category_id: UUID | None
    source: str | None
    status: str | None
    date_from: date | None
    date_to: date | None
    cursor: tuple[date, UUID] | None
    limit: int


@dataclass(frozen=True, slots=True)
class ShiftRef:
    id: UUID
    branch_id: UUID
    cash_register_id: UUID
    status: str


@dataclass(frozen=True, slots=True)
class RuleRow:
    id: UUID
    branch_id: UUID
    category_id: UUID
    name: str | None
    amount: Decimal
    period: str
    day_of_month: int
    source: str
    cash_register_id: UUID | None
    next_due_date: date
    last_triggered_at: datetime | None
    is_active: bool
    created_by: UUID
    version: int


class ExpenseStore(Protocol):
    # --- grants / approvals ---------------------------------------------------------------------
    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant: ...

    async def insert_approval_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def approval_requester(self, s: AsyncSession, request_id: UUID) -> UUID | None: ...

    # --- categories -----------------------------------------------------------------------------
    async def list_categories(self, s: AsyncSession, *, include_archived: bool) -> list[CategoryRow]: ...

    async def get_category(
        self, s: AsyncSession, category_id: UUID, *, lock: bool = False
    ) -> CategoryRow | None: ...

    async def category_name_taken(self, s: AsyncSession, name: str, exclude: UUID | None) -> bool: ...

    async def insert_category(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def update_category(
        self, s: AsyncSession, category_id: UUID, version: int, changes: Mapping[str, Any]
    ) -> bool: ...

    # --- references -----------------------------------------------------------------------------
    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool: ...

    async def register_branch(self, s: AsyncSession, register_id: UUID) -> UUID | None: ...

    async def get_shift(self, s: AsyncSession, shift_id: UUID) -> ShiftRef | None: ...

    async def open_shift_of_register(self, s: AsyncSession, register_id: UUID) -> ShiftRef | None: ...

    async def attachment_kind(self, s: AsyncSession, attachment_id: UUID) -> str | None: ...

    async def last_closed_period(self, s: AsyncSession) -> date | None: ...

    # --- expenses -------------------------------------------------------------------------------
    async def insert_expense(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def get_expense(
        self, s: AsyncSession, expense_id: UUID, *, lock: bool = False
    ) -> ExpenseRow | None: ...

    async def list_expenses(self, s: AsyncSession, flt: ExpenseFilter) -> list[ExpenseRow]: ...

    async def totals(self, s: AsyncSession, flt: ExpenseFilter) -> dict[str, Decimal]: ...

    async def mark_posted(self, s: AsyncSession, expense_id: UUID, number: str) -> datetime: ...

    async def mark_cancelled(
        self, s: AsyncSession, expense_id: UUID, user_id: UUID, reason: str
    ) -> datetime: ...

    async def insert_cash_move(self, s: AsyncSession, row: Mapping[str, Any]) -> UUID: ...

    async def live_cash_moves(
        self, s: AsyncSession, doc_id: UUID
    ) -> list[tuple[UUID, Decimal, UUID | None, UUID | None, str]]: ...

    # --- recurring rules ------------------------------------------------------------------------
    async def list_rules(
        self,
        s: AsyncSession,
        branch_ids: Sequence[UUID] | None,
        is_active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[RuleRow], int]: ...

    async def get_rule(self, s: AsyncSession, rule_id: UUID, *, lock: bool = False) -> RuleRow | None: ...

    async def insert_rule(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def update_rule(
        self, s: AsyncSession, rule_id: UUID, version: int, changes: Mapping[str, Any]
    ) -> bool: ...

    async def due_rules(self, s: AsyncSession, today: date) -> list[RuleRow]: ...

    async def mark_rule_triggered(self, s: AsyncSession, rule_id: UUID) -> None: ...
