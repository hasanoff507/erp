"""``EInvoicePort`` / ``SignaturePort`` contract tests (21 §2, §5; COMMON: port + fake + contract tests).

The same contract suite runs against every adapter: the fake always, the Faktura.uz adapter when a test
tenant's credentials are given (``FAKTURA_UZ_LOGIN``, ``FAKTURA_UZ_PASSWORD``, ``FAKTURA_UZ_CLIENT_ID``,
``FAKTURA_UZ_CLIENT_SECRET``, ``FAKTURA_UZ_INN`` — no public sandbox, 26 #47). Calls whose request/response
model is not publicly documented must answer a transient :class:`EInvoiceProviderError` (never invented data).
The documented Faktura.uz wire format (``POST /token`` password grant, ``CheckCompanyExist``) is checked against
``httpx.MockTransport`` (source https://api.faktura.uz/help/).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.modules.integrations.einvoice.application.ports import (
    EInvoicePort,
    EInvoiceProviderError,
    Pkcs7Signature,
    SignatureUnavailableError,
)
from app.modules.integrations.einvoice.application.signing import Signer
from app.modules.integrations.einvoice.domain.documents import document_hash, marking_due_at, signed_content
from app.modules.integrations.einvoice.infrastructure.eimzo_server import EImzoServerVerifier
from app.modules.integrations.einvoice.infrastructure.fake import (
    FakeEInvoiceAdapter,
    FakeSignatureVerifier,
    fake_pkcs7,
)
from app.modules.integrations.einvoice.infrastructure.faktura_uz import (
    FakturaCredentials,
    FakturaUzEInvoiceAdapter,
)

DOC = UUID("01900000-0000-7000-8000-000000000001")
SIG = Pkcs7Signature(fake_pkcs7("x"), "FAKE0001")


def _real_faktura() -> EInvoicePort | None:
    env = os.environ
    keys = (
        "FAKTURA_UZ_LOGIN",
        "FAKTURA_UZ_PASSWORD",
        "FAKTURA_UZ_CLIENT_ID",
        "FAKTURA_UZ_CLIENT_SECRET",
        "FAKTURA_UZ_INN",
    )
    if not all(env.get(k) for k in keys):
        return None
    return FakturaUzEInvoiceAdapter(FakturaCredentials(*(env[k] for k in keys)))


ADAPTERS: dict[str, Callable[[], EInvoicePort | None]] = {
    "fake": FakeEInvoiceAdapter,
    "faktura_uz": _real_faktura,
}


@pytest.fixture(params=list(ADAPTERS), name="port")
def port_fixture(request: pytest.FixtureRequest) -> EInvoicePort:
    port = ADAPTERS[request.param]()
    if port is None:
        pytest.skip("real Faktura.uz credentials not given (26 #47: no public sandbox)")
    return port


async def _documented_or_unavailable(call: object) -> object | None:
    kind: str | None = None
    try:
        return await call  # type: ignore[misc]
    except EInvoiceProviderError as exc:
        kind = exc.kind
    assert kind == "transient"
    return None


async def test_contract_einvoice_port_lookup_company(port: EInvoicePort) -> None:
    info = await port.lookup_company("301234567")
    assert info is None or info.stir == "301234567"


async def test_contract_einvoice_port_risk_flag_is_three_valued(port: EInvoicePort) -> None:
    assert await port.get_risk_flag("ANY") in ("green", "red", "unknown")


async def test_contract_einvoice_port_fetch_incoming_shape(port: EInvoicePort) -> None:
    docs = await _documented_or_unavailable(port.fetch_incoming(datetime(2026, 10, 1, tzinfo=UTC)))
    if docs is not None:
        assert isinstance(docs, list)
        for doc in docs:
            assert doc.operator_doc_id and doc.factura_type in ("standard", "additional", "corrected")


async def test_contract_einvoice_port_send_ettn_is_idempotent(port: EInvoicePort) -> None:
    first = await _documented_or_unavailable(
        port.send_ettn(DOC, {"transport_type": "warehouse_to_warehouse"}, SIG)
    )
    if first is None:
        return
    second = await port.send_ettn(DOC, {"transport_type": "warehouse_to_warehouse"}, SIG)
    assert first == second


async def test_contract_einvoice_port_outgoing_and_poa(port: EInvoicePort) -> None:
    sent = await _documented_or_unavailable(port.send_outgoing(DOC, SIG, payload={"lines": []}))
    if sent is not None:
        assert sent.status == "sent" and sent.operator_doc_id  # type: ignore[attr-defined]
    poa = await _documented_or_unavailable(port.send_power_of_attorney(DOC, SIG, payload={}))
    if poa is not None:
        assert poa.status in ("sent", "failed")  # type: ignore[attr-defined]


async def test_contract_einvoice_port_transient_errors() -> None:
    port = FakeEInvoiceAdapter(fail=True)
    with pytest.raises(EInvoiceProviderError) as info:
        await port.lookup_company("301234567")
    assert info.value.kind == "transient"


# --- Faktura.uz documented wire format (https://api.faktura.uz/help/) ---------------------------------------
CREDS = FakturaCredentials("login1", "pa$$", "client-1", "secret-1", "301234567")


def _mock(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_contract_faktura_uz_token_password_grant_and_bearer() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/token":
            return httpx.Response(
                200, json={"access_token": "T1", "token_type": "bearer", "expires_in": 604799}
            )
        return httpx.Response(200, json={"Success": True, "Data": {"CompanyExist": True}})

    port = FakturaUzEInvoiceAdapter(CREDS, http=_mock(handler))
    info = await port.lookup_company("302222222")
    assert info is not None and info.stir == "302222222"
    await port.lookup_company("303333333")
    token, lookup, lookup2 = seen  # the token is cached for the next call
    assert (str(token.url), token.method) == ("https://account.faktura.uz/token", "POST")
    assert token.headers["content-type"] == "application/x-www-form-urlencoded"
    assert parse_qs(token.content.decode()) == {
        "grant_type": ["password"], "username": ["login1"], "password": ["pa$$"], "client_id": ["client-1"],
        "client_secret": ["secret-1"],
    }  # fmt: skip
    assert str(lookup.url) == "https://api.faktura.uz/Api/CheckCompanyExist/302222222"
    assert lookup.headers["authorization"] == "Bearer T1"
    assert lookup2.headers["authorization"] == "Bearer T1"


async def test_contract_faktura_uz_unknown_company_and_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "T", "expires_in": 3600})
        if request.url.path.endswith("/500000000"):
            return httpx.Response(503)
        return httpx.Response(200, json={"Success": True, "Data": {"CompanyExist": False}})

    port = FakturaUzEInvoiceAdapter(CREDS, http=_mock(handler))
    assert await port.lookup_company("301234567") is None
    with pytest.raises(EInvoiceProviderError) as down:
        await port.lookup_company("500000000")
    assert down.value.kind == "transient"

    def bad_login(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(EInvoiceProviderError) as auth:
        await FakturaUzEInvoiceAdapter(CREDS, http=_mock(bad_login)).check_credentials()
    assert auth.value.kind == "auth"
    with pytest.raises(EInvoiceProviderError) as missing:
        await FakturaUzEInvoiceAdapter(None).lookup_company("301234567")
    assert missing.value.kind == "auth"


async def test_contract_faktura_uz_undocumented_calls_never_invent_data() -> None:
    port = FakturaUzEInvoiceAdapter(CREDS, http=_mock(lambda r: httpx.Response(500)))
    for call in (
        port.fetch_incoming(datetime(2026, 10, 1, tzinfo=UTC)),
        port.sign_and_accept(DOC, SIG),
        port.send_outgoing(DOC, SIG),
        port.send_power_of_attorney(DOC, SIG),
        port.send_ettn(DOC, {}, SIG),
        port.respond_ettn(DOC, "OP", "accept", SIG),
    ):
        with pytest.raises(EInvoiceProviderError) as info:
            await call
        assert info.value.kind == "transient" and "not publicly documented" in str(info.value)
    assert await port.get_risk_flag("OP") == "unknown"


# --- SignaturePort (21 §5) -----------------------------------------------------------------------------------
async def test_contract_signature_port_fake_verifier() -> None:
    verifier = FakeSignatureVerifier(expired_serials={"OLD"})
    content = signed_content("ab" * 32)
    ok = await verifier.verify_attached(fake_pkcs7(content, serial="S1", tin="123456789"), content)
    assert (ok.valid, ok.certificate_serial, ok.signer_tin) == (True, "S1", "123456789")
    assert (await verifier.verify_attached(fake_pkcs7(b"other"), content)).reason == "content_mismatch"
    assert (await verifier.verify_attached("not base64!!", content)).reason == "bad_format"
    assert (
        await verifier.verify_attached(fake_pkcs7(content, serial="OLD"), content)
    ).reason == "certificate_expired"


async def test_contract_signature_port_eimzo_server_is_not_contracted() -> None:
    """26 #118: without E-IMZO-SERVER a signature is never accepted unverified."""
    with pytest.raises(SignatureUnavailableError):
        await EImzoServerVerifier().verify_attached("x", b"y")

    class _NoStore:
        async def put(self, *_: object) -> None: ...
        async def take(self, _: str) -> dict[str, str] | None:
            return None

    with pytest.raises(AppError) as info:
        await Signer(_NoStore(), EImzoServerVerifier()).verify("ab" * 32, "x")
    assert info.value.params == {"reason": "verification_unavailable"}


def test_eimzo_fake_refused_in_prod() -> None:
    with pytest.raises(ValueError, match="EIMZO"):
        Settings(environment="prod", eimzo_verifier="fake", einvoice_provider="faktura_uz")


def test_document_hash_binds_entity_action_and_content() -> None:
    base = document_hash("einvoices", str(DOC), "sign", {"a": 1, "b": [1, 2]})
    assert base == document_hash("einvoices", str(DOC), "sign", {"b": [1, 2], "a": 1})  # canonical JSON
    assert base != document_hash("einvoices", str(DOC), "accept", {"a": 1, "b": [1, 2]})
    assert base != document_hash("ettn_documents", str(DOC), "sign", {"a": 1, "b": [1, 2]})
    assert len(base) == 64


def test_marking_deadline_72_hours_and_3_business_days() -> None:
    """19 §8 / VM 833 66–67: from the dispatch day (Asia/Tashkent); weekends are skipped for business days."""
    friday = date(2026, 10, 16)
    assert marking_due_at(friday, "72_hours") == datetime(2026, 10, 18, 19, tzinfo=UTC)  # Mon 00:00 +05
    assert marking_due_at(friday, "3_business_days") == datetime(2026, 10, 21, 19, tzinfo=UTC)  # end of Wed
