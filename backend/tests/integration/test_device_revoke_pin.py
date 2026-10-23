"""Device revoke → tenant-local PIN reset (16 §9, 14 §18.2), staff snapshot (D1), SEC-08 / SEC-09.

Real PostgreSQL + Redis; "Redis down" is a real client pointed at a closed port.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.revocation import RevocationCache, TokenRevokedError
from app.modules.auth.domain.pin_verifier import check_pin_verifier
from app.modules.auth.infrastructure.repositories import AuthRepository
from app.modules.auth.wiring import AuthModule, staff_pin_snapshot
from tests.conftest import MigratedDb
from tests.support.auth import android_tokens, bearer, bff_login, client_at
from tests.support.branches import add_cash_register, add_member, api, audit_rows, make_shop
from tests.support.device_auth import (
    credential_row,
    one,
    pin_verify,
    registered_pos,
    set_pin,
    write,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def env(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    async with api(migrated_db, redis_url) as pair:
        yield pair


async def _revoke(client: httpx.AsyncClient, owner_headers: dict[str, str], device: UUID) -> None:
    r = await client.post(
        f"/api/v1/devices/{device}/revoke", json={"reason": "Yo'qolgan"}, headers=owner_headers
    )
    assert r.status_code == 200, r.text


async def test_qt_device_revoke_pin_reset_is_tenant_local(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    """A cashier active in two shops: shop A revokes its POS → only A refuses the PIN; B's credential use stays."""
    app, client_a = env
    shop_a = await make_shop(app_db, client_a, "A do'kon")
    shop_b = await make_shop(app_db, client_a, "B do'kon")
    shared = await add_member(app_db, client_a, shop_a, SystemRole.CASHIER, name="Umumiy")
    await write(  # the same account is also an active cashier of shop B
        admin_engine,
        "INSERT INTO app.memberships (tenant_id, user_id, role_ids) SELECT :t, :u, ARRAY[r.id] "
        "FROM app.roles r WHERE r.tenant_id = :t AND r.system_code = 'cashier'",
        t=shop_b.tenant_id,
        u=shared.user_id,
    )
    local_only = await add_member(app_db, client_a, shop_a, SystemRole.CASHIER, name="Faqat A")
    shared_hash = await set_pin(app_db, shared.user_id, "2580")
    await set_pin(app_db, local_only.user_id, "1470")

    reg_a = await add_cash_register(app_db, shop_a.tenant_id, shop_a.branch_id)
    device_a = await registered_pos(client_a, shop_a.owner.phone, reg_a)
    assert (await pin_verify(client_a, shared.user_id, "2580")).status_code == 200
    assert (await pin_verify(client_a, local_only.user_id, "1470")).status_code == 200

    await _revoke(client_a, shop_a.owner.headers(write=True), device_a)

    # shared credential untouched; tenant-local marker in A only
    shared_row = await credential_row(admin_engine, shared.user_id)
    assert shared_row.pin_hash == shared_hash and not shared_row.must_change_pin
    assert shared_row.pin_local_hash is not None
    markers = await one(
        admin_engine,
        "SELECT count(*) FILTER (WHERE tenant_id = :a AND pin_reset_at IS NOT NULL) AS a, "
        "count(*) FILTER (WHERE tenant_id = :b AND pin_reset_at IS NOT NULL) AS b "
        "FROM app.memberships WHERE user_id = :u",
        a=shop_a.tenant_id,
        b=shop_b.tenant_id,
        u=shared.user_id,
    )
    assert (markers.a, markers.b) == (1, 0)
    # the user only in A: the credential's PIN itself is reset (14 §18.2)
    local_row = await credential_row(admin_engine, local_only.user_id)
    assert local_row.pin_hash is None and local_row.pin_local_hash is None and local_row.must_change_pin
    scopes = {
        a["entity_id"]: a["after"]["scope"]
        for a in await audit_rows(admin_engine, shop_a.tenant_id, "pin_reset_forced")
    }
    assert scopes == {shared.user_id: "tenant", local_only.user_id: "credential"}
    assert await audit_rows(admin_engine, shop_b.tenant_id, "pin_reset_forced") == []

    # A: a new POS refuses the shared PIN until it is changed; B keeps working with it
    reg_a2 = await add_cash_register(app_db, shop_a.tenant_id, shop_a.branch_id, "Kassa 2")
    async with client_at(app, "127.0.0.2") as fresh_a:
        await registered_pos(fresh_a, shop_a.owner.phone, reg_a2)
        refused = await pin_verify(fresh_a, shared.user_id, "2580")
        assert refused.status_code == 400 and refused.json()["error"]["params"] == {
            "reason": "must_change_pin"
        }
    reg_b = await add_cash_register(app_db, shop_b.tenant_id, shop_b.branch_id)
    async with client_at(app, "127.0.0.3") as client_b:
        await registered_pos(client_b, shop_b.owner.phone, reg_b)
        assert (await pin_verify(client_b, shared.user_id, "2580")).status_code == 200

    # snapshot (permissions pull scope): A withholds the verifier, B delivers it
    snapshot = staff_pin_snapshot()
    async with app_db.session_factory() as s, tenant_transaction(s, shop_a.tenant_id):
        rows_a = {r.user_id: r for r in await snapshot.for_branch(s, shop_a.tenant_id, shop_a.branch_id)}
    async with app_db.session_factory() as s, tenant_transaction(s, shop_b.tenant_id):
        rows_b = {r.user_id: r for r in await snapshot.for_branch(s, shop_b.tenant_id, shop_b.branch_id)}
    assert rows_a[shared.user_id].pin_local_hash is None and rows_a[shared.user_id].must_change_pin
    assert rows_a[local_only.user_id].pin_local_hash is None and rows_a[local_only.user_id].must_change_pin
    assert check_pin_verifier(rows_b[shared.user_id].pin_local_hash or "", "2580")
    assert not rows_b[shared.user_id].must_change_pin

    # a new PIN (set by the user) lifts the tenant-local reset in every tenant — no clock comparison
    await set_pin(app_db, shared.user_id, "3690")
    cleared = await one(
        admin_engine,
        "SELECT count(*) AS n FROM app.memberships WHERE user_id = :u AND pin_reset_at IS NOT NULL",
        u=shared.user_id,
    )
    assert cleared.n == 0
    async with app_db.session_factory() as s, tenant_transaction(s, shop_a.tenant_id):
        row = next(
            r
            for r in await snapshot.for_branch(s, shop_a.tenant_id, shop_a.branch_id)
            if r.user_id == shared.user_id
        )
    assert not row.must_change_pin and check_pin_verifier(row.pin_local_hash or "", "3690")


