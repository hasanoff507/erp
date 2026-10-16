"""Live access-token revocation (G-04), tenant switch (G-07) and revoke-all (G-12).

14 §5, §7, §9, §20; RFC 7009. Real PostgreSQL and Redis — no mocks (14 §21).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.auth.application.tokens import token_hash
from scripts.seed import seed_demo_tenant, seed_demo_user
from tests.conftest import MigratedDb
from tests.support.auth import (
    PASSWORD,
    Pkce,
    android_tokens,
    auth_settings,
    authorize_params,
    bearer,
    bff_login,
    client_at,
    csrf_token,
    exchange_code,
    login_for_code,
    new_phone,
    query_of,
    refresh,
    running_app,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@dataclass(frozen=True)
class TwoShops:
    """One owner with an active membership in shop A and shop B; shop C is a stranger's."""

    user_id: UUID
    phone: str
    tenant_a: UUID
    tenant_b: UUID
    tenant_c: UUID


async def _shop(db: Database, name: str) -> UUID:
    tenant_id = uuid7()
    await seed_demo_tenant(db, tenant_id=tenant_id, name=name, phone=new_phone())
    return tenant_id


@pytest.fixture
async def shops(oauth_platform: None, app_db: Database, clean_redis: Redis) -> TwoShops:
    tenant_a = await _shop(app_db, "Do'kon A")
    tenant_b = await _shop(app_db, "Do'kon B")
    tenant_c = await _shop(app_db, "Do'kon C")
    phone = new_phone()
    user_id = await seed_demo_user(app_db, tenant_id=tenant_a, phone=phone, name="Egasi", password=PASSWORD)
    await seed_demo_user(
        app_db, tenant_id=tenant_b, phone=phone, name="Egasi", password=PASSWORD, user_id=user_id
    )
    await seed_demo_user(app_db, tenant_id=tenant_c, phone=new_phone(), name="Begona", password=PASSWORD)
    return TwoShops(user_id, phone, tenant_a, tenant_b, tenant_c)


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str):  # type: ignore[no-untyped-def]
    return auth_settings(migrated_db, redis_url)


def _claims(token: str) -> dict[str, Any]:
    raw = token.split(".")[1]
    data: dict[str, Any] = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    return data


async def _android_in(client: httpx.AsyncClient, phone: str, tenant_id: UUID) -> dict[str, Any]:
    pkce = Pkce.new()
    posted = await login_for_code(client, phone, PASSWORD, authorize_params(pkce, tenant_id=str(tenant_id)))
    assert posted.status_code == 302, posted.text
    issued = await exchange_code(client, query_of(posted)["code"], pkce.verifier)
    assert issued.status_code == 200, issued.text
    body: dict[str, Any] = issued.json()
    return body


async def _session_status(client: httpx.AsyncClient, access_token: str) -> httpx.Response:
    return await client.get("/auth/session", headers=bearer(access_token))


# --- G-04: /oauth/revoke and family revocation kill live access tokens ------------------------------------
async def test_oauth_revoke_refresh_kills_live_access_token_of_its_family(  # type: ignore[no-untyped-def]
    oauth_platform: None, app_db: Database, clean_redis: Redis, settings
) -> None:
    tenant = await _shop(app_db, "Revoke do'kon")
    phone = new_phone()
    await seed_demo_user(app_db, tenant_id=tenant, phone=phone, name="Egasi", password=PASSWORD)
    async with running_app(settings) as (_, client):
        device_a = await android_tokens(client, phone)
        device_b = await android_tokens(client, phone)
        claims = _claims(device_a["access_token"])
        assert "sid" not in claims and claims["fam"]  # Android tokens: no session, family claim only
        assert (await _session_status(client, device_a["access_token"])).status_code == 200

        revoked = await client.post(
            "/oauth/revoke",
            data={
                "token": device_a["refresh_token"],
                "token_type_hint": "refresh_token",
                "client_id": "android-pos",
            },
        )
        assert revoked.status_code == 200
        # immediately — not at the access token's ``exp``
        r = await _session_status(client, device_a["access_token"])
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        assert await clean_redis.exists(f"auth:fam_revoked:{claims['fam']}")
        assert (await refresh(client, device_a["refresh_token"])).status_code == 400
        # an unrelated family of the same user keeps working
        assert (await _session_status(client, device_b["access_token"])).status_code == 200
        assert (await refresh(client, device_b["refresh_token"])).status_code == 200


async def test_oauth_revoke_access_token_by_jti_keeps_the_family(  # type: ignore[no-untyped-def]
    oauth_platform: None, app_db: Database, clean_redis: Redis, settings
) -> None:
    tenant = await _shop(app_db, "Jti do'kon")
    phone = new_phone()
    await seed_demo_user(app_db, tenant_id=tenant, phone=phone, name="Egasi", password=PASSWORD)
    async with running_app(settings) as (_, client):
        tokens = await android_tokens(client, phone)
        jti = _claims(tokens["access_token"])["jti"]
        revoked = await client.post(
            "/oauth/revoke",
            data={
                "token": tokens["access_token"],
                "token_type_hint": "access_token",
                "client_id": "android-pos",
            },
        )
        assert revoked.status_code == 200
        assert await clean_redis.exists(f"auth:jti_revoked:{jti}")
        r = await _session_status(client, tokens["access_token"])
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        # RFC 7009: only that access token is gone — the refresh family still yields new ones
        renewed = await refresh(client, tokens["refresh_token"])
        assert renewed.status_code == 200, renewed.text
        assert (await _session_status(client, renewed.json()["access_token"])).status_code == 200


