"""OTP channels, limits and attempts (14 §4.2, §12; 21 §10, §11.1; qaror #34; QT-M17-01/06)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database, tenant_transaction
from app.modules.integrations.otp.wiring import ESKIZ_TEST_TEXT
from tests.conftest import MigratedDb
from tests.support.auth import auth_settings, client_at, new_phone, running_app
from tests.support.auth_signup import Stub, request_otp, start_stub, stub_settings, verify_otp
from tests.support.factories import create_tenant_world

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def stub() -> Iterator[Stub]:
    yield from start_stub()


@pytest.fixture
async def ready(oauth_platform: None, clean_redis: Redis, stub: Stub) -> Stub:
    stub.state.reset()
    return stub


def _settings(migrated_db: MigratedDb, redis_url: str, stub: Stub, **extra: Any):  # type: ignore[no-untyped-def]
    return auth_settings(migrated_db, redis_url, **{**stub_settings(stub), **extra})


async def _linked_user(app_db: Database, admin_engine: AsyncEngine, chat_id: str) -> tuple[str, UUID]:
    """A user whose phone is linked to a Telegram chat (telegram_links, 15 §1.4)."""
    world = await create_tenant_world(app_db, "Telegram do'kon")
    async with app_db.session_factory() as s, tenant_transaction(s, world.tenant_id, user_id=world.user_id):
        await s.execute(
            text("INSERT INTO app.telegram_links (tenant_id, user_id, chat_id) VALUES (:t, :u, :c)"),
            {"t": world.tenant_id, "u": world.user_id, "c": chat_id},
        )
        await s.execute(text("SELECT app.auth_set_credentials(:u, NULL, NULL)"), {"u": world.user_id})
    async with admin_engine.connect() as conn:
        phone = (
            await conn.execute(text("SELECT phone FROM app.users WHERE id=:u"), {"u": world.user_id})
        ).scalar_one()
    return str(phone), world.tenant_id


async def test_telegram_is_the_first_channel_when_linked(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, app_db: Database, admin_engine: AsyncEngine
) -> None:
    phone, _ = await _linked_user(app_db, admin_engine, "777001")
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        response = await request_otp(client, phone, "recovery")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["channel_used"] == "telegram" and body["warnings"] == []
        assert not ready.state.sms
        verified = await verify_otp(client, body["challenge_id"], ready.telegram_code("777001"))
    assert verified.status_code == 200, verified.text
    async with admin_engine.connect() as conn:
        channel = (
            await conn.execute(
                text("SELECT channel FROM auth.otp_challenges WHERE id=:i"), {"i": body["challenge_id"]}
            )
        ).scalar_one()
    assert channel == "telegram"


async def test_telegram_failure_falls_back_to_sms(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, app_db: Database, admin_engine: AsyncEngine
) -> None:
    phone, _ = await _linked_user(app_db, admin_engine, "777002")
    ready.state.telegram_fail = True  # the user blocked the bot
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        body = (await request_otp(client, phone, "recovery")).json()
        assert body["channel_used"] == "sms"
        assert [w["code"] for w in body["warnings"]] == ["TELEGRAM_NOT_LINKED"]
        assert (await verify_otp(client, body["challenge_id"], ready.sms_code(phone))).status_code == 200


async def test_qt_m17_06_no_channel_delivers_503(
    ready: Stub, migrated_db: MigratedDb, redis_url: str
) -> None:
    """QT-M17-06: no Telegram link and Eskiz down → 503 OTP_CHANNEL_UNAVAILABLE."""
    ready.state.sms_fail = True
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        response = await request_otp(client, new_phone())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "OTP_CHANNEL_UNAVAILABLE"


async def test_only_uzbek_numbers_are_accepted(ready: Stub, migrated_db: MigratedDb, redis_url: str) -> None:
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        foreign = await request_otp(client, "+79161234567")
        wrong_purpose = await client.post(
            "/auth/otp/request",
            json={"phone": new_phone(), "purpose": "invite"},
            headers={"Origin": "https://testserver"},
        )
    assert foreign.status_code == 422 and foreign.json()["error"]["details"][0]["field"] == "phone"
    assert wrong_purpose.status_code == 422
    assert not ready.state.sms


async def test_sms_limit_five_per_phone_per_day(ready: Stub, migrated_db: MigratedDb, redis_url: str) -> None:
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, ready)) as (app, client):
        for _ in range(5):
            assert (await request_otp(client, phone)).status_code == 200
        limited = await request_otp(client, phone)
        assert limited.status_code == 429 and limited.json()["error"]["code"] == "RATE_LIMITED"
        assert limited.json()["error"]["params"]["channel"] == "sms" and limited.headers["Retry-After"]
        async with client_at(app, "10.9.9.9") as other_ip:  # the limit is per phone, not per IP
            assert (await request_otp(other_ip, phone)).status_code == 429
    assert len(ready.state.sms) == 5


async def test_telegram_limit_ten_per_phone_per_day(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, app_db: Database, admin_engine: AsyncEngine
) -> None:
    phone, _ = await _linked_user(app_db, admin_engine, "777003")
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        for _ in range(10):
            assert (await request_otp(client, phone, "recovery")).json()["channel_used"] == "telegram"
        limited = await request_otp(client, phone, "recovery")
    assert limited.status_code == 429 and limited.json()["error"]["params"]["channel"] == "telegram"
    assert not ready.state.sms  # a hit Telegram limit never spills over to the costlier SMS


async def test_per_ip_limit_twenty_per_hour(ready: Stub, migrated_db: MigratedDb, redis_url: str) -> None:
    async with running_app(_settings(migrated_db, redis_url, ready, otp_sms_per_ip_hour=3)) as (_, client):
        for _ in range(3):
            assert (await request_otp(client, new_phone())).status_code == 200
        assert (await request_otp(client, new_phone())).status_code == 429


async def test_sms_daily_budget_refuses_when_exhausted(
    ready: Stub, migrated_db: MigratedDb, redis_url: str
) -> None:
    async with running_app(_settings(migrated_db, redis_url, ready, otp_sms_daily_budget=2)) as (_, client):
        assert (await request_otp(client, new_phone())).status_code == 200
        assert (await request_otp(client, new_phone())).status_code == 200
        assert (await request_otp(client, new_phone())).status_code == 429


async def test_five_wrong_codes_then_max_attempts(
    ready: Stub, migrated_db: MigratedDb, redis_url: str
) -> None:
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        challenge = (await request_otp(client, phone)).json()["challenge_id"]
        good = ready.sms_code(phone)
        bad = "000000" if good != "000000" else "111111"
        for _ in range(5):
            wrong = await verify_otp(client, challenge, bad)
            assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "OTP_INVALID"
        locked = await verify_otp(client, challenge, good)
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "OTP_MAX_ATTEMPTS"


async def test_expired_and_superseded_codes(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, migrator_engine: AsyncEngine
) -> None:
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, ready)) as (_, client):
        first = (await request_otp(client, phone)).json()["challenge_id"]
        first_code = ready.sms_code(phone)
        second = (await request_otp(client, phone)).json()["challenge_id"]
        # a newer code closes the older challenge of the same (phone, purpose)
        superseded = await verify_otp(client, first, first_code)
        assert superseded.json()["error"]["code"] == "OTP_EXPIRED"
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("UPDATE auth.otp_challenges SET expires_at = now() WHERE id=:i"), {"i": second}
            )
        expired = await verify_otp(client, second, ready.sms_code(phone))
        unknown = await verify_otp(client, str(UUID(int=7)), "123456")
    assert expired.status_code == 400 and expired.json()["error"]["code"] == "OTP_EXPIRED"
    assert unknown.json()["error"]["code"] == "OTP_EXPIRED"


async def test_recovery_is_enumeration_safe(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """14 §12: an unknown phone gets the same answer, but no message and no challenge row."""
    world = await create_tenant_world(app_db, "Enum")
    async with app_db.session_factory() as s, tenant_transaction(s, world.tenant_id, user_id=world.user_id):
        await s.execute(text("SELECT app.auth_set_credentials(:u, NULL, NULL)"), {"u": world.user_id})
    async with admin_engine.connect() as conn:
        known = str(
            (
                await conn.execute(text("SELECT phone FROM app.users WHERE id=:u"), {"u": world.user_id})
            ).scalar_one()
        )
    unknown = new_phone()
    async with running_app(_settings(migrated_db, redis_url, ready, otp_recovery_min_response_ms=50)) as (
        _,
        client,
    ):
        a = await request_otp(client, known, "recovery")
        b = await request_otp(client, unknown, "recovery")
        assert a.status_code == b.status_code == 200
        assert (
            set(a.json()) == set(b.json()) and a.json()["channel_used"] == b.json()["channel_used"] == "sms"
        )
        decoy = await verify_otp(client, b.json()["challenge_id"], "123456")
    assert decoy.json()["error"]["code"] == "OTP_INVALID"
    assert [m["mobile_phone"] for m in ready.state.sms] == [known.lstrip("+")]
    async with admin_engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT count(*) FROM auth.otp_challenges WHERE phone=:p"), {"p": unknown}
            )
        ).scalar_one()
        audit = (
            (
                await conn.execute(
                    text("SELECT action FROM app.audit_log WHERE tenant_id=:t AND action LIKE 'otp_%'"),
                    {"t": world.tenant_id},
                )
            )
            .scalars()
            .all()
        )
    assert rows == 0
    assert "otp_requested" in audit and "otp_failed" not in audit


async def test_eskiz_test_mode_sends_only_the_allowed_text(
    ready: Stub, migrated_db: MigratedDb, redis_url: str
) -> None:
    """21 §10: ERP_ESKIZ_TEST_MODE=true — Eskiz accepts only its test text; the code is not in the SMS."""
    phone = new_phone()
    async with running_app(_settings(migrated_db, redis_url, ready, eskiz_test_mode=True)) as (_, client):
        response = await request_otp(client, phone)
    assert response.status_code == 200 and response.json()["channel_used"] == "sms"
    assert ready.state.sms[-1]["message"] == ESKIZ_TEST_TEXT
    assert ready.state.sms[-1]["from"] == "4546" and ready.state.sms[-1]["mobile_phone"] == phone.lstrip("+")


async def test_test_number_path_runs_the_real_flow_without_sending(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, admin_engine: AsyncEngine
) -> None:
    """qaror #34: the test-number path — real limits, challenge row and verify; no message leaves."""
    phone = new_phone()
    settings = _settings(migrated_db, redis_url, ready, otp_test_phones=[phone], otp_test_code="246810")
    async with running_app(settings) as (_, client):
        body = (await request_otp(client, phone)).json()
        assert (await verify_otp(client, body["challenge_id"], "111111")).json()["error"][
            "code"
        ] == "OTP_INVALID"
        assert (await verify_otp(client, body["challenge_id"], "246810")).status_code == 200
    assert not ready.state.sms and not ready.state.telegram
    async with admin_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT attempts, verified_at, code_hash FROM auth.otp_challenges WHERE id=:i"),
                {"i": body["challenge_id"]},
            )
        ).one()
    assert row.attempts == 1 and row.verified_at is not None and "246810" not in row.code_hash


