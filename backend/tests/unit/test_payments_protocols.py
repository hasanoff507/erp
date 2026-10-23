"""Pure protocol rules of the payments slice: Click ``sign_string`` (docs.click.uz), Payme GET checkout link and
Basic auth (developer.help.paycom.uz), Uzum Dynamic QR ``Authorization`` (developer.uzumbank.uz), the tenant
credential fingerprint, and the ``UzqrPort`` contract suite (``test_contract_uzqr_*``: Fake now, the real adapter
⛔ 26 #49 — set ``ERP_UZQR_CONTRACT_REAL=1`` once it exists)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.integrations.payments.application.ports import PaymentProviderUnavailableError, UzqrPort
from app.modules.integrations.payments.domain.model import (
    basic_credentials,
    click_pay_url,
    click_sign,
    payme_checkout_url,
    same,
    to_tiyin,
)
from app.modules.integrations.payments.infrastructure.uzqr import (
    FakeUzqrAdapter,
    UzqrStubAdapter,
    fake_signature,
)
from app.modules.integrations.payments.infrastructure.uzum_qr import authorization
from app.modules.integrations.tenant_keys.domain.providers import credential_hash, lookup_hash, secret_aad

REF = UUID("01a14bd6-2b64-7361-9552-ae7b17c8db60")


def test_click_sign_prepare_and_complete_formula() -> None:
    form = {"click_trans_id": "1", "service_id": "2", "merchant_trans_id": "3", "amount": "1000.00", "action": "0",
            "sign_time": "2026-10-18 10:00:00"}  # fmt: skip
    expected = hashlib.md5(b"12SECRET31000.0002026-10-18 10:00:00", usedforsecurity=False).hexdigest()
    assert click_sign(form, "SECRET") == expected
    complete = {**form, "action": "1", "merchant_prepare_id": "77"}
    expected = hashlib.md5(b"12SECRET3771000.0012026-10-18 10:00:00", usedforsecurity=False).hexdigest()
    assert click_sign(complete, "SECRET") == expected


def test_click_and_payme_links() -> None:
    url = click_pay_url("https://my.click.uz/services/pay", service_id="36", merchant_id="46",
                        amount=Decimal("1000"), ref=REF)  # fmt: skip
    assert (
        url
        == f"https://my.click.uz/services/pay?service_id=36&merchant_id=46&amount=1000.00&transaction_param={REF}"
    )
    # developer.help.paycom.uz example: m=587f72c72cac0d162c722ae2;ac.order_id=197;a=500 → bT01ODdm...
    params = base64.b64encode(b"m=587f72c72cac0d162c722ae2;ac.order_id=197;a=500").decode()
    assert params == "bT01ODdmNzJjNzJjYWMwZDE2MmM3MjJhZTI7YWMub3JkZXJfaWQ9MTk3O2E9NTAw"
    link = payme_checkout_url("https://checkout.paycom.uz", merchant_id="m1", ref=REF, amount=Decimal("5.00"))
    assert base64.b64decode(link.rsplit("/", 1)[1]).decode() == f"m=m1;ac.order_id={REF};a=500"
    assert to_tiyin(Decimal("12000.55")) == 1_200_055


def test_basic_credentials_and_constant_time_compare() -> None:
    header = "Basic " + base64.b64encode(b"Paycom:key:with:colons").decode()
    assert basic_credentials(header) == ("Paycom", "key:with:colons")
    assert basic_credentials("Bearer x") is None and basic_credentials("Basic !!!") is None
    assert basic_credentials(None) is None
    assert same("abc", "abc") and not same("abc", "abd")


def test_uzum_dynamic_qr_authorization_header() -> None:
    value = authorization("8461", "secret", 1727122154352)
    user, digest, ts = value.split(":")
    assert user == "8461" and ts == "1727122154352"
    assert digest == hashlib.sha1(b"1727122154352secret", usedforsecurity=False).hexdigest()


def test_tenant_credential_fingerprint_and_aad() -> None:
    assert lookup_hash("payme", {"key": "K"}) == hashlib.sha256(b"payme:Paycom:K").digest()
    assert lookup_hash("uzum", {"login": "L", "password": "P"}) == credential_hash("uzum", "L", "P")
    assert lookup_hash("click", {"secret_key": "S"}) is None
    tenant = uuid4()
    assert secret_aad(tenant, "uzqr", None) == f"tenant_secrets:{tenant}:uzqr:-".encode()


# --- UzqrPort contract (21 §9.1) ---------------------------------------------------------------------------


def _adapters() -> list[UzqrPort]:
    adapters: list[UzqrPort] = [FakeUzqrAdapter()]
    if os.environ.get("ERP_UZQR_CONTRACT_REAL") == "1":  # pragma: no cover — real adapter ⛔ 26 #49
        pytest.fail("real UzQR adapter is not implemented (26 #49)")
    return adapters


SECRET = {"merchant_id": "M-1", "terminal_id": "T-1", "api_key": "register-key"}


@pytest.mark.parametrize("port", _adapters(), ids=lambda p: type(p).__name__)
async def test_contract_uzqr_create_check_refund(port: UzqrPort) -> None:
    created = await port.create_dynamic_qr(SECRET, uuid4(), 1_200_000, str(REF))
    assert created.provider_tx_id and created.qr_payload
    status = await port.check_transaction(SECRET, created.provider_tx_id)
    assert status.status == "pending" and status.provider_tx_id == created.provider_tx_id
    assert (await port.refund(SECRET, created.provider_tx_id, 1)).status == "failed"  # nothing paid yet
    unknown = await port.check_transaction(SECRET, "no-such-tx")
    assert unknown.status == "failed"


@pytest.mark.parametrize("port", _adapters(), ids=lambda p: type(p).__name__)
async def test_contract_uzqr_webhook_signature(port: UzqrPort) -> None:
    created = await port.create_dynamic_qr(SECRET, uuid4(), 500_000, str(REF))
    body = json.dumps(
        {"provider_tx_id": created.provider_tx_id, "status": "paid", "amount_tiyin": 500_000}
    ).encode()
    good = {"x-fake-uzqr-signature": fake_signature("register-key", body)}
    parsed = port.webhook_transaction(good, body)
    assert parsed is not None and parsed.status == "paid" and parsed.amount_tiyin == 500_000
    assert port.verify_webhook(good, body, SECRET)
    assert not port.verify_webhook({"x-fake-uzqr-signature": fake_signature("other", body)}, body, SECRET)
    assert not port.verify_webhook(good, body + b" ", SECRET)
    assert port.webhook_transaction({}, b"not json") is None


async def test_contract_uzqr_without_register_key_is_refused() -> None:
    with pytest.raises(PaymentProviderUnavailableError):
        await FakeUzqrAdapter().create_dynamic_qr({"merchant_id": "M"}, uuid4(), 1, "o")


async def test_uzqr_stub_refuses_everything() -> None:
    """The production default until the POS API arrives (26 #49): no dynamic UzQR, no webhook accepted."""
    stub = UzqrStubAdapter()
    with pytest.raises(PaymentProviderUnavailableError):
        await stub.create_dynamic_qr(SECRET, uuid4(), 1, "o")
    assert stub.webhook_transaction({}, b"{}") is None and not stub.verify_webhook({}, b"{}", SECRET)
