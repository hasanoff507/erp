"""BO-11 ``PATCH /admin/users/{id}`` — block/unblock, roles/branches, "claims stale", owner guard.

US-M13-05, QT-M13-05 (QT-OAUTH-07 semantics: immediate), QT-M13-09, 14 §5. Real Postgres/Redis, no mocks.
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
from tests.conftest import MigratedDb
from tests.support.admin_users import (
    StaffWorld,
    add_branch,
    audit_actions,
    claims_of,
    invite,
    live_sessions,
    make_staff_world,
    owner_headers,
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
    return await make_staff_world(app_db, admin_engine, "Bloklash do'koni")


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str) -> Settings:
    return auth_settings(migrated_db, redis_url, otp_dev_fakes=True)


@pytest.fixture
async def app_client(settings: Settings) -> AsyncIterator[tuple[Any, Any]]:
    async with running_app(settings) as pair:
        yield pair


async def _staff(
    client: Any, db: Database, world: StaffWorld, owner: str, roles: list[str]
) -> tuple[UUID, str]:
    phone = new_phone()
    r = await invite(
        client, owner, phone=phone, role_ids=[world.roles[c] for c in roles], branch_ids=[world.branch_id]
    )
    assert r.status_code == 201, r.text
    user_id = UUID(r.json()["user_id"])
    await set_password(db, user_id)
    return user_id, phone


async def _patch(client: Any, owner: str, user_id: UUID, body: dict[str, Any]) -> Any:
    return await client.patch(f"/api/v1/admin/users/{user_id}", json=body, headers=owner_headers(owner))


# --- QT-M13-05 / US-M13-05 ----------------------------------------------------------------------------------
async def test_qt_m13_05_block_revokes_now_and_unblock_restores_login(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff(client, app_db, world, owner, ["cashier"])
    async with client_at(app, "10.0.0.9") as web:
        await bff_login(web, phone)
        android = await android_tokens(client, phone)
        assert (await web.get("/auth/session")).status_code == 200
        assert (await client.get("/auth/session", headers=bearer(android["access_token"]))).status_code == 200

        blocked = await _patch(client, owner, user_id, {"status": "blocked"})
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["status"] == "blocked" and blocked.json()["sessions_revoked"] >= 1

        # immediately — the very next request, not the next refresh
        assert (await web.get("/auth/session")).status_code == 401
        r = await client.get("/auth/session", headers=bearer(android["access_token"]))
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        assert (await refresh(client, android["refresh_token"])).status_code == 400
        assert await live_sessions(admin_engine, user_id) == 0
        denied = await login_for_code(client, phone, PASSWORD, authorize_params(Pkce.new()))
        assert denied.status_code == 403  # cannot log in until unblocked

        listed = (await client.get("/api/v1/admin/users", headers=bearer(owner))).json()
        assert {i["user_id"]: i["status"] for i in listed["items"]}[str(user_id)] == "blocked"

        unblocked = await _patch(client, owner, user_id, {"status": "active"})
        assert unblocked.json() == {"user_id": str(user_id), "status": "active", "sessions_revoked": 0}
        assert (await android_tokens(client, phone))["access_token"]
    actions = await audit_actions(admin_engine, world.tenant_id)
    for action in ("membership_status_changed", "user_blocked", "all_sessions_revoked", "user_unblocked"):
        assert action in actions


# --- QT-M13-09 -------------------------------------------------------------------------------------------
async def test_qt_m13_09_owner_cannot_block_himself_or_drop_the_owner_role(
    world: StaffWorld, app_client: Any, admin_engine: AsyncEngine
) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    self_block = await _patch(client, owner, world.owner_id, {"status": "blocked"})
    assert self_block.status_code == 422
    assert self_block.json()["error"]["details"] == [
        {"field": "status", "message_key": "validation.cannot_block_self"}
    ]
    drop_owner = await _patch(client, owner, world.owner_id, {"role_ids": [str(world.roles["manager"])]})
    assert drop_owner.status_code == 422
    assert drop_owner.json()["error"]["details"] == [
        {"field": "role_ids", "message_key": "validation.owner_role_not_assignable"}
    ]
    async with admin_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, role_ids FROM app.memberships WHERE tenant_id = :t AND user_id = :u"),
                {"t": world.tenant_id, "u": world.owner_id},
            )
        ).one()
    assert row.status == "active" and list(row.role_ids) == [world.roles["owner"]]
    # the owner can still manage his own non-owner extras (owner role kept)
    keep = await _patch(
        client, owner, world.owner_id, {"role_ids": [str(world.roles["owner"]), str(world.roles["cashier"])]}
    )
    assert keep.status_code == 200, keep.text


async def test_qt_m13_09_last_active_owner_is_never_blocked(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """A custom role holding ``settings.users`` (US-M13-03) cannot touch an owner (SEC-07, OWNER_ONLY)."""
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    hr_role = uuid7()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO app.roles (id, tenant_id, name) VALUES (:id, :t, 'Kadrlar')"),
            {"id": hr_role, "t": world.tenant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO app.role_permissions (tenant_id, role_id, permission_code) "
                "VALUES (:t, :r, 'settings.users')"
            ),
            {"t": world.tenant_id, "r": hr_role},
        )
    phone = new_phone()
    r = await invite(client, owner, phone=phone, role_ids=[hr_role], branch_ids=[world.branch_id])
    assert r.status_code == 201, r.text
    await set_password(app_db, UUID(r.json()["user_id"]))
    hr = (await android_tokens(client, phone))["access_token"]

    # SEC-07: settings.users alone never reaches an owner's membership — 403 OWNER_ONLY everywhere
    target = f"/api/v1/admin/users/{world.owner_id}"
    for refused in (
        await _patch(client, hr, world.owner_id, {"status": "blocked"}),
        await _patch(client, hr, world.owner_id, {"branch_ids": [str(world.branch_id)]}),
        await client.post(f"{target}/reset-password", headers=owner_headers(hr)),
        await client.post(f"{target}/reset-pin", headers=owner_headers(hr)),
        await client.post(f"{target}/revoke-sessions", headers=owner_headers(hr)),
        await client.post(f"{target}/sessions/{uuid7()}/revoke", headers=owner_headers(hr)),
    ):
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "OWNER_ONLY"
    assert (await client.get("/auth/session", headers=bearer(owner))).status_code == 200  # untouched
    async with admin_engine.connect() as conn:
        creds = (
            await conn.execute(
                text("SELECT password_hash FROM auth.user_credentials WHERE user_id = :u"),
                {"u": world.owner_id},
            )
        ).scalar()
    assert creds is not None

    # an owner may act on another owner; the tenant still keeps one active owner
    second_id, second_phone = await _staff(client, app_db, world, owner, ["manager"])
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE app.memberships SET role_ids = CAST(:r AS uuid[]) WHERE tenant_id = :t AND user_id = :u"
            ),
            {"r": [str(world.roles["owner"])], "t": world.tenant_id, "u": second_id},
        )
    second = (await android_tokens(client, second_phone))["access_token"]
    assert (await _patch(client, second, world.owner_id, {"status": "blocked"})).status_code == 200
    refused = await _patch(client, second, second_id, {"status": "blocked"})
    assert refused.status_code == 422  # never himself (and never the last active owner)


async def test_patch_validates_input_and_unknown_user(world: StaffWorld, app_client: Any) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    empty = await _patch(client, owner, world.owner_id, {})
    assert empty.status_code == 422
    unknown = await _patch(client, owner, UUID(int=7), {"status": "active"})
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "NOT_FOUND"
    bad = await _patch(client, owner, world.owner_id, {"status": "deleted"})
    assert bad.status_code == 422
    no_roles = await _patch(client, owner, world.owner_id, {"role_ids": []})
    assert no_roles.status_code == 422


# --- 14 §5 "claims stale" (QT-M13-01/02 user side through PATCH) ------------------------------------------
async def test_role_change_reissues_bearer_claims(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff(client, app_db, world, owner, ["cashier"])
    tokens = await android_tokens(client, phone)
    assert claims_of(tokens["access_token"])["roles"] == ["cashier"]

    same = await _patch(client, owner, user_id, {"role_ids": [str(world.roles["cashier"])]})
    assert same.status_code == 200
    assert (await client.get("/auth/session", headers=bearer(tokens["access_token"]))).status_code == 200

    second = await add_branch(admin_engine, world.tenant_id, "07", "Yunusobod")
    changed = await _patch(
        client, owner, user_id,
        {"role_ids": [str(world.roles["cashier"]), str(world.roles["storekeeper"])], "branch_ids": [str(second)]},
    )  # fmt: skip
    assert changed.status_code == 200, changed.text
    stale = await client.get("/auth/session", headers=bearer(tokens["access_token"]))
    assert stale.status_code == 401 and stale.json()["error"]["code"] == "TOKEN_EXPIRED"
    renewed = await refresh(client, tokens["refresh_token"])
    assert renewed.status_code == 200, renewed.text
    claims = claims_of(renewed.json()["access_token"])
    assert sorted(claims["roles"]) == ["cashier", "storekeeper"]
    assert claims["branch_ids"] == [str(second)]
    session = await client.get("/auth/session", headers=bearer(renewed.json()["access_token"]))
    assert session.status_code == 200 and sorted(session.json()["roles"]) == ["cashier", "storekeeper"]
    assert [b["id"] for b in session.json()["branches"]] == [str(second)]
    assert "membership_changed" in await audit_actions(admin_engine, world.tenant_id)


async def test_role_change_refreshes_cookie_session_server_side(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    user_id, phone = await _staff(client, app_db, world, owner, ["cashier"])
    async with client_at(app, "10.0.0.11") as web:
        await bff_login(web, phone)
        first = await web.get("/auth/session")
        assert first.status_code == 200 and first.json()["roles"] == ["cashier"]  # profile now cached
        sid = app.state.auth_module.cookies.unsign(web.cookies.get("__Host-sid"))
        before = await _current_rt(admin_engine, sid)

        r = await _patch(client, owner, user_id, {"role_ids": [str(world.roles["manager"])]})
        assert r.status_code == 200, r.text
        now = await web.get("/auth/session")
        assert now.status_code == 200  # the browser notices nothing
        assert now.json()["roles"] == ["manager"]  # profile cache dropped, ≤ 60 s rule not even needed
        assert "settings.users" not in now.json()["permissions"]
        after = await _current_rt(admin_engine, sid)
        assert after != before  # access token re-issued (forced refresh of the session)
        assert (await web.get("/auth/session")).status_code == 200
        assert await _current_rt(admin_engine, sid) == after  # once — the new token is current


async def _current_rt(admin_engine: AsyncEngine, sid: Any) -> Any:
    async with admin_engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT current_refresh_token_id FROM auth.sessions WHERE id = :s"), {"s": sid}
            )
        ).scalar()
