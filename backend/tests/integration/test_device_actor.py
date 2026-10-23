"""PIN actor on device sessions — ``X-Actor-User-Id`` (14 §4.3, 17 §5, 15 §6.1). Real PG + Redis.

A device session belongs to whoever logged the device in (here the Owner); the staff member at the till
acts only after an online PIN check, with rights never wider than the session user's, and documents and
audit name the actor.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from app.modules.auth.wiring import AuthModule
from tests.support.auth import (
    PASSWORD,
    Pkce,
    authorize_params,
    bearer,
    exchange_code,
    login_for_code,
    query_of,
)
from tests.support.branches import add_cash_register, add_device
from tests.support.catalog import Env, Shop, create_product, make_shop
from tests.support.device_auth import set_pin
from tests.support.purchasing import GR, create_supplier, gr_line, purchasing_env_fixture, warehouse_of

pytestmark = [pytest.mark.db, pytest.mark.redis]
env = purchasing_env_fixture

ROLES = (SystemRole.OWNER, SystemRole.CASHIER, SystemRole.STOREKEEPER)


async def _phone(env: Env, shop: Shop, user_id: UUID) -> str:
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        return str(
            (await s.execute(text("SELECT phone FROM app.users WHERE id = :u"), {"u": user_id})).scalar()
        )


async def _device_token(env: Env, shop: Shop, role: str) -> tuple[str, UUID]:
    """``role`` logs a registered Android POS in: a device-bound Bearer session (14 §7.2)."""
    register = await add_cash_register(env.db, shop.tenant_id, shop.branch_id)
    device = await add_device(env.db, shop.tenant_id, register, kind="android")
    pkce = Pkce.new()
    posted = await login_for_code(
        env.client,
        await _phone(env, shop, shop.user_ids[role]),
        PASSWORD,
        authorize_params(pkce, device_id=str(device)),
    )
    tokens = (await exchange_code(env.client, query_of(posted)["code"], pkce.verifier)).json()
    return str(tokens["access_token"]), device


async def _verify(env: Env, token: str, user_id: UUID, pin: str) -> httpx.Response:
    return await env.client.post(
        "/auth/pin/verify", json={"user_id": str(user_id), "pin": pin}, headers=bearer(token)
    )


def _headers(shop: Shop, token: str, actor: UUID | None) -> dict[str, str]:
    headers = {**bearer(token), "Idempotency-Key": str(uuid7()), "X-Branch-Id": str(shop.branch_id)}
    if actor is not None:
        headers["X-Actor-User-Id"] = str(actor)
    return headers


async def _receipt_body(env: Env, shop: Shop) -> dict[str, Any]:
    product = await create_product(env.client, shop, "Non")
    supplier = await create_supplier(env.client, shop)
    return {
        "warehouse_id": str(await warehouse_of(env.db, shop)),
        "doc_date": str(business_today()),
        "supplier_id": supplier["id"],
        "lines": [gr_line(product["id"], "2.000", "5000.0000")],
    }


def _reason(response: httpx.Response) -> Any:
    return response.json()["error"]["params"].get("reason") or response.json()["error"]["params"]


async def test_qt_actor_device_write_runs_as_pin_verified_actor(env: Env, clean_redis: Redis) -> None:
    shop = await make_shop(env.db, env.client, "Aktor", ROLES)
    cashier, keeper, owner = (shop.user_ids[r] for r in ("cashier", "storekeeper", "owner"))
    await set_pin(env.db, cashier, "2580")
    await set_pin(env.db, keeper, "1470")
    token, device = await _device_token(env, shop, "owner")
    body = await _receipt_body(env, shop)

    # a write from a device session without an actor → actor_required
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, None))
    assert r.status_code == 403 and _reason(r) == "actor_required", r.text
    # F-4 / SEC-04: reads need the actor too
    r = await env.client.get(GR, headers=_headers(shop, token, None))
    assert r.status_code == 403 and _reason(r) == "actor_required", r.text
    # an actor that never passed the PIN on this session → actor_not_verified
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert r.status_code == 403 and _reason(r) == "actor_not_verified", r.text

    # the cashier proves the PIN, but has no purchases.receive: the owner's rights are not borrowed
    assert (await _verify(env, token, cashier, "2580")).status_code == 200
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, cashier))
    assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED", r.text
    assert r.json()["error"]["params"].get("permission") == "purchases.receive"

    # the storekeeper (has purchases.receive) after the PIN: the document and audit name the storekeeper
    assert (await _verify(env, token, keeper, "1470")).status_code == 200
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert r.status_code == 201, r.text
    receipt = r.json()
    assert receipt["created_by"] == str(keeper)
    audit = await _audit(env, shop, "goods_receipt.created")
    assert audit.user_id == keeper and audit.after["on_behalf_session_user"] == str(owner)
    assert audit.device_id in (None, device)

    # the binding expires → the POS must ask for the PIN again
    await clean_redis.delete(*[k async for k in clean_redis.scan_iter(f"auth:actor:{device}:*")])
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert r.status_code == 403 and _reason(r) == "actor_not_verified"


async def test_qt_actor_rights_never_exceed_the_session_user(env: Env) -> None:
    """A cashier-logged device: the storekeeper actor still cannot receive goods (intersection)."""
    shop = await make_shop(env.db, env.client, "Kesishma", ROLES)
    keeper = shop.user_ids["storekeeper"]
    await set_pin(env.db, keeper, "1470")
    token, _ = await _device_token(env, shop, "cashier")
    body = await _receipt_body(env, shop)
    assert (await _verify(env, token, keeper, "1470")).status_code == 200
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED", r.text


async def test_qt_actor_blocked_member_and_redis_down_fail_closed(env: Env) -> None:
    shop = await make_shop(env.db, env.client, "Yopiq", ROLES)
    keeper = shop.user_ids["storekeeper"]
    await set_pin(env.db, keeper, "1470")
    token, _ = await _device_token(env, shop, "owner")
    body = await _receipt_body(env, shop)
    assert (await _verify(env, token, keeper, "1470")).status_code == 200

    module: AuthModule = env.app.state.auth_module
    real = module.actors._redis
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    module.actors._redis = lambda: broken
    try:
        r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
        assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED", r.text
    finally:
        module.actors._redis = real
        await broken.aclose()

    # a member blocked after the PIN check is refused at once
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.memberships SET status = 'blocked' WHERE tenant_id = :t AND user_id = :u"),
            {"t": shop.tenant_id, "u": keeper},
        )
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert r.status_code == 403 and _reason(r) == "actor_not_verified"


async def test_qt_actor_back_office_sessions_are_unchanged(env: Env) -> None:
    """A non-device session writes as itself; an X-Actor-User-Id header there changes nothing."""
    shop = await make_shop(env.db, env.client, "Ofis", ROLES)
    body = await _receipt_body(env, shop)
    headers = {**shop.h(branch=shop.branch_id), "X-Actor-User-Id": str(shop.user_ids["cashier"])}
    r = await env.client.post(GR, json=body, headers=headers)
    assert r.status_code == 201 and r.json()["created_by"] == str(shop.user_ids["owner"]), r.text
    audit = await _audit(env, shop, "goods_receipt.created")
    assert "on_behalf_session_user" not in (audit.after or {})


async def _audit(env: Env, shop: Shop, action: str) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        return (
            await s.execute(
                text(
                    "SELECT user_id, after, device_id FROM app.audit_log WHERE tenant_id = :t AND action = :a "
                    "ORDER BY at DESC LIMIT 1"
                ),
                {"t": shop.tenant_id, "a": action},
            )
        ).first()


async def _verify_as(env: Env, token: str, user_id: UUID, pin: str, purpose: str) -> httpx.Response:
    return await env.client.post(
        "/auth/pin/verify",
        json={"user_id": str(user_id), "pin": pin, "purpose": purpose},
        headers=bearer(token),
    )


async def test_qt_sec_05_one_live_actor_release_and_approval_does_not_bind(env: Env) -> None:
    """SEC-05 (F-10): a new actor replaces the previous one; release ends it; an approver PIN never binds."""
    shop = await make_shop(env.db, env.client, "Bitta aktor", ROLES)
    cashier, keeper = shop.user_ids["cashier"], shop.user_ids["storekeeper"]
    await set_pin(env.db, cashier, "2580")
    await set_pin(env.db, keeper, "1470")
    token, _ = await _device_token(env, shop, "owner")
    body = await _receipt_body(env, shop)

    assert (await _verify(env, token, keeper, "1470")).status_code == 200
    # a manager/owner-style approval check of another user does not take over the till
    assert (await _verify_as(env, token, cashier, "2580", "approval")).status_code == 200
    ok = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert ok.status_code == 201, ok.text
    # the cashier takes over → the storekeeper is no longer the actor
    assert (await _verify(env, token, cashier, "2580")).status_code == 200
    r = await env.client.post(GR, json=body, headers=_headers(shop, token, keeper))
    assert r.status_code == 403 and _reason(r) == "actor_not_verified"
    # release → nobody is the actor
    released = await env.client.post("/auth/pin/release", headers=bearer(token))
    assert released.status_code == 204
    r = await env.client.get(GR, headers=_headers(shop, token, cashier))
    assert r.status_code == 403 and _reason(r) == "actor_not_verified"


async def test_qt_sec_04_device_reads_need_the_actor_except_bootstrap(env: Env) -> None:
    """F-4: reads on a device session run as the PIN actor; /sync/* and /api/v1/auth/* stay exempt."""
    shop = await make_shop(env.db, env.client, "Oqish", ROLES)
    keeper = shop.user_ids["storekeeper"]
    await set_pin(env.db, keeper, "1470")
    token, _ = await _device_token(env, shop, "owner")
    r = await env.client.get("/api/v1/branches", headers=bearer(token))
    assert r.status_code == 403 and _reason(r) == "actor_required"
    assert (await env.client.get("/auth/session", headers=bearer(token))).status_code == 200
    assert (await _verify(env, token, keeper, "1470")).status_code == 200
    r = await env.client.get("/api/v1/branches", headers={**bearer(token), "X-Actor-User-Id": str(keeper)})
    assert r.status_code == 200, r.text
    # the release endpoint refuses a non-device session
    assert (await env.client.post("/auth/pin/release", headers=shop.h(key=None))).status_code == 403
