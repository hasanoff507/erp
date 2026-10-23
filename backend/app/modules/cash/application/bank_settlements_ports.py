"""Ports of the bank settlements slice (implemented in ``cash.infrastructure.bank_settlements_sql``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash.domain.bank_matching import Batch


@dataclass(frozen=True, slots=True)
class SettlementRow:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    source: str
    method: str
    settled_from: date
    settled_to: date
    gross_amount: Decimal
    commission_amount: Decimal
    variance_amount: Decimal
    net_amount: Decimal
    bank_ref: str | None
    attachment_id: UUID | None
    statement_import_id: UUID | None
    comment: str | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: UUID | None
    cancel_reason: str | None
    version: int


@dataclass(frozen=True, slots=True)
class SettlementFilter:
    branch_ids: tuple[UUID, ...] | None
    method: str | None
    status: str | None
    source: str | None
    date_from: date | None
    date_to: date | None
    cursor: tuple[date, UUID] | None
    limit: int


@dataclass(frozen=True, slots=True)
class CardTx:
    """An approved integrated card purchase (``rrn`` from the terminal result)."""

    id: UUID
    branch_id: UUID
    rrn: str
    amount: Decimal
    business_date: date


class BankSettlementRepository(Protocol):
    async def open_terminal_batches(
        self, s: AsyncSession, branch_id: UUID, identifiers: Sequence[str], up_to: date
    ) -> list[Batch]:
        """Batches of the terminals with these TID/MID, ``business_date ≤ up_to``, not ``failed``, without a
        bank settlement and outside every open draft's ``settled_from … settled_to`` (13 §2.18a)."""
        ...

    async def link_batches(self, s: AsyncSession, batch_ids: Sequence[UUID], settlement_id: UUID) -> None: ...

    # tenant / references
    async def tenant_bank(self, s: AsyncSession) -> tuple[str | None, str | None]:
        """``(settings.bank_account, settings.payment_org_commission_account)``."""
        ...

    async def branch_ids(self, s: AsyncSession) -> list[UUID]: ...

    async def attachment_exists(self, s: AsyncSession, attachment_id: UUID) -> bool: ...

    async def terminal_identifiers(self, s: AsyncSession) -> dict[str, UUID]:
        """``tid``/``mid`` of the tenant's card terminals → branch."""
        ...

    async def acquirer_inns(self, s: AsyncSession) -> list[str]: ...

    async def lock_imports(self, s: AsyncSession, tenant_id: UUID) -> None:
        """SYNC-04 (23 §2.1): one statement import of a tenant at a time (transaction advisory lock)."""
        ...

    async def lock_transit(self, s: AsyncSession, branch_id: UUID, method: str) -> None:
        """Serialise settlements of one (branch, method) — transaction-scoped advisory lock."""
        ...

    # documents
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def get(
        self, s: AsyncSession, settlement_id: UUID, *, lock: bool = False
    ) -> SettlementRow | None: ...

    async def update_draft(self, s: AsyncSession, settlement_id: UUID, values: Mapping[str, Any]) -> None: ...

    async def mark_posted(self, s: AsyncSession, settlement_id: UUID) -> None: ...

    async def mark_cancelled(
        self, s: AsyncSession, settlement_id: UUID, user_id: UUID, reason: str
    ) -> None: ...

    async def list_settlements(self, s: AsyncSession, flt: SettlementFilter) -> list[SettlementRow]: ...

    async def ledger_rows(self, s: AsyncSession, settlement_id: UUID) -> list[dict[str, Any]]: ...

    async def is_duplicate(self, s: AsyncSession, bank_ref: str, doc_date: date, net: Decimal) -> bool: ...

    # transit (5710) — ledger_entries by branch × analytics.payment_method
    async def transit_balance(
        self, s: AsyncSession, branch_id: UUID, method: str, as_of: date | None
    ) -> Decimal: ...

    async def transit_balances(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> list[tuple[UUID, str, Decimal]]: ...

    async def daily_inflows(
        self, s: AsyncSession, branch_id: UUID, method: str, as_of: date
    ) -> list[tuple[date, Decimal]]:
        """Net 5710 movement per day of everything except bank settlements (sales − refunds …)."""
        ...

    async def holds(self, s: AsyncSession, branch_id: UUID, method: str) -> list[tuple[date, date, Decimal]]:
        """``(settled_from, settled_to, gross_amount)`` of the posted and draft settlements."""
        ...

    async def integrated_card(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> dict[UUID, Decimal]:
        """Per branch: integrated card inflow (5710 card rows with ``rrn``) minus RRN-linked settled."""
        ...

    # card terminal links (21 §9.2 / §9.4)
    async def card_txs_by_rrn(self, s: AsyncSession, rrns: Sequence[str]) -> list[CardTx]: ...

    async def open_card_txs(
        self, s: AsyncSession, branch_id: UUID, date_from: date, date_to: date
    ) -> list[CardTx]: ...

    async def link_card_txs(self, s: AsyncSession, tx_ids: Sequence[UUID], settlement_id: UUID) -> None: ...

    async def link_terminal_batches(self, s: AsyncSession, row: SettlementRow) -> int: ...

    async def unlink(self, s: AsyncSession, settlement_id: UUID) -> None: ...

    # statement imports
    async def import_by_sha(self, s: AsyncSession, sha256: str) -> UUID | None: ...

    async def insert_attachment(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def insert_import(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def finish_import(self, s: AsyncSession, import_id: UUID, values: Mapping[str, Any]) -> None: ...


class FileStore(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...
