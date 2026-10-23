"""Credential-set sessions (14 §4.2, §18.2), recovery end to end, device-revoked refresh (14 §21),
and the BFF forced refresh used for "claims stale" (14 §5)."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.auth.application.tokens import RequestMeta, token_hash
from app.modules.auth.wiring import AuthModule
from tests.conftest import MigratedDb
from tests.support.auth import auth_settings, bff_login, new_phone, refresh, running_app
from tests.support.auth_signup import (
    SAME_ORIGIN,
    STRONG_PASSWORD,
    Stub,
    ensure_terms,
    request_otp,
    signup_body,
    start_stub,
    stub_settings,
    verified_signup_challenge,
    verify_otp,
)

pytestmark = pytest.mark.db

NEW_PASSWORD = "Boshqa-Parol-777"


@pytest.fixture(scope="module")
def stub() -> Iterator[Stub]:
    yield from start_stub()


@pytest.fixture
async def terms(oauth_platform: None, migrator_engine: AsyncEngine, clean_redis: Redis, stub: Stub) -> str:
    stub.state.reset()
    return await ensure_terms(migrator_engine)


def _settings(migrated_db: MigratedDb, redis_url: str, stub: Stub, **extra: Any):  # type: ignore[no-untyped-def]
    return auth_settings(migrated_db, redis_url, **{**stub_settings(stub), **extra})


async def _owner(client: httpx.AsyncClient, stub: Stub, terms: str) -> tuple[str, UUID, UUID]:
    phone = new_phone()
    challenge = await verified_signup_challenge(client, stub, phone)
    created = await client.post("/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN)
    assert created.status_code == 201, created.text
    return phone, UUID(created.json()["tenant_id"]), UUID(created.json()["user_id"])


async def _set(client: httpx.AsyncClient, token: str, **values: str) -> httpx.Response:
    return await client.post(
        "/auth/credentials", json={"credential_token": token, **values}, headers=SAME_ORIGIN
    )


async def test_recovery_end_to_end_resets_password_and_ends_sessions(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine
) -> None:
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_app, client):
        phone, tenant_id, user_id = await _owner(client, stub, terms)
        assert (await client.get("/auth/session")).status_code == 200  # the signup session
        requested = await request_otp(client, phone, "recovery")
        verified = await verify_otp(client, requested.json()["challenge_id"], stub.sms_code(phone))
        assert verified.status_code == 200, verified.text
        body = verified.json()
        assert body["purpose"] == "recovery" and body["credential_kinds"] == ["password"]
        assert "access_token" not in body and "refresh_token" not in body  # no tokens (14 §4.2)
        token = body["credential_token"]
        assert (await _set(client, token)).status_code == 422  # nothing to set
        assert (await _set(client, token, pin="1234")).status_code == 422  # recovery sets a password
        done = await _set(client, token, password=NEW_PASSWORD)
        assert done.status_code == 204, done.text
        assert (await _set(client, token, password=NEW_PASSWORD)).status_code == 401  # single use
        assert (await client.get("/auth/session")).status_code == 401  # old sessions revoked
        await asyncio.sleep(1.1)  # the user-revoke watermark has 1 s granularity (token iat)
        client.cookies.clear()
        await bff_login(client, phone, NEW_PASSWORD)
        assert (await client.get("/auth/session")).status_code == 200
        client.cookies.clear()
        old = await client.post(
            "/oauth/authorize",
            data={"phone": phone, "password": STRONG_PASSWORD, "client_id": "web-bff"},
            headers=SAME_ORIGIN,
        )
        assert old.status_code != 302
    async with admin_engine.connect() as conn:
        actions = (
            (
                await conn.execute(
                    text("SELECT action FROM app.audit_log WHERE tenant_id=:t"), {"t": tenant_id}
                )
            )
            .scalars()
            .all()
        )
    assert {"otp_requested", "otp_verified", "password_reset"} <= set(actions)
    assert user_id


@pytest.mark.parametrize(
    ("purpose", "kinds", "values", "must"),
    [
        ("admin_reset", ["password"], {"password": NEW_PASSWORD}, "must_change_password"),
        ("pin_reset", ["pin"], {"pin": "4321"}, "must_change_pin"),
        ("invite", ["password", "pin"], {"password": NEW_PASSWORD, "pin": "135790"}, "must_change_pin"),
    ],
)
async def test_invite_and_owner_resets_open_a_credential_set_session(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine,
    migrator_engine: AsyncEngine, purpose: str, kinds: list[str], values: dict[str, str], must: str,
) -> None:  # fmt: skip
    async with running_app(_settings(migrated_db, redis_url, stub)) as (app, client):
        phone, _, user_id = await _owner(client, stub, terms)
        # what the owner's reset does (A2): must_change_* = true; an invite opens a credential session
        # only for an account without credentials (14 §18.2) — a fresh invitee
        reset_password = purpose == "invite"
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("SELECT app.auth_reset_credentials(:u, :p, true)"), {"u": user_id, "p": reset_password}
            )
        module: AuthModule = app.state.auth_module
        issued = await module.otp.issue(phone, purpose, ip="10.1.1.1")  # type: ignore[arg-type]
        verified = await verify_otp(client, str(issued.challenge_id), stub.sms_code(phone))
        assert verified.status_code == 200, verified.text
        assert verified.json()["credential_kinds"] == kinds
        token = verified.json()["credential_token"]
        if purpose == "pin_reset":
            assert (await _set(client, token, password=NEW_PASSWORD)).status_code == 422
        assert (await _set(client, token, pin="12a4")).status_code == 422
        assert (await _set(client, token, **values)).status_code == 204
    async with admin_engine.connect() as conn:
        row = (
            await conn.execute(
                text(f"SELECT pin_hash, {must} AS must FROM auth.user_credentials WHERE user_id=:u"),
                {"u": user_id},
            )
        ).one()
    assert row.must is False
    if "pin" in values:
        assert row.pin_hash.startswith("$argon2id$")


async def test_credential_token_is_bound_to_its_ttl_and_unknown_tokens_fail(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, clean_redis: Redis
) -> None:
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        phone, _, _ = await _owner(client, stub, terms)
        challenge = (await request_otp(client, phone, "recovery")).json()["challenge_id"]
        token = (await verify_otp(client, challenge, stub.sms_code(phone))).json()["credential_token"]
        keys = [k async for k in clean_redis.scan_iter("auth:cred:*")]
        assert len(keys) == 1 and token not in keys[0]  # only the hash is stored
        ttl = await clean_redis.ttl(keys[0])
        assert 0 < ttl <= 600
        await clean_redis.delete(keys[0])  # expired
        assert (await _set(client, token, password=NEW_PASSWORD)).status_code == 401
        assert (await _set(client, secrets.token_urlsafe(32), password=NEW_PASSWORD)).status_code == 401


async def test_refresh_is_refused_for_a_revoked_device(
    terms: str,
    migrated_db: MigratedDb,
    redis_url: str,
    stub: Stub,
    app_db: Database,
    admin_engine: AsyncEngine,
) -> None:
    """14 §21 "Qurilma bekor qilish": devices.revoked_at → the device's refresh family is refused."""
    async with running_app(_settings(migrated_db, redis_url, stub)) as (app, client):
        _, tenant_id, user_id = await _owner(client, stub, terms)
        module: AuthModule = app.state.auth_module
        device_id = uuid7()
        async with app_db.session_factory() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            await s.execute(
                text("INSERT INTO app.devices (id, tenant_id, kind) VALUES (:id, :t, 'android')"),
                {"id": device_id, "t": tenant_id},
            )
        await module.clients.refresh(force=True)
        android = module.clients.get("android-pos")
        assert android is not None
        rt = secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        await module.repo.issue_tokens(
            user_id=user_id, tenant_id=tenant_id, client_id=android.id, device_id=device_id,
            refresh_hash=token_hash(rt), refresh_expires_at=now + timedelta(days=14), scope="* pos sync",
            with_session=False, idle_expires_at=None, absolute_expires_at=None, ip=None, user_agent=None,
        )  # fmt: skip
        ok = await refresh(client, rt)
        assert ok.status_code == 200, ok.text
        rotated = ok.json()["refresh_token"]
        async with admin_engine.begin() as conn:  # app.devices is FORCE RLS: the superuser fixture writes
            await conn.execute(
                text("UPDATE app.devices SET revoked_at = now() WHERE id=:d"), {"d": device_id}
            )
        refused = await refresh(client, rotated)
        assert refused.status_code == 400
        assert refused.json() == {"error": "invalid_grant", "error_description": "device_revoked"}
        async with admin_engine.begin() as conn:
            await conn.execute(text("UPDATE app.devices SET revoked_at = NULL WHERE id=:d"), {"d": device_id})
        assert (await refresh(client, rotated)).status_code == 400  # the family stays revoked


