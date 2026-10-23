"""Auth quality-gate fixes against real PostgreSQL and Redis (14 §2.1/§7/§9/§16.4, 23 §3). No mocks."""

from __future__ import annotations

import base64
import json

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.auth.application.tokens import token_hash
from tests.conftest import MigratedDb
from tests.integration.test_oauth import World, make_world
from tests.support.auth import (
    android_tokens,
    auth_settings,
    bearer,
    bff_login,
    csrf_token,
    refresh,
    running_app,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def world(oauth_platform: None, app_db: Database, clean_redis: Redis) -> World:
    return await make_world(app_db, "Gate do'kon")


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str):  # type: ignore[no-untyped-def]
    return auth_settings(migrated_db, redis_url)


def _claims(token: str) -> dict[str, object]:
    raw = token.split(".")[1]
    data: dict[str, object] = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    return data


async def _age_used_at(admin_engine: AsyncEngine, refresh_token: str) -> None:
    """Push a rotated RT out of the 30 s grace window (a stolen copy coming back later)."""
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE auth.refresh_tokens SET used_at = used_at - interval '31 seconds' WHERE token_hash = :h"
            ),
            {"h": token_hash(refresh_token)},
        )


# --- SEC-2: re-login in the same browser retires the previous BFF session (14 §2.1, §9) ---------------
async def test_relogin_revokes_previous_bff_session(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (app, client):
        cookies = app.state.auth_module.cookies
        first = cookies.unsign(await bff_login(client, world.owner_phone))
        assert first is not None
        assert await clean_redis.exists(f"bff:sess:{first}")
        second = cookies.unsign(await bff_login(client, world.owner_phone))  # old cookie still sent
        assert second is not None and second != first
        async with admin_engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT revoked_at, revoked_reason FROM auth.sessions WHERE id = :s"), {"s": first}
                )
            ).one()
            live_rt = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM auth.refresh_tokens t WHERE t.revoked_at IS NULL "
                        "AND t.family_id = (SELECT f.family_id FROM auth.refresh_tokens f "
                        "JOIN auth.sessions s ON s.current_refresh_token_id = f.id WHERE s.id = :s)"
                    ),
                    {"s": first},
                )
            ).scalar()
        assert row.revoked_at is not None and row.revoked_reason == "logout"
        assert live_rt == 0
        assert not await clean_redis.exists(f"bff:sess:{first}")
        assert await clean_redis.exists(f"bff:sess:{second}")
        assert (await client.get("/auth/session")).status_code == 200  # the new session works


# --- SEC-3: a revoked token gets no Idempotency-Key replay (23 §3) ------------------------------------
async def test_revoked_bearer_gets_no_idempotent_replay(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        owner = await android_tokens(client, world.owner_phone)
        url = f"/api/v1/admin/users/{world.cashier_id}"
        headers = {**bearer(owner["access_token"]), "Idempotency-Key": str(uuid7())}
        first = await client.patch(url, json={"status": "active"}, headers=headers)
        assert first.status_code == 200, first.text
        revoked = await client.post(
            "/oauth/revoke", data={"token": owner["access_token"], "client_id": "android-pos"}
        )
        assert revoked.status_code == 200
        again = await client.patch(url, json={"status": "active"}, headers=headers)
        assert again.status_code == 401 and again.json()["error"]["code"] == "TOKEN_REVOKED"


async def test_revoked_cookie_session_gets_no_idempotent_replay(  # type: ignore[no-untyped-def]
    world: World, settings, clean_redis: Redis
) -> None:
    async with running_app(settings) as (app, client):
        sid = app.state.auth_module.cookies.unsign(await bff_login(client, world.owner_phone))
        token = await csrf_token(client)
        url = f"/api/v1/admin/users/{world.cashier_id}"
        headers = {"X-CSRF-Token": token, "Idempotency-Key": str(uuid7())}
        first = await client.patch(url, json={"status": "active"}, headers=headers)
        assert first.status_code == 200, first.text
        # the session is revoked elsewhere (admin/reuse) while bff:sess:* still exists
        await clean_redis.set(f"auth:sid_revoked:{sid}", "1", ex=300)
        again = await client.patch(url, json={"status": "active"}, headers=headers)
        assert again.status_code == 401


# --- COR-3: reuse revokes only the reused family (14 §7, QT-OAUTH-03) --------------------------------
async def test_reuse_revokes_only_the_reused_family(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine
) -> None:
    async with running_app(settings) as (_, client):
        await bff_login(client, world.owner_phone)  # a third, cookie session of the same user
        device_a = await android_tokens(client, world.owner_phone)
        device_b = await android_tokens(client, world.owner_phone)
        assert _claims(device_a["access_token"])["fam"] != _claims(device_b["access_token"])["fam"]
        rotated = await refresh(client, device_a["refresh_token"])
        assert rotated.status_code == 200, rotated.text
        at_a2 = rotated.json()["access_token"]
        await _age_used_at(admin_engine, device_a["refresh_token"])
        reuse = await refresh(client, device_a["refresh_token"])
        assert reuse.status_code == 400 and reuse.json()["error"] == "invalid_grant"

        r = await client.get("/auth/session", headers=bearer(at_a2))
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        r = await client.get("/auth/session", headers=bearer(device_a["access_token"]))
        assert r.status_code == 401
        # device B and the web session are untouched
        assert (
            await client.get("/auth/session", headers=bearer(device_b["access_token"]))
        ).status_code == 200
        assert (await refresh(client, device_b["refresh_token"])).status_code == 200
        assert (await client.get("/auth/session")).status_code == 200


# --- COR-11: a suspended family refuses any scope but sync.drain, without burning the RT (14 §16.4) ---
async def test_suspended_refresh_rejects_non_drain_scope_without_burning(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (_, client):
        tokens = await android_tokens(client, world.owner_phone)
        granted = str(_claims(tokens["access_token"])["scope"]).split()
        assert "sales" in granted
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE app.subscriptions SET status = 'restricted' WHERE tenant_id = :t"),
                {"t": world.tenant_id},
            )
            await conn.execute(text("SELECT app.auth_suspend_tenant(:t, true)"), {"t": world.tenant_id})
        await clean_redis.set(f"sub_status:{world.tenant_id}", "restricted")

        denied = await refresh(client, tokens["refresh_token"], scope="sales")
        assert denied.status_code == 400 and denied.json()["error"] == "invalid_scope", denied.text
        mixed = await refresh(client, tokens["refresh_token"], scope="sales sync.drain")
        assert mixed.status_code == 400 and mixed.json()["error"] == "invalid_scope"
        async with admin_engine.connect() as conn:
            used = (
                await conn.execute(
                    text("SELECT used_at, revoked_at FROM auth.refresh_tokens WHERE token_hash = :h"),
                    {"h": token_hash(tokens["refresh_token"])},
                )
            ).one()
        assert used.used_at is None and used.revoked_at is None  # not burnt

        drain = await refresh(client, tokens["refresh_token"], scope="sync.drain")
        assert drain.status_code == 200, drain.text
        assert drain.json()["scope"] == "sync.drain"
        plain = await refresh(client, drain.json()["refresh_token"])
        assert plain.status_code == 200 and plain.json()["scope"] == "sync.drain"
