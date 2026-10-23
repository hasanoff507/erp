"""Ports of the fiscal package (21 §1 ``FiscalPort``) and its repository.

Port boundary: money in **tiyin** (``int``) — the receipt payload keeps decimal strings and the adapter
converts with :func:`app.core.money.to_tiyin` (01 #26).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.fiscal.domain.boundary import ResendResult

ErrorKind = Literal["transient", "auth", "validation"]


class FiscalProviderError(Exception):
    """A provider call failed: ``transient`` → retry with backoff; ``auth``/``validation`` → ``failed``."""

    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind


@dataclass(frozen=True, slots=True)
class CashRegisterRef:
    id: UUID
    tenant_id: UUID
    fiscal_module_id: str | None = None


@dataclass(frozen=True, slots=True)
class FiscalResult:
    """``FiscalResult{terminal_id, fm_receipt_seq, fiscal_at, fiscal_sign, qr_url}`` (21 §1); ``ofd_acked_at``
    — the OFD acknowledgement when the provider already has it (the fake acks at once)."""

    terminal_id: str
    fm_receipt_seq: int
    fiscal_at: datetime
    fiscal_sign: str
    qr_url: str
    ofd_acked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RefundInfo:
    """The original receipt's FM requisites (21 §1)."""

    terminal_id: str | None
    receipt_seq: int | None
    datetime: datetime | None
    fiscal_sign: str | None


@dataclass(frozen=True, slots=True)
class FiscalReceiptPayload:
    id: UUID  # fiscal_receipts.id — the provider idempotency key
    kind: str
    register: CashRegisterRef
    receipt_seq: int | None
    body: Mapping[str, Any]  # fiscal_receipts.payload (items, totals, payments — decimal strings)


@dataclass(frozen=True, slots=True)
class FiscalDeviceStatus:
    fm_state: str  # ok | locked | ack_overdue | memory_full | unknown
    pending: int = 0
    oldest_unacked_at: datetime | None = None
    acked: Sequence[tuple[str, int]] = field(default_factory=tuple)  # (terminal_id, fm_receipt_seq)


@dataclass(frozen=True, slots=True)
class FiscalShiftResult:
    """``FiscalShiftResult {fm_terminal_id, opened_at}`` (21 §16.1)."""

    terminal_id: str
    opened_at: datetime


@dataclass(frozen=True, slots=True)
class UnsentReceipt:
    """``UnsentReceipt {fm_receipt_seq, fiscal_at, amount_tiyin}`` (21 §16.1)."""

    fm_receipt_seq: int
    fiscal_at: datetime
    amount_tiyin: int


class FiscalPort(Protocol):
    """21 §1. ``close_shift`` takes the server's ``z_report`` receipt row (its id is the provider idempotency
    key) and answers with the FM requisites of the Z-report (``fm_receipt_seq`` = Z number); the local
    bridge's ``ZReport`` comes back through the ``fiscal.zreport`` agent task instead."""

    async def open_shift(self, register: CashRegisterRef) -> FiscalShiftResult: ...

    async def register_sale(self, receipt: FiscalReceiptPayload) -> FiscalResult: ...

    async def register_refund(
        self, receipt: FiscalReceiptPayload, refund_ref: RefundInfo
    ) -> FiscalResult: ...

    async def close_shift(self, receipt: FiscalReceiptPayload) -> FiscalResult: ...

    async def get_device_status(self, register: CashRegisterRef) -> FiscalDeviceStatus: ...

    async def list_unsent(self, register: CashRegisterRef) -> list[UnsentReceipt]: ...

    async def resend_unsent(self, register: CashRegisterRef) -> ResendResult: ...


class AgentTaskPort(Protocol):
    """The store-agent task queue (b5-agent ``onec_integration.application.ports.AgentTaskPort``, 23 §4.2):
    ``capabilities.<family>.enabled`` is checked → ``409 AGENT_CAPABILITY_DISABLED``;
    ``purpose='device_service'``,
    ``base_id=None``. Runs in the caller's tenant transaction."""

    async def enqueue(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        kind: str,
        payload: dict[str, Any],
        *,
        priority: int = 100,
        not_before: datetime | None = None,
        dedupe_key: str | None = None,
        created_by: UUID | None = None,
        expires_in_s: int | None = 86400,
        timeout_s: int | None = None,
    ) -> UUID: ...


# --- repository -------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ReceiptRow:
    id: UUID
    kind: str
    sale_id: UUID | None
    return_id: UUID | None
    debt_payment_id: UUID | None
    cash_register_id: UUID | None
    shift_id: UUID | None
    receipt_seq: int | None
    fm_terminal_id: str | None
    fm_receipt_seq: int | None
    fiscal_at: datetime | None
    payload: Mapping[str, Any]
    fiscal_sign: str | None
    qr_url: str | None
    payment_form: str | None
    delivery: str
    delivery_reason: str | None
    sent_at: datetime | None
    ofd_acked_at: datetime | None
    offline_since: datetime | None
    status: str
    attempts: int
    created_at: datetime
    branch_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    payload: Mapping[str, Any]
    attempts: int


