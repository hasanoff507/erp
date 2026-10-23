"""Persistence port of the cloud print slice (12 ``cloud_printers``, ``print_jobs``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class PrinterRow:
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    name: str
    protocol: str
    model: str | None
    status: str
    printer_mac: str | None
    last_poll_at: datetime | None
    last_status: str | None
    version: int
    online: bool  # last_poll_at within ONLINE_WITHIN_S (computed by the database clock)


@dataclass(frozen=True, slots=True)
class JobRow:
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    cloud_printer_id: UUID
    kind: str
    width_dots: int
    height_dots: int
    data: bytes | None
    data_sha256: str
    status: str
    result_code: str | None
    attempts: int


@dataclass(frozen=True, slots=True)
class PrinterFilter:
    branch_ids: Sequence[UUID]  # empty = all
    branch_id: UUID | None
    status: str | None


@dataclass(frozen=True, slots=True)
class PrinterAuth:
    """Who is polling — resolved by ``app.cloud_printer_by_secret`` (12 §4.5)."""

    printer_id: UUID
    tenant_id: UUID
    branch_id: UUID
    protocol: str


class CloudPrintRepository(Protocol):
    async def printer_by_secret(
        self, s: AsyncSession, printer_id: UUID, secret_hash: str
    ) -> PrinterAuth | None: ...
    async def printer(
        self, s: AsyncSession, printer_id: UUID, *, lock: bool = False
    ) -> PrinterRow | None: ...
    async def list_printers(
        self, s: AsyncSession, flt: PrinterFilter, page: int, size: int
    ) -> tuple[list[PrinterRow], int]: ...
    async def insert_printer(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...
    async def update_printer(self, s: AsyncSession, printer_id: UUID, values: Mapping[str, Any]) -> None: ...
    async def touch_poll(
        self, s: AsyncSession, printer_id: UUID, *, mac: str | None, status: str | None
    ) -> None: ...
    async def queued_count(self, s: AsyncSession, printer_id: UUID) -> int: ...
    # jobs
    async def job(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> JobRow | None: ...
    async def insert_job(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...
    async def expire_jobs(self, s: AsyncSession, printer_id: UUID) -> int: ...
    async def next_queued(self, s: AsyncSession, printer_id: UUID, limit: int) -> list[JobRow]: ...
    async def printing_jobs(self, s: AsyncSession, printer_id: UUID) -> list[JobRow]: ...
    async def mark_printing(self, s: AsyncSession, job_id: UUID) -> None: ...
    async def finish_job(self, s: AsyncSession, job_id: UUID, *, status: str, code: str | None) -> None: ...
    async def requeue(self, s: AsyncSession, job_id: UUID, code: str | None) -> None: ...
