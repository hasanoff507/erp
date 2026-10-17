"""B3-EP-14#21 ``POST /auth/pin/verify`` + the local verifier (D1) — 14 §4.3, §12, §13; 16 §12. Real PG + Redis."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.otp import VerifiedOtp
from app.modules.auth.domain.pin_verifier import ITERATIONS, check_pin_verifier, make_pin_verifier
from app.modules.auth.wiring import AuthModule, pin_verifier
from tests.conftest import MigratedDb
from tests.support.auth import bff_login
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

# known-answer vectors shared with the TS verifier (contracts/device-auth.md, 14 §13)
SALT = bytes(range(16))
VECTORS = [
    (
        "1234",
        600_000,
        "pbkdf2_sha256$600000$AAECAwQFBgcICQoLDA0ODw==$nznZxxwixMRZvCy6zG104hhBhdZx2R8KNKaDRBOghJ0=",
    ),
    (
        "908172",
        600_000,
        "pbkdf2_sha256$600000$AAECAwQFBgcICQoLDA0ODw==$ZFpC4a2/irbU78Q8BXzcFRObJpCksrlR4+9qsCkAHJQ=",
    ),
    (
        "1234",
        1000,
        "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=",
    ),
]


@pytest.fixture
async def env(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    async with api(migrated_db, redis_url) as pair:
        yield pair


@pytest.mark.parametrize(("pin", "iterations", "expected"), VECTORS)
def test_qt_pin_local_verifier_known_answer_vectors(pin: str, iterations: int, expected: str) -> None:
    assert make_pin_verifier(pin, salt=SALT, iterations=iterations) == expected
    assert check_pin_verifier(expected, pin)
    assert not check_pin_verifier(expected, "0000")
    # format: standard base64 with padding, 16-byte salt, 32-byte key
    algorithm, count, salt_b64, key_b64 = expected.split("$")
    assert algorithm == "pbkdf2_sha256" and int(count) == iterations
    key = base64.b64decode(key_b64, validate=True)
    assert base64.b64decode(salt_b64, validate=True) == SALT and len(key) == 32
    assert key == hashlib.pbkdf2_hmac("sha256", pin.encode(), SALT, iterations, 32)


def test_qt_pin_local_verifier_rejects_malformed() -> None:
    assert not check_pin_verifier("argon2id$v=19$m=19456,t=2,p=1$abc$def", "1234")
    assert not check_pin_verifier("pbkdf2_sha256$999999999$AAAA$BBBB", "1234")  # DoS guard
    assert not check_pin_verifier("pbkdf2_sha256$x$y", "1234")
    fresh = make_pin_verifier("4321")
    assert fresh.startswith(f"pbkdf2_sha256${ITERATIONS}$") and check_pin_verifier(fresh, "4321")
    with pytest.raises(ValueError, match="ASCII digits"):
        make_pin_verifier("12ab")


async def _pos_with_cashier(client: httpx.AsyncClient, db: Database) -> tuple[UUID, UUID, UUID]:
    shop = await make_shop(db, client)
    register = await add_cash_register(db, shop.tenant_id, shop.branch_id)
    cashier = await add_member(db, client, shop, SystemRole.CASHIER, name="Dilnoza")
    device = await registered_pos(client, shop.owner.phone, register)
    return shop.tenant_id, cashier.user_id, device


async def test_b3_ep_14_21_pin_verify_success_returns_verifier_and_audits(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    _, client = env
    tenant, cashier, device = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580", local=False)  # a PIN set before 0027a: no verifier yet

    r = await pin_verify(client, cashier, "2580")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == str(cashier) and body["full_name"] == "Dilnoza"
    assert body["roles"] == ["cashier"] and "sales.create" in body["permissions"]
    verifier = body["pin_local_hash"]
    assert verifier.startswith(f"pbkdf2_sha256${ITERATIONS}$") and check_pin_verifier(verifier, "2580")
    stored = await credential_row(admin_engine, cashier)
    assert stored.pin_local_hash == verifier and stored.pin_hash.startswith("$argon2id$")
    assert verifier != stored.pin_hash  # the argon2 hash never leaves the server
    audit = await audit_rows(admin_engine, tenant, "pin_verified")
    assert [(a["entity_id"], a["device_id"]) for a in audit] == [(cashier, device)]
    # the verifier is reused, not re-derived, on the next check
    again = await pin_verify(client, cashier, "2580")
    assert again.status_code == 200 and again.json()["pin_local_hash"] == verifier


async def test_b3_ep_14_21_pin_lockout_progressive_per_device(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    """qaror #54, 14 §12: 5 wrong PINs → 1 min; next 5 → 5 min (1 → 5 → 15 → 60)."""
    _, client = env
    tenant, cashier, device = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580")
    for _ in range(4):
        wrong = await pin_verify(client, cashier, "1111")
        assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "PIN_INVALID"
    fifth = await pin_verify(client, cashier, "1111")
    assert fifth.status_code == 400
    locked = await pin_verify(client, cashier, "2580")  # even the right PIN is refused while locked
    assert locked.status_code == 423 and locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert 0 < locked.json()["error"]["params"]["retry_after_s"] <= 60
    assert int(locked.headers["retry-after"]) <= 60
    # fake clock: the lock expires
    pair = f"{tenant}:{cashier}:{device}"
    await clean_redis.delete(f"auth:pin:lock:{pair}")
    for _ in range(5):
        await pin_verify(client, cashier, "1111")
    second = await pin_verify(client, cashier, "2580")
    assert second.status_code == 423 and 60 < second.json()["error"]["params"]["retry_after_s"] <= 300
    actions = [a["after"] for a in await audit_rows(admin_engine, tenant, "account_locked")]
    assert sorted(a["locked_for_s"] for a in actions) == [60, 300] and all(
        a["scope"] == "pin" for a in actions
    )
    assert len(await audit_rows(admin_engine, tenant, "pin_failed")) == 10


