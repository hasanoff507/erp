"""Provider webhooks — ``POST /payments/webhooks/{provider}`` (18 §16.4, EP-18 #39; 17 §14; 15 webhook security):
Click SHOP API (docs.click.uz), Payme Merchant API (developer.help.paycom.uz), Uzum Bank Merchant API
(developer.uzumbank.uz/en/merchant). Signature/credential checks, replay idempotency by ``provider_tx_id``, amount
and tenant binding, protocol error codes, rate limit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.db.base import uuid7
from app.modules.integrations.payments.application.webhooks import PaymeWebhook, UzumWebhook, WebhookRequest
from app.modules.integrations.payments.infrastructure.sql import SqlCheckoutRepository, SqlTenantLookup
from app.modules.integrations.tenant_keys.wiring import tenant_secrets
from tests.support.payments import (
    WEBHOOKS,
    PayEnv,
    basic,
    click,
    click_form,
    connect_all,
    create_checkout,
    get_checkout,
    payme,
    payments_env_fixture,
    tiyin,
    uzum,
)
from tests.support.sales import make_pos, new_item, one, rows, sale_line, sale_payload, sell

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["payments_env_fixture"]


# --- Click --------------------------------------------------------------------------------------------------


async def test_ep18_39_click_prepare_complete_and_replay(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "click", "15000.00")
    ref = co["checkout_ref"]
    prepared = await click(
        env, click_form(keys, ref=ref, amount="15000.00", action=0, click_trans_id="777001")
    )
    assert (
        prepared["error"] == 0
        and prepared["click_trans_id"] == 777001
        and prepared["merchant_trans_id"] == ref
    )
    prepare_id = str(prepared["merchant_prepare_id"])
    again = await click(env, click_form(keys, ref=ref, amount="15000.00", action=0, click_trans_id="777001"))
    assert again["merchant_prepare_id"] == prepared["merchant_prepare_id"]  # idempotent Prepare
    wrong = await click(env, click_form(keys, ref=ref, amount="15000.00", action=1, click_trans_id="777001",
                                        prepare_id="1"))  # fmt: skip
    assert wrong["error"] == -6
    done = await click(env, click_form(keys, ref=ref, amount="15000.00", action=1, click_trans_id="777001",
                                       prepare_id=prepare_id))  # fmt: skip
    assert done["error"] == 0 and done["merchant_confirm_id"] == prepared["merchant_prepare_id"]
    state = await get_checkout(env, pos, ref)
    assert state["status"] == "confirmed" and state["provider_tx_id"] == "777001"
    replay = await click(env, click_form(keys, ref=ref, amount="15000.00", action=1, click_trans_id="777001",
                                         prepare_id=prepare_id))  # fmt: skip
    assert replay["error"] == -4  # Already paid — never counted twice
    assert await one(env.db, pos.tenant_id,
                     "SELECT count(*) FROM app.audit_log WHERE action = 'payment_checkout.confirmed'") == 1  # fmt: skip


async def test_ep18_39_click_rejects_bad_sign_amount_ref_action(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "click", "15000.00")
    ref = co["checkout_ref"]
    forged = await click(env, click_form(keys, ref=ref, amount="15000.00", action=0, secret_key="guess"))
    assert forged["error"] == -1
    assert (await get_checkout(env, pos, ref))[
        "provider_tx_id"
    ] is None  # an unverified request writes nothing
    assert (await click(env, click_form(keys, ref=ref, amount="14999.00", action=0)))["error"] == -2
    assert (await click(env, click_form(keys, ref=str(uuid7()), amount="15000.00", action=0)))["error"] == -5
    assert (await click(env, click_form(keys, ref=ref, amount="15000.00", action=5)))["error"] == -3
    form = click_form(keys, ref=ref, amount="15000.00", action=0)
    del form["sign_time"]
    assert (await click(env, form))["error"] == -8
    other = await make_pos(
        env, "Boshqa"
    )  # a checkout of another tenant cannot be signed with this tenant's key
    other_keys = await connect_all(env, other)
    foreign = await create_checkout(env, other, "click", "15000.00")
    assert (await click(env, click_form(keys, ref=foreign["checkout_ref"], amount="15000.00", action=0)))[
        "error"
    ] == -1
    assert other_keys.click["secret_key"] != keys.click["secret_key"]


async def test_ep18_39_click_reports_failed_payment(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "click", "500.00")
    ref = co["checkout_ref"]
    prepared = await click(env, click_form(keys, ref=ref, amount="500.00", action=0, click_trans_id="9"))
    failed = await click(env, click_form(keys, ref=ref, amount="500.00", action=1, click_trans_id="9",
                                         prepare_id=str(prepared["merchant_prepare_id"]), error="-5017"))  # fmt: skip
    assert failed["error"] == -9
    assert (await get_checkout(env, pos, ref))["status"] == "failed"


# --- Payme --------------------------------------------------------------------------------------------------


async def test_ep18_39_payme_full_cycle(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    key = keys.payme["key"]
    co = await create_checkout(env, pos, "payme", "20000.00")
    ref = co["checkout_ref"]
    account = {"order_id": ref}
    assert (await payme(env, key, "CheckPerformTransaction", {"amount": 2_000_000, "account": account}))[
        "result"
    ] == {"allow": True}
    bad_amount = await payme(env, key, "CheckPerformTransaction", {"amount": 1, "account": account})
    assert bad_amount["error"]["code"] == -31001
    unknown = await payme(env, key, "CheckPerformTransaction", {"amount": 1, "account": {"order_id": "x"}})
    assert unknown["error"]["code"] == -31050 and unknown["error"]["data"] == "order_id"
    assert set(unknown["error"]["message"]) == {"ru", "uz", "en"}
    tx = "63118a3a1c63b0e3d5c3b2a1"
    created = await payme(env, key, "CreateTransaction",
                          {"id": tx, "time": 1_760_000_000_000, "amount": 2_000_000, "account": account})  # fmt: skip
    assert created["result"]["state"] == 1 and created["result"]["transaction"] == ref
    repeat = await payme(env, key, "CreateTransaction",
                         {"id": tx, "time": 1_760_000_000_000, "amount": 2_000_000, "account": account})  # fmt: skip
    assert repeat["result"]["create_time"] == created["result"]["create_time"]
    second = await payme(env, key, "CreateTransaction",
                         {"id": "other-tx", "time": 1_760_000_000_001, "amount": 2_000_000, "account": account})  # fmt: skip
    assert second["error"]["code"] == -31051  # one order — one transaction in progress
    performed = await payme(env, key, "PerformTransaction", {"id": tx})
    assert performed["result"]["state"] == 2
    assert (await payme(env, key, "PerformTransaction", {"id": tx}))["result"] == performed["result"]
    assert (await get_checkout(env, pos, ref))["status"] == "confirmed"
    check = (await payme(env, key, "CheckTransaction", {"id": tx}))["result"]
    assert check["state"] == 2 and check["perform_time"] == performed["result"]["perform_time"]
    assert check["cancel_time"] == 0 and check["reason"] is None
    statement = await payme(env, key, "GetStatement", {"from": 1_759_999_999_000, "to": 1_760_000_001_000})
    [item] = statement["result"]["transactions"]
    assert (
        item["id"] == tx and item["amount"] == 2_000_000 and item["account"] == account and item["state"] == 2
    )
    assert (await payme(env, key, "CheckTransaction", {"id": "nope"}))["error"]["code"] == -31003
    # the sale consumes the checkout → Payme cannot cancel any more (-31007)
    product = await new_item(env, pos, price="20000.00")
    pay = {"method": "payme", "amount": "20000.00", "checkout_ref": ref, "provider_tx_id": tx}
    await sell(env, pos, sale_payload(pos, [sale_line(product, price="20000.0000")], [pay]))
    assert (await payme(env, key, "CancelTransaction", {"id": tx, "reason": 5}))["error"]["code"] == -31007


async def test_ep18_39_payme_auth_and_protocol_errors(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "payme", "100.00")
    params = {"amount": 10_000, "account": {"order_id": co["checkout_ref"]}}
    assert (await payme(env, "wrong-key", "CheckPerformTransaction", params))["error"]["code"] == -32504
    assert (await payme(env, keys.payme["key"], "CheckPerformTransaction", params, login="Admin"))["error"][
        "code"
    ] == -32504
    no_auth = await env.client.post(
        f"{WEBHOOKS}/payme", json={"id": 1, "method": "CheckTransaction", "params": {}}
    )
    assert no_auth.json()["error"]["code"] == -32504
    broken = await env.client.post(f"{WEBHOOKS}/payme", content=b"{not json", headers=basic("Paycom", "x"))
    assert broken.status_code == 200 and broken.json()["error"]["code"] == -32700
    assert (await payme(env, keys.payme["key"], "DoMagic", {}))["error"]["code"] == -32601
    other = await make_pos(env, "Begona")
    other_keys = await connect_all(env, other)  # another tenant's key never reaches this tenant's order
    foreign = await payme(env, other_keys.payme["key"], "CheckPerformTransaction", params)
    assert foreign["error"]["code"] == -31050


async def test_ep18_39_payme_cancel_and_timeout(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    key = keys.payme["key"]
    first = await create_checkout(env, pos, "payme", "300.00")
    acc = {"order_id": first["checkout_ref"]}
    await payme(env, key, "CreateTransaction", {"id": "c-1", "time": 1, "amount": 30_000, "account": acc})
    cancelled = await payme(env, key, "CancelTransaction", {"id": "c-1", "reason": 3})
    assert cancelled["result"]["state"] == -1
    assert (await payme(env, key, "CancelTransaction", {"id": "c-1", "reason": 3}))["result"]["state"] == -1
    assert (await payme(env, key, "PerformTransaction", {"id": "c-1"}))["error"]["code"] == -31008
    assert (await get_checkout(env, pos, first["checkout_ref"]))["status"] == "failed"
    # 12 h Payme timeout: a handler with an explicit clock 13 h later cancels with reason 4 (-31008)
    second = await create_checkout(env, pos, "payme", "400.00")
    acc2 = {"order_id": second["checkout_ref"]}
    await payme(env, key, "CreateTransaction", {"id": "c-2", "time": 2, "amount": 40_000, "account": acc2})
    sf = env.db.session_factory
    late = PaymeWebhook(sf, SqlCheckoutRepository(), SqlTenantLookup(sf), tenant_secrets(env.settings),
                        clock=lambda: datetime.now(UTC) + timedelta(hours=13))  # fmt: skip
    body = b'{"id": 7, "method": "PerformTransaction", "params": {"id": "c-2"}}'
    auth = basic("Paycom", key)["Authorization"]
    reply = await late.handle(WebhookRequest(headers={"authorization": auth}, body=body, ip=None))
    assert reply.body["error"]["code"] == -31008
    check = (await payme(env, key, "CheckTransaction", {"id": "c-2"}))["result"]
    assert check["state"] == -1 and check["reason"] == 4


# --- Uzum ---------------------------------------------------------------------------------------------------


async def test_ep18_39_uzum_merchant_api_cycle(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "uzum", "8000.00")
    ref = co["checkout_ref"]
    base = {"serviceId": int(keys.uzum["merchant_id"]), "timestamp": 1_760_000_000_000}
    checked = await uzum(env, keys, "check", {**base, "params": {"account": ref}})
    assert checked.status_code == 200 and checked.json()["status"] == "OK"
    assert checked.json()["data"]["account"]["value"] == ref
    tx = str(uuid7())
    bad_amount = await uzum(
        env, keys, "create", {**base, "transId": tx, "params": {"account": ref}, "amount": 1}
    )
    assert bad_amount.status_code == 400 and bad_amount.json()["errorCode"] == "10011"
    created = await uzum(env, keys, "create", {**base, "transId": tx, "params": {"account": ref},
                                                "amount": tiyin("8000.00")})  # fmt: skip
    assert created.status_code == 200 and created.json()["status"] == "CREATED"
    dup = await uzum(
        env, keys, "create", {**base, "transId": tx, "params": {"account": ref}, "amount": 800_000}
    )
    assert dup.json()["errorCode"] == "10010"
    confirmed = await uzum(env, keys, "confirm", {**base, "transId": tx, "paymentSource": "HUMO",
                                                   "phone": "998901112233"})  # fmt: skip
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "CONFIRMED"
    assert (await get_checkout(env, pos, ref))["status"] == "confirmed"
    again = await uzum(env, keys, "confirm", {**base, "transId": tx, "paymentSource": "HUMO", "phone": "1"})
    assert again.json()["errorCode"] == "10016"
    status = await uzum(env, keys, "status", {**base, "transId": tx})
    assert status.json()["status"] == "CONFIRMED" and status.json()["confirmTime"]
    stored = await one(env.db, pos.tenant_id, "SELECT provider_data FROM app.payment_checkouts")
    assert stored["payment_source"] == "HUMO" and "phone" not in stored  # no customer phone / card data
    reversed_ = await uzum(env, keys, "reverse", {**base, "transId": tx})
    assert reversed_.json()["status"] == "REVERSED"
    assert (await get_checkout(env, pos, ref))["status"] == "failed"
    assert (await uzum(env, keys, "reverse", {**base, "transId": tx})).json()["errorCode"] == "10018"


async def test_ep18_39_uzum_auth_service_account(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "uzum", "100.00")
    base = {"serviceId": int(keys.uzum["merchant_id"]), "timestamp": 1}
    denied = await uzum(env, keys, "check", {**base, "params": {"account": co["checkout_ref"]}}, password="x")
    assert denied.status_code == 400 and denied.json()["errorCode"] == "10001"
    service = await uzum(
        env, keys, "check", {**base, "serviceId": 1, "params": {"account": co["checkout_ref"]}}
    )
    assert service.json()["errorCode"] == "10006"
    assert (await uzum(env, keys, "check", {**base, "params": {"account": "nope"}})).json()[
        "errorCode"
    ] == "10007"
    assert (await uzum(env, keys, "confirm", {**base, "transId": "x"})).json()["errorCode"] == "10014"
    assert (await uzum(env, keys, "check", {"serviceId": 1})).json()["errorCode"] in ("10005", "10001")


async def test_ep18_39_uzum_confirm_window(env: PayEnv) -> None:
    """No /confirm within 30 min of /create → FAILED (explicit clock 31 min later)."""
    pos = await make_pos(env)
    keys = await connect_all(env, pos)
    co = await create_checkout(env, pos, "uzum", "100.00")
    base = {"serviceId": int(keys.uzum["merchant_id"]), "timestamp": 1}
    tx = str(uuid7())
    await uzum(env, keys, "create", {**base, "transId": tx, "params": {"account": co["checkout_ref"]},
                                      "amount": 10_000})  # fmt: skip
    sf = env.db.session_factory
    late = UzumWebhook(sf, SqlCheckoutRepository(), SqlTenantLookup(sf), tenant_secrets(env.settings),
                       clock=lambda: datetime.now(UTC) + timedelta(minutes=31))  # fmt: skip
    auth = basic(keys.uzum["login"], keys.uzum["password"])["Authorization"]
    body = (
        f'{{"serviceId": {base["serviceId"]}, "timestamp": 1, "transId": "{tx}", "paymentSource": "UZCARD", '
        '"phone": "1"}'
    )
    reply = await late.handle(
        "confirm", WebhookRequest(headers={"authorization": auth}, body=body.encode(), ip=None)
    )
    assert reply.status_code == 400 and reply.body["errorCode"] == "10015"
    assert (await get_checkout(env, pos, co["checkout_ref"]))["status"] == "failed"


async def test_ep18_39_webhook_rate_limit_and_unknown_provider(env: PayEnv) -> None:
    pos = await make_pos(env)
    await connect_all(env, pos)
    env.app.state.payments.webhook_rate_per_min = 2
    codes = []
    for _ in range(3):
        response = await env.client.post(f"{WEBHOOKS}/payme", json={"id": 1}, headers=basic("Paycom", "x"))
        codes.append(response.status_code)
    assert codes == [200, 200, 429]
    unknown = await env.client.post(f"{WEBHOOKS}/paypal", json={})
    assert unknown.status_code == 404
    audit = await rows(
        env.db, pos.tenant_id, "SELECT action FROM app.audit_log WHERE entity = 'payment_checkouts'"
    )
    assert audit == []
