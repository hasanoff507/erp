"""Faktura.uz adapter (21 §2) — only what the public API documentation describes.

Source: https://api.faktura.uz/help/ (checked 2026-10-18). Documented and implemented here:

* ``POST https://account.faktura.uz/token`` — OAuth2 password grant, ``application/x-www-form-urlencoded``
  ``grant_type=password``, ``username``, ``password``, ``client_id``, ``client_secret`` → ``access_token``,
  ``token_type``, ``expires_in`` (seconds, ≈ 7 days), ``refresh_token``; every API call carries
  ``Authorization: Bearer <access_token>``. The token is cached per adapter until 60 s before expiry.
* ``GET https://api.faktura.uz/Api/CheckCompanyExist/{inn}`` → ``{Success, Data: {CompanyExist}}`` — used by
  :meth:`lookup_company` (the endpoint answers existence only, so the suggested requisites are empty).

Not publicly documented (request/response models of ``GetDocuments`` documents, ``GetDocumentHashcodes``,
``SignDocument``, document rejection, the e-TTN document type, the power-of-attorney model; no public
sandbox): those calls raise a transient :class:`EInvoiceProviderError` ("operator unavailable"), so outbox
jobs stay in ``retry``/``failed`` and the API answers ``503 EINVOICE_PROVIDER_UNAVAILABLE`` — nothing is
invented (26 #47 Xat 4, #167). The same contract test suite runs against this adapter once a tenant's
credentials are given (``tests/integration/test_einvoice_contract.py``, ``FAKTURA_UZ_*`` env).
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, NoReturn
from uuid import UUID

import httpx

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
)

TOKEN_URL: Final = "https://account.faktura.uz/token"  # noqa: S105 — an URL, not a secret
API_URL: Final = "https://api.faktura.uz"
DOCS_URL: Final = "https://api.faktura.uz/help/"
TIMEOUT_S: Final = 15.0
TOKEN_SKEW_S: Final = 60


@dataclass(frozen=True, slots=True)
class FakturaCredentials:
    """The tenant's own Faktura.uz login + API client (``tenant_secrets(kind='faktura_uz')``, 21 §2)."""

    login: str
    password: str
    client_id: str
    client_secret: str
    company_inn: str


