"""``EInvoicePort`` — the e-invoice operator boundary (21 §2; e-TTN §3, e-ishonchnoma §6, STIR lookup 19 §9),
and ``SignaturePort`` — server-side verification of the browser's E-IMZO PKCS#7 (21 §5).

One port covers every operator document (EHF, e-TTN, e-ishonchnoma) and the company lookup; the MVP
operator is Faktura.uz, Didox is a second adapter of the same port (21 §2 "Operator tanlovi"). The real
operator works with the **tenant's own** credentials (``tenant_secrets``), so workers obtain the port per
tenant through :class:`EInvoicePortProvider`.

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
PoaStatus = Literal["sent", "accepted", "rejected"]
ResponseAction = Literal["accept", "reject"]


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
    """Attached E-IMZO PKCS#7 made in the browser (21 §5); the key never reaches the server."""

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
    """One inbox document from ``fetch_incoming`` (21 §2: ``factura_type``, ``related_operator_doc_id``).

    ``payload`` is the operator document normalised by the adapter to the ``einvoices.payload`` shape
    (``number``, ``doc_date``, ``seller``, ``buyer``, ``lines[]`` with ``name``/``mxik``/``barcode``/
    ``unit_code``/``qty``/``net_amount``/``vat_rate``/``vat_amount``/``marking_codes``, ``total_amount``,
    ``vat_amount``, optional ``ettn`` for a combined EHF+TTN).
    """

    operator_doc_id: str
    factura_type: str
    related_operator_doc_id: str | None
    seller_stir: str
    doc_date: date
    status: EInvoiceStatus
    updated_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)
    risk_flag: RiskFlag = "unknown"  # Didox ``scoring``; Faktura.uz has no such field (26 #47)


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
class PoaState:
    """The supplier's answer to a sent e-ishonchnoma (polled, 19 §8a)."""

    status: PoaStatus
    reason: str | None = None


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

    async def sign_and_accept(
        self, einvoice_id: UUID, signature: Pkcs7Signature, *, operator_doc_id: str | None = None
    ) -> EInvoiceResult: ...

    async def reject_incoming(
        self,
        einvoice_id: UUID,
        reason: str,
        signature: Pkcs7Signature | None = None,
        *,
        operator_doc_id: str | None = None,
    ) -> EInvoiceResult: ...

    async def send_outgoing(
        self, einvoice_id: UUID, signature: Pkcs7Signature, *, payload: Mapping[str, Any] | None = None
    ) -> EInvoiceResult: ...

    async def get_status(self, operator_doc_id: str) -> EInvoiceStatus: ...

    async def get_risk_flag(self, operator_doc_id: str) -> RiskFlag: ...

    async def send_power_of_attorney(
        self, poa_id: UUID, signed_payload: Pkcs7Signature, *, payload: Mapping[str, Any] | None = None
    ) -> PoaResult: ...

    async def get_power_of_attorney_status(self, operator_doc_id: str) -> PoaState: ...

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

    async def respond_ettn(
        self,
        ettn_id: UUID,
        operator_doc_id: str,
        action: ResponseAction,
        signature: Pkcs7Signature,
        reason: str | None = None,
    ) -> EInvoiceResult:
        """The receiver's signed accept/reject of an e-TTN (19 §20) → ``accepted`` / ``rejected``."""
        ...


class EInvoicePortProvider(Protocol):
    """The operator adapter bound to one tenant's credentials (``tenant_secrets``)."""

    async def for_tenant(self, tenant_id: UUID) -> EInvoicePort: ...


@dataclass(frozen=True, slots=True)
class StaticPortProvider:
    """Every tenant uses the same adapter (fake operator; tests)."""

    port: EInvoicePort

    async def for_tenant(self, tenant_id: UUID) -> EInvoicePort:
        del tenant_id
        return self.port


# --- E-IMZO server-side verification (21 §5) ---------------------------------------------------------
class SignatureUnavailableError(Exception):
    """The verification service (E-IMZO-SERVER) cannot be reached / is not contracted (26 #118)."""


@dataclass(frozen=True, slots=True)
class SignatureCheck:
    valid: bool
    signer_tin: str | None = None
    certificate_serial: str | None = None
    reason: str | None = None  # bad_format | content_mismatch | certificate_expired | …


class SignaturePort(Protocol):
    """Verify an **attached** PKCS#7 whose signed content must equal ``expected_content``.

    Real adapter: E-IMZO-SERVER (contract + VPN key — 26 #118); fake: local/test/staging only."""

    async def verify_attached(self, pkcs7_b64: str, expected_content: bytes) -> SignatureCheck: ...