async def test_b3_staff_pin_snapshot_shape_branch_filter_and_blocked(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database
) -> None:
    _, client = env
    shop = await make_shop(app_db, client)
    second = (
        await client.post(
            "/api/v1/branches", json={"name": "Filial-2"}, headers=shop.owner.headers(write=True)
        )
    ).json()
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER, name="Ali")
    other_branch = await add_member(
        app_db, client, shop, SystemRole.CASHIER, branch_ids=(UUID(second["id"]),), name="Vali"
    )
    blocked = await add_member(app_db, client, shop, SystemRole.STOREKEEPER, name="Bloklangan")
    await set_pin(app_db, cashier.user_id, "2580")
    await set_pin(app_db, blocked.user_id, "1470")
    async with app_db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.memberships SET status = 'blocked' WHERE tenant_id = :t AND user_id = :u"),
            {"t": shop.tenant_id, "u": blocked.user_id},
        )
    async with app_db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        rows = await staff_pin_snapshot().for_branch(s, shop.tenant_id, shop.branch_id)
    by_user = {r.user_id: r for r in rows}
    assert other_branch.user_id not in by_user  # works only in Filial-2
    ali = by_user[cashier.user_id]
    assert ali.full_name == "Ali" and ali.role_codes == ("cashier",) and ali.active
    assert "sales.create" in ali.permission_codes and list(ali.permission_codes) == sorted(
        ali.permission_codes
    )
    assert ali.branch_ids == () and check_pin_verifier(ali.pin_local_hash or "", "2580")
    assert not ali.pin_local_hash.startswith("$argon2")  # type: ignore[union-attr]
    gone = by_user[blocked.user_id]
    assert not gone.active and gone.pin_local_hash is None
    owner = by_user[shop.owner.user_id]
    assert owner.pin_local_hash is None and owner.must_change_pin  # no PIN set