async def _recovery_user(app_db: Database, admin_engine: AsyncEngine) -> str:
    world = await create_tenant_world(app_db, "Tiklash")
    async with app_db.session_factory() as s, tenant_transaction(s, world.tenant_id, user_id=world.user_id):
        await s.execute(text("SELECT app.auth_set_credentials(:u, NULL, NULL)"), {"u": world.user_id})
    async with admin_engine.connect() as conn:
        phone = (
            await conn.execute(text("SELECT phone FROM app.users WHERE id=:u"), {"u": world.user_id})
        ).scalar_one()
    return str(phone)


async def test_recovery_decoy_answers_verify_like_a_real_challenge(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """SEC-03: known and unknown phones give the same error sequence (5 × OTP_INVALID, then locked)."""
    known, unknown = await _recovery_user(app_db, admin_engine), new_phone()
    settings = _settings(migrated_db, redis_url, ready, otp_recovery_min_response_ms=10)
    sequences: list[list[str]] = []
    async with running_app(settings) as (_, client):
        for phone in (known, unknown):
            challenge = (await request_otp(client, phone, "recovery")).json()["challenge_id"]
            wrong = "000000" if phone == unknown or ready.sms_code(phone) != "000000" else "111111"
            sequence = []
            for _ in range(7):
                r = await verify_otp(client, challenge, wrong)
                sequence.append(f"{r.status_code} {r.json()['error']['code']}")
            sequences.append(sequence)
    assert sequences[0] == sequences[1]
    assert sequences[0] == ["400 OTP_INVALID"] * 5 + ["429 OTP_MAX_ATTEMPTS"] * 2


def test_recovery_response_floor_is_at_least_one_and_a_half_seconds() -> None:
    from app.core.config import Settings
    from app.modules.auth.application.otp import OtpPolicy

    assert OtpPolicy().recovery_min_response_s >= 1.5
    assert Settings(_env_file=None).otp_recovery_min_response_ms >= 1500  # type: ignore[call-arg]


async def test_refused_requests_do_not_spend_the_sms_budget(
    ready: Stub, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> None:
    """SEC-04: per-phone/IP limits come first; the global budget counts only messages actually sent."""
    phone = new_phone()
    settings = _settings(migrated_db, redis_url, ready, otp_sms_per_phone_day=2, otp_sms_daily_budget=3)
    async with running_app(settings) as (_, client):
        assert [(await request_otp(client, phone)).status_code for _ in range(2)] == [200, 200]
        assert {(await request_otp(client, phone)).status_code for _ in range(10)} == {429}
        keys = [k async for k in clean_redis.scan_iter("otp:send:sms:budget:*")]
        assert len(keys) == 1 and int(await clean_redis.get(keys[0]) or 0) == 2
        # an unknown recovery phone (decoy) sends nothing and spends nothing either
        assert (await request_otp(client, new_phone(), "recovery")).status_code == 200
        assert int(await clean_redis.get(keys[0]) or 0) == 2
        assert (await request_otp(client, new_phone())).status_code == 200  # the 3rd real SMS
        refused = await request_otp(client, new_phone())
    assert refused.status_code == 429 and len(ready.state.sms) == 3


async def test_verify_is_capped_per_phone_per_day_across_challenges(
    ready: Stub, migrated_db: MigratedDb, redis_url: str
) -> None:
    """14 §12: 10 wrong codes / phone / day over every challenge → 429, even with a fresh code."""
    phone = new_phone()
    settings = _settings(migrated_db, redis_url, ready, otp_sms_per_phone_day=10)
    async with running_app(settings) as (_, client):
        failures = 0
        while failures < 10:
            challenge = (await request_otp(client, phone)).json()["challenge_id"]
            wrong = "000000" if ready.sms_code(phone) != "000000" else "111111"
            for _ in range(min(5, 10 - failures)):
                r = await verify_otp(client, challenge, wrong)
                assert r.json()["error"]["code"] == "OTP_INVALID"
                failures += 1
        challenge = (await request_otp(client, phone)).json()["challenge_id"]
        capped = await verify_otp(client, challenge, ready.sms_code(phone))  # even the right code
        other = new_phone()
        free = (await request_otp(client, other)).json()["challenge_id"]
        unaffected = await verify_otp(client, free, ready.sms_code(other))
    assert capped.status_code == 429 and capped.json()["error"]["code"] == "RATE_LIMITED"
    assert "retry-after" in capped.headers
    assert unaffected.status_code == 200  # another phone is not affected


async def test_verify_is_limited_per_ip(ready: Stub, migrated_db: MigratedDb, redis_url: str) -> None:
    settings = _settings(migrated_db, redis_url, ready, otp_verify_per_ip_hour=3)
    async with running_app(settings) as (app, client):
        codes = [(await verify_otp(client, str(UUID(int=i)), "123456")).status_code for i in range(4)]
        by_phone = await client.post(
            "/auth/otp/verify",
            json={"phone": new_phone(), "purpose": "invite", "code": "123456"},
            headers={"Origin": "https://testserver"},
        )
        async with client_at(app, "10.20.30.40") as elsewhere:
            other_ip = await verify_otp(elsewhere, str(UUID(int=99)), "123456")
    assert codes == [400, 400, 400, 429] and by_phone.status_code == 429
    assert other_ip.status_code == 400  # OTP_EXPIRED: the limit is per IP