async def test_bff_forced_refresh_even_with_a_fresh_access_token(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    """``fresh_session(force=True)`` — the "claims stale" path (14 §5) mints a new access token now."""
    async with running_app(_settings(migrated_db, redis_url, stub)) as (app, client):
        await _owner(client, stub, terms)
        module: AuthModule = app.state.auth_module
        sid = module.cookies.unsign(client.cookies.get("__Host-sid"))
        assert sid is not None
        meta = RequestMeta(ip="127.0.0.1", user_agent=None)
        before = await module.bff.session(sid)
        assert before is not None
        same = await module.bff.fresh_session(sid, meta)
        assert same is not None and same.access_token == before.access_token
        forced = await module.bff.fresh_session(sid, meta, force=True)
    assert forced is not None and forced.access_token != before.access_token
    assert forced.refresh_token != before.refresh_token and forced.sid == before.sid


async def test_staff_code_is_verified_with_phone_and_purpose(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, migrator_engine: AsyncEngine
) -> None:
    """The BO-11 invite/reset message carries only the code: /invite proves it with the phone (14 §4.2)."""
    async with running_app(_settings(migrated_db, redis_url, stub)) as (app, client):
        phone, _, user_id = await _owner(client, stub, terms)
        async with migrator_engine.begin() as conn:  # a fresh invitee: no password/PIN yet
            await conn.execute(text("SELECT app.auth_reset_credentials(:u, true, true)"), {"u": user_id})
        module: AuthModule = app.state.auth_module
        await module.otp.issue(phone, "invite", ip="10.1.1.2")
        first_code = stub.sms_code(phone)
        await module.otp.issue(phone, "invite", ip="10.1.1.2")  # a resend supersedes the first code
        code = stub.sms_code(phone)

        async def by_phone(**body: str) -> httpx.Response:
            return await client.post("/auth/otp/verify", json=body, headers=SAME_ORIGIN)

        if first_code != code:
            stale = await by_phone(phone=phone, purpose="invite", code=first_code)
            assert stale.status_code == 400 and stale.json()["error"]["code"] == "OTP_INVALID"
        # wrong purpose / unknown phone: no challenge → OTP_EXPIRED, nothing is revealed
        assert (await by_phone(phone=phone, purpose="pin_reset", code=code)).json()["error"][
            "code"
        ] == "OTP_EXPIRED"
        assert (await by_phone(phone=new_phone(), purpose="invite", code=code)).json()["error"][
            "code"
        ] == "OTP_EXPIRED"
        # public purposes still need their challenge id; mixing both ways is rejected
        assert (await by_phone(phone=phone, purpose="recovery", code=code)).status_code == 422
        mixed = await client.post(
            "/auth/otp/verify",
            json={"challenge_id": str(uuid7()), "phone": phone, "purpose": "invite", "code": code},
            headers=SAME_ORIGIN,
        )
        assert mixed.status_code == 422
        ok = await by_phone(phone=phone, purpose="invite", code=code)
        assert ok.status_code == 200, ok.text
        assert ok.json()["purpose"] == "invite" and ok.json()["credential_kinds"] == ["password", "pin"]
        assert (
            await _set(client, ok.json()["credential_token"], password=NEW_PASSWORD, pin="246810")
        ).status_code == 204


async def test_staff_code_attempts_are_limited_per_challenge(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    async with running_app(_settings(migrated_db, redis_url, stub)) as (app, client):
        phone, _, _ = await _owner(client, stub, terms)
        module: AuthModule = app.state.auth_module
        await module.otp.issue(phone, "admin_reset", ip="10.1.1.3")
        code = stub.sms_code(phone)
        wrong = "000000" if code != "000000" else "111111"
        codes = []
        for _ in range(6):
            r = await client.post(
                "/auth/otp/verify",
                json={"phone": phone, "purpose": "admin_reset", "code": wrong},
                headers=SAME_ORIGIN,
            )
            codes.append(r.json()["error"]["code"])
        assert codes[-1] == "OTP_MAX_ATTEMPTS"
        late = await client.post(
            "/auth/otp/verify",
            json={"phone": phone, "purpose": "admin_reset", "code": code},
            headers=SAME_ORIGIN,
        )
        assert late.status_code != 200  # the right code no longer works after 5 misses
