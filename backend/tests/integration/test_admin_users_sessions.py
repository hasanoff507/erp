"""BO-11 sessions/devices (US-M13-07, QT-M13-07) and the RS revoked-device rejection (16 §9, 14 §21).

Real Postgres/Redis, no mocks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.auth.application.gateway import mark_device_revoked
from app.modules.auth.application.tokens import token_hash
from tests.conftest import MigratedDb
from tests.support.admin_users import (
    StaffWorld,
    audit_actions,
    claims_of,
    idem,
    invite,
    live_sessions,
    make_staff_world,
    owner_headers,
    set_password,
)
from tests.support.auth import (
    android_tokens,
    auth_settings,
    bearer,
    bff_login,
    client_at,
    new_phone,
    refresh,
    running_app,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def world(
    oauth_platform: None, app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> StaffWorld:
    return await make_staff_world(app_db, admin_engine, "Sessiya do'koni")


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str) -> Settings:
    return auth_settings(migrated_db, redis_url, otp_dev_fakes=True)


@pytest.fixture
async def app_client(settings: Settings) -> AsyncIterator[tuple[Any, Any]]:
    async with running_app(settings) as pair:
        yield pair


async def _staff(client: Any, db: Database, world: StaffWorld, owner: str) -> tuple[UUID, str]:
    phone = new_phone()
    r = await invite(
        client, owner, phone=phone, role_ids=[world.roles["cashier"]], branch_ids=[world.branch_id]
    )
    assert r.status_code == 201, r.text
    user_id = UUID(r.json()["user_id"])
    await set_password(db, user_id)
    return user_id, phone


async def _device(admin_engine: AsyncEngine, world: StaffWorld, kind: str = "android") -> tuple[UUID, UUID]:
    """A cash register + device of the tenant (what device registration will create in Bosqich 3)."""
    register_id, device_id = uuid7(), uuid7()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) "
                "VALUES (:id, :t, :b, :name, :kind)"
            ),
            {"id": register_id, "t": world.tenant_id, "b": world.branch_id, "name": f"K-{register_id.hex[-4:]}",
             "kind": "android" if kind == "android" else "web"},
        )  # fmt: skip
        await conn.execute(
            text(
                "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind, app_version, last_seen_at) "
                "VALUES (:id, :t, :c, :kind, '1.0.0', now())"
            ),
            {"id": device_id, "t": world.tenant_id, "c": register_id, "kind": kind},
        )
    return register_id, device_id


async def _bind_family(admin_engine: AsyncEngine, refresh_token: str, device_id: UUID) -> None:
    """Device-bound refresh family (14 §7: Android login with a registered device)."""
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE auth.refresh_tokens SET device_id = :d WHERE family_id = "
                "(SELECT family_id FROM auth.refresh_tokens WHERE token_hash = :h)"
            ),
            {"d": device_id, "h": token_hash(refresh_token)},
        )


# --- QT-M13-07 / US-M13-07 --------------------------------------------------------------------------------
async def test_qt_m13_07_revoking_one_session_leaves_the_other(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff(client, app_db, world, owner)
    async with client_at(app, "10.0.1.1") as web1, client_at(app, "10.0.1.2") as web2:
        await bff_login(web1, phone)
        await bff_login(web2, phone)
        cookies = app.state.auth_module.cookies
        sid1 = cookies.unsign(web1.cookies.get("__Host-sid"))
        sid2 = cookies.unsign(web2.cookies.get("__Host-sid"))

        listed = await client.get(f"/api/v1/admin/users/{user_id}/sessions", headers=bearer(owner))
        assert listed.status_code == 200, listed.text
        items = listed.json()["items"]
        assert {i["session_id"] for i in items} == {str(sid1), str(sid2)}
        one = next(i for i in items if i["session_id"] == str(sid1))
        assert set(one) == {
            "session_id", "client_id", "device_id", "device_kind", "created_at", "last_seen_at", "ip",
            "user_agent", "current",
        }  # fmt: skip
        assert one["client_id"] == "web-bff" and one["ip"] == "10.0.1.1" and one["current"] is False
        assert one["created_at"] and one["last_seen_at"]

        r = await client.post(
            f"/api/v1/admin/users/{user_id}/sessions/{sid1}/revoke", headers=owner_headers(owner)
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"user_id": str(user_id), "sessions_revoked": 1}
        assert (await web1.get("/auth/session")).status_code == 401  # immediately, back to login
        assert (await web2.get("/auth/session")).status_code == 200  # the other one is untouched
        after = (await client.get(f"/api/v1/admin/users/{user_id}/sessions", headers=bearer(owner))).json()
        assert [i["session_id"] for i in after["items"]] == [str(sid2)]

        again = await client.post(
            f"/api/v1/admin/users/{user_id}/sessions/{sid1}/revoke", headers=owner_headers(owner)
        )
        assert again.status_code == 404  # already gone
        foreign = await client.post(
            f"/api/v1/admin/users/{world.owner_id}/sessions/{sid2}/revoke", headers=owner_headers(owner)
        )
        assert foreign.status_code == 404  # the session must belong to that user
    assert "session_revoked" in await audit_actions(admin_engine, world.tenant_id)


async def test_revoke_sessions_ends_every_session_and_device_token(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff(client, app_db, world, owner)
    async with client_at(app, "10.0.2.1") as web:
        await bff_login(web, phone)
        android = await android_tokens(client, phone)
        r = await client.post(f"/api/v1/admin/users/{user_id}/revoke-sessions", headers=owner_headers(owner))
        assert r.status_code == 200, r.text
        assert r.json() == {"user_id": str(user_id), "sessions_revoked": 1}
        assert (await web.get("/auth/session")).status_code == 401
        sid_less = await client.get("/auth/session", headers=bearer(android["access_token"]))
        assert sid_less.status_code == 401 and sid_less.json()["error"]["code"] == "TOKEN_REVOKED"
        assert (await refresh(client, android["refresh_token"])).status_code == 400
    assert await live_sessions(admin_engine, user_id) == 0
    # the owner's own sessions are not affected, and the user may log in again (not blocked)
    assert (await client.get("/auth/session", headers=bearer(owner))).status_code == 200
    assert (await android_tokens(client, phone))["access_token"]
    assert "all_sessions_revoked" in await audit_actions(admin_engine, world.tenant_id)


async def test_owner_sees_current_flag_on_own_cookie_session(world: StaffWorld, app_client: Any) -> None:
    app, _ = app_client
    async with client_at(app, "10.0.3.1") as web:
        await bff_login(web, world.owner_phone)
        sid = app.state.auth_module.cookies.unsign(web.cookies.get("__Host-sid"))
        items = (await web.get(f"/api/v1/admin/users/{world.owner_id}/sessions")).json()["items"]
        assert [i["current"] for i in items if i["session_id"] == str(sid)] == [True]


async def test_devices_of_a_user(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff(client, app_db, world, owner)
    web_register, web_device = await _device(admin_engine, world, "web")
    pos_register, pos_device = await _device(admin_engine, world, "android")
    _, other_device = await _device(admin_engine, world, "android")
    async with client_at(app, "10.0.4.1") as web:
        await bff_login(web, phone)
        sid = app.state.auth_module.cookies.unsign(web.cookies.get("__Host-sid"))
        async with admin_engine.begin() as conn:
            # a web-kassa session bound to its device; a shift the user opened on the Android POS
            await conn.execute(
                text("UPDATE auth.sessions SET device_id = :d WHERE id = :s"), {"d": web_device, "s": sid}
            )
            await conn.execute(
                text(
                    "INSERT INTO app.shifts (tenant_id, branch_id, cash_register_id, device_id, shift_no, opened_by) "
                    "VALUES (:t, :b, :c, :d, 1, :u)"
                ),
                {
                    "t": world.tenant_id,
                    "b": world.branch_id,
                    "c": pos_register,
                    "d": pos_device,
                    "u": user_id,
                },
            )
        sessions = (await client.get(f"/api/v1/admin/users/{user_id}/sessions", headers=bearer(owner))).json()
        assert (
            sessions["items"][0]["device_id"] == str(web_device)
            and sessions["items"][0]["device_kind"] == "web"
        )
        r = await client.get(f"/api/v1/admin/users/{user_id}/devices", headers=bearer(owner))
        assert r.status_code == 200, r.text
        items = {i["id"]: i for i in r.json()["items"]}
        assert set(items) == {str(web_device), str(pos_device)}  # not the device the user never used
        assert str(other_device) not in items
        pos = items[str(pos_device)]
        assert pos["kind"] == "android" and pos["cash_register_id"] == str(pos_register)
        assert pos["branch_id"] == str(world.branch_id) and pos["app_version"] == "1.0.0"
        assert pos["revoked_at"] is None and pos["cash_register_name"].startswith("K-")
        assert items[str(web_device)]["cash_register_id"] == str(web_register)


# --- revoked device → 403 DEVICE_REVOKED (16 §9, 14 §21) ----------------------------------------------------
async def test_revoked_device_token_is_rejected_immediately(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    _, phone = await _staff(client, app_db, world, owner)
    _, device_id = await _device(admin_engine, world)
    tokens = await android_tokens(client, phone)
    await _bind_family(admin_engine, tokens["refresh_token"], device_id)
    rotated = await refresh(client, tokens["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    access = rotated.json()["access_token"]
    assert claims_of(access)["device_id"] == str(device_id)
    assert (
        await client.get("/auth/session", headers=bearer(access))
    ).status_code == 200  # positive cache now set

    async with admin_engine.begin() as conn:
        await conn.execute(text("UPDATE app.devices SET revoked_at = now() WHERE id = :d"), {"d": device_id})
    await mark_device_revoked(clean_redis, device_id)  # what POST /devices/{id}/revoke calls after commit
    r = await client.get("/auth/session", headers=bearer(access))
    assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_REVOKED"
    # no Idempotency-Key replay either: a write is refused the same way
    w = await client.post(
        f"/api/v1/admin/users/{world.owner_id}/reset-pin", headers={**bearer(access), **idem()}
    )
    assert w.status_code == 403


async def test_revoked_device_is_caught_by_the_database_fallback(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    """Without the Redis marker the RS still refuses once the positive cache (≤ 30 s) is gone."""
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    _, phone = await _staff(client, app_db, world, owner)
    _, device_id = await _device(admin_engine, world)
    tokens = await android_tokens(client, phone)
    await _bind_family(admin_engine, tokens["refresh_token"], device_id)
    access = (await refresh(client, tokens["refresh_token"])).json()["access_token"]
    assert (await client.get("/auth/session", headers=bearer(access))).status_code == 200
    assert await clean_redis.exists(f"auth:device_ok:{device_id}")
    async with admin_engine.begin() as conn:
        await conn.execute(text("UPDATE app.devices SET revoked_at = now() WHERE id = :d"), {"d": device_id})
    await clean_redis.delete(f"auth:device_ok:{device_id}")  # the 30 s positive cache expired
    r = await client.get("/auth/session", headers=bearer(access))
    assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_REVOKED"
    assert await clean_redis.exists(f"auth:device_revoked:{device_id}")  # cached for the next request
