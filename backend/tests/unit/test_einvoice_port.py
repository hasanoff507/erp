"""E-invoice port: fake adapter, Faktura.uz placeholder, provider setting guard (21 §2/§3, 27 Bosqich 2)."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.modules.integrations.einvoice.application.ports import EInvoiceProviderError
from app.modules.integrations.einvoice.infrastructure.faktura_uz import FakturaUzEInvoiceAdapter
from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter, einvoice_port

_PROD = {
    "environment": "prod",
    "ai_mode": "api",
    "auth_secret": SecretStr("s" * 40),
    "kek": SecretStr("b3RoZXIta2VrLW9mLWV4YWN0bHktMzItYnl0ZXMhISE="),
    "web_bff_client_secret": SecretStr("w" * 40),
    "public_base_url": "https://app.example.uz",
}


async def test_fake_lookup_is_deterministic_and_can_fail() -> None:
    fake = FakeEInvoiceAdapter()
    first = await fake.lookup_company("301234567")
    assert first is not None and first == await fake.lookup_company("301234567")
    assert first.stir == "301234567" and first.name
    assert first.bank_account is not None and len(first.bank_account) == 20 and first.bank_account.isdigit()
    assert first.bank_mfo is not None and len(first.bank_mfo) == 5
    assert await fake.lookup_company("301234568") != first
    fake.unknown_stirs.add("399999999")
    assert await fake.lookup_company("399999999") is None
    fake.fail = True
    with pytest.raises(EInvoiceProviderError) as exc:
        await fake.lookup_company("301234567")
    assert exc.value.kind == "transient"


async def test_fake_registers_ettn_immediately_and_idempotently() -> None:
    fake = FakeEInvoiceAdapter()
    ettn_id = UUID("01933a1e-7c9a-7c3a-9b1e-2f6a8e9d0c1a")
    payload = {"transfer_id": "t", "lines": [{"product_id": "p", "qty": "1.000"}]}
    first = await fake.send_ettn(ettn_id, payload)
    assert first.status == "registered" and first.error is None
    assert first.operator_doc_id == "FAKE-TTN-01933A1E7C9A"
    assert await fake.send_ettn(ettn_id, payload) == first
    assert fake.sent_ettn[ettn_id] == payload
    fake.reject_ettn = True
    rejected = await fake.send_ettn(ettn_id, payload)
    assert rejected.status == "failed" and rejected.operator_doc_id is None
    assert rejected.error_kind == "validation"


async def test_faktura_uz_placeholder_answers_unavailable() -> None:
    adapter = FakturaUzEInvoiceAdapter()
    with pytest.raises(EInvoiceProviderError):
        await adapter.lookup_company("301234567")
    with pytest.raises(EInvoiceProviderError):
        await adapter.send_ettn(UUID(int=1), {})


def test_provider_setting_and_wiring() -> None:
    assert Settings(_env_file=None).einvoice_provider == "faktura_uz"
    local = Settings(_env_file=None, einvoice_provider="fake")
    assert isinstance(einvoice_port(local), FakeEInvoiceAdapter)
    assert isinstance(einvoice_port(Settings(_env_file=None)), FakturaUzEInvoiceAdapter)
    # staging may run the fake operator (27 Bosqich 2); prod may not
    staging = Settings(_env_file=None, **{**_PROD, "environment": "staging"}, einvoice_provider="fake")
    assert isinstance(einvoice_port(staging), FakeEInvoiceAdapter)
    with pytest.raises(ValidationError, match="EINVOICE"):
        Settings(_env_file=None, **_PROD, einvoice_provider="fake")
    assert Settings(_env_file=None, **_PROD).einvoice_provider == "faktura_uz"
