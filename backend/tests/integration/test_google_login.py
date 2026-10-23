"""Google sign-in (14 §2.2, 21 §9.3, qaror #34; QT-M17-02) against a local stub IdP with its own key."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
import pytest
from joserfc.jwk import RSAKey
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import MigratedDb
from tests.support.auth import ANDROID_CALLBACK, Pkce, auth_settings, exchange_code, new_phone, running_app
from tests.support.auth_signup import (
    GOOGLE_ANDROID_CLIENT_ID,
    SAME_ORIGIN,
    Stub,
    ensure_terms,
    signup_body,
    start_stub,
    stub_settings,
    verified_signup_challenge,
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


async def _google_round(
    client: httpx.AsyncClient, stub: Stub, claims: dict[str, Any], *, state: str | None = None, **query: str
) -> httpx.Response:
    """Browser: /auth/google/start → (Google consent) → /auth/google/callback?code&state."""
    start = await client.get("/auth/google/start", params={"return_to": "/app"})
    assert start.status_code == 302, start.text
    location = start.headers["location"]
    assert location.startswith(f"{stub.base_url}/google/auth?")
    params = {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
    assert params["code_challenge_method"] == "S256" and params["scope"] == "openid email profile"
    code = f"code-{len(stub.state.google_codes)}-{params['state'][:6]}"
    stub.state.google_codes[code] = {"nonce": params["nonce"], **claims}
    return await client.get(
        "/auth/google/callback", params={"code": code, "state": state or params["state"], **query}
    )


async def _identity_user(engine: AsyncEngine, sub: str) -> UUID | None:
    async with engine.connect() as conn:
        value = (
            await conn.execute(
                text(
                    "SELECT user_id FROM app.user_identities WHERE provider='google' AND provider_user_id=:s"
                ),
                {"s": sub},
            )
        ).scalar()
    return value if isinstance(value, UUID) else None


async def test_qt_m17_02_new_google_account_signs_up_without_password_then_logs_in(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine
) -> None:
    """QT-M17-02: OIDC ok → user_identities, no password, 30-day trial; the next Google login is direct."""
    sub, phone = f"g-{new_phone()}", new_phone()
    claims = {"sub": sub, "email": f"{sub}@gmail.com", "email_verified": True, "name": "Aziz"}
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        first = await _google_round(client, stub, claims)
        assert first.status_code == 302 and first.headers["location"] == "/onboarding?method=google"
        assert client.cookies.get("__Host-erp_google")
        challenge = await verified_signup_challenge(
            client, stub, phone
        )  # the phone (STIR/fiscal) is verified
        body = signup_body(challenge, terms)
        del body["password"]
        created = await client.post("/auth/signup", json=body, headers=SAME_ORIGIN)
        assert created.status_code == 201, created.text
        assert created.json()["sub_status"] == "trial"
        user_id = UUID(created.json()["user_id"])
        assert await _identity_user(admin_engine, sub) == user_id
        assert (await client.get("/auth/session")).status_code == 200
        client.cookies.clear()
        again = await _google_round(client, stub, claims)
        assert again.status_code == 302 and again.headers["location"] == "/app", again.headers
        session = await client.get("/auth/session")
    assert session.status_code == 200 and session.json()["user"]["id"] == str(user_id)
    async with admin_engine.connect() as conn:
        cred = (
            await conn.execute(
                text("SELECT password_hash FROM auth.user_credentials WHERE user_id=:u"), {"u": user_id}
            )
        ).scalar()
        status = (
            await conn.execute(
                text(
                    "SELECT s.status FROM app.subscriptions s JOIN app.memberships m ON m.tenant_id=s.tenant_id WHERE m.user_id=:u"
                ),
                {"u": user_id},
            )
        ).scalar()
    assert cred is None and status == "trial"


async def test_google_account_links_by_verified_email(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, admin_engine: AsyncEngine
) -> None:
    sub, phone = f"g-{new_phone()}", new_phone()
    email = f"{sub}@gmail.com"
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        await _google_round(client, stub, {"sub": sub, "email": email, "email_verified": True})
        challenge = await verified_signup_challenge(client, stub, phone)
        created = await client.post("/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN)
        user_id = UUID(created.json()["user_id"])
        client.cookies.clear()
        other_sub = f"{sub}-second"
        linked = await _google_round(
            client, stub, {"sub": other_sub, "email": email.upper(), "email_verified": True}
        )
    assert linked.status_code == 302 and linked.headers["location"] == "/app"
    assert await _identity_user(admin_engine, other_sub) == user_id


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"email_verified": False}, "google_email_not_verified"),
        ({"aud": "someone-else.apps.googleusercontent.com"}, "google_auth_failed"),
        ({"iss": "https://evil.example"}, "google_auth_failed"),
        ({"exp": 1_000_000}, "google_auth_failed"),
        ({"nonce": "replayed-nonce"}, "google_auth_failed"),
    ],
)
async def test_google_negative_paths_redirect_with_error(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub, claims: dict[str, Any], reason: str
) -> None:
    base = {"sub": f"g-{new_phone()}", "email": "x@gmail.com", "email_verified": True}
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        response = await _google_round(client, stub, {**base, **claims})
    assert response.status_code == 302 and response.headers["location"] == f"/login?error={reason}"
    assert not response.cookies.get("__Host-sid")


async def test_google_state_mismatch_denial_and_token_endpoint_failure(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    base = {"sub": f"g-{new_phone()}", "email": "y@gmail.com", "email_verified": True}
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        mismatch = await _google_round(client, stub, base, state="forged-state")
        denied = await _google_round(client, stub, base, error="access_denied")
        stub.state.google_token_fail = True
        failed = await _google_round(client, stub, base)
        no_cookie = await client.get("/auth/google/callback", params={"code": "x", "state": "y"})
    assert mismatch.headers["location"] == "/login?error=state_mismatch"
    assert denied.headers["location"] == "/login?error=google_auth_failed"
    assert failed.headers["location"] == "/login?error=google_auth_failed"
    assert no_cookie.headers["location"] == "/login?error=login_state_missing"


async def test_android_google_token_returns_a_pkce_code_for_oauth_token(
    terms: str, migrated_db: MigratedDb, redis_url: str, stub: Stub
) -> None:
    sub, phone = f"g-{new_phone()}", new_phone()
    async with running_app(_settings(migrated_db, redis_url, stub)) as (_, client):
        await _google_round(client, stub, {"sub": sub, "email": f"{sub}@gmail.com", "email_verified": True})
        challenge = await verified_signup_challenge(client, stub, phone)
        assert (
            await client.post("/auth/signup", json=signup_body(challenge, terms), headers=SAME_ORIGIN)
        ).status_code == 201
        client.cookies.clear()
        pkce = Pkce.new()

        def body(token: str) -> dict[str, str]:
            return {"id_token": token, "code_challenge": pkce.challenge, "redirect_uri": ANDROID_CALLBACK}

        native = stub.state.id_token({"sub": sub, "email_verified": True, "aud": GOOGLE_ANDROID_CLIENT_ID})
        issued = await client.post("/auth/google/token", json=body(native))
        assert issued.status_code == 200, issued.text
        tokens = await exchange_code(client, issued.json()["code"], pkce.verifier)
        assert tokens.status_code == 200, tokens.text and tokens.json()["refresh_token"]

        forged = stub.state.id_token(
            {"sub": sub, "email_verified": True}, key=RSAKey.generate_key(2048, parameters={"kid": "stub-1"})
        )
        bad_sig = await client.post("/auth/google/token", json=body(forged))
        unverified = await client.post(
            "/auth/google/token", json=body(stub.state.id_token({"sub": sub, "email_verified": False}))
        )
        unknown = await client.post(
            "/auth/google/token", json=body(stub.state.id_token({"sub": "nobody", "email_verified": True}))
        )
    assert bad_sig.status_code == 401 and bad_sig.json()["error"]["code"] == "GOOGLE_AUTH_FAILED"
    assert unverified.status_code == 403 and unverified.json()["error"]["code"] == "GOOGLE_EMAIL_NOT_VERIFIED"
    assert unknown.status_code == 401 and unknown.json()["error"]["params"]["reason"] == "account_not_found"


async def test_google_not_configured_is_google_auth_failed(
    terms: str, migrated_db: MigratedDb, redis_url: str
) -> None:
    """WEB-05: a browser GET never ends on JSON — back to the login page with the error."""
    async with running_app(auth_settings(migrated_db, redis_url)) as (_, client):
        response = await client.get("/auth/google/start")
        token = await client.post("/auth/google/token", json=_android_body())
    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=google_auth_failed"
    assert "set-cookie" not in response.headers
    assert token.status_code == 401 and token.json()["error"]["code"] == "GOOGLE_AUTH_FAILED"


def _android_body() -> dict[str, str]:
    return {
        "id_token": "x" * 40, "code_challenge": "c" * 43, "redirect_uri": ANDROID_CALLBACK,
    }  # fmt: skip


async def test_google_entry_points_are_rate_limited_per_ip(
    terms: str, migrated_db: MigratedDb, redis_url: str
) -> None:
    """SEC-11 (14 §12): 30 / IP / 10 min on /auth/google/start and /auth/google/token → 429."""
    async with running_app(auth_settings(migrated_db, redis_url)) as (_, client):
        starts = [(await client.get("/auth/google/start")).status_code for _ in range(31)]
        tokens = [
            (await client.post("/auth/google/token", json=_android_body())).status_code for _ in range(31)
        ]
        limited = await client.get("/auth/google/start")
    assert starts[:30] == [302] * 30 and starts[30] == 429
    assert tokens[:30] == [401] * 30 and tokens[30] == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED" and "retry-after" in limited.headers