def _claims(**extra: Any) -> dict[str, Any]:
    now = int(time.time())
    return {
        "sub": str(uuid7()),
        "tenant_id": str(uuid7()),
        "jti": str(uuid7()),
        "iat": now,
        "exp": now + 900,
        **extra,
    }


async def test_qt_sec_08_redis_down_sidless_token_checks_family_in_db(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    """SEC-08 (14 §5): without Redis a sid-less (Android/device) token is checked by its refresh family."""
    _, client = env
    shop = await make_shop(app_db, client)
    tokens = await android_tokens(client, shop.owner.phone)
    family = (
        await one(
            admin_engine,
            "SELECT family_id FROM auth.refresh_tokens WHERE user_id = :u ORDER BY issued_at DESC LIMIT 1",
            u=shop.owner.user_id,
        )
    ).family_id
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    cache = RevocationCache(
        AuthRepository(app_db.session_factory), lambda: broken, access_ttl_s=900, session_check_cache_s=30
    )
    try:
        await cache.check(_claims(fam=str(family)))  # live family → accepted
        with pytest.raises(TokenRevokedError):
            await cache.check(_claims(fam=str(uuid7())))  # unknown family → fail-closed
        with pytest.raises(TokenRevokedError):
            await cache.check(_claims())  # neither sid nor fam → fail-closed
        # revoke-all/block revokes the family rows → the token dies even without Redis
        revoked = await client.post(
            "/oauth/revoke", data={"token": tokens["refresh_token"], "client_id": "android-pos"}
        )
        assert revoked.status_code == 200
        with pytest.raises(TokenRevokedError):
            await cache.check(_claims(fam=str(family)))
    finally:
        await broken.aclose()


async def test_qt_sec_09_single_session_revoke_kills_family_tokens_at_once(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    """SEC-09: revoking one session marks its refresh family — sid-less tokens of that family die now."""
    app, client = env
    shop = await make_shop(app_db, client)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    await bff_login(client, cashier.phone)
    row = await one(
        admin_engine,
        "SELECT s.id, t.family_id FROM auth.sessions s JOIN auth.refresh_tokens t "
        "ON t.id = s.current_refresh_token_id WHERE s.user_id = :u AND s.revoked_at IS NULL",
        u=cashier.user_id,
    )
    module: AuthModule = app.state.auth_module
    claims = _claims(sub=str(cashier.user_id), tenant_id=str(shop.tenant_id), fam=str(row.family_id))
    await module.revocation.check(claims)  # live before the revoke
    r = await client.post(
        f"/api/v1/admin/users/{cashier.user_id}/sessions/{row.id}/revoke",
        headers=shop.owner.headers(write=True),
    )
    assert r.status_code == 200, r.text
    assert await clean_redis.get(f"auth:fam_revoked:{row.family_id}") == "1"
    with pytest.raises(TokenRevokedError):
        await module.revocation.check(claims)


async def test_qt_device_revoke_kills_device_tokens_immediately(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    """Revoke → 403 DEVICE_REVOKED and the device's sessions/families are revoked in the DB + Redis now."""
    _, client = env
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device = await registered_pos(client, shop.owner.phone, register)
    session = await one(
        admin_engine,
        "SELECT s.id, t.family_id FROM auth.sessions s JOIN auth.refresh_tokens t "
        "ON t.id = s.current_refresh_token_id WHERE s.device_id = :d AND s.revoked_at IS NULL",
        d=device,
    )
    await _revoke(client, bearer(shop.owner.token) | {"Idempotency-Key": str(uuid7())}, device)
    assert await clean_redis.get(f"auth:sid_revoked:{session.id}") == "1"
    assert await clean_redis.get(f"auth:fam_revoked:{session.family_id}") == "1"
    refused = await client.get("/auth/session")  # the POS learns it at its next call (heartbeat)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "DEVICE_REVOKED"
    audit = await audit_rows(admin_engine, shop.tenant_id, "device_revoked")
    assert audit[0]["after"]["sessions_revoked"] == 1