async def test_b3_ep_14_21_pin_brute_force_across_devices_locks_user(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, clean_redis: Redis
) -> None:
    """20 wrong PINs a day per (tenant, user) over any devices → the user's PIN is locked 60 min."""
    app, client = env
    tenant, cashier, _ = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580")
    module: AuthModule = app.state.auth_module
    for i in range(20):
        with pytest.raises(AppError) as exc:
            await module.pin.verify(tenant_id=tenant, user_id=cashier, pin="9999", device_id=None, ip=None)
        assert exc.value.code in (ErrorCode.PIN_INVALID, ErrorCode.ACCOUNT_LOCKED)
        await clean_redis.delete(f"auth:pin:lock:{tenant}:{cashier}:-")  # per-device locks expire
        if i == 19:
            assert exc.value.code is ErrorCode.PIN_INVALID
    locked = await pin_verify(client, cashier, "2580")  # another device, right PIN
    assert locked.status_code == 423 and locked.json()["error"]["params"]["retry_after_s"] > 300


async def test_b3_ep_14_21_pin_not_member_or_other_branch_is_plain_pin_invalid(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database
) -> None:
    _, client = env
    shop = await make_shop(app_db, client)
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    second = (
        await client.post(
            "/api/v1/branches", json={"name": "Filial-2"}, headers=shop.owner.headers(write=True)
        )
    ).json()
    elsewhere = await add_member(
        app_db, client, shop, SystemRole.CASHIER, branch_ids=(UUID(second["id"]),), name="Boshqa filial"
    )
    stranger_shop = await make_shop(app_db, client, "Begona")
    await registered_pos(client, shop.owner.phone, register)
    await set_pin(app_db, elsewhere.user_id, "2580")
    await set_pin(app_db, stranger_shop.owner.user_id, "2580")
    for user in (elsewhere.user_id, stranger_shop.owner.user_id):
        r = await pin_verify(client, user, "2580")
        assert r.status_code == 400, r.text
        assert r.json()["error"]["code"] == "PIN_INVALID" and not r.json()["error"]["params"]