def _kind_of(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 429 or status >= 500:
        return "transient"
    return "validation"


class FakturaUzEInvoiceAdapter:
    def __init__(
        self,
        credentials: FakturaCredentials | None = None,
        *,
        http: httpx.AsyncClient | None = None,
        token_url: str = TOKEN_URL,
        api_url: str = API_URL,
        clock: Any = time.monotonic,
    ) -> None:
        self._creds = credentials
        self._http = http
        self._token_url = token_url
        self._api_url = api_url.rstrip("/")
        self._clock = clock
        self._token: str | None = None
        self._token_expires: float = 0.0

    # --- transport --------------------------------------------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=TIMEOUT_S)
        return self._http

    def _require_credentials(self) -> FakturaCredentials:
        if self._creds is None:
            raise EInvoiceProviderError(
                "Faktura.uz credentials are not configured for the tenant", kind="auth"
            )
        return self._creds

    async def _access_token(self) -> str:
        if self._token is not None and self._clock() < self._token_expires:
            return self._token
        creds = self._require_credentials()
        try:
            response = await self._client().post(
                self._token_url,
                data={
                    "grant_type": "password",
                    "username": creds.login,
                    "password": creds.password,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise EInvoiceProviderError(f"Faktura.uz token: {type(exc).__name__}") from exc
        if response.status_code != 200:
            kind = "auth" if response.status_code in (400, 401, 403) else _kind_of(response.status_code)
            raise EInvoiceProviderError(f"Faktura.uz token: HTTP {response.status_code}", kind=kind)  # type: ignore[arg-type]
        body = response.json()
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise EInvoiceProviderError("Faktura.uz token: no access_token", kind="auth")
        expires_in = int(body.get("expires_in") or 0)
        self._token = token
        self._token_expires = self._clock() + max(expires_in - TOKEN_SKEW_S, 0)
        return token

    async def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        token = await self._access_token()
        try:
            response = await self._client().get(
                f"{self._api_url}{path}",
                params=dict(params or {}),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise EInvoiceProviderError(f"Faktura.uz {path}: {type(exc).__name__}") from exc
        if response.status_code == 401:  # token revoked early: drop it, the next call re-authenticates
            self._token = None
        if response.status_code != 200:
            kind = _kind_of(response.status_code)
            raise EInvoiceProviderError(f"Faktura.uz {path}: HTTP {response.status_code}", kind=kind)  # type: ignore[arg-type]
        return response.json()

    def _undocumented(self, operation: str) -> NoReturn:
        raise EInvoiceProviderError(
            f"Faktura.uz {operation}: request/response model is not publicly documented ({DOCS_URL}; 26 #47)",
            kind="transient",
        )

    # --- documented -------------------------------------------------------------------------------
    async def check_credentials(self) -> None:
        """Obtain a token (``POST /token``) — raises :class:`EInvoiceProviderError` (``auth``) on a bad "
        "login."""
        self._token = None
        await self._access_token()

    async def lookup_company(self, stir: str) -> CompanyInfo | None:
        body = await self._get(f"/Api/CheckCompanyExist/{stir}")
        data = body.get("Data") if isinstance(body, dict) else None
        exists = isinstance(data, dict) and bool(data.get("CompanyExist"))
        if not (isinstance(body, dict) and body.get("Success")) or not exists:
            return None
        return CompanyInfo(
            stir=stir, name="", legal_address=None, bank_account=None, bank_mfo=None, vat_payer=None
        )

    # --- not publicly documented ------------------------------------------------------------------
    async def fetch_incoming(self, updated_from: datetime) -> list[IncomingInvoice]:
        self._undocumented("GetDocuments (IsInbox) document model")

    async def sign_and_accept(
        self, einvoice_id: UUID, signature: Pkcs7Signature, *, operator_doc_id: str | None = None
    ) -> EInvoiceResult:
        self._undocumented("SignDocument")

    async def reject_incoming(
        self,
        einvoice_id: UUID,
        reason: str,
        signature: Pkcs7Signature | None = None,
        *,
        operator_doc_id: str | None = None,
    ) -> EInvoiceResult:
        self._undocumented("reject document")

    async def send_outgoing(
        self, einvoice_id: UUID, signature: Pkcs7Signature, *, payload: Mapping[str, Any] | None = None
    ) -> EInvoiceResult:
        self._undocumented("ImportDocumentRegister/SendDocument invoice model")

    async def get_status(self, operator_doc_id: str) -> EInvoiceStatus:
        self._undocumented("GetDocuments document status")

    async def get_risk_flag(self, operator_doc_id: str) -> RiskFlag:
        return "unknown"  # Faktura.uz exposes no VM 830 risk field (21 §2, 26 #47)

    async def send_power_of_attorney(
        self, poa_id: UUID, signed_payload: Pkcs7Signature, *, payload: Mapping[str, Any] | None = None
    ) -> PoaResult:
        self._undocumented("PowerOfAttorney (type 20) model")

    async def get_power_of_attorney_status(self, operator_doc_id: str) -> PoaState:
        self._undocumented("PowerOfAttorney status")

    async def send_ettn(
        self,
        ettn_id: UUID,
        payload: Mapping[str, Any],
        signature: Pkcs7Signature | None = None,
    ) -> ETtnResult:
        self._undocumented("e-TTN document type")

    async def respond_ettn(
        self,
        ettn_id: UUID,
        operator_doc_id: str,
        action: ResponseAction,
        signature: Pkcs7Signature,
        reason: str | None = None,
    ) -> EInvoiceResult:
        self._undocumented("e-TTN accept/reject")
