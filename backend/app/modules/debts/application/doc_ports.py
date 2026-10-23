"""Ports + read models of the debt-book documents (18 §12; 12 ``debt_payments``, ``debt_payment_allocations``,
``debt_openings``, ``debt_writeoffs``, ``debt_writeoff_allocations``, ``debt_doubtful_flags``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

Row = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TargetDoc:
    """A receivable debt document of a customer: a sale on debt, a receivable opening or a posted write-off.

    ``original`` — the debt it created (sales: debt part + returns put on the account; write-offs: the
    written-off amount); ``open_amount = original − paid − written_off`` (write-offs: ``original − paid``)."""

    counterparty_id: UUID
    doc_type: str
    doc_id: UUID
    number: str | None
    doc_date: date
    due_date: date | None
    branch_id: UUID | None
    original: Decimal
    paid: Decimal
    written_off: Decimal
    open_amount: Decimal
    limit_exceeded: bool
    created_by: UUID | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class SaleLineRow:
    sale_line_id: UUID
    sale_id: UUID
    line_no: int
    product_id: UUID
    name: str
    name_ru: str | None
    mxik_code: str | None
    package_code: str | None
    unit_code: str
    barcode: str | None
    qty: Decimal
    price: Decimal
    line_total: Decimal
    vat_rate: Decimal
    vat_exemption_code: str | None
    settled_amount: Decimal
    marking_code: str | None
    returned_qty: Decimal = Decimal("0.000")  # Σ posted return_lines.qty (ACC-01)
    returned_amount: Decimal = Decimal("0.00")  # Σ posted return_lines.line_total


@dataclass(frozen=True, slots=True)
class LedgerMove:
    """``debt_moves`` of one document of one counterparty/direction, netted (storno included)."""

    doc_type: str
    doc_id: UUID
    amount: Decimal
    reversed: bool
    due_date: date | None
    first_id: UUID


@dataclass(frozen=True, slots=True)
class DocInfo:
    doc_type: str
    doc_id: UUID
    number: str | None
    doc_date: date | None
    status: str | None
    created_by: UUID | None
    created_by_name: str | None
    comment: str | None
    branch_id: UUID | None


class DebtDocsRepository(Protocol):
    # --- open documents (16 §1, 18 §12.2) -------------------------------------------------------------
    async def target_docs(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID], *, only_open: bool = True
    ) -> dict[UUID, list[TargetDoc]]: ...
    async def sale_lines(
        self, s: AsyncSession, sale_ids: Sequence[UUID], *, counterparty_id: UUID | None = None
    ) -> dict[UUID, list[SaleLineRow]]: ...
    async def receivable_balances(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID]
    ) -> dict[UUID, Decimal]: ...
    async def add_settled(self, s: AsyncSession, amounts: Mapping[UUID, Decimal]) -> None: ...
    async def touch_balance(self, s: AsyncSession, counterparty_id: UUID) -> None: ...
    async def set_due_date(self, s: AsyncSession, counterparty_id: UUID, due: date | None) -> None: ...
    async def counterparty_due_date(self, s: AsyncSession, counterparty_id: UUID) -> date | None: ...
    async def live_allocation_reason(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> str | None: ...

    # --- reference data ---------------------------------------------------------------------------
    async def go_live_date(self, s: AsyncSession) -> date | None: ...
    async def tenant_name(self, s: AsyncSession) -> str: ...
    async def default_branch(self, s: AsyncSession) -> UUID | None: ...
    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool: ...
    async def user_names(self, s: AsyncSession, user_ids: Sequence[UUID]) -> dict[UUID, str]: ...
    async def checkout(self, s: AsyncSession, checkout_ref: UUID) -> Row | None: ...
    async def consume_checkout(self, s: AsyncSession, checkout_ref: UUID) -> None: ...
    async def insert_cash_moves(self, s: AsyncSession, rows: Sequence[Row]) -> None: ...
    async def reserve_4910(self, s: AsyncSession, counterparty_id: UUID) -> Decimal: ...

    # --- documents --------------------------------------------------------------------------------
    async def insert_doc(self, s: AsyncSession, table: str, row: Row) -> None: ...
    async def get_doc(
        self, s: AsyncSession, table: str, doc_id: UUID, *, lock: bool = False
    ) -> Row | None: ...
    async def update_doc(self, s: AsyncSession, table: str, doc_id: UUID, values: Row) -> None: ...
    async def docs_page(
        self,
        s: AsyncSession,
        table: str,
        *,
        filters: Row,
        branch_ids: Sequence[UUID] | None,
        after: tuple[date, UUID] | None,
        limit: int,
    ) -> list[Row]: ...
    async def insert_allocations(self, s: AsyncSession, table: str, rows: Sequence[Row]) -> None: ...
    async def allocations_of(
        self, s: AsyncSession, table: str, doc_ids: Sequence[UUID]
    ) -> dict[UUID, list[Row]]: ...
    async def payment_receipts(self, s: AsyncSession, payment_ids: Sequence[UUID]) -> dict[UUID, Row]: ...

    # --- doubtful flags ---------------------------------------------------------------------------
    async def active_flags(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID] | None
    ) -> dict[UUID, Row]: ...
    async def insert_flag(self, s: AsyncSession, row: Row) -> None: ...
    async def get_flag(self, s: AsyncSession, flag_id: UUID, *, lock: bool = False) -> Row | None: ...
    async def unflag(self, s: AsyncSession, flag_id: UUID) -> None: ...

    # --- ledger / aging ---------------------------------------------------------------------------
    async def ledger_moves(
        self, s: AsyncSession, counterparty_id: UUID, direction: str
    ) -> list[LedgerMove]: ...
    async def doc_infos(
        self, s: AsyncSession, refs: Sequence[tuple[str, UUID]]
    ) -> dict[tuple[str, UUID], DocInfo]: ...
    async def promise_dates(self, s: AsyncSession, counterparty_id: UUID) -> dict[tuple[str, UUID], date]: ...
    async def debtors(self, s: AsyncSession, direction: str) -> list[Row]: ...
    async def payable_charges(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID]
    ) -> dict[UUID, list[Row]]: ...
    async def last_payments(self, s: AsyncSession, counterparty_ids: Sequence[UUID]) -> dict[UUID, Row]: ...
