"""Faktura.uz adapter placeholder (21 §2; real client — Bosqich 5).

Until the client exists (tenant OAuth2 password grant, ``CheckCompanyExist/:inn``, ``GetDocuments``,
``Sign/SignDocument``) every call answers "operator unavailable": the STIR lookup returns
``503 EINVOICE_PROVIDER_UNAVAILABLE`` and outbox jobs stay in ``retry`` — nothing is faked where a
real operator was configured.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, NoReturn
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


class FakturaUzEInvoiceAdapter:
    def _unavailable(self) -> NoReturn:
        raise EInvoiceProviderError("Faktura.uz adapter is not implemented yet (Bosqich 5)", kind="transient")

    async def lookup_company(self, stir: str) -> CompanyInfo | None:
        self._unavailable()

    async def fetch_incoming(self, updated_from: datetime) -> list[IncomingInvoice]:
        self._unavailable()

    async def sign_and_accept(self, einvoice_id: UUID, signature: Pkcs7Signature) -> EInvoiceResult:
        self._unavailable()

    async def send_outgoing(self, einvoice_id: UUID, signature: Pkcs7Signature) -> EInvoiceResult:
        self._unavailable()

    async def get_status(self, operator_doc_id: str) -> EInvoiceStatus:
        self._unavailable()

    async def get_risk_flag(self, operator_doc_id: str) -> RiskFlag:
        self._unavailable()

    async def send_power_of_attorney(self, poa_id: UUID, signed_payload: Pkcs7Signature) -> PoaResult:
        self._unavailable()

    async def send_ettn(
        self,
        ettn_id: UUID,
        payload: Mapping[str, Any],
        signature: Pkcs7Signature | None = None,
    ) -> ETtnResult:
        self._unavailable()
