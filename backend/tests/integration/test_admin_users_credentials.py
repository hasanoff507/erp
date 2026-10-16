"""BO-11 reset-password / reset-pin (US-M13-06, QT-M13-06, 14 §4.2/§18.2). Real Postgres/Redis, no mocks."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.db.session import Database, unscoped_transaction
from app.core.errors import AppError
from app.modules.auth.application.passwords import hash_pin
from tests.conftest import MigratedDb
from tests.support.admin_users import (
    StaffWorld,
    audit_actions,
    credentials,
    invite,
    live_sessions,
    make_staff_world,
    message_texts,
    owner_headers,
    sent_code,
    set_password,
)
from tests.support.auth import (
    PASSWORD,
    Pkce,
    android_tokens,
    auth_settings,
    authorize_params,
    bearer,
    bff_login,
    client_at,
    login_for_code,
    new_phone,
    refresh,
    running_app,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def world(
    oauth_platform: None, app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> StaffWorld:
    return await make_staff_world(app_db, admin_engine, "Tiklash do'koni")


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str) -> Settings:
    return auth_settings(migrated_db, redis_url, otp_dev_fakes=True)


@pytest.fixture
async def app_client(settings: Settings) -> AsyncIterator[tuple[Any, Any]]:
    async with running_app(settings) as pair:
        yield pair


async def _staff_with_pin(
    client: Any, db: Database, admin_engine: AsyncEngine, world: StaffWorld, owner: str
) -> tuple[UUID, str]:
    phone = new_phone()
    r = await invite(
        client, owner, phone=phone, role_ids=[world.roles["cashier"]], branch_ids=[world.branch_id]
    )
    assert r.status_code == 201, r.text
    user_id = UUID(r.json()["user_id"])
    await set_password(db, user_id)
    async with db.session_factory() as s, unscoped_transaction(s):
        await s.execute(
            text("SELECT app.auth_set_credentials(:u, NULL, :p)"), {"u": user_id, "p": hash_pin("4321")}
        )
    creds = await credentials(admin_engine, user_id)
    assert creds.password_hash and creds.pin_hash
    return user_id, phone


# --- QT-M13-06 / US-M13-06 --------------------------------------------------------------------------------
async def test_qt_m13_06_reset_password_kills_sessions_and_sends_admin_reset_code(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff_with_pin(client, app_db, admin_engine, world, owner)
    async with client_at(app, "10.0.0.21") as web:
        await bff_login(web, phone)
        android = await android_tokens(client, phone)

        r = await client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=owner_headers(owner))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user_id"] == str(user_id) and body["sessions_revoked"] >= 1
        assert body["channel_used"] == "sms"

        # every session ends now
        assert (await web.get("/auth/session")).status_code == 401
        stale = await client.get("/auth/session", headers=bearer(android["access_token"]))
        assert stale.status_code == 401 and stale.json()["error"]["code"] == "TOKEN_REVOKED"
        assert (await refresh(client, android["refresh_token"])).status_code == 400
    assert await live_sessions(admin_engine, user_id) == 0
    # the old password no longer works
    denied = await login_for_code(client, phone, PASSWORD, authorize_params(Pkce.new()))
    assert denied.status_code != 302
    creds = await credentials(admin_engine, user_id)
    assert creds.password_hash is None and creds.must_change_password is True
    assert creds.pin_hash is not None  # reset-password touches only the password
    # a one-time admin_reset code — never the password itself
    channel, code = sent_code(app, phone)
    assert channel == "sms" and len(code) == 6
    assert all(PASSWORD not in t for t in message_texts(app, phone))
    async with admin_engine.connect() as conn:
        purpose = (
            await conn.execute(
                text("SELECT purpose FROM auth.otp_challenges WHERE phone = :p ORDER BY id DESC LIMIT 1"),
                {"p": phone},
            )
        ).scalar()
    assert purpose == "admin_reset"
    actions = await audit_actions(admin_engine, world.tenant_id)
    assert "password_reset" in actions and "all_sessions_revoked" in actions


async def test_qt_m13_06_reset_pin_forces_a_new_pin_and_keeps_sessions(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff_with_pin(client, app_db, admin_engine, world, owner)
    android = await android_tokens(client, phone)
    r = await client.post(f"/api/v1/admin/users/{user_id}/reset-pin", headers=owner_headers(owner))
    assert r.status_code == 200, r.text
    assert r.json() == {"user_id": str(user_id), "sessions_revoked": 0, "channel_used": "sms"}
    creds = await credentials(admin_engine, user_id)
    assert creds.pin_hash is None and creds.must_change_pin is True
    assert creds.password_hash is not None and creds.must_change_password is False
    assert (await client.get("/auth/session", headers=bearer(android["access_token"]))).status_code == 200
    channel, _ = sent_code(app, phone)
    assert channel == "sms"
    async with admin_engine.connect() as conn:
        purpose = (
            await conn.execute(
                text("SELECT purpose FROM auth.otp_challenges WHERE phone = :p ORDER BY id DESC LIMIT 1"),
                {"p": phone},
            )
        ).scalar()
    assert purpose == "pin_reset"
    assert "pin_reset_forced" in await audit_actions(admin_engine, world.tenant_id)


async def test_reset_is_rolled_back_when_no_code_can_be_sent(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff_with_pin(client, app_db, admin_engine, world, owner)
    android = await android_tokens(client, phone)
    module = app.state.auth_module
    limited = False
    for _ in range(module.settings.otp_sms_per_phone_day):  # exhaust the per-phone SMS limit
        try:
            await module.otp.issue(phone, "recovery", ip="10.2.2.2")
        except AppError as exc:
            limited = exc.code == "RATE_LIMITED"
            break
    assert limited
    r = await client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=owner_headers(owner))
    assert r.status_code == 429
    creds = await credentials(admin_engine, user_id)
    assert creds.password_hash is not None and creds.must_change_password is False  # nothing changed
    assert (await client.get("/auth/session", headers=bearer(android["access_token"]))).status_code == 200
