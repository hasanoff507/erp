"""Deterministic in-process e-invoice operator (local/test/staging only — 27 Bosqich 2).

* ``lookup_company`` — requisites derived from the STIR itself (same STIR → same answer);
* ``send_ettn`` — registers the e-TTN immediately (``registered``, operator id derived from the
  ettn id, so a resend is idempotent), 27 B2 "FakeEInvoiceAdapter e-TTN ni darhol registered qiladi";
* test hooks: ``fail`` (every call raises a transient :class:`EInvoiceProviderError` → 503 / retry),
  ``unknown_stirs`` (lookup answers "no such company"), ``reject_ettn`` (permanent ``failed``).

Real operator calls (EHF inbox, signing, e-ishonchnoma) are Bosqich 5; here they are stubs.
"""

from __future__ import annotations

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
    RiskFlag,
)


def _digits(seed: str, count: int) -> str:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return "".join(str(int(ch, 16) % 10) for ch in digest)[:count]


@dataclass(slots=True)
class FakeEInvoiceAdapter:
    fail: bool = False
    reject_ettn: bool = False
    unknown_stirs: set[str] = field(default_factory=set)
    sent_ettn: dict[UUID, Mapping[str, Any]] = field(default_factory=dict)
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
        return []

    async def sign_and_accept(self, einvoice_id: UUID, signature: Pkcs7Signature) -> EInvoiceResult:
        self._check()
        return EInvoiceResult(status="accepted", operator_doc_id=f"FAKE-EHF-{einvoice_id.hex[:12].upper()}")

    async def send_outgoing(self, einvoice_id: UUID, signature: Pkcs7Signature) -> EInvoiceResult:
        self._check()
        return EInvoiceResult(status="sent", operator_doc_id=f"FAKE-EHF-{einvoice_id.hex[:12].upper()}")

    async def get_status(self, operator_doc_id: str) -> EInvoiceStatus:
        self._check()
        return "accepted"

    async def get_risk_flag(self, operator_doc_id: str) -> RiskFlag:
        self._check()
        return "unknown"  # Faktura.uz has no risk field (21 §2) — the fake behaves the same

    async def send_power_of_attorney(self, poa_id: UUID, signed_payload: Pkcs7Signature) -> PoaResult:
        self._check()
        suffix = poa_id.hex[:12].upper()
        return PoaResult(status="sent", number=f"FAKE-POA-{suffix}", operator_doc_id=f"FAKE-POA-{suffix}")

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
        return ETtnResult(status="registered", operator_doc_id=f"FAKE-TTN-{ettn_id.hex[:12].upper()}")
