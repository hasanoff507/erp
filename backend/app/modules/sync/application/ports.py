"""Ports of the sync module (implemented in ``sync.infrastructure``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.principal import Principal
from app.modules.sync.domain.cursor import Position


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    id: UUID
    kind: str
    revoked_at: datetime | None
    cash_register_id: UUID | None
    branch_id: UUID | None


@dataclass(frozen=True, slots=True)
class ActorInfo:
    status: str
    branch_ids: tuple[UUID, ...]
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class StoredReceipt:
    id: UUID
    device_id: UUID
    result: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ExceptionRow:
    id: UUID
    kind: str
    device_id: UUID | None
    branch_id: UUID | None
    client_event_id: UUID | None
    doc_type: str | None
    doc_id: UUID | None
    details: Mapping[str, Any]
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: UUID | None
    review_note: str | None


@dataclass(frozen=True, slots=True)
class ExceptionFilter:
    reviewed: bool | None = None
    branch_id: UUID | None = None
    device_id: UUID | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


class SyncStore(Protocol):
    """``devices`` (sync columns), ``sync_receipts``, ``sync_exceptions``, actor lookups (caller's txn)."""

    async def device(self, s: AsyncSession, device_id: UUID) -> DeviceInfo | None: ...
    async def touch_seen(self, s: AsyncSession, device_id: UUID) -> None: ...
    async def db_now(self, s: AsyncSession) -> datetime: ...
    async def settle_cutoff(self, s: AsyncSession, settle_s: float) -> tuple[datetime, datetime]: ...
    async def report_outbox(
        self, s: AsyncSession, device_id: UUID, pending_count: int, oldest_pending_at: datetime | None
    ) -> None: ...
    async def lock_event(self, s: AsyncSession, tenant_id: UUID, client_event_id: UUID) -> None: ...
    async def receipt(self, s: AsyncSession, client_event_id: UUID) -> StoredReceipt | None: ...
    async def insert_receipt(
        self,
        s: AsyncSession,
        *,
        receipt_id: UUID,
        tenant_id: UUID,
        device_id: UUID,
        client_event_id: UUID,
        result: Mapping[str, Any],
    ) -> None: ...
    async def insert_exception(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def actor(self, s: AsyncSession, user_id: UUID) -> ActorInfo | None: ...
    async def actor_limits(self, s: AsyncSession, user_id: UUID, code: str) -> list[Decimal | None]: ...
    async def grace_ends_at(self, s: AsyncSession) -> datetime | None: ...
    async def audit_exists(self, s: AsyncSession, action: str, device_id: UUID, since: datetime) -> bool: ...


class ExceptionStore(Protocol):
    async def page(
        self,
        s: AsyncSession,
        flt: ExceptionFilter,
        *,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[ExceptionRow]: ...
    async def get(
        self, s: AsyncSession, exception_id: UUID, *, lock: bool = False
    ) -> ExceptionRow | None: ...
    async def mark_reviewed(
        self, s: AsyncSession, exception_id: UUID, user_id: UUID, note: str
    ) -> datetime: ...


@dataclass(frozen=True, slots=True)
class PullContext:
    tenant_id: UUID
    device_id: UUID
    branch_id: UUID
    cash_register_id: UUID | None
    settle_before: datetime  # rows newer than this are not settled yet (late-committing transactions)
    now: datetime


@dataclass(frozen=True, slots=True)
class StreamRow:
    data: dict[str, Any]
    position: Position


class PullReader(Protocol):
    """Read-only SQL over the owning modules' tables (catalog, pricing, debts, inventory, fiscal …)."""

    async def stream(
        self, s: AsyncSession, stream: str, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]: ...
    async def staff(self, s: AsyncSession, ctx: PullContext) -> list[dict[str, Any]]: ...
    async def shift(self, s: AsyncSession, ctx: PullContext) -> dict[str, Any]: ...
    async def settings(self, s: AsyncSession, ctx: PullContext) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class StaffPin:
    user_id: UUID
    pin_local_hash: str | None
    must_change_pin: bool
    active: bool


class StaffPinSource(Protocol):
    """b3-device's ``auth.wiring.staff_pin_snapshot()`` adapted to this module (contract 6)."""

    async def for_branch(self, s: AsyncSession, tenant_id: UUID, branch_id: UUID) -> list[StaffPin]: ...


class PushGate(Protocol):
    """Backpressure (16 §3.1): per-device rate, per-device single flight, per-tenant concurrency."""

    async def enter(self, tenant_id: UUID, device_id: UUID) -> str: ...
    async def leave(self, tenant_id: UUID, device_id: UUID, token: str) -> None: ...


class ActorVerifier(Protocol):
    """SEC-02: is ``user_id`` PIN-bound to the pushing device session (``auth`` ``ActorBindings``)?
    Never raises — an unavailable binding store answers ``False`` (cannot be proven)."""

    async def bound(self, principal: Principal, user_id: UUID) -> bool: ...
