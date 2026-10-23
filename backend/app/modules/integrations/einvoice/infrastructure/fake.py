"""Deterministic in-process e-invoice operator and E-IMZO verifier (local/test/staging only — 27 B2/B5).

``FakeEInvoiceAdapter``:

* ``lookup_company`` — requisites derived from the STIR itself (same STIR → same answer);
* ``fetch_incoming`` — the documents put into ``inbox`` (test hook) updated at/after ``updated_from``;
* ``send_ettn`` / ``send_outgoing`` / ``send_power_of_attorney`` / ``sign_and_accept`` /
  ``reject_incoming`` / ``respond_ettn`` — succeed at once with an operator id derived from the document
  id (a resend is idempotent);
* ``get_status`` / ``get_power_of_attorney_status`` — ``statuses`` / ``poa_states`` (test hooks), else
  the document stays where it is (``sent``);
* test hooks: ``fail`` (every call raises a transient :class:`EInvoiceProviderError` → 503 / retry),
  ``unknown_stirs`` (lookup answers "no such company"), ``reject_ettn`` / ``reject_send`` (permanent
  ``validation`` failure).

``FakeSignatureVerifier`` accepts the fake PKCS#7 of :func:`fake_pkcs7` —
``base64("FAKE-PKCS7\\n<serial>\\n<tin>\\n" + content)`` — whose content equals the challenge; the real
verification is E-IMZO-SERVER (26 #118).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.integrations.einvoice.application.ports import (
    CompanyInfo,
    EInvoiceProviderError,
    EInvoiceResult,
    EInvoiceStatus,
    ETtnResult,
    IncomingInvoice,
    Pkcs7Signature,
    PoaResult,
    PoaState,
    ResponseAction,
    RiskFlag,
    SignatureCheck,
)

FAKE_PKCS7_MAGIC = b"FAKE-PKCS7\n"


def _digits(seed: str, count: int) -> str:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return "".join(str(int(ch, 16) % 10) for ch in digest)[:count]


@dataclass(slots=True)
class FakeEInvoiceAdapter:
    fail: bool = False
    reject_ettn: bool = False
    reject_send: bool = False
    unknown_stirs: set[str] = field(default_factory=set)
    inbox: list[IncomingInvoice] = field(default_factory=list)
    statuses: dict[str, EInvoiceStatus] = field(default_factory=dict)
    risk_flags: dict[str, RiskFlag] = field(default_factory=dict)
    poa_states: dict[str, PoaState] = field(default_factory=dict)
    sent_ettn: dict[UUID, Mapping[str, Any]] = field(default_factory=dict)
    signatures: dict[UUID, Pkcs7Signature | None] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)
    lookups: list[str] = field(default_factory=list)

    def _check(self) -> None:
        if self.fail:
            raise EInvoiceProviderError("fake e-invoice operator is down", kind="transient")

    async def lookup_company(self, stir: str) -> CompanyInfo | None:
        self._check()
        self.lookups.append(stir)
        if stir in self.unknown_stirs:
            return None
        return CompanyInfo(
            stir=stir,
            name=f'"TEST {stir}" MChJ',
            legal_address=f"Toshkent sh., Test ko'chasi, {int(stir[-3:]) or 1}-uy",
            bank_account=_digits(f"acc:{stir}", 20),
            bank_mfo=_digits(f"mfo:{stir}", 5),
            vat_payer=int(stir[-1]) % 2 == 0,
            director_name="Test Direktor",
        )

    async def fetch_incoming(self, updated_from: datetime) -> list[IncomingInvoice]:
        self._check()
        self.calls.append(("fetch_incoming", updated_from.isoformat()))
        return [doc for doc in self.inbox if doc.updated_at >= updated_from]

    async def sign_and_accept(
        self, einvoice_id: UUID, signature: Pkcs7Signature, *, operator_doc_id: str | None = None
    ) -> EInvoiceResult:
        self._check()
        self.calls.append(("sign_and_accept", str(einvoice_id)))
        self.signatures[einvoice_id] = signature
        return EInvoiceResult(
            status="accepted", operator_doc_id=operator_doc_id or f"FAKE-EHF-{einvoice_id.hex[:12].upper()}"
        )

    async def reject_incoming(
        self,
        einvoice_id: UUID,
        reason: str,
        signature: Pkcs7Signature | None = None,
        *,
        operator_doc_id: str | None = None,
    ) -> EInvoiceResult:
        self._check()
        self.calls.append(("reject_incoming", str(einvoice_id)))
        return EInvoiceResult(status="rejected", operator_doc_id=operator_doc_id)

    async def send_outgoing(
        self, einvoice_id: UUID, signature: Pkcs7Signature, *, payload: Mapping[str, Any] | None = None
    ) -> EInvoiceResult:
        self._check()
        self.calls.append(("send_outgoing", str(einvoice_id)))
        if self.reject_send:
            return EInvoiceResult(status="draft", operator_doc_id=None, error="fake operator rejected")
        self.signatures[einvoice_id] = signature
        return EInvoiceResult(status="sent", operator_doc_id=f"FAKE-EHF-{einvoice_id.hex[:12].upper()}")

    async def get_status(self, operator_doc_id: str) -> EInvoiceStatus:
        self._check()
        return self.statuses.get(operator_doc_id, "sent")

    async def get_risk_flag(self, operator_doc_id: str) -> RiskFlag:
        self._check()
        return self.risk_flags.get(operator_doc_id, "unknown")  # Faktura.uz has no risk field (21 §2)

    async def send_power_of_attorney(
        self, poa_id: UUID, signed_payload: Pkcs7Signature, *, payload: Mapping[str, Any] | None = None
    ) -> PoaResult:
        self._check()
        self.calls.append(("send_power_of_attorney", str(poa_id)))
        if self.reject_send:
            return PoaResult(
                status="failed", number=None, operator_doc_id=None, error="fake operator rejected"
            )
        suffix = poa_id.hex[:12].upper()
        return PoaResult(status="sent", number=f"FAKE-POA-{suffix}", operator_doc_id=f"FAKE-POA-{suffix}")

    async def get_power_of_attorney_status(self, operator_doc_id: str) -> PoaState:
        self._check()
        return self.poa_states.get(operator_doc_id, PoaState("sent"))

    async def send_ettn(
        self,
        ettn_id: UUID,
        payload: Mapping[str, Any],
        signature: Pkcs7Signature | None = None,
    ) -> ETtnResult:
        self._check()
        if self.reject_ettn:
            return ETtnResult(
                status="failed", operator_doc_id=None, error="fake operator rejected", error_kind="validation"
            )
        self.sent_ettn[ettn_id] = dict(payload)
        self.signatures[ettn_id] = signature
        return ETtnResult(status="registered", operator_doc_id=f"FAKE-TTN-{ettn_id.hex[:12].upper()}")

    async def respond_ettn(
        self,
        ettn_id: UUID,
        operator_doc_id: str,
        action: ResponseAction,
        signature: Pkcs7Signature,
        reason: str | None = None,
    ) -> EInvoiceResult:
        self._check()
        self.calls.append((f"respond_ettn:{action}", str(ettn_id)))
        return EInvoiceResult(
            status="accepted" if action == "accept" else "rejected", operator_doc_id=operator_doc_id
        )


# --- E-IMZO ------------------------------------------------------------------------------------------
def fake_pkcs7(content: bytes | str, *, serial: str = "FAKE0001", tin: str = "123456789") -> str:
    """The fake attached PKCS#7 a dev/test browser (or test) produces for ``content``."""
    raw = content.encode() if isinstance(content, str) else content
    return base64.b64encode(FAKE_PKCS7_MAGIC + f"{serial}\n{tin}\n".encode() + raw).decode()


@dataclass(slots=True)
class FakeSignatureVerifier:
    """Accepts :func:`fake_pkcs7` blobs whose content equals the expected content."""

    expired_serials: set[str] = field(default_factory=set)

    async def verify_attached(self, pkcs7_b64: str, expected_content: bytes) -> SignatureCheck:
        try:
            raw = base64.b64decode(pkcs7_b64, validate=True)
        except (binascii.Error, ValueError):
            return SignatureCheck(False, reason="bad_format")
        if not raw.startswith(FAKE_PKCS7_MAGIC):
            return SignatureCheck(False, reason="bad_format")
        parts = raw[len(FAKE_PKCS7_MAGIC) :].split(b"\n", 2)
        if len(parts) != 3:
            return SignatureCheck(False, reason="bad_format")
        serial, tin, content = parts[0].decode(errors="replace"), parts[1].decode(errors="replace"), parts[2]
        if serial in self.expired_serials:
            return SignatureCheck(False, tin, serial, reason="certificate_expired")
        if content != expected_content:
            return SignatureCheck(False, tin, serial, reason="content_mismatch")
        return SignatureCheck(True, signer_tin=tin, certificate_serial=serial)
