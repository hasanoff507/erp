"""``MarkingPort`` — the CRPT Turon (Asl belgisi, xTrace Open API) boundary (21 §4, qaror #62).

The CRPT API is used ONLY for: the optional pre-sale code check (``verify_code``), the ownership notices of
a goods receipt (``accept``), a return to the supplier (``supplier_return``) and a write-off
(``write_off``). Retail sales and customer returns never call CRPT — the code travels inside the fiscal
receipt through the OFD (``items[].marking_codes``, VM 833 75–77, 90-band).

Rules shared by every adapter:

* the port is tenant-scoped (each tenant's own ``crpt_api_key`` from ``tenant_secrets``) — obtain it with
  :class:`MarkingPortProvider` (``None`` = the tenant has no CRPT key: treated as "CRPT did not answer");
* never called inside a business transaction: ``verify_code`` is synchronous (``timeout=3s``, no retry,
  18 §15) between two transactions; the notices go through ``outbox_jobs`` (21 §0) and the worker;
* a failure the caller cannot fix → :class:`MarkingProviderError` with the 21 §0 class (``transient`` →
  retry, ``auth``/``validation`` → ``failed``); a notice CRPT already has is a success (idempotent by
  ``doc_id``), never an error;
* codes are passed exactly as scanned (GS separators kept).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

ErrorKind = Literal["transient", "auth", "validation"]
CodeStatus = Literal["in_stock", "sold", "written_off", "returned_to_supplier", "unknown"]
NoticeStatus = Literal["accepted", "rejected"]


class MarkingProviderError(Exception):
    def __init__(self, message: str, *, kind: ErrorKind = "transient") -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind


@dataclass(frozen=True, slots=True)
class MarkingVerifyResult:
    """``valid`` — the code may be sold by this tenant; ``reason`` (when not valid) is one of
    ``already_sold`` / ``expired`` / ``not_found`` / ``written_off`` / ``returned_to_supplier`` /
    ``not_owner`` (18 §15)."""

    valid: bool
    status: CodeStatus = "unknown"
    reason: str | None = None
    gtin: str | None = None


@dataclass(frozen=True, slots=True)
class MarkingAcceptResult:
    """Ownership acceptance of a goods receipt's codes (M07)."""

    status: NoticeStatus
    crpt_doc_id: str | None = None
    rejected_codes: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MarkingResult:
    """A supplier-return / write-off notice."""

    status: NoticeStatus
    crpt_doc_id: str | None = None
    rejected_codes: tuple[str, ...] = ()
    error: str | None = None


class MarkingPort(Protocol):
    async def verify_code(self, code: str) -> MarkingVerifyResult: ...

    async def accept(self, codes: Sequence[str], receipt_id: UUID) -> MarkingAcceptResult: ...

    async def supplier_return(self, codes: Sequence[str], return_id: UUID) -> MarkingResult: ...

    async def write_off(self, codes: Sequence[str], write_off_id: UUID) -> MarkingResult: ...


class MarkingPortProvider(Protocol):
    """The tenant's adapter (reads ``tenant_secrets(kind='crpt')`` in the caller's transaction)."""

    async def for_tenant(self, s: AsyncSession, tenant_id: UUID) -> MarkingPort | None: ...


@dataclass(frozen=True, slots=True)
class NoticeJob:
    """A claimed ``outbox_jobs`` row of one of the four marking kinds."""

    id: UUID
    kind: str
    attempts: int
    payload: dict[str, object] = field(default_factory=dict)
