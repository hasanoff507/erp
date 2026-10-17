"""``EInvoicePort`` — the e-invoice operator boundary (21 §2; e-TTN §3, e-ishonchnoma §6, STIR lookup 19 §9).

One port covers every operator document (EHF, e-TTN, e-ishonchnoma) and the company lookup; the MVP
operator is Faktura.uz, Didox is a second adapter of the same port (21 §2 "Operator tanlovi").

Rules shared by every adapter:

* the port is never called inside a business transaction (23 §2.1 step 5) — documents go through
  ``outbox_jobs`` (21 §0) and the worker calls the adapter; only the suggest-only STIR lookup
  (``POST /counterparties/lookup-by-stir``) calls it synchronously, outside any transaction;
* a failure the caller cannot fix is raised as :class:`EInvoiceProviderError` with the 21 §0 error
  class (``transient`` → retry with backoff, ``auth``/``validation`` → ``failed``); a document the
  operator already has is a success (``duplicate`` is idempotent, never an error).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol
from uuid import UUID

ErrorKind = Literal["transient", "auth", "validation"]
RiskFlag = Literal["green", "red", "unknown"]
EInvoiceStatus = Literal["draft", "signed", "sent", "received", "accepted", "rejected", "cancelled"]
OperatorSendStatus = Literal["sent", "failed"]
ETtnSendStatus = Literal["registered", "failed"]


class EInvoiceProviderError(Exception):
    """The operator could not answer (network, 5xx, credentials, rejected payload) — 21 §0 error classes.

    API callers map it to ``503 EINVOICE_PROVIDER_UNAVAILABLE`` (17 §7.2); the outbox worker maps
    ``kind`` to ``retry`` (transient) or ``failed`` (auth/validation).
    """

    def __init__(self, message: str, *, kind: ErrorKind = "transient") -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind


@dataclass(frozen=True, slots=True)
class Pkcs7Signature:
    """Detached/attached E-IMZO PKCS#7 made in the browser (21 §5); the key never reaches the server."""

    signed_content: str  # base64 PKCS#7
    certificate_serial: str | None = None


@dataclass(frozen=True, slots=True)
class CompanyInfo:
    """Requisites suggested by the operator for a STIR (Faktura.uz ``CheckCompanyExist/:inn``, 19 §9)."""

    stir: str
    name: str
    legal_address: str | None
    bank_account: str | None
    bank_mfo: str | None
    vat_payer: bool | None
    director_name: str | None = None


@dataclass(frozen=True, slots=True)
class IncomingInvoice:
    """One inbox document from ``fetch_incoming`` (21 §2: ``factura_type``, ``related_operator_doc_id``)."""

    operator_doc_id: str
    factura_type: str
    related_operator_doc_id: str | None
    seller_stir: str
    doc_date: date
    status: EInvoiceStatus
    updated_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EInvoiceResult:
    status: EInvoiceStatus
    operator_doc_id: str | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PoaResult:
    """``send_power_of_attorney`` (21 §6): ``sent`` with the operator's number, or ``failed``."""

    status: OperatorSendStatus
    number: str | None
    operator_doc_id: str | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ETtnResult:
    """``send_ettn`` outcome (21 §3) — maps 1:1 onto the ``ettn_documents`` row.

    ``registered`` → ``ettn_documents.status='registered'`` + ``operator_doc_id``; ``failed`` →
    ``status='failed'`` + ``last_error`` (permanent: ``validation``/``auth``). Transient problems are
    raised as :class:`EInvoiceProviderError` instead, so the outbox job goes to ``retry``.
    """

    status: ETtnSendStatus
    operator_doc_id: str | None
    error: str | None = None
    error_kind: ErrorKind | None = None


class EInvoicePort(Protocol):
    """21 §2 port + ``lookup_company`` (19 §9). Adapters: fake (local/test/staging), Faktura.uz."""

    async def lookup_company(self, stir: str) -> CompanyInfo | None:
        """Requisites for a 9-digit STIR; ``None`` — the operator does not know the company."""
        ...

    async def fetch_incoming(self, updated_from: datetime) -> list[IncomingInvoice]: ...

    async def sign_and_accept(self, einvoice_id: UUID, signature: Pkcs7Signature) -> EInvoiceResult: ...

    async def send_outgoing(self, einvoice_id: UUID, signature: Pkcs7Signature) -> EInvoiceResult: ...

    async def get_status(self, operator_doc_id: str) -> EInvoiceStatus: ...

    async def get_risk_flag(self, operator_doc_id: str) -> RiskFlag: ...

    async def send_power_of_attorney(self, poa_id: UUID, signed_payload: Pkcs7Signature) -> PoaResult: ...

    async def send_ettn(
        self,
        ettn_id: UUID,
        payload: Mapping[str, Any],
        signature: Pkcs7Signature | None = None,
    ) -> ETtnResult:
        """Register an e-TTN at the operator (21 §3).

        ``ettn_id`` — ``ettn_documents.id`` (operator idempotency key: a resend of the same id returns
        the same ``operator_doc_id``); ``payload`` — ``ettn_documents.payload`` (transfer requisites,
        lines, vehicle); ``signature`` — the sender's E-IMZO signature, ``None`` only for the fake
        adapter / operators that sign server-side.
        """
        ...
