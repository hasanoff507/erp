"""Tenant devices — BO-11 "Qurilmalar" (20 #29a/#29b, qaror #56, 16 §9). Real PG + Redis."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.tokens import token_hash
from tests.conftest import MigratedDb
from tests.support.auth import android_tokens, bearer, refresh
from tests.support.branches import (
    add_cash_register,
    add_device,
    add_member,
    api,
    audit_rows,
    make_shop,
    open_shift,
    scalar,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def client(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[httpx.AsyncClient]:
    async with api(migrated_db, redis_url) as (_, c):
        yield c


async def _must_change_pin(admin_engine: AsyncEngine, user_id: UUID) -> bool:
    async with admin_engine.connect() as conn:
        value = (
            await conn.execute(
                text("SELECT must_change_pin FROM auth.user_credentials WHERE user_id = :u"), {"u": user_id}
            )
        ).scalar()
    return bool(value)


async def test_devices_list_filters_and_branch_scope(client: httpx.AsyncClient, app_db: Database) -> None:
    shop = await make_shop(app_db, client)
    second = (
        await client.post(
            "/api/v1/branches", json={"name": "Filial-2"}, headers=shop.owner.headers(write=True)
        )
    ).json()
    reg_a = await add_cash_register(app_db, shop.tenant_id, shop.branch_id, "Kassa A")
    reg_b = await add_cash_register(app_db, shop.tenant_id, UUID(second["id"]), "Kassa B")
    dev_a = await add_device(app_db, shop.tenant_id, reg_a, pending=3)
    dev_b = await add_device(app_db, shop.tenant_id, reg_b, kind="web", pending=0)
    agent = await add_device(app_db, shop.tenant_id, None, kind="onec_agent")

    r = await client.get("/api/v1/devices", headers=shop.owner.headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["size"] == 50
    by_id = {i["id"]: i for i in body["items"]}
    assert by_id[str(dev_a)]["cash_register_name"] == "Kassa A"
    assert by_id[str(dev_a)]["branch_id"] == str(shop.branch_id)
    assert by_id[str(dev_a)]["has_pending"] is True and by_id[str(dev_a)]["outbox_pending_count"] == 3
    assert by_id[str(dev_b)]["has_pending"] is False
    assert by_id[str(agent)]["branch_id"] is None and by_id[str(agent)]["kind"] == "onec_agent"

    only_web = (
        await client.get("/api/v1/devices", params={"kind": "web"}, headers=shop.owner.headers())
    ).json()
    assert [i["id"] for i in only_web["items"]] == [str(dev_b)]
    branch_b = await client.get(
        "/api/v1/devices", params={"branch_id": second["id"]}, headers=shop.owner.headers()
    )
    assert [i["id"] for i in branch_b.json()["items"]] == [str(dev_b)]

    # a manager of branch B sees only B's devices; asking for A is a scope violation
    manager = await add_member(app_db, client, shop, SystemRole.MANAGER, branch_ids=(UUID(second["id"]),))
    mine = (await client.get("/api/v1/devices", headers=manager.headers())).json()
    assert [i["id"] for i in mine["items"]] == [str(dev_b)]
    denied = await client.get(
        "/api/v1/devices", params={"branch_id": str(shop.branch_id)}, headers=manager.headers()
    )
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"
    cross = await client.post(
        f"/api/v1/devices/{dev_a}/revoke", json={"reason": "x"}, headers=manager.headers(write=True)
    )
    assert cross.status_code == 403

    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    assert (await client.get("/api/v1/devices", headers=cashier.headers())).status_code == 403


async def test_revoke_device_pending_confirmation_pin_reset_and_audit(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device = await add_device(app_db, shop.tenant_id, register, pending=2)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER, name="Dilnoza")
    bystander = await add_member(app_db, client, shop, SystemRole.CASHIER, name="Boshqa")
    await open_shift(app_db, shop.tenant_id, shop.branch_id, register, device, cashier.user_id)
    url = f"/api/v1/devices/{device}/revoke"

    unconfirmed = await client.post(
        url, json={"reason": "O'g'irlangan"}, headers=shop.owner.headers(write=True)
    )
    assert unconfirmed.status_code == 422
    error = unconfirmed.json()["error"]
    assert error["details"] == [
        {"field": "confirm_pending_loss", "message_key": "validation.pending_events_unconfirmed"}
    ]
    assert error["params"] == {"outbox_pending_count": 2}
    missing_reason = await client.post(
        url, json={"confirm_pending_loss": True}, headers=shop.owner.headers(write=True)
    )
    assert missing_reason.status_code == 422

    ok = await client.post(
        url,
        json={"reason": "O'g'irlangan", "confirm_pending_loss": True},
        headers=shop.owner.headers(write=True),
    )
    assert ok.status_code == 200, ok.text
    assert (
        ok.json()["id"] == str(device) and ok.json()["revoked_at"] and ok.json()["outbox_pending_count"] == 2
    )
    revoked_by = await scalar(
        app_db, shop.tenant_id, "SELECT revoked_by FROM app.devices WHERE id = :d", d=device
    )
    assert revoked_by == shop.owner.user_id

    # 16 §9: whoever worked on the device must set a new PIN; others are untouched
    assert await _must_change_pin(admin_engine, cashier.user_id) is True
    assert await _must_change_pin(admin_engine, bystander.user_id) is False
    pin_audit = await audit_rows(admin_engine, shop.tenant_id, "pin_reset_forced")
    assert [(a["entity_id"], a["device_id"]) for a in pin_audit] == [(cashier.user_id, device)]
    audit = await audit_rows(admin_engine, shop.tenant_id, "device_revoked")
    assert len(audit) == 1
    assert audit[0]["after"]["reason"] == "O'g'irlangan" and audit[0]["after"]["confirm_pending_loss"] is True
    assert audit[0]["user_id"] == shop.owner.user_id and audit[0]["device_id"] == device

    again = await client.post(url, json={"reason": "yana"}, headers=shop.owner.headers(write=True))
    assert again.status_code == 409 and again.json()["error"]["code"] == "RESOURCE_ARCHIVED"
    listed = (await client.get("/api/v1/devices", headers=shop.owner.headers())).json()["items"]
    assert listed == []  # revoked devices are hidden by default
    with_revoked = await client.get(
        "/api/v1/devices", params={"include_revoked": "true"}, headers=shop.owner.headers()
    )
    assert with_revoked.json()["items"][0]["revoked_at"]


async def test_revoke_without_pending_and_onec_agent_is_rejected(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device = await add_device(app_db, shop.tenant_id, register)  # outbox never reported
    manager = await add_member(app_db, client, shop, SystemRole.MANAGER)  # devices.revoke (qaror #56)
    ok = await client.post(
        f"/api/v1/devices/{device}/revoke", json={"reason": "Eski"}, headers=manager.headers(write=True)
    )
    assert ok.status_code == 200, ok.text
    agent = await add_device(app_db, shop.tenant_id, None, kind="onec_agent")
    rejected = await client.post(
        f"/api/v1/devices/{agent}/revoke", json={"reason": "x"}, headers=shop.owner.headers(write=True)
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["details"] == [
        {"field": "id", "message_key": "validation.onec_agent_device"}
    ]


async def test_rls_other_tenant_device_is_not_found(client: httpx.AsyncClient, app_db: Database) -> None:
    shop_a = await make_shop(app_db, client, "A")
    shop_b = await make_shop(app_db, client, "B")
    register = await add_cash_register(app_db, shop_a.tenant_id, shop_a.branch_id)
    device = await add_device(app_db, shop_a.tenant_id, register)
    r = await client.post(
        f"/api/v1/devices/{device}/revoke", json={"reason": "x"}, headers=shop_b.owner.headers(write=True)
    )
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert (await client.get("/api/v1/devices", headers=shop_b.owner.headers())).json()["items"] == []
    still = await scalar(
        app_db, shop_a.tenant_id, "SELECT revoked_at FROM app.devices WHERE id = :d", d=device
    )
    assert still is None


async def test_revoked_device_tokens_are_refused_at_once(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """16 §9 / 20 #29b: after the revoke commits, a token bound to the device gets 403 DEVICE_REVOKED."""
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device = await add_device(app_db, shop.tenant_id, register)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    tokens = await android_tokens(client, cashier.phone)
    async with (
        admin_engine.begin() as conn
    ):  # device-bound refresh family (14 §7, device registration: Bosqich 3)
        await conn.execute(
            text(
                "UPDATE auth.refresh_tokens SET device_id = :d WHERE family_id = "
                "(SELECT family_id FROM auth.refresh_tokens WHERE token_hash = :h)"
            ),
            {"d": device, "h": token_hash(tokens["refresh_token"])},
        )
    rotated = await refresh(client, tokens["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    access = rotated.json()["access_token"]
    before = await client.get("/api/v1/branches", headers=bearer(access))
    # the device check passes (positive cache set); without a PIN actor the read is refused (14 §4.3, F-4)
    assert before.status_code == 403 and before.json()["error"]["params"]["reason"] == "actor_required"

    r = await client.post(
        f"/api/v1/devices/{device}/revoke",
        json={"reason": "Yo'qolgan"},
        headers=shop.owner.headers(write=True),
    )
    assert r.status_code == 200, r.text
    refused = await client.get("/api/v1/branches", headers=bearer(access))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "DEVICE_REVOKED"
