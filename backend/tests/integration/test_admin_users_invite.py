"""BO-11 ``POST/GET /admin/users`` — invite, link, validation, RLS (US-M13-01/02/04, QT-M13-01/02/04).

Real PostgreSQL + Redis; OTP through the dev fakes (ERP_OTP_DEV_FAKES, qaror #34). No mocks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

import pytest
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.db.session import Database
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from tests.conftest import MigratedDb
from tests.support.admin_users import (
    StaffWorld,
    add_branch,
    audit_actions,
    invite,
    make_staff_world,
    message_texts,
    owner_headers,
    sent_code,
    set_password,
)
from tests.support.auth import (
    ISSUER,
    PASSWORD,
    Pkce,
    android_tokens,
    auth_settings,
    authorize_params,
    bearer,
    exchange_code,
    login_for_code,
    new_phone,
    query_of,
    running_app,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def world(
    oauth_platform: None, app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> StaffWorld:
    return await make_staff_world(app_db, admin_engine, "BO-11 do'kon")


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str) -> Settings:
    return auth_settings(migrated_db, redis_url, otp_dev_fakes=True)


@pytest.fixture
async def app_client(settings: Settings) -> AsyncIterator[tuple[Any, Any]]:
    async with running_app(settings) as pair:
        yield pair


async def _role_permissions(admin_engine: AsyncEngine, role_ids: list[UUID]) -> set[str]:
    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT permission_code FROM app.role_permissions WHERE role_id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [str(r) for r in role_ids]},
        )
        return {r[0] for r in rows}


def _add_probe_routes(app: Any) -> None:
    """Real ``require_permission`` / ``current_branch_scope`` dependencies behind throw-away routes."""

    for code in ("sales.create", "catalog.manage", "discount.give", "settings.users"):

        def make(code: str) -> Any:
            # a default (not an Annotated string under ``from __future__``) — ``code`` is a closure value
            async def probe(grant: PermissionGrant = Depends(require_permission(code))) -> dict[str, Any]:  # noqa: B008
                limit = None if grant.limit_value is None else str(grant.limit_value)
                return {"code": grant.code, "limit_value": limit}

            return probe

        app.add_api_route(f"/api/v1/_probe/{code}", make(code), methods=["GET"])

    async def branch_probe(scope: Annotated[BranchScope, Depends(current_branch_scope)]) -> dict[str, Any]:
        return {"allowed": [str(b) for b in scope.allowed], "current": str(scope.current)}

    app.add_api_route("/api/v1/_probe/branch", branch_probe, methods=["GET"])


# --- QT-M13-04 / US-M13-04 -------------------------------------------------------------------------------
async def test_qt_m13_04_invite_sends_one_time_code_never_a_secret(
    world: StaffWorld, app_client: Any, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = await android_tokens(client, world.owner_phone)
    phone = new_phone()
    r = await invite(
        client,
        owner["access_token"],
        phone=phone,
        role_ids=[world.roles["cashier"]],
        branch_ids=[world.branch_id],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {
        "user_id", "name", "phone", "role_ids", "branch_ids", "status", "last_login_at", "channel_used",
    }  # fmt: skip
    assert body["phone"] == phone and body["name"] == "Dilnoza Karimova" and body["status"] == "active"
    assert body["role_ids"] == [str(world.roles["cashier"])] and body["branch_ids"] == [str(world.branch_id)]
    assert body["last_login_at"] is None
    # Telegram first, SMS fallback: a fresh phone has no Telegram link → SMS (14 §4.2)
    channel, code = sent_code(app, phone)
    assert body["channel_used"] == channel == "sms"
    assert len(code) == 6
    # the message carries only the code: no password/PIN
    assert all(PASSWORD not in t for t in message_texts(app, phone))
    user_id = UUID(body["user_id"])
    async with admin_engine.connect() as conn:
        m = (
            await conn.execute(
                text(
                    "SELECT status, role_ids, branch_ids FROM app.memberships WHERE tenant_id = :t AND user_id = :u"
                ),
                {"t": world.tenant_id, "u": user_id},
            )
        ).one()
        challenge = (
            await conn.execute(
                text(
                    "SELECT purpose, channel FROM auth.otp_challenges WHERE phone = :p ORDER BY id DESC LIMIT 1"
                ),
                {"p": phone},
            )
        ).one()
        creds = (
            await conn.execute(
                text("SELECT password_hash, pin_hash FROM auth.user_credentials WHERE user_id = :u"),
                {"u": user_id},
            )
        ).one()
    assert m.status == "active" and list(m.role_ids) == [world.roles["cashier"]]
    assert (challenge.purpose, challenge.channel) == ("invite", "sms")
    assert creds.password_hash is None and creds.pin_hash is None  # the invitee sets them himself
    assert "user_created" in await audit_actions(admin_engine, world.tenant_id)

    listed = await client.get("/api/v1/admin/users", headers=bearer(owner["access_token"]))
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["next_cursor"] is None
    assert {i["user_id"] for i in page["items"]} == {str(world.owner_id), str(user_id)}


async def test_invite_rejects_phone_already_member_and_validates_input(
    world: StaffWorld, app_client: Any
) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    cashier = [world.roles["cashier"]]
    r = await invite(client, owner, phone=world.owner_phone, role_ids=cashier, branch_ids=[world.branch_id])
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [
        {"field": "phone", "message_key": "validation.phone_already_member"}
    ]
    phone = new_phone()
    assert (
        await invite(client, owner, phone=phone, role_ids=cashier, branch_ids=[world.branch_id])
    ).status_code == 201
    again = await invite(client, owner, phone=phone, role_ids=cashier, branch_ids=[world.branch_id])
    assert again.status_code == 422 and again.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_phone = await invite(
        client, owner, phone="+7 900 123", role_ids=cashier, branch_ids=[world.branch_id]
    )
    assert bad_phone.status_code == 422 and bad_phone.json()["error"]["details"][0]["field"] == "phone"
    no_roles = await invite(client, owner, phone=new_phone(), role_ids=[], branch_ids=[world.branch_id])
    assert no_roles.status_code == 422 and no_roles.json()["error"]["details"][0]["field"] == "role_ids"
    no_branch = await invite(client, owner, phone=new_phone(), role_ids=cashier, branch_ids=[])
    assert no_branch.status_code == 422 and no_branch.json()["error"]["details"][0]["field"] == "branch_ids"
    owner_role = await invite(
        client, owner, phone=new_phone(), role_ids=[world.roles["owner"]], branch_ids=[world.branch_id]
    )
    assert owner_role.json()["error"]["details"] == [
        {"field": "role_ids", "message_key": "validation.owner_role_not_assignable"}
    ]
    extra = await client.post(
        "/api/v1/admin/users",
        json={"phone": new_phone(), "name": "Ali", "role_ids": [], "branch_ids": [], "password": "x"},
        headers=owner_headers(owner),
    )
    assert extra.status_code == 422  # extra="forbid": a password can never be posted


async def test_invite_validates_roles_and_branches_belong_to_tenant(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    _, client = app_client
    other = await make_staff_world(app_db, admin_engine, "Boshqa do'kon")
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    foreign_role = await invite(
        client, owner, phone=new_phone(), role_ids=[other.roles["cashier"]], branch_ids=[world.branch_id]
    )
    assert foreign_role.status_code == 422
    assert foreign_role.json()["error"]["details"] == [
        {"field": "role_ids", "message_key": "validation.role_not_found"}
    ]
    foreign_branch = await invite(
        client, owner, phone=new_phone(), role_ids=[world.roles["cashier"]], branch_ids=[other.branch_id]
    )
    assert foreign_branch.json()["error"]["details"] == [
        {"field": "branch_ids", "message_key": "validation.branch_not_found"}
    ]


async def _membership(admin_engine: AsyncEngine, tenant_id: UUID, user_id: UUID) -> Any:
    async with admin_engine.connect() as conn:
        return (
            await conn.execute(
                text(
                    "SELECT status, invited_name FROM app.memberships WHERE tenant_id = :t AND user_id = :u"
                ),
                {"t": tenant_id, "u": user_id},
            )
        ).one()


async def test_invite_of_an_existing_account_waits_for_acceptance(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """SEC-01/02 (14 §18.2): an existing account is ``invited`` — no access, no real name, no global reset."""
    app, client = app_client
    other = await make_staff_world(app_db, admin_engine, "Qo'shni do'kon")
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    r = await invite(
        client, owner, phone=other.owner_phone, role_ids=[world.roles["manager"]], branch_ids=[world.branch_id],
        name="Boshqa ism",
    )  # fmt: skip
    assert r.status_code == 201, r.text
    assert r.json()["user_id"] == str(other.owner_id)  # the existing user is linked, not duplicated
    # the inviter sees what he typed, never the account's own name ("Egasi"), until acceptance
    assert r.json()["name"] == "Boshqa ism" and r.json()["status"] == "invited"
    assert sent_code(app, other.owner_phone)[0] == "sms"
    listed = (await client.get("/api/v1/admin/users", headers=bearer(owner))).json()["items"]
    row = next(i for i in listed if i["user_id"] == str(other.owner_id))
    assert (row["name"], row["status"]) == ("Boshqa ism", "invited")
    m = await _membership(admin_engine, world.tenant_id, other.owner_id)
    assert (m.status, m.invited_name) == ("invited", "Boshqa ism")
    async with admin_engine.connect() as conn:
        users = (
            await conn.execute(
                text("SELECT count(*) FROM app.users WHERE phone = :p"), {"p": other.owner_phone}
            )
        ).scalar()
        creds = (
            await conn.execute(
                text("SELECT password_hash FROM auth.user_credentials WHERE user_id = :u"),
                {"u": other.owner_id},
            )
        ).scalar()
    assert users == 1 and creds is not None  # the existing password is untouched

    # an invited membership gives no access: login, tenant choice and the token ignore it
    pkce = Pkce.new()
    refused = await login_for_code(
        client, other.owner_phone, PASSWORD, authorize_params(pkce, tenant_id=str(world.tenant_id))
    )
    assert "code=" not in refused.headers.get("location", "")
    own = await android_tokens(client, other.owner_phone)  # one active membership: no tenant chooser
    session = (await client.get("/auth/session", headers=bearer(own["access_token"]))).json()
    assert session["tenant"]["id"] == str(other.tenant_id)

    # the tenant may not reset a credential it does not own alone (password/PIN are global)
    for path in ("reset-password", "reset-pin"):
        reset = await client.post(
            f"/api/v1/admin/users/{other.owner_id}/{path}", headers=owner_headers(owner)
        )
        assert reset.status_code == 422, reset.text
        assert reset.json()["error"]["details"] == [
            {"field": "user_id", "message_key": "validation.credential_shared_across_tenants"}
        ]
    assert (await client.get("/auth/session", headers=bearer(own["access_token"]))).status_code == 200

    # a role change keeps the invite pending (never activates it on the inviter's behalf)
    roles_only = await client.patch(
        f"/api/v1/admin/users/{other.owner_id}",
        json={"role_ids": [str(world.roles["cashier"])]},
        headers=owner_headers(owner),
    )
    assert roles_only.status_code == 200 and roles_only.json()["status"] == "invited"

    # the account owner redeems the code: the membership becomes active, his password stays
    _, code = sent_code(app, other.owner_phone)  # the refused resets sent nothing
    accepted = await client.post(
        "/auth/otp/verify",
        json={"phone": other.owner_phone, "purpose": "invite", "code": code},
        headers={"Origin": ISSUER},
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["invite_accepted"] is True
    assert body["credential_token"] is None and body["credential_kinds"] is None  # no global reset
    m = await _membership(admin_engine, world.tenant_id, other.owner_id)
    assert (m.status, m.invited_name) == ("active", None)
    assert "membership_status_changed" in await audit_actions(admin_engine, world.tenant_id)
    listed = (await client.get("/api/v1/admin/users", headers=bearer(owner))).json()["items"]
    row = next(i for i in listed if i["user_id"] == str(other.owner_id))
    assert (row["name"], row["status"]) == ("Egasi", "active")  # now the account's own name

    # the linked user logs in to the new tenant with his own password
    pkce = Pkce.new()
    code = query_of(
        await login_for_code(
            client, other.owner_phone, PASSWORD, authorize_params(pkce, tenant_id=str(world.tenant_id))
        )
    )["code"]
    issued = await exchange_code(client, code, pkce.verifier)
    assert issued.status_code == 200, issued.text
    session = (await client.get("/auth/session", headers=bearer(issued.json()["access_token"]))).json()
    assert session["tenant"]["id"] == str(world.tenant_id) and session["roles"] == ["cashier"]

    # a member of two tenants: neither may reset the shared password/PIN; blocking/revoking still works
    for path in ("reset-password", "reset-pin"):
        reset = await client.post(
            f"/api/v1/admin/users/{other.owner_id}/{path}", headers=owner_headers(owner)
        )
        assert reset.status_code == 422, reset.text
    revoke = await client.post(
        f"/api/v1/admin/users/{other.owner_id}/revoke-sessions", headers=owner_headers(owner)
    )
    assert revoke.status_code == 200, revoke.text
    gone = await client.get("/auth/session", headers=bearer(issued.json()["access_token"]))
    assert gone.status_code == 401  # this tenant's token is revoked now
    # his session in the other tenant is untouched
    assert (await client.get("/auth/session", headers=bearer(own["access_token"]))).status_code == 200


async def test_unblocking_a_pending_invite_never_skips_the_acceptance(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    _, client = app_client
    other = await make_staff_world(app_db, admin_engine, "Uchinchi do'kon")
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    r = await invite(
        client,
        owner,
        phone=other.owner_phone,
        role_ids=[world.roles["cashier"]],
        branch_ids=[world.branch_id],
    )
    assert r.status_code == 201 and r.json()["status"] == "invited"
    target = f"/api/v1/admin/users/{other.owner_id}"
    blocked = await client.patch(target, json={"status": "blocked"}, headers=owner_headers(owner))
    assert blocked.status_code == 200 and blocked.json()["status"] == "blocked"
    listed = (await client.get("/api/v1/admin/users", headers=bearer(owner))).json()["items"]
    row = next(i for i in listed if i["user_id"] == str(other.owner_id))
    assert (row["name"], row["status"]) == ("Dilnoza Karimova", "blocked")  # still the typed name
    unblocked = await client.patch(target, json={"status": "active"}, headers=owner_headers(owner))
    assert unblocked.status_code == 200 and unblocked.json()["status"] == "invited"
    m = await _membership(admin_engine, world.tenant_id, other.owner_id)
    assert (m.status, m.invited_name) == ("invited", "Dilnoza Karimova")


async def test_invite_is_rolled_back_when_no_code_can_be_sent(
    world: StaffWorld, app_client: Any, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    phone = new_phone()
    module = app.state.auth_module
    for _ in range(module.settings.otp_sms_per_phone_day):
        await module.otp.issue(phone, "recovery", ip="10.1.1.1")
    r = await invite(
        client, owner, phone=phone, role_ids=[world.roles["cashier"]], branch_ids=[world.branch_id]
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    async with admin_engine.connect() as conn:
        count = (
            await conn.execute(text("SELECT count(*) FROM app.users WHERE phone = :p"), {"p": phone})
        ).scalar()
    assert count == 0  # nothing created without a delivered invite


async def test_invite_idempotency_key_replays_the_same_response(world: StaffWorld, app_client: Any) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    headers = owner_headers(owner)
    payload = {
        "phone": new_phone(), "name": "Sardor", "role_ids": [str(world.roles["cashier"])],
        "branch_ids": [str(world.branch_id)],
    }  # fmt: skip
    first = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    second = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert first.status_code == second.status_code == 201
    assert second.headers.get("idempotent-replayed") == "true"
    assert first.json() == second.json()
    missing = await client.post("/api/v1/admin/users", json=payload, headers=bearer(owner))
    assert missing.status_code == 422  # Idempotency-Key is mandatory on writes (17 §6)


async def test_list_is_cursor_paginated(world: StaffWorld, app_client: Any) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    for _ in range(3):
        r = await invite(
            client, owner, phone=new_phone(), role_ids=[world.roles["cashier"]], branch_ids=[world.branch_id]
        )
        assert r.status_code == 201
    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = (await client.get("/api/v1/admin/users", params=params, headers=bearer(owner))).json()
        seen += [i["user_id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 4
    bad = await client.get("/api/v1/admin/users", params={"cursor": "%%%"}, headers=bearer(owner))
    assert bad.status_code == 422 and bad.json()["error"]["details"][0]["field"] == "cursor"


# --- QT-M13-01 / QT-M13-02 (user side) — US-M13-01/02/04 ---------------------------------------------------
async def test_qt_m13_01_cashier_role_gives_cashier_permissions(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    _add_probe_routes(app)
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    phone = new_phone()
    r = await invite(
        client, owner, phone=phone, role_ids=[world.roles["cashier"]], branch_ids=[world.branch_id]
    )
    user_id = UUID(r.json()["user_id"])
    await set_password(app_db, user_id)
    token = (await android_tokens(client, phone))["access_token"]
    session = (await client.get("/auth/session", headers=bearer(token))).json()
    assert session["roles"] == ["cashier"]
    assert set(session["permissions"]) == await _role_permissions(admin_engine, [world.roles["cashier"]])
    assert (await client.get("/api/v1/_probe/sales.create", headers=bearer(token))).status_code == 200
    denied = await client.get("/api/v1/_probe/catalog.manage", headers=bearer(token))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "PERMISSION_DENIED"
    # non-owner: settings.users is owner-only (15 §2.2)
    assert (await client.get("/api/v1/_probe/settings.users", headers=bearer(token))).status_code == 403


async def test_qt_m13_02_two_roles_give_the_union_and_the_higher_right_wins(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    _add_probe_routes(app)
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    phone = new_phone()
    roles = [world.roles["cashier"], world.roles["storekeeper"]]
    r = await invite(client, owner, phone=phone, role_ids=roles, branch_ids=[world.branch_id])
    assert r.status_code == 201, r.text
    user_id = UUID(r.json()["user_id"])
    await set_password(app_db, user_id)
    token = (await android_tokens(client, phone))["access_token"]
    session = (await client.get("/auth/session", headers=bearer(token))).json()
    assert sorted(session["roles"]) == ["cashier", "storekeeper"]
    assert set(session["permissions"]) == await _role_permissions(admin_engine, roles)
    for code in ("sales.create", "catalog.manage"):  # one from each role
        assert (await client.get(f"/api/v1/_probe/{code}", headers=bearer(token))).status_code == 200
    capped = (await client.get("/api/v1/_probe/discount.give", headers=bearer(token))).json()
    assert Decimal(capped["limit_value"]) == Decimal("5.00")

    # adding the manager role (unlimited discount.give) through PATCH: the more generous limit wins
    patched = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role_ids": [str(r) for r in [*roles, world.roles["manager"]]]},
        headers=owner_headers(owner),
    )
    assert patched.status_code == 200, patched.text
    token = (await android_tokens(client, phone))["access_token"]
    widened = (await client.get("/api/v1/_probe/discount.give", headers=bearer(token))).json()
    assert widened["limit_value"] is None


async def test_us_m13_04_staff_sees_only_assigned_branches(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    app, client = app_client
    _add_probe_routes(app)
    second = await add_branch(admin_engine, world.tenant_id, "02", "Chilonzor-3")
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    phone = new_phone()
    r = await invite(client, owner, phone=phone, role_ids=[world.roles["cashier"]], branch_ids=[second])
    await set_password(app_db, UUID(r.json()["user_id"]))
    token = (await android_tokens(client, phone))["access_token"]
    session = (await client.get("/auth/session", headers=bearer(token))).json()
    assert [b["id"] for b in session["branches"]] == [str(second)]
    ok = await client.get("/api/v1/_probe/branch", headers={**bearer(token), "X-Branch-Id": str(second)})
    assert ok.status_code == 200 and ok.json()["allowed"] == [str(second)]
    closed = await client.get(
        "/api/v1/_probe/branch", headers={**bearer(token), "X-Branch-Id": str(world.branch_id)}
    )
    assert closed.status_code == 403 and closed.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"


# --- permission denial / RLS -------------------------------------------------------------------------------
async def test_non_owner_roles_are_denied(world: StaffWorld, app_client: Any, app_db: Database) -> None:
    _, client = app_client
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    phone = new_phone()
    r = await invite(
        client, owner, phone=phone, role_ids=[world.roles["manager"]], branch_ids=[world.branch_id]
    )
    await set_password(app_db, UUID(r.json()["user_id"]))
    manager = (await android_tokens(client, phone))["access_token"]
    for response in (
        await client.get("/api/v1/admin/users", headers=bearer(manager)),
        await invite(
            client,
            manager,
            phone=new_phone(),
            role_ids=[world.roles["cashier"]],
            branch_ids=[world.branch_id],
        ),
        await client.post(f"/api/v1/admin/users/{world.owner_id}/reset-pin", headers=owner_headers(manager)),
        await client.get(f"/api/v1/admin/users/{world.owner_id}/sessions", headers=bearer(manager)),
    ):
        assert response.status_code == 403 and response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_other_tenants_user_is_not_found(
    world: StaffWorld, app_client: Any, app_db: Database, admin_engine: AsyncEngine
) -> None:
    _, client = app_client
    other = await make_staff_world(app_db, admin_engine, "Begona do'kon")
    owner = (await android_tokens(client, world.owner_phone))["access_token"]
    target = other.owner_id
    calls = [
        await client.patch(
            f"/api/v1/admin/users/{target}", json={"status": "blocked"}, headers=owner_headers(owner)
        ),
        await client.post(f"/api/v1/admin/users/{target}/reset-password", headers=owner_headers(owner)),
        await client.post(f"/api/v1/admin/users/{target}/reset-pin", headers=owner_headers(owner)),
        await client.post(f"/api/v1/admin/users/{target}/revoke-sessions", headers=owner_headers(owner)),
        await client.get(f"/api/v1/admin/users/{target}/sessions", headers=bearer(owner)),
        await client.get(f"/api/v1/admin/users/{target}/devices", headers=bearer(owner)),
    ]
    for r in calls:
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND", r.text
    listed = (await client.get("/api/v1/admin/users", headers=bearer(owner))).json()
    assert str(target) not in {i["user_id"] for i in listed["items"]}
    async with admin_engine.connect() as conn:
        status = (
            await conn.execute(
                text("SELECT status FROM app.memberships WHERE user_id = :u AND tenant_id = :t"),
                {"u": target, "t": other.tenant_id},
            )
        ).scalar()
    assert status == "active"
