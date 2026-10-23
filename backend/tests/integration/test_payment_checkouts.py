"""Shop checkouts — ``POST/GET /payments/checkouts`` (18 §16.2/§16.3, EP-18 #37/#38), dynamic UzQR through
``UzqrPort`` (Fake; real ⛔ 26 #49), Uzum Dynamic QR (public API, mock bank), expiry sweep (qaror #54) and
QT-M01-13 (POS «to'lov kutilmoqda»: the sale posts only with a confirmed checkout, once)."""

from __future__ import annotations

import base64
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.integrations.payments.infrastructure.uzqr import UzqrStubAdapter
from app.modules.integrations.payments.wiring import checkout_expiry
from tests.support.payments import (
    PayEnv,
    click,
    click_form,
    confirm,
    connect_all,
    create_checkout,
    get_checkout,
    payments_env_fixture,
    tiyin,
    uzqr_webhook,
)
from tests.support.sales import (
    D,
    deliver,
    ledger_rows,
    make_pos,
    new_item,
    one,
    rows,
    sale_line,
    sale_payload,
    sell,
    sums,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["payments_env_fixture"]


async def test_ep18_37_click_checkout_link_and_replay(env: PayEnv) -> None:
    pos = await make_pos(env)
    await connect_all(env, pos)
    ref = uuid7()
    created = await create_checkout(env, pos, "click", "12000.00", ref=ref)
    assert created["status"] == "pending" and created["provider_tx_id"] is None
    url = urlsplit(created["checkout_url"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://my.click.uz/services/pay"
    assert parse_qs(url.query) == {"service_id": ["2002"], "merchant_id": ["1001"], "amount": ["12000.00"],
                                   "transaction_param": [str(ref)]}  # fmt: skip
    assert created["qr_payload"] == created["checkout_url"]
    row = await rows(env.db, pos.tenant_id, "SELECT expires_at - created_at AS ttl, branch_id, cash_register_id, "
                     "created_by FROM app.payment_checkouts")  # fmt: skip
    assert row[0]["ttl"] >= timedelta(hours=23, minutes=59) and row[0]["cash_register_id"] == pos.register_id
    assert row[0]["created_by"] == pos.shop.user_ids["cashier"]
    again = await create_checkout(env, pos, "click", "12000.00", ref=ref)  # a new Idempotency-Key, same ref
    assert (
        again["checkout_ref"] == created["checkout_ref"] and again["checkout_url"] == created["checkout_url"]
    )
    other = await create_checkout(env, pos, "click", "13000.00", ref=ref, expect=422)
    assert other["error"]["details"] == [
        {"field": "checkout_ref", "message_key": "validation.checkout_ref_reused"}
    ]
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.payment_checkouts") == 1
    audit = await one(env.db, pos.tenant_id,
                      "SELECT count(*) FROM app.audit_log WHERE action = 'payment_checkout.created'")  # fmt: skip
    assert audit == 1


async def test_ep18_37_payme_link_and_validation(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    ref = uuid7()
    created = await create_checkout(env, pos, "payme", "5000.50", ref=ref)
    prefix = "https://checkout.paycom.uz/"
    assert created["checkout_url"].startswith(prefix)
    decoded = base64.b64decode(created["checkout_url"][len(prefix) :]).decode()
    assert decoded == f"m={keys.payme['merchant_id']};ac.order_id={ref};a=500050"
    static = await create_checkout(env, pos, "uzqr", "1000.00", qr_type="static", expect=422)
    assert static["error"]["details"][0]["field"] == "qr_type"
    no_type = await create_checkout(env, pos, "click", "1000.00", qr_type="dynamic", expect=422)
    assert no_type["error"]["details"][0]["message_key"] == "validation.qr_type_uzqr_only"
    zero = await create_checkout(env, pos, "click", "0.00", expect=422)
    assert zero["error"]["details"][0]["field"] == "amount"
    bare = await make_pos(env, "Kalitsiz do'kon")
    missing = await create_checkout(env, bare, "payme", "1000.00", expect=422)
    assert missing["error"]["details"] == [
        {"field": "provider", "message_key": "validation.payment_provider_not_configured"}
    ]
    foreign = await create_checkout(
        env, pos, "click", "1000.00", cash_register_id=str(bare.register_id), expect=422
    )
    assert foreign["error"]["details"][0]["field"] == "cash_register_id"


async def test_ep18_37_uzqr_dynamic_through_port_and_stub_refuses(env: PayEnv) -> None:
    pos = await make_pos(env)
    await connect_all(env, pos)
    created = await create_checkout(env, pos, "uzqr", "12000.00")
    assert created["qr_type"] == "dynamic" and created["provider_tx_id"].startswith("fake-uzqr-")
    assert created["qr_payload"].startswith("uzqr-fake://pay?")
    env.rewire(uzqr=UzqrStubAdapter())  # production default until the POS API arrives (26 #49)
    refused = await create_checkout(env, pos, "uzqr", "12000.00", expect=502)
    assert refused["error"]["code"] == "PAYMENT_PROVIDER_ERROR"
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.payment_checkouts") == 1


async def test_ep18_38_uzum_dynamic_qr_create_and_poll(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    created = await create_checkout(env, pos, "uzum", "25000.00")
    ref = created["checkout_ref"]
    assert created["qr_payload"] == f"https://www.apelsin.uz/open-service?serviceId=111&orderId={ref}"
    request = env.uzum_bank.requests[0]
    user, digest, ts = request.headers["Authorization"].split(":")
    assert user == "8461" and len(digest) == 40 and ts.isdigit()
    assert env.uzum_bank.orders[ref]["amount"] == 2_500_000
    assert (await get_checkout(env, pos, ref))["status"] == "pending"  # bank: CREATED
    payment_id = env.uzum_bank.pay(ref)
    polled = await get_checkout(env, pos, ref)
    assert (
        polled["status"] == "confirmed" and polled["provider_tx_id"] == payment_id and polled["confirmed_at"]
    )
    env.uzum_bank.fail = True
    assert (await create_checkout(env, pos, "uzum", "1.00", expect=502))["error"][
        "code"
    ] == "PAYMENT_PROVIDER_ERROR"
    assert keys.uzum["login"]


async def test_ep18_38_scope_and_permissions(env: PayEnv) -> None:
    pos = await make_pos(env)
    await connect_all(env, pos)
    created = await create_checkout(env, pos, "click", "100.00")
    other = await make_pos(env, "Begona do'kon")
    response = await env.client.get(f"/api/v1/payments/checkouts/{created['checkout_ref']}",
                                    headers=other.shop.h("cashier", key=None))  # fmt: skip
    assert response.status_code == 404


async def test_checkout_expiry_sweep_per_test_clock(env: PayEnv) -> None:
    """Explicit clock (COMMON test hygiene): the sweep runs "1 s after expires_at" of THIS tenant's checkout."""
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    created = await create_checkout(env, pos, "click", "7000.00")
    expires_at = await one(env.db, pos.tenant_id, "SELECT expires_at FROM app.payment_checkouts")
    sweep = checkout_expiry(env.db.session_factory)
    assert await sweep.run(pos.tenant_id, now=expires_at - timedelta(seconds=1)) == 0
    assert await sweep.run(pos.tenant_id, now=expires_at + timedelta(seconds=1)) == 1
    assert (await get_checkout(env, pos, created["checkout_ref"]))["status"] == "expired"
    late = await click(env, click_form(keys, ref=created["checkout_ref"], amount="7000.00", action=0))
    assert late["error"] == -9
    assert await one(env.db, pos.tenant_id,
                     "SELECT count(*) FROM app.audit_log WHERE action = 'payment_checkout.expired'") == 1  # fmt: skip


async def test_qt_m01_13_pending_checkout_then_confirmed_once(env: PayEnv) -> None:
    """Dynamic UzQR scanned, bank confirmation not yet in → the sale cannot post (POS keeps «to'lov kutilmoqda»
    and may switch method); the webhook confirms; a repeated webhook does not count twice; the sale consumes the
    checkout exactly once."""
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    product = await new_item(env, pos)
    checkout = await create_checkout(env, pos, "uzqr", "12000.00")
    tx = checkout["provider_tx_id"]
    pay = {"method": "uzqr", "amount": "12000.00", "qr_type": "dynamic", "checkout_ref": checkout["checkout_ref"],
           "provider_tx_id": tx}  # fmt: skip
    pending = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert pending.code == "PAYMENT_NOT_CONFIRMED"
    assert (await get_checkout(env, pos, checkout["checkout_ref"]))["status"] == "pending"
    forged = await uzqr_webhook(env, keys, tx, "paid", tiyin("12000.00"), api_key="wrong-key")
    assert forged.status_code == 403 and forged.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
    assert (await get_checkout(env, pos, checkout["checkout_ref"]))["status"] == "pending"
    assert (await uzqr_webhook(env, keys, tx, "paid", tiyin("12000.00"))).json() == {"status": "ok"}
    replay = await uzqr_webhook(env, keys, tx, "paid", tiyin("12000.00"))
    assert replay.status_code == 200 and replay.json()["duplicate"] is True
    confirmed = await one(env.db, pos.tenant_id,
                          "SELECT count(*) FROM app.audit_log WHERE action = 'payment_checkout.confirmed'")  # fmt: skip
    assert confirmed == 1
    sale = sale_payload(pos, [sale_line(product)], [pay])
    await sell(env, pos, sale)
    assert (await get_checkout(env, pos, checkout["checkout_ref"]))["status"] == "consumed"
    totals = sums(await ledger_rows(env, pos, UUID(sale["id"])))
    assert totals[("5710", "9020")] == D("10714.29") and totals[("5710", "6410")] == D("1285.71")
    again = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert again.code == "PAYMENT_NOT_CONFIRMED"


async def test_qt_m01_13_click_sale_end_to_end(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    product = await new_item(env, pos)
    checkout = await create_checkout(env, pos, "click", "12000.00")
    tx = await confirm(env, keys, "click", checkout)
    pay = {
        "method": "click",
        "amount": "12000.00",
        "checkout_ref": checkout["checkout_ref"],
        "provider_tx_id": tx,
    }
    sale = sale_payload(pos, [sale_line(product)], [pay])
    await sell(env, pos, sale)
    stored = await rows(env.db, pos.tenant_id, "SELECT method, provider_tx_id, checkout_ref FROM app.sale_payments "
                        "WHERE sale_id = :s", s=sale["id"])  # fmt: skip
    assert stored == [
        {"method": "click", "provider_tx_id": tx, "checkout_ref": UUID(checkout["checkout_ref"])}
    ]
    totals = sums(await ledger_rows(env, pos, UUID(sale["id"])))
    assert totals[("5710", "9020")] + totals[("5710", "6410")] == D("12000.00")
