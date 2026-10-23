"""B3-T17 — web-POS device registration and device-bound login (14 §7, §7.2; 16 §9). Real PG + Redis."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.tokens import token_hash
from tests.conftest import MigratedDb
from tests.support.auth import (
    ISSUER,
    PASSWORD,
    Pkce,
    authorize_params,
    bearer,
    bff_login,
    exchange_code,
    login_for_code,
    query_of,
    refresh,
)
from tests.support.branches import add_cash_register, add_device, add_member, api, audit_rows, make_shop
from tests.support.device_auth import (
    DEVICE_COOKIE,
    SID_COOKIE,
    cookie_write_headers,
    one,
    register_device,
    registered_pos,
    write,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]

DAY = timedelta(days=1)


@pytest.fixture
async def client(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[httpx.AsyncClient]:
    async with api(migrated_db, redis_url) as (_, c):
        yield c


def _close(value: datetime, expected: datetime, slack: timedelta = timedelta(minutes=2)) -> bool:
    return abs(value - expected) <= slack


async def test_b3_t17_register_binds_session_to_device_14d_180d(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id, "Kassa 2")
    await bff_login(client, shop.owner.phone)
    old_sid = client.cookies.get(SID_COOKIE)

    r = await register_device(client, register)
    assert r.status_code == 201, r.text
    body = r.json()
    device_id = UUID(body["id"])
    assert body["created"] is True and body["kind"] == "web"
    assert body["cash_register_id"] == str(register) and body["branch_id"] == str(shop.branch_id)
    assert body["cash_register_name"] == "Kassa 2" and body["app_version"] == "web-1.0.0"
    assert body["session"]["device"] == {
        "id": str(device_id),
        "cash_register_id": str(register),
        "branch_id": str(shop.branch_id),
    }
    assert client.cookies.get(DEVICE_COOKIE)
    new_sid = client.cookies.get(SID_COOKIE)
    assert new_sid and new_sid != old_sid  # the session was replaced by a device-bound one

    now = datetime.now(UTC)
    row = await one(
        admin_engine,
        "SELECT s.device_id, s.idle_expires_at, s.absolute_expires_at, t.device_id AS rt_device, "
        "t.expires_at FROM auth.sessions s JOIN auth.refresh_tokens t ON t.id = s.current_refresh_token_id "
        "WHERE s.user_id = :u AND s.revoked_at IS NULL",
        u=shop.owner.user_id,
    )
    assert row.device_id == device_id and row.rt_device == device_id
    assert _close(row.idle_expires_at, now + 14 * DAY) and _close(row.expires_at, now + 14 * DAY)
    assert _close(row.absolute_expires_at, now + 180 * DAY)
    revoked = await one(
        admin_engine,
        "SELECT count(*) AS n FROM auth.sessions WHERE user_id = :u AND revoked_reason = 'device_bound'",
        u=shop.owner.user_id,
    )
    assert revoked.n == 1
    dev = await one(admin_engine, "SELECT kind, cash_register_id FROM app.devices WHERE id = :d", d=device_id)
    assert dev.kind == "web" and dev.cash_register_id == register
    audit = await audit_rows(admin_engine, shop.tenant_id, "device_registered")
    assert [a["entity_id"] for a in audit] == [device_id]

    session = await client.get("/auth/session")
    assert session.status_code == 200 and session.json()["device"]["id"] == str(device_id)


async def test_b3_t17_reregistration_is_idempotent_per_browser(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    other = await add_cash_register(app_db, shop.tenant_id, shop.branch_id, "Boshqa")
    device_id = await registered_pos(client, shop.owner.phone, register)
    sid = client.cookies.get(SID_COOKIE)

    again = await register_device(client, register, "web-1.1.0")
    assert again.status_code == 200, again.text
    assert again.json()["id"] == str(device_id) and again.json()["created"] is False
    assert again.json()["app_version"] == "web-1.1.0"
    assert client.cookies.get(SID_COOKIE) == sid  # already bound — the session is kept

    moved = await register_device(client, other)
    assert moved.status_code == 422, moved.text
    detail = moved.json()["error"]["details"][0]
    assert detail["field"] == "cash_register_id"
    assert detail["message_key"] == "validation.device_bound_to_other_register"
    count = await one(
        admin_engine, "SELECT count(*) AS n FROM app.devices WHERE tenant_id = :t", t=shop.tenant_id
    )
    assert count.n == 1

    # a new login on the same browser is device-bound again (the device cookie survives logout)
    logout = await client.post("/auth/logout", headers=await cookie_write_headers(client))
    assert logout.status_code == 204
    assert client.cookies.get(DEVICE_COOKIE)
    await bff_login(client, shop.owner.phone)
    assert (await client.get("/auth/session")).json()["device"]["id"] == str(device_id)


async def test_b3_t17_registration_requires_cash_register_manage_and_cookie(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    # Bearer (Android) — not this flow
    bearer_try = await client.post(
        "/auth/devices/register", json={"cash_register_id": str(register)}, headers=bearer(shop.owner.token)
    )
    assert bearer_try.status_code == 401
    # a cashier may not register the shop's devices (cash_register.manage)
    await bff_login(client, cashier.phone)
    denied = await register_device(client, register)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "PERMISSION_DENIED"
    # CSRF is enforced on the cookie write
    no_csrf = await client.post("/auth/devices/register", json={"cash_register_id": str(register)})
    assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "CSRF_INVALID"


async def test_b3_t17_revoked_device_login_is_unbound_and_revoked_session_gets_device_revoked(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device_id = await registered_pos(client, shop.owner.phone, register)
    r = await client.post(
        f"/api/v1/devices/{device_id}/revoke",
        json={"reason": "O'g'irlangan"},
        headers=shop.owner.headers(write=True),
    )
    assert r.status_code == 200, r.text
    # 16 §3.4/§9: the device-bound cookie session learns DEVICE_REVOKED (wipe), not a plain 401
    refused = await client.get("/auth/session")
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "DEVICE_REVOKED"
    live = await one(
        admin_engine,
        "SELECT count(*) AS n FROM auth.sessions WHERE device_id = :d AND revoked_at IS NULL",
        d=device_id,
    )
    assert live.n == 0
    fam = await one(
        admin_engine,
        "SELECT count(*) AS n FROM auth.refresh_tokens WHERE device_id = :d AND revoked_at IS NULL",
        d=device_id,
    )
    assert fam.n == 0
    # the browser still holds the cookie of the revoked device: a new login is an ordinary session
    client.cookies.delete(SID_COOKIE)
    await bff_login(client, shop.owner.phone)
    info = await client.get("/auth/session")
    assert info.status_code == 200 and info.json()["device"] is None
    # registering again creates a NEW device
    again = await register_device(client, register)
    assert again.status_code == 201 and again.json()["id"] != str(device_id)


async def test_b3_t17_tampered_authorize_device_id_is_rejected_at_callback(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    """A code bound to a device the browser did not prove (no device cookie) never yields a session."""
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device_id = await add_device(app_db, shop.tenant_id, register, kind="web")
    start = await client.get("/auth/login/start", params={"return_to": "/pos"})
    page = await client.get(start.headers["location"] + f"&device_id={device_id}")
    hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page.text))
    assert hidden["device_id"] == str(device_id)
    posted = await login_for_code(client, shop.owner.phone, PASSWORD, {**hidden})
    callback = await client.get(posted.headers["location"])
    assert callback.status_code == 302
    assert callback.headers["location"] == "/login?error=device_mismatch"
    assert client.cookies.get(SID_COOKIE) is None


async def test_b3_t17_android_device_bound_code_and_refresh_lifetimes(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """``authorization_codes.device_id`` → device-bound family: sliding 14 d, absolute 180 d (fake clock)."""
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device_id = await add_device(app_db, shop.tenant_id, register, kind="android")
    pkce = Pkce.new()
    posted = await login_for_code(
        client, shop.owner.phone, PASSWORD, authorize_params(pkce, device_id=str(device_id))
    )
    code = query_of(posted)["code"]
    stored = await one(
        admin_engine,
        "SELECT device_id FROM auth.authorization_codes WHERE code_hash = :h",
        h=token_hash(code),
    )
    assert stored.device_id == device_id
    tokens = (await exchange_code(client, code, pkce.verifier)).json()
    claims = await _claims(client, tokens["access_token"])
    assert claims["device_id"] == str(device_id)
    rt = await one(
        admin_engine,
        "SELECT device_id, expires_at, family_id FROM auth.refresh_tokens WHERE token_hash = :h",
        h=token_hash(tokens["refresh_token"]),
    )
    now = datetime.now(UTC)
    assert rt.device_id == device_id and _close(rt.expires_at, now + 14 * DAY)

    # fake clock: the family was issued 179 days ago → the next token is capped at the 180 d absolute
    await write(
        admin_engine,
        "UPDATE auth.refresh_tokens SET issued_at = now() - interval '179 days' WHERE family_id = :f",
        f=rt.family_id,
    )
    rotated = await refresh(client, tokens["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    capped = await one(
        admin_engine,
        "SELECT expires_at FROM auth.refresh_tokens WHERE token_hash = :h",
        h=token_hash(rotated.json()["refresh_token"]),
    )
    assert _close(capped.expires_at, now + DAY)
    # past the absolute lifetime the family yields nothing
    await write(
        admin_engine,
        "UPDATE auth.refresh_tokens SET issued_at = now() - interval '181 days', expires_at = now() + interval '1 day' "
        "WHERE family_id = :f",
        f=rt.family_id,
    )
    dead = await refresh(client, rotated.json()["refresh_token"])
    assert dead.status_code == 400 and dead.json()["error"] == "invalid_grant"


async def test_b3_t17_unbound_code_keeps_12h_7d_and_foreign_device_is_not_bound(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    other = await make_shop(app_db, client, "Boshqa do'kon")
    foreign_register = await add_cash_register(app_db, other.tenant_id, other.branch_id)
    foreign = await add_device(app_db, other.tenant_id, foreign_register, kind="android")
    pkce = Pkce.new()
    posted = await login_for_code(
        client, shop.owner.phone, PASSWORD, authorize_params(pkce, device_id=str(foreign))
    )
    tokens = (await exchange_code(client, query_of(posted)["code"], pkce.verifier)).json()
    assert "device_id" not in await _claims(client, tokens["access_token"])
    rt = await one(
        admin_engine,
        "SELECT device_id, expires_at FROM auth.refresh_tokens WHERE token_hash = :h",
        h=token_hash(tokens["refresh_token"]),
    )
    assert rt.device_id is None and _close(rt.expires_at, datetime.now(UTC) + timedelta(hours=12))


async def _claims(client: httpx.AsyncClient, access_token: str) -> dict[str, str]:
    payload = access_token.split(".")[1]
    data: dict[str, str] = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    assert data["iss"] == ISSUER
    return data


async def test_qt_sec_01_device_session_cannot_switch_tenant_or_revoke_all(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    other = await make_shop(app_db, client, "Ikkinchi do'kon")
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device_id = await registered_pos(client, shop.owner.phone, register)
    await write(  # the owner is also an owner of another shop
        admin_engine,
        "INSERT INTO app.memberships (tenant_id, user_id, role_ids) SELECT :t, :u, ARRAY[r.id] "
        "FROM app.roles r WHERE r.tenant_id = :t AND r.system_code = 'owner'",
        t=other.tenant_id,
        u=shop.owner.user_id,
    )
    switch = await client.post(
        "/bff/switch-tenant",
        json={"tenant_id": str(other.tenant_id)},
        headers=await cookie_write_headers(client),
    )
    assert switch.status_code == 403 and switch.json()["error"]["params"] == {"reason": "device_session"}
    revoke_all = await client.post("/auth/sessions/revoke-all", headers=await cookie_write_headers(client))
    assert revoke_all.status_code == 403 and revoke_all.json()["error"]["params"] == {
        "reason": "device_session"
    }
    info = await client.get("/auth/session")
    assert info.status_code == 200
    assert info.json()["tenant"]["id"] == str(shop.tenant_id) and info.json()["device"]["id"] == str(
        device_id
    )