async def test_oauth_revoke_reuse_detection_kills_every_access_token_of_the_family(  # type: ignore[no-untyped-def]
    oauth_platform: None, app_db: Database, clean_redis: Redis, admin_engine: AsyncEngine, settings
) -> None:
    tenant = await _shop(app_db, "Reuse do'kon")
    phone = new_phone()
    await seed_demo_user(app_db, tenant_id=tenant, phone=phone, name="Egasi", password=PASSWORD)
    async with running_app(settings) as (_, client):
        other = await android_tokens(client, phone)
        tokens = await android_tokens(client, phone)
        rotated = await refresh(client, tokens["refresh_token"])
        assert rotated.status_code == 200, rotated.text
        at1, at2 = tokens["access_token"], rotated.json()["access_token"]
        assert _claims(at1)["fam"] == _claims(at2)["fam"]
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE auth.refresh_tokens SET used_at = used_at - interval '31 seconds' WHERE token_hash = :h"
                ),
                {"h": token_hash(tokens["refresh_token"])},
            )
        assert (await refresh(client, tokens["refresh_token"])).status_code == 400
        for token in (at1, at2):
            r = await _session_status(client, token)
            assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        assert (await _session_status(client, other["access_token"])).status_code == 200


# --- G-07: POST /bff/switch-tenant (14 §9) -----------------------------------------------------------------
async def test_bff_switch_tenant_repoints_the_cookie(  # type: ignore[no-untyped-def]
    shops: TwoShops, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (app, client):
        cookies = app.state.auth_module.cookies
        old_cookie = await bff_login(client, shops.phone, tenant_id=shops.tenant_a)
        old_sid = cookies.unsign(old_cookie)
        assert (await client.get("/auth/session")).json()["tenant"]["id"] == str(shops.tenant_a)
        old_csrf = await csrf_token(client)

        switched = await client.post(
            "/bff/switch-tenant", json={"tenant_id": str(shops.tenant_b)}, headers={"X-CSRF-Token": old_csrf}
        )
        assert switched.status_code == 200, switched.text
        assert switched.headers["cache-control"] == "no-store"
        body = switched.json()
        assert body["tenant"]["id"] == str(shops.tenant_b) and body["user"]["id"] == str(shops.user_id)
        new_cookie = client.cookies.get("__Host-sid")
        assert new_cookie and new_cookie != old_cookie
        new_sid = cookies.unsign(new_cookie)
        assert new_sid is not None and new_sid != old_sid

        session = await client.get("/auth/session")
        assert session.status_code == 200 and session.json()["tenant"]["id"] == str(shops.tenant_b)
        # the CSRF token of the old sid is dead; a fresh one works
        stale = await client.post("/auth/logout", headers={"X-CSRF-Token": old_csrf})
        assert stale.status_code == 403 and stale.json()["error"]["code"] == "CSRF_INVALID"
        assert await csrf_token(client) != old_csrf

        # the old sid, its refresh family and its live access tokens are dead
        async with admin_engine.connect() as conn:
            reason = (
                await conn.execute(
                    text("SELECT revoked_reason FROM auth.sessions WHERE id = :s"), {"s": old_sid}
                )
            ).scalar_one()
            live_rt = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM auth.refresh_tokens t WHERE t.revoked_at IS NULL "
                        "AND t.family_id = (SELECT f.family_id FROM auth.refresh_tokens f "
                        "JOIN auth.sessions s ON s.current_refresh_token_id = f.id WHERE s.id = :s)"
                    ),
                    {"s": old_sid},
                )
            ).scalar()
            audit = (
                await conn.execute(
                    text(
                        "SELECT action, after FROM app.audit_log WHERE tenant_id = :t AND action = 'tenant_switched'"
                    ),
                    {"t": shops.tenant_b},
                )
            ).all()
        assert reason == "tenant_switch" and live_rt == 0
        assert len(audit) == 1 and audit[0].after["from_tenant_id"] == str(shops.tenant_a)
        assert await clean_redis.exists(f"auth:sid_revoked:{old_sid}")
        assert not await clean_redis.exists(f"bff:sess:{old_sid}")
        client.cookies.set("__Host-sid", old_cookie)
        assert (await client.get("/auth/session")).status_code == 401


