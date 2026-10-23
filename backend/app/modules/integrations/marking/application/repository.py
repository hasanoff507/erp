"""Repository port of the marking integration (SQL: ``infrastructure/marking_sql.py``, caller's txn)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.marking.application.ports import NoticeJob


@dataclass(frozen=True, slots=True)
class CodeRow:
    code: str
    product_id: UUID
    status: str
    last_doc_id: UUID | None


@dataclass(frozen=True, slots=True)
class ReceiptCode:
    code: str
    product_id: UUID
    deadline_kind: str | None


@dataclass(frozen=True, slots=True)
class JobRow:
    id: UUID
    kind: str
    status: str
    attempts: int
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ProductRef:
    id: UUID
    is_marked: bool
    name: str


class MarkingRepository(Protocol):
    # --- reads -------------------------------------------------------------------------------------
    async def precheck_mode(self, s: AsyncSession) -> str | None: ...

    async def code_taken(self, s: AsyncSession, code: str) -> bool:
        """``marking_codes.status IN ('sold','pending_verification')`` in the tenant (18 §15 local check)."""
        ...

    async def product(self, s: AsyncSession, product_id: UUID) -> ProductRef | None: ...

    async def receipt_codes(self, s: AsyncSession, receipt_id: UUID) -> list[ReceiptCode]: ...

    async def codes(
        self, s: AsyncSession, codes: Sequence[str], *, lock: bool = False
    ) -> dict[str, CodeRow]: ...

    async def doc_codes(self, s: AsyncSession, doc_id: UUID, status: str) -> list[str]: ...

    async def sale_acked(self, s: AsyncSession, sale_id: UUID) -> bool: ...

    async def receipt_info(self, s: AsyncSession, receipt_id: UUID) -> Mapping[str, Any] | None:
        """``{number, branch_id, supplier_name}`` of a goods receipt (M18 payload)."""
        ...

    # --- outbox ------------------------------------------------------------------------------------
    async def insert_job(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], key: str
    ) -> UUID:
        """``ON CONFLICT (tenant_id, idempotency_key) DO NOTHING`` — returns the new or the existing id."""
        ...

    async def job_by_key(self, s: AsyncSession, key: str, *, lock: bool = False) -> JobRow | None: ...

    async def open_jobs(self, s: AsyncSession, kind: str) -> list[JobRow]:
        """Jobs of ``kind`` not ``done`` (queued/running/retry/failed), ordered by id."""
        ...

    async def claim(self, s: AsyncSession, job_id: UUID | None, stale_s: int) -> NoticeJob | None: ...

    async def lock_job(self, s: AsyncSession, job_id: UUID) -> JobRow | None: ...

    async def finish(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        *,
        run_after: timedelta | None = None,
        patch: Mapping[str, Any] | None = None,
    ) -> None: ...

    # --- marking_codes writes ----------------------------------------------------------------------
    async def move_codes(self, s: AsyncSession, codes: Sequence[str], status: str, doc_id: UUID) -> None: ...

    async def restore_codes(self, s: AsyncSession, doc_id: UUID, from_status: str) -> int: ...

    async def mark_verified(self, s: AsyncSession, codes: Sequence[str], at: Any) -> None: ...