async def test_b3_ep_14_21_pin_after_reset_requires_change(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    _, client = env
    _, cashier, _ = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580")
    await write(admin_engine, "SELECT app.auth_reset_credentials(:u, false, true)", u=cashier)
    stored = await credential_row(admin_engine, cashier)
    assert stored.pin_hash is None and stored.pin_local_hash is None and stored.must_change_pin
    r = await pin_verify(client, cashier, "2580")
    assert r.status_code == 400 and r.json()["error"]["params"] == {"reason": "must_change_pin"}


async def test_b3_ep_14_21_pin_verify_requires_device_bound_session(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database
) -> None:
    _, client = env
    shop = await make_shop(app_db, client)
    await bff_login(client, shop.owner.phone)  # an ordinary (unbound) web session
    r = await pin_verify(client, shop.owner.user_id, "2580")
    assert r.status_code == 403 and r.json()["error"]["params"] == {"reason": "device_required"}
    malformed = await client.post("/auth/pin/verify", json={"user_id": str(shop.owner.user_id), "pin": "12"})
    assert malformed.status_code in (403, 422)


async def test_b3_ep_14_21_pin_check_fails_closed_without_redis(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database
) -> None:
    app, client = env
    tenant, cashier, _ = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580")
    module: AuthModule = app.state.auth_module
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    verifier = pin_verifier(module.settings, app.state.db, lambda: broken)
    with pytest.raises(AppError) as exc:
        await verifier.verify(tenant_id=tenant, user_id=cashier, pin="2580", device_id=None, ip=None)
    assert exc.value.code is ErrorCode.RATE_LIMITED
    await broken.aclose()


async def test_b3_pin_verifier_contract_for_approvals(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database
) -> None:
    """``app.modules.auth.wiring.pin_verifier`` (b3-cash approvals, 18 §9.4)."""
    app, client = env
    tenant, cashier, device = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580")
    verifier = pin_verifier(app.state.auth_module.settings, app.state.db, lambda: app.state.redis)
    assert await verifier.verify(tenant_id=tenant, user_id=cashier, pin="2580", device_id=device, ip=None)
    assert not await verifier.verify(tenant_id=tenant, user_id=cashier, pin="0000", device_id=device, ip=None)


async def test_b3_pin_set_through_credentials_writes_local_verifier(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    """D1: setting a PIN (``POST /auth/credentials``) writes the PBKDF2 verifier with the argon2 hash."""
    app, client = env
    shop = await make_shop(app_db, client)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    phone = (await one(admin_engine, "SELECT phone FROM app.users WHERE id = :u", u=cashier.user_id)).phone
    module: AuthModule = app.state.auth_module
    session = await module.credentials.open_session(
        VerifiedOtp(challenge_id=cashier.user_id, phone=phone, purpose="pin_reset", tenant_id=shop.tenant_id)
    )
    await module.credentials.set_credentials(session.token, password=None, pin="7531", ip=None)
    stored = await credential_row(admin_engine, cashier.user_id)
    assert stored.pin_hash.startswith("$argon2id$") and not stored.must_change_pin
    assert check_pin_verifier(stored.pin_local_hash, "7531")
    # a newer PIN clears the old verifier atomically (auth_set_credentials) before the new one is written
    await set_pin(app_db, cashier.user_id, "8642", local=False)
    assert (await credential_row(admin_engine, cashier.user_id)).pin_local_hash is None


def test_known_vectors_match_contract_file() -> None:
    """The vectors published for the TS side are the ones tested here."""
    from pathlib import Path

    contract = Path(__file__).resolve().parents[3] / ".claude-scratch" / "b3" / "contracts" / "device-auth.md"
    if not contract.exists():
        pytest.skip("contract file is not part of this checkout")
    text = contract.read_text(encoding="utf-8")
    for _, _, expected in VECTORS:
        assert expected in text, json.dumps(expected)


async def test_qt_sec_06_parallel_wrong_pins_are_reserved_before_argon2(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database, admin_engine: AsyncEngine
) -> None:
    """SEC-06: 30 parallel wrong PINs — at most 5 reach the argon2 check (pin_failed), the rest are locked."""
    import asyncio

    app, client = env
    tenant, cashier, device = await _pos_with_cashier(client, app_db)
    await set_pin(app_db, cashier, "2580")
    module: AuthModule = app.state.auth_module

    async def attempt() -> ErrorCode:
        try:
            await module.pin.verify(tenant_id=tenant, user_id=cashier, pin="1111", device_id=device, ip=None)
        except AppError as exc:
            return exc.code
        return ErrorCode.UNAUTHORIZED  # never: the PIN is wrong

    codes = await asyncio.gather(*(attempt() for _ in range(30)))
    assert set(codes) <= {ErrorCode.PIN_INVALID, ErrorCode.ACCOUNT_LOCKED}
    assert codes.count(ErrorCode.PIN_INVALID) <= 5
    assert len(await audit_rows(admin_engine, tenant, "pin_failed")) <= 5


async def test_qt_sec_12_pin_state_functions_answer_only_for_current_tenant_members(
    env: tuple[FastAPI, httpx.AsyncClient], app_db: Database
) -> None:
    from sqlalchemy import text

    from app.core.db.session import tenant_transaction

    _, client = env
    shop_a = await make_shop(app_db, client, "A")
    shop_b = await make_shop(app_db, client, "B")
    await set_pin(app_db, shop_a.owner.user_id, "2580")
    await set_pin(app_db, shop_b.owner.user_id, "1470")
    async with app_db.session_factory() as s, tenant_transaction(s, shop_a.tenant_id):
        states = text("SELECT count(*) FROM app.auth_staff_pin_states(CAST(:ids AS uuid[]))")
        state = text("SELECT count(*) FROM app.auth_pin_state(:u)")
        assert (await s.execute(states, {"ids": [str(shop_b.owner.user_id)]})).scalar() == 0
        assert (await s.execute(state, {"u": shop_b.owner.user_id})).scalar() == 0
        assert (await s.execute(states, {"ids": [str(shop_a.owner.user_id)]})).scalar() == 1
        assert (await s.execute(state, {"u": shop_a.owner.user_id})).scalar() == 1
