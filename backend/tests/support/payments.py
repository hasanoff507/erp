"""Helpers for the shop-payment tests (Bosqich 5, b5-payments slice — 18 §16, 20 #40d/#40e, 21 §9).

Real app + PostgreSQL/Redis (the sales setup: ``ERP_FISCAL_PROVIDER=fake``) with ``ERP_UZQR_PROVIDER=fake``.
``app.state.payments`` is rebuilt with ONE :class:`FakeUzqrAdapter` (the test keeps a handle) and an
``httpx.MockTransport`` that plays Uzum Bank Dynamic QR (``UzumQrBank``). Provider webhooks are sent exactly as the
provider sends them: Click — form-urlencoded with ``sign_string``; Payme — JSON-RPC with
``Authorization: Basic Paycom:<key>``; Uzum — JSON with Basic ``login:password`` on ``/uzum/<operation>``;
dynamic UzQR — the fake's own signed JSON. Secrets are unique per test (``secrets.token_hex``) because the
Payme/Uzum credential fingerprint is unique across tenants.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis

from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.integrations.payments.infrastructure.uzqr import FakeUzqrAdapter, fake_signature
from app.modules.integrations.payments.wiring import build_payments_module
from tests.conftest import MigratedDb
from tests.support.catalog import Env, catalog_app, catalog_settings
from tests.support.sales import API, Pos, reset_fake_fm

WEBHOOKS = f"{API}/payments/webhooks"


@dataclass
class UzumQrBank:
    """In-memory Uzum Bank Dynamic QR (developer.uzumbank.uz/en/dynamicqr) behind ``httpx.MockTransport``."""

    orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    fail: bool = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(
                200, json={"error_code": 503, "error_message": "apelsin.pay.service.not.working"}
            )
        body = json.loads(request.content)
        if request.url.path.endswith("/create"):
            order = body["order_id"]
            self.orders[order] = {"amount": body["amount"], "status": "CREATED", "payment_id": None}
            link = f"https://www.apelsin.uz/open-service?serviceId={body['service_id']}&orderId={order}"
            return httpx.Response(200, json={"payment_link": link, "error_code": 0})
        if request.url.path.endswith("/status-by-order"):
            found = self.orders.get(body["order_id"])
            if found is None:
                return httpx.Response(200, json={"error_code": 400, "error_message": "order.not.found"})
            return httpx.Response(200, json={
                "payment_id": found["payment_id"] or "", "payment_status": found["status"], "error_code": 0,
            })  # fmt: skip
        return httpx.Response(404)

    def pay(self, order_id: str) -> str:
        payment_id = str(uuid7())
        self.orders[order_id].update(status="SUCCESS", payment_id=payment_id)
        return payment_id


@dataclass
class PayEnv(Env):
    uzqr: FakeUzqrAdapter = field(default_factory=FakeUzqrAdapter)
    uzum_bank: UzumQrBank = field(default_factory=UzumQrBank)

    def rewire(self, **kw: Any) -> None:
        self.app.state.payments = build_payments_module(
            self.settings, self.db, uzqr=kw.get("uzqr", self.uzqr),
            uzum_transport=httpx.MockTransport(self.uzum_bank.handler),
        )  # fmt: skip


@pytest.fixture(name="env")
async def payments_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[PayEnv]:
    reset_fake_fm()
    settings = catalog_settings(
        migrated_db, redis_url, tmp_path / "files", fiscal_provider="fake", card_fake_terminals=True,
        uzqr_provider="fake",
    )  # fmt: skip
    async with catalog_app(settings) as (app, client):
        env = PayEnv(settings, app, client, app_db)
        env.rewire()
        yield env
    reset_fake_fm()


# --- tenant keys (20 #40d) -------------------------------------------------------------------------------------


@dataclass
class Keys:
    click: dict[str, Any]
    payme: dict[str, Any]
    uzum: dict[str, Any]
    uzqr: dict[str, Any]


def new_keys() -> Keys:
    token = secrets.token_hex(8)
    return Keys(
        click={"merchant_id": "1001", "service_id": "2002", "secret_key": f"click-{token}",
               "provider_autofiscal_disabled_confirmed": True},
        payme={"merchant_id": f"5e730e8e0b852a417aa49ce{token[:1]}", "key": f"payme-key-{token}",
               "provider_autofiscal_disabled_confirmed": True},
        uzum={"merchant_id": "498615418", "login": f"uzum-{token}", "password": f"pw-{token}",
              "dynamic_qr_service_id": "111", "dynamic_qr_user_id": "8461", "dynamic_qr_secret_key": f"qr-{token}",
              "provider_autofiscal_disabled_confirmed": True},
        uzqr={"merchant_id": "M-1", "terminal_id": "T-1", "api_key": f"uzqr-{token}"},
    )  # fmt: skip


async def put_keys(
    env: Env, pos: Pos, provider: str, body: Mapping[str, Any], *, role: str = "owner"
) -> httpx.Response:
    return await env.client.put(
        f"{API}/tenant/integrations/{provider}", json=dict(body), headers=pos.shop.h(role)
    )


async def connect_all(env: Env, pos: Pos) -> Keys:
    keys = new_keys()
    for provider in ("click", "payme", "uzum"):
        response = await put_keys(env, pos, provider, getattr(keys, provider))
        assert response.status_code == 200, response.text
    response = await put_keys(env, pos, "uzqr", {**keys.uzqr, "cash_register_id": str(pos.register_id)})
    assert response.status_code == 200, response.text
    return keys


# --- checkouts (18 §16.2) --------------------------------------------------------------------------------------


async def create_checkout(
    env: Env, pos: Pos, provider: str, amount: str, *, ref: UUID | None = None, role: str = "cashier",
    expect: int = 201, **extra: Any,
) -> dict[str, Any]:  # fmt: skip
    body: dict[str, Any] = {"checkout_ref": str(ref or uuid7()), "provider": provider,
                            "cash_register_id": str(pos.register_id), "amount": amount}  # fmt: skip
    if provider == "uzqr":
        body["qr_type"] = "dynamic"
    body.update(extra)
    response = await env.client.post(f"{API}/payments/checkouts", json=body, headers=pos.shop.h(role))
    assert response.status_code == expect, response.text
    out: dict[str, Any] = response.json()
    return out


async def get_checkout(env: Env, pos: Pos, ref: str, *, role: str = "cashier") -> dict[str, Any]:
    response = await env.client.get(f"{API}/payments/checkouts/{ref}", headers=pos.shop.h(role, key=None))
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


# --- provider webhooks -----------------------------------------------------------------------------------------


def click_form(
    keys: Keys, *, ref: str, amount: str, action: int, click_trans_id: str = "", prepare_id: str = "",
    error: str = "0", sign_time: str = "2026-10-18 10:00:00", secret_key: str | None = None,
) -> dict[str, str]:  # fmt: skip
    """A Click SHOP API request with ``sign_string`` per docs.click.uz."""
    form = {
        "click_trans_id": click_trans_id or str(secrets.randbelow(10**9) + 1), "service_id": keys.click["service_id"],
        "click_paydoc_id": str(secrets.randbelow(10**9) + 1), "merchant_trans_id": ref, "amount": amount,
        "action": str(action), "error": error, "error_note": "Success", "sign_time": sign_time,
    }  # fmt: skip
    if action == 1:
        form["merchant_prepare_id"] = prepare_id
    raw = (
        form["click_trans_id"] + form["service_id"] + (secret_key or keys.click["secret_key"]) + ref
        + (prepare_id if action == 1 else "") + amount + form["action"] + sign_time
    )  # fmt: skip
    form["sign_string"] = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()
    return form


async def click(env: Env, form: Mapping[str, str]) -> dict[str, Any]:
    response = await env.client.post(
        f"{WEBHOOKS}/click", content=urlencode(dict(form)),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )  # fmt: skip
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def basic(login: str, password: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{login}:{password}".encode()).decode()}


async def payme(
    env: Env, key: str, method: str, params: Mapping[str, Any], *, login: str = "Paycom"
) -> dict[str, Any]:
    body = {"jsonrpc": "2.0", "id": secrets.randbelow(10**6), "method": method, "params": dict(params)}
    response = await env.client.post(f"{WEBHOOKS}/payme", json=body, headers=basic(login, key))
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    assert out["id"] == body["id"]
    return out


async def uzum(env: Env, keys: Keys, operation: str, body: Mapping[str, Any], *, password: str | None = None
               ) -> httpx.Response:  # fmt: skip
    return await env.client.post(
        f"{WEBHOOKS}/uzum/{operation}", json=dict(body),
        headers=basic(keys.uzum["login"], password or keys.uzum["password"]),
    )  # fmt: skip


async def uzqr_webhook(env: Env, keys: Keys, tx: str, status: str, amount_tiyin: int | None,
                       *, api_key: str | None = None) -> httpx.Response:  # fmt: skip
    body = FakeUzqrAdapter.webhook_body(tx, status, amount_tiyin)
    sig = fake_signature(api_key or keys.uzqr["api_key"], body)
    return await env.client.post(
        f"{WEBHOOKS}/uzqr", content=body,
        headers={"Content-Type": "application/json", "X-Fake-Uzqr-Signature": sig},
    )  # fmt: skip


def tiyin(amount: str) -> int:
    return int(Decimal(amount) * 100)


async def confirm(env: PayEnv, keys: Keys, provider: str, checkout: Mapping[str, Any]) -> str:
    """Drive the provider's own protocol until the checkout is ``confirmed``; returns ``provider_tx_id``."""
    ref, amount = checkout["checkout_ref"], checkout["amount"]
    if provider == "click":
        prepared = await click(env, click_form(keys, ref=ref, amount=amount, action=0))
        assert prepared["error"] == 0, prepared
        tx = str(prepared["click_trans_id"])
        done = await click(env, click_form(keys, ref=ref, amount=amount, action=1, click_trans_id=tx,
                                           prepare_id=str(prepared["merchant_prepare_id"])))  # fmt: skip
        assert done["error"] == 0, done
        return tx
    if provider == "payme":
        tx = secrets.token_hex(12)
        params = {"id": tx, "time": 1_760_000_000_000, "amount": tiyin(amount), "account": {"order_id": ref}}
        assert "result" in await payme(env, keys.payme["key"], "CreateTransaction", params)
        assert "result" in await payme(env, keys.payme["key"], "PerformTransaction", {"id": tx})
        return tx
    if provider == "uzum":
        tx = str(uuid7())
        base = {"serviceId": int(keys.uzum["merchant_id"]), "timestamp": 1_760_000_000_000}
        created = await uzum(env, keys, "create", {**base, "transId": tx, "params": {"account": ref},
                                                    "amount": tiyin(amount)})  # fmt: skip
        assert created.status_code == 200, created.text
        confirmed = await uzum(env, keys, "confirm", {**base, "transId": tx, "paymentSource": "UZCARD",
                                                       "phone": "998901234567"})  # fmt: skip
        assert confirmed.status_code == 200, confirmed.text
        return tx
    tx = str(checkout["provider_tx_id"])
    response = await uzqr_webhook(env, keys, tx, "paid", tiyin(amount))
    assert response.status_code == 200, response.text
    return tx
