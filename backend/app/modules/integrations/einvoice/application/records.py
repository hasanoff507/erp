"""Rows and repository ports of the e-documents application layer (implemented in ``infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EInvoice:
    id: UUID
    direction: str
    operator: str
    operator_doc_id: str | None
    counterparty_id: UUID
    counterparty_name: str | None
    counterparty_stir: str | None
    counterparty_kind: str | None
    related_doc_type: str | None
    related_doc_id: UUID | None
    status: str
    number: str | None
    doc_date: date | None
    total_amount: Decimal | None
    vat_amount: Decimal | None
    signed_by: UUID | None
    risk_flag: str
    factura_type: str
    related_einvoice_id: UUID | None
    signed_at: datetime | None
    payload: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None  # the newest outbox job error (send/accept)
    job_status: str | None = None


@dataclass(frozen=True, slots=True)
class EttnDoc:
    id: UUID
    direction: str
    transport_type: str
    status: str
    operator_doc_id: str | None
    transfer_id: UUID | None
    einvoice_id: UUID | None
    counterparty_id: UUID | None
    receipt_id: UUID | None
    doc_date: date | None
    signed_at: datetime | None
    last_error: str | None
    payload: Mapping[str, Any]
    created_at: datetime
    transfer_from_branch_id: UUID | None = None
    transfer_to_branch_id: UUID | None = None
    transfer_status: str | None = None


@dataclass(frozen=True, slots=True)
class PowerOfAttorney:
    id: UUID
    branch_id: UUID
    purchase_order_id: UUID | None
    supplier_id: UUID
    supplier_name: str | None
    supplier_stir: str | None
    employee_user_id: UUID
    employee_name: str | None
    doc_date: date
    valid_from: date
    valid_to: date
    number: str | None
    operator_doc_id: str | None
    status: str
    last_error: str | None
    signed_at: datetime | None
    sent_at: datetime | None
    responded_at: datetime | None
    reject_reason: str | None
    created_by: UUID
    created_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class StoredSignature:
    signature_pkcs7: str
    certificate_serial: str | None
    document_hash: str


@dataclass(frozen=True, slots=True)
class SaleForInvoice:
    """A posted sale with its lines net of posted returns (``from-receipt`` / B2B auto-draft)."""

    id: UUID
    branch_id: UUID
    status: str
    number: str | None
    doc_date: date
    counterparty_id: UUID | None
    has_debt_payment: bool
    lines: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    # line: product_id, name, mxik, unit_code, qty, line_total, vat_rate, vat_amount, marking_code


@dataclass(frozen=True, slots=True)
class CounterpartyRef:
    id: UUID
    kind: str
    name: str
    stir: str | None
    archived: bool


@dataclass(frozen=True, slots=True)
class Page:
    after: tuple[datetime, UUID] | None
    limit: int


class EDocsRepository(Protocol):
    # einvoices
    async def einvoice(
        self, s: AsyncSession, einvoice_id: UUID, *, lock: bool = False
    ) -> EInvoice | None: ...
    async def einvoices(self, s: AsyncSession, filters: Mapping[str, Any], page: Page) -> list[EInvoice]: ...
    async def insert_einvoice(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def insert_out_once(self, s: AsyncSession, row: Mapping[str, Any]) -> UUID | None: ...
    async def active_out_for(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> UUID | None: ...
    async def update_einvoice(
        self, s: AsyncSession, einvoice_id: UUID, values: Mapping[str, Any]
    ) -> None: ...
    async def upsert_incoming(self, s: AsyncSession, row: Mapping[str, Any]) -> tuple[UUID, bool]: ...
    async def einvoice_by_operator_doc(self, s: AsyncSession, operator_doc_id: str) -> UUID | None: ...
    async def last_incoming_update(self, s: AsyncSession) -> datetime | None: ...
    async def sent_out_operator_ids(self, s: AsyncSession, limit: int) -> list[tuple[UUID, str]]: ...
    # counterparties / sales
    async def counterparty(self, s: AsyncSession, counterparty_id: UUID) -> CounterpartyRef | None: ...
    async def supplier_by_stir(self, s: AsyncSession, stir: str) -> UUID | None: ...
    async def insert_supplier(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def sale(self, s: AsyncSession, sale_id: UUID) -> SaleForInvoice | None: ...
    async def tenant_stir(self, s: AsyncSession) -> tuple[str | None, str | None]: ...
    # e-TTN
    async def ettn(self, s: AsyncSession, ettn_id: UUID, *, lock: bool = False) -> EttnDoc | None: ...
    async def ettns(self, s: AsyncSession, filters: Mapping[str, Any], page: Page) -> list[EttnDoc]: ...
    async def update_ettn(self, s: AsyncSession, ettn_id: UUID, values: Mapping[str, Any]) -> None: ...
    async def insert_ettn(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def ettns_of_einvoice(self, s: AsyncSession, einvoice_id: UUID) -> list[UUID]: ...
    async def lock_transfer(self, s: AsyncSession, transfer_id: UUID) -> None: ...
    async def set_transfer_ettn_ref(self, s: AsyncSession, transfer_id: UUID, ref: str) -> None: ...
    # powers of attorney
    async def poa(self, s: AsyncSession, poa_id: UUID, *, lock: bool = False) -> PowerOfAttorney | None: ...
    async def poas(
        self, s: AsyncSession, filters: Mapping[str, Any], page: Page
    ) -> list[PowerOfAttorney]: ...
    async def insert_poa(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def update_poa(self, s: AsyncSession, poa_id: UUID, values: Mapping[str, Any]) -> None: ...
    async def sent_poas(self, s: AsyncSession, limit: int) -> list[tuple[UUID, str]]: ...
    async def purchase_order_supplier(self, s: AsyncSession, po_id: UUID) -> tuple[UUID, UUID] | None: ...
    async def tenant_user_exists(self, s: AsyncSession, user_id: UUID) -> bool: ...
    # signatures + outbox
    async def insert_signature(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def latest_signature(
        self, s: AsyncSession, entity: str, entity_id: UUID, action: str
    ) -> StoredSignature | None: ...
    async def queue_job(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        kind: str,
        payload: Mapping[str, Any],
        key: str,
        created_by: UUID | None,
    ) -> UUID: ...
    async def alerts(self, s: AsyncSession) -> dict[str, int]: ...


__all__ = [
    "CounterpartyRef",
    "EDocsRepository",
    "EInvoice",
    "EttnDoc",
    "Page",
    "PowerOfAttorney",
    "SaleForInvoice",
    "StoredSignature",
]
