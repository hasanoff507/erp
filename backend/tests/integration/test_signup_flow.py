"""US-M17-01 signup (14 §20, 15 §1.5, 07 BO-21 ①②) — real app, Postgres, Redis, adapters over HTTP."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database, tenant_transaction
from app.modules.branches.domain.model import tashkent_today
from app.modules.branches.wiring import turnover_rate_on
from tests.conftest import MigratedDb
from tests.support.auth import ISSUER, auth_settings, bff_login, new_phone, running_app
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


@pytest.fixture(scope="module")
def stub() -> Iterator[Stub]:
    yield from start_stub()


@pytest.fixture
async def terms(oauth_platform: None, migrator_engine: AsyncEngine, clean_redis: Redis, stub: Stub) -> str:
    stub.state.reset()
    return await ensure_terms(migrator_engine)


def _settings(migrated_db: MigratedDb, redis_url: str, stub: Stub, **extra: Any):  # type: ignore[no-untyped-def]
    return auth_settings(migrated_db, redis_url, **{**stub_settings(stub), **extra})


async def _rows(engine: AsyncEngine, sql: str, **params: object) -> list[Any]:
    async with engine.connect() as conn:
        return list((await conn.execute(text(sql), params)).all())


async def test_qt_nfr_signup_01_otp_verify_signup_session_under_two_minutes(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    """QT-NFR-SIGNUP-01 (signup half): otp request → verify → signup → authenticated /auth/session."""
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        started = time.perf_counter()
        challenge = await verified_signup_challenge(client, stub, phone)
        created = await client.post("/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN)
        assert created.status_code == 201, created.text
        assert client.cookies.get("__Host-sid")
        session = await client.get("/auth/session")
        elapsed = time.perf_counter() - started
    assert session.status_code == 200, session.text
    body = session.json()
    assert body["roles"] == ["owner"] and body["tenant"]["name"] == "Aziz do'koni"
    assert body["sub_status"] == "trial" and body["user"]["full_name"] == "Aziz Karimov"
    assert "settings.users" in body["permissions"]
    assert elapsed < 120, elapsed
    print(f"QT-NFR-SIGNUP-01 signup half elapsed: {elapsed:.3f} s")


async def test_qt_m17_01_sms_code_then_trial_and_full_provisioning(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine
) -> None:
    """QT-M17-01 + 15 §1.5: SMS fallback (no Telegram), 6-digit code, 5 min TTL, trial 30 days."""
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        requested = await request_otp(client, phone)
        assert requested.status_code == 200, requested.text
        payload = requested.json()
        assert payload["channel_used"] == "sms"
        assert [w["code"] for w in payload["warnings"]] == ["TELEGRAM_NOT_LINKED"]
        ttl = datetime.fromisoformat(payload["expires_at"]) - datetime.now(UTC)
        assert timedelta(seconds=290) < ttl <= timedelta(seconds=300)
        code = stub.sms_code(phone)
        assert len(code) == 6 and code.isdigit()
        assert (await verify_otp(client, payload["challenge_id"], code)).status_code == 200
        created = await client.post(
            "/auth/signup", json=signup_body(payload["challenge_id"], terms), headers=SAME_ORIGIN
        )
        assert created.status_code == 201, created.text
        result = created.json()
    tenant_id, user_id = UUID(result["tenant_id"]), UUID(result["user_id"])
    assert result["sub_status"] == "trial"
    sub = (
        await _rows(
            admin_engine,
            "SELECT status, current_period_end FROM app.subscriptions WHERE tenant_id=:t",
            t=tenant_id,
        )
    )[0]
    assert sub.status == "trial"
    assert timedelta(days=29, hours=23) < sub.current_period_end - datetime.now(UTC) <= timedelta(days=30)
    tenant = (
        await _rows(
            admin_engine,
            "SELECT name, phone, legal_form, activity_type, accepted_terms_version, accepted_terms_at, "
            "host(accepted_terms_ip) AS ip, settings FROM app.tenants WHERE id=:t",
            t=tenant_id,
        )
    )[0]
    assert (tenant.name, tenant.phone, tenant.legal_form, tenant.activity_type) == (
        "Aziz do'koni",
        phone,
        "llc",
        "retail",
    )
    assert (
        tenant.accepted_terms_version == terms
        and tenant.accepted_terms_at is not None
        and tenant.ip == "127.0.0.1"
    )
    assert tenant.settings == {"ai_cross_border_enabled": False}
    user = (await _rows(admin_engine, "SELECT phone, name FROM app.users WHERE id=:u", u=user_id))[0]
    assert (user.phone, user.name) == (phone, "Aziz Karimov")
    cred = (
        await _rows(
            admin_engine,
            "SELECT password_hash, password_algo FROM auth.user_credentials WHERE user_id=:u",
            u=user_id,
        )
    )[0]
    assert cred.password_hash.startswith("$argon2id$") and cred.password_algo == "argon2id"
    roles = {
        r.system_code
        for r in await _rows(
            admin_engine, "SELECT system_code FROM app.roles WHERE tenant_id=:t", t=tenant_id
        )
    }
    assert roles == {"owner", "manager", "cashier", "storekeeper", "accountant"}
    member = (
        await _rows(
            admin_engine,
            "SELECT m.status, m.branch_ids, r.system_code FROM app.memberships m JOIN app.roles r ON r.id = ANY(m.role_ids) WHERE m.tenant_id=:t AND m.user_id=:u",
            t=tenant_id,
            u=user_id,
        )
    )[0]
    assert (member.status, list(member.branch_ids), member.system_code) == ("active", [], "owner")
    branch = await _rows(
        admin_engine, "SELECT id, code, is_default FROM app.branches WHERE tenant_id=:t", t=tenant_id
    )
    assert [(b.code, b.is_default) for b in branch] == [("01", True)]
    tax = await _rows(
        admin_engine,
        "SELECT valid_from, settlement_category, activity_type, created_by FROM app.branch_tax_settings WHERE branch_id=:b",
        b=branch[0].id,
    )
    today = tashkent_today()  # CORR-03: business dates are Tashkent dates
    assert [(r.valid_from, r.settlement_category, r.activity_type, r.created_by) for r in tax] == [
        (today.replace(day=1), "city_100k_plus", "retail", user_id)
    ]
    assert await _rows(
        admin_engine,
        "SELECT 1 FROM app.warehouses WHERE tenant_id=:t AND inventory_account='2920'",
        t=tenant_id,
    )
    assert await _rows(
        admin_engine, "SELECT 1 FROM app.cash_registers WHERE tenant_id=:t AND kind='web'", t=tenant_id
    )
    categories = await _rows(
        admin_engine, "SELECT count(*) AS n FROM app.expense_categories WHERE tenant_id=:t", t=tenant_id
    )
    assert categories[0].n == 21
    valuation = (
        await _rows(
            admin_engine,
            "SELECT method, valid_from, created_by FROM app.valuation_method_history WHERE tenant_id=:t",
            t=tenant_id,
        )
    )[0]
    assert (valuation.method, valuation.valid_from, valuation.created_by) == (
        "aveco",
        date(today.year, 1, 1),
        user_id,
    )
    consents = await _rows(
        admin_engine,
        "SELECT purpose, terms_version, accepted FROM app.consents WHERE tenant_id=:t",
        t=tenant_id,
    )
    assert [(c.purpose, c.terms_version, c.accepted) for c in consents] == [("terms", terms, True)]
    audit = {
        r.action
        for r in await _rows(admin_engine, "SELECT action FROM app.audit_log WHERE tenant_id=:t", t=tenant_id)
    }
    assert {"terms_accepted", "login_success"} <= audit


async def test_signup_business_type_other_reaches_the_branch_and_its_tax_setting(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine,
    app_db: Database,
) -> None:  # fmt: skip
    """CORR-01: ``business_type`` = ``branches.activity_type`` and the first tax row → ``general`` rate."""
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        challenge = await verified_signup_challenge(client, stub, phone)
        created = await client.post(
            "/auth/signup", json=signup_body(challenge, terms, business_type="other"), headers=SAME_ORIGIN
        )
    assert created.status_code == 201, created.text
    tenant_id = UUID(created.json()["tenant_id"])
    branch = (
        await _rows(
            admin_engine, "SELECT id, activity_type FROM app.branches WHERE tenant_id=:t", t=tenant_id
        )
    )[0]
    tax = await _rows(
        admin_engine,
        "SELECT valid_from, activity_type FROM app.branch_tax_settings WHERE branch_id=:b",
        b=branch.id,
    )
    today = tashkent_today()
    assert branch.activity_type == "other"
    assert [(r.valid_from, r.activity_type) for r in tax] == [(today.replace(day=1), "other")]
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        rate = await turnover_rate_on(s, tenant_id, branch.id, today)
    assert (rate.activity_type, rate.rate_code) == ("other", "general")


async def test_signup_owner_can_log_in_with_phone_and_password(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    """US-M17-01 (1): telefon + parol — the new owner logs in through the AS page afterwards."""
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        challenge = await verified_signup_challenge(client, stub, phone)
        assert (
            await client.post("/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN)
        ).status_code == 201
        client.cookies.clear()
        await bff_login(client, phone, STRONG_PASSWORD)
        assert (await client.get("/auth/session")).status_code == 200


async def test_qt_m17_08_terms_required_current_and_consent_recorded(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine
) -> None:
    """QT-M17-08 (signup part): no/old terms → 422 and no tenant; consent → settings + consents row."""
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        challenge = await verified_signup_challenge(client, stub, phone)
        missing = signup_body(challenge, terms)
        del missing["accepted_terms_version"]
        refused = await client.post("/auth/signup", json=missing, headers=SAME_ORIGIN)
        assert refused.status_code == 422 and refused.json()["error"]["code"] == "VALIDATION_ERROR"
        old = await client.post("/auth/signup", json=signup_body(challenge, "v0-old"), headers=SAME_ORIGIN)
        assert old.status_code == 422, old.text
        assert old.json()["error"]["details"][0]["field"] == "accepted_terms_version"
        assert not await _rows(admin_engine, "SELECT 1 FROM app.users WHERE phone=:p", p=phone)
        assert not await _rows(admin_engine, "SELECT 1 FROM app.tenants WHERE phone=:p", p=phone)
        # the verified ticket was not burnt by the refused attempts
        ok = await client.post(
            "/auth/signup",
            json=signup_body(challenge, terms, ai_cross_border_consent=True),
            headers=SAME_ORIGIN,
        )
        assert ok.status_code == 201, ok.text
        tenant_id = UUID(ok.json()["tenant_id"])
    settings = (await _rows(admin_engine, "SELECT settings FROM app.tenants WHERE id=:t", t=tenant_id))[
        0
    ].settings
    assert settings == {"ai_cross_border_enabled": True}
    purposes = sorted(
        c.purpose
        for c in await _rows(admin_engine, "SELECT purpose FROM app.consents WHERE tenant_id=:t", t=tenant_id)
    )
    assert purposes == ["ai_cross_border", "terms"]
    audit = {
        r.action
        for r in await _rows(admin_engine, "SELECT action FROM app.audit_log WHERE tenant_id=:t", t=tenant_id)
    }
    assert "consent.ai_cross_border_changed" in audit


async def test_signup_phone_already_registered_is_validation_error(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        first = await verified_signup_challenge(client, stub, phone)
        assert (
            await client.post("/auth/signup", json=signup_body(first, terms), headers=SAME_ORIGIN)
        ).status_code == 201
        second = await verified_signup_challenge(client, stub, phone)
        again = await client.post("/auth/signup", json=signup_body(second, terms), headers=SAME_ORIGIN)
    assert again.status_code == 422
    error = again.json()["error"]
    assert (
        error["code"] == "VALIDATION_ERROR" and error["details"][0]["message_key"] == "validation.phone_taken"
    )


async def test_signup_needs_a_verified_single_use_signup_challenge(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine
) -> None:
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        unverified = (await request_otp(client, phone)).json()["challenge_id"]
        refused = await client.post("/auth/signup", json=signup_body(unverified, terms), headers=SAME_ORIGIN)
        assert refused.status_code == 400 and refused.json()["error"]["code"] == "OTP_INVALID"
        await verify_otp(client, unverified, stub.sms_code(phone))
        assert (
            await client.post("/auth/signup", json=signup_body(unverified, terms), headers=SAME_ORIGIN)
        ).status_code == 201
        replay = await client.post(
            "/auth/signup", json=signup_body(unverified, terms, store_name="Ikkinchi"), headers=SAME_ORIGIN
        )
        assert replay.status_code in (400, 422)
        # a recovery-purpose challenge never opens a signup
        other = new_phone()
        rec = await request_otp(client, other, "recovery")
        assert rec.status_code == 200
        wrong = await client.post(
            "/auth/signup", json=signup_body(rec.json()["challenge_id"], terms), headers=SAME_ORIGIN
        )
        assert wrong.json()["error"]["code"] == "OTP_INVALID"
    assert len(await _rows(admin_engine, "SELECT 1 FROM app.tenants WHERE phone=:p", p=phone)) == 1


async def test_signup_without_password_on_the_phone_path_is_refused(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        challenge = await verified_signup_challenge(client, stub, new_phone())
        body = signup_body(challenge, terms)
        del body["password"]
        refused = await client.post("/auth/signup", json=body, headers=SAME_ORIGIN)
        short = await client.post(
            "/auth/signup", json=signup_body(challenge, terms, password="short"), headers=SAME_ORIGIN
        )
        extra = await client.post(
            "/auth/signup", json=signup_body(challenge, terms, role="owner"), headers=SAME_ORIGIN
        )
    assert refused.status_code == 422 and refused.json()["error"]["details"][0]["field"] == "password"
    assert short.status_code == 422 and extra.status_code == 422


async def test_signup_is_one_transaction(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:  # fmt: skip
    """A failure in the middle (trial: the plan is missing) leaves no tenant/user/role/credential rows."""
    phone = new_phone()
    settings = _settings(migrated_db, redis_url, stub)
    async with running_app(settings) as (_, client):
        challenge = await verified_signup_challenge(client, stub, phone)
        async with migrator_engine.begin() as conn:
            await conn.execute(text("UPDATE platform.plans SET code='standard-hidden' WHERE code='standard'"))
        try:
            failed = await client.post(
                "/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN
            )
            assert failed.status_code == 500 and failed.json()["error"]["code"] == "INTERNAL_ERROR"
        finally:
            async with migrator_engine.begin() as conn:
                await conn.execute(
                    text("UPDATE platform.plans SET code='standard' WHERE code='standard-hidden'")
                )
        assert not await _rows(admin_engine, "SELECT 1 FROM app.users WHERE phone=:p", p=phone)
        assert not await _rows(admin_engine, "SELECT 1 FROM app.tenants WHERE phone=:p", p=phone)
        assert not await _rows(
            admin_engine,
            "SELECT 1 FROM auth.user_credentials c JOIN app.users u ON u.id=c.user_id WHERE u.phone=:p",
            p=phone,
        )
        # nothing was half-created, and the ticket survived: the retry succeeds
        retry = await client.post("/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN)
        assert retry.status_code == 201, retry.text
    tenant_id = UUID(retry.json()["tenant_id"])
    assert len(await _rows(admin_engine, "SELECT 1 FROM app.roles WHERE tenant_id=:t", t=tenant_id)) == 5


async def test_signup_rate_limited_per_ip_and_cross_origin_refused(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    async with running_app(_settings(migrated_db, redis_url, stub, signup_per_ip_hour=1)) as (_, client):
        cross = await client.post(
            "/auth/signup",
            json=signup_body(str(UUID(int=1)), terms),
            headers={"Origin": "https://evil.example"},
        )
        assert cross.status_code == 403 and cross.json()["error"]["code"] == "CSRF_INVALID"
        no_origin = await client.post("/auth/otp/request", json={"phone": new_phone(), "purpose": "signup"})
        assert no_origin.status_code == 403
        first = await client.post(
            "/auth/signup", json=signup_body(str(UUID(int=1)), terms), headers=SAME_ORIGIN
        )
        assert first.json()["error"]["code"] == "OTP_INVALID"
        limited = await client.post(
            "/auth/signup", json=signup_body(str(UUID(int=1)), terms), headers=SAME_ORIGIN
        )
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.headers["Retry-After"]
    assert ISSUER  # same-origin means the issuer origin