async def test_bff_switch_tenant_refusals_keep_the_session(  # type: ignore[no-untyped-def]
    shops: TwoShops, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (_, client):
        cookie = await bff_login(client, shops.phone, tenant_id=shops.tenant_a)
        token = await csrf_token(client)
        url = "/bff/switch-tenant"

        no_csrf = await client.post(url, json={"tenant_id": str(shops.tenant_b)})
        assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "CSRF_INVALID"

        stranger = await client.post(
            url, json={"tenant_id": str(shops.tenant_c)}, headers={"X-CSRF-Token": token}
        )
        assert stranger.status_code == 403 and stranger.json()["error"]["code"] == "PERMISSION_DENIED"
        unknown = await client.post(url, json={"tenant_id": str(uuid7())}, headers={"X-CSRF-Token": token})
        assert unknown.status_code == 403 and unknown.json()["error"]["code"] == "PERMISSION_DENIED"

        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE app.memberships SET status = 'blocked' WHERE tenant_id = :t AND user_id = :u"),
                {"t": shops.tenant_b, "u": shops.user_id},
            )
        blocked = await client.post(
            url, json={"tenant_id": str(shops.tenant_b)}, headers={"X-CSRF-Token": token}
        )
        assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "PERMISSION_DENIED"

        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE app.memberships SET status = 'active' WHERE tenant_id = :t AND user_id = :u"),
                {"t": shops.tenant_b, "u": shops.user_id},
            )
            await conn.execute(
                text("UPDATE app.subscriptions SET status = 'restricted' WHERE tenant_id = :t"),
                {"t": shops.tenant_b},
            )
        await clean_redis.set(f"sub_status:{shops.tenant_b}", "restricted")
        locked = await client.post(
            url, json={"tenant_id": str(shops.tenant_b)}, headers={"X-CSRF-Token": token}
        )
        assert locked.status_code == 403 and locked.json()["error"]["code"] == "SUBSCRIPTION_RESTRICTED"

        # the current tenant is a no-op: same cookie, same session
        same = await client.post(
            url, json={"tenant_id": str(shops.tenant_a)}, headers={"X-CSRF-Token": token}
        )
        assert same.status_code == 200 and same.json()["tenant"]["id"] == str(shops.tenant_a)
        # nothing above touched the current session
        assert client.cookies.get("__Host-sid") == cookie
        session = await client.get("/auth/session")
        assert session.status_code == 200 and session.json()["tenant"]["id"] == str(shops.tenant_a)


async def test_bff_switch_tenant_needs_a_cookie_session(  # type: ignore[no-untyped-def]
    shops: TwoShops, settings
) -> None:
    async with running_app(settings) as (_, client):
        tokens = await _android_in(client, shops.phone, shops.tenant_a)
        r = await client.post(
            "/bff/switch-tenant",
            json={"tenant_id": str(shops.tenant_b)},
            headers=bearer(tokens["access_token"]),
        )
        assert r.status_code == 401


# --- G-12: POST /auth/sessions/revoke-all across tenants and devices (14 §2.1, §20) ------------------------
async def test_auth_revoke_all_ends_every_session_in_every_tenant(  # type: ignore[no-untyped-def]
    shops: TwoShops, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (app, laptop):
        await bff_login(laptop, shops.phone, tenant_id=shops.tenant_a)
        async with client_at(app, "10.0.0.8") as phone_browser:
            await bff_login(phone_browser, shops.phone, tenant_id=shops.tenant_b)
            android = await _android_in(laptop, shops.phone, shops.tenant_a)
            assert (await phone_browser.get("/auth/session")).status_code == 200
            assert (await _session_status(laptop, android["access_token"])).status_code == 200

            token = await csrf_token(laptop)
            no_csrf = await laptop.post("/auth/sessions/revoke-all")
            assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "CSRF_INVALID"
            bearer_only = await laptop.post(
                "/auth/sessions/revoke-all",
                headers=bearer(android["access_token"]),
            )
            assert bearer_only.status_code == 401  # BFF cookie sessions only

            done = await laptop.post("/auth/sessions/revoke-all", headers={"X-CSRF-Token": token})
            assert done.status_code == 200, done.text
            assert done.json() == {"sessions_revoked": 2}  # the two browser sessions (A and B)
            set_cookie = done.headers.get("set-cookie", "")
            assert "__Host-sid=" in set_cookie and (
                "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()
            )
            assert laptop.cookies.get("__Host-sid") is None

            # every session, every refresh family, every live access token — in both tenants
            assert (await phone_browser.get("/auth/session")).status_code == 401
            r = await _session_status(laptop, android["access_token"])
            assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
            assert (await refresh(laptop, android["refresh_token"])).status_code == 400
            async with admin_engine.connect() as conn:
                live = (
                    await conn.execute(
                        text(
                            "SELECT (SELECT count(*) FROM auth.sessions WHERE user_id = :u AND revoked_at IS NULL)"
                            " + (SELECT count(*) FROM auth.refresh_tokens WHERE user_id = :u AND revoked_at IS NULL)"
                        ),
                        {"u": shops.user_id},
                    )
                ).scalar()
                audit = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM app.audit_log WHERE user_id = :u AND action = 'all_sessions_revoked'"
                        ),
                        {"u": shops.user_id},
                    )
                ).scalar()
            assert live == 0 and audit == 1
            assert await clean_redis.exists(f"auth:user_revoked:*:{shops.user_id}")