@dataclass(frozen=True, slots=True)
class RegisterState:
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    fm_state: str
    fiscal_module_id: str | None
    last_unacked_receipt_at: datetime | None


@dataclass(frozen=True, slots=True)
class RegisterBinding:
    """A register's local-bridge binding (``cash_registers.fiscal_agent_id`` / ``fiscal_local_device_id``)."""

    id: UUID
    branch_id: UUID
    name: str
    agent_id: UUID | None
    local_id: str | None
    fm_state: str
    fm_receipts_pending: int | None
    archived: bool = False


@dataclass(frozen=True, slots=True)
class ReceiptFilter:
    branch_ids: tuple[UUID, ...] | None = None
    sale_id: UUID | None = None
    return_id: UUID | None = None
    debt_payment_id: UUID | None = None
    shift_id: UUID | None = None
    kind: str | None = None
    status: str | None = None


class FiscalRepository(Protocol):
    async def register(
        self, s: AsyncSession, register_id: UUID, *, lock: bool = False
    ) -> RegisterState | None: ...

    async def set_fm_state(self, s: AsyncSession, register_id: UUID, fm_state: str) -> None: ...

    async def set_last_unacked(self, s: AsyncSession, register_id: UUID, at: datetime | None) -> None: ...

    async def oldest_unacked(self, s: AsyncSession, register_id: UUID) -> tuple[UUID, datetime] | None: ...

    async def unacked_registers(self, s: AsyncSession) -> list[tuple[UUID, UUID, datetime]]:
        """``(register_id, oldest receipt id, its created_at)`` of every register with an unacked receipt."""
        ...

    async def blocked_registers(self, s: AsyncSession) -> list[tuple[UUID, datetime]]:
        """Registers whose ``last_unacked_receipt_at`` is set: ``(register_id, value)``."""
        ...

    async def seq_taken(
        self, s: AsyncSession, register_id: UUID, shift_id: UUID, receipt_seq: int
    ) -> bool: ...

    async def max_seq(self, s: AsyncSession, register_id: UUID, shift_id: UUID) -> int: ...

    async def z_exists(self, s: AsyncSession, shift_id: UUID) -> bool: ...

    async def insert_receipt(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def insert_job(self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID) -> UUID: ...

    async def job_of(self, s: AsyncSession, receipt_id: UUID) -> UUID | None: ...

    async def get(self, s: AsyncSession, receipt_id: UUID, *, lock: bool = False) -> ReceiptRow | None: ...

    async def page(
        self, s: AsyncSession, flt: ReceiptFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[ReceiptRow]: ...

    async def claim(self, s: AsyncSession, job_id: UUID | None) -> ClaimedJob | None: ...

    async def finish_job(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        run_after: timedelta | None = None,
    ) -> None:
        """``run_after`` → ``next_run_at = now() + run_after`` (database clock, the claim's clock); ``None``
        keeps it."""
        ...

    async def requeue(self, s: AsyncSession, receipt_id: UUID) -> UUID | None:
        """``failed`` job of the receipt → ``queued`` (now); returns the job id."""
        ...

    async def set_fiscalized(self, s: AsyncSession, receipt_id: UUID, result: FiscalResult) -> None: ...

    async def set_status(
        self, s: AsyncSession, receipt_id: UUID, status: str, *, attempt: bool = False
    ) -> None: ...

    async def ack(self, s: AsyncSession, receipt_id: UUID, at: datetime) -> None: ...

    async def ack_fm(
        self, s: AsyncSession, fm_terminal_id: str, fm_receipt_seq: int, at: datetime
    ) -> UUID | None: ...

    async def mark_codes_sold(self, s: AsyncSession, doc_id: UUID) -> None: ...

    async def original_sale_receipt(self, s: AsyncSession, return_id: UUID) -> ReceiptRow | None: ...

    async def binding(self, s: AsyncSession, register_id: UUID) -> RegisterBinding | None: ...

    async def bound_registers(self, s: AsyncSession) -> list[RegisterBinding]: ...

    async def set_fm_status(
        self, s: AsyncSession, register_id: UUID, fm_state: str, pending: int | None
    ) -> None: ...

    async def z_of_shift(self, s: AsyncSession, shift_id: UUID) -> ReceiptRow | None: ...

    async def set_z_fiscalized(
        self,
        s: AsyncSession,
        receipt_id: UUID,
        terminal_id: str,
        fiscal_at: datetime,
        fm_z: Mapping[str, Any],
    ) -> None: ...

    async def unacked_by_register(self, s: AsyncSession, provider_side: bool) -> list[tuple[UUID, int]]: ...

    async def readiness(
        self, s: AsyncSession, date_from: date, date_to: date
    ) -> tuple[int, int, datetime | None]: ...

    async def alert_counts(
        self, s: AsyncSession, at: datetime, branch_ids: tuple[UUID, ...] | None
    ) -> tuple[int, int, int, int]: ...

    async def registers_overview(
        self, s: AsyncSession, branch_ids: tuple[UUID, ...] | None
    ) -> list[dict[str, Any]]: ...
