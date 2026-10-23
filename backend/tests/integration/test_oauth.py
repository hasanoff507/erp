"""OAuth 2.0 AS + RS against real PostgreSQL and Redis (14 §21, 31 QT-OAUTH-01…07). No mocks."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.tokens import token_hash
from scripts.seed import seed_demo_tenant, seed_demo_user
from tests.conftest import MigratedDb
from tests.support.auth import (
    ANDROID_CALLBACK,
    BFF_SECRET,
    ISSUER,
    PASSWORD,
    Pkce,
    android_code,
    android_tokens,
    auth_settings,
    authorize_params,
    bearer,
    bff_login,
    client_at,
    csrf_token,
    exchange_code,
    login_for_code,
    new_phone,
    query_of,
    refresh,
    running_app,
)
from tests.support.ordering import TXN_ORDER

pytestmark = [pytest.mark.db, pytest.mark.redis]


@dataclass(frozen=True)
class World:
    tenant_id: UUID
    owner_id: UUID
    owner_phone: str
    cashier_id: UUID
    cashier_phone: str


async def make_world(db: Database, name: str) -> World:
    tenant_id = uuid7()
    await seed_demo_tenant(db, tenant_id=tenant_id, name=name, phone=new_phone())
    owner_phone, cashier_phone = new_phone(), new_phone()
    owner = await seed_demo_user(db, tenant_id=tenant_id, phone=owner_phone, name="Egasi", password=PASSWORD)
    cashier = await seed_demo_user(
        db,
        tenant_id=tenant_id,
        phone=cashier_phone,
        name="Kassir",
        password=PASSWORD,
        role=SystemRole.CASHIER,
    )
    return World(tenant_id, owner, owner_phone, cashier, cashier_phone)


@pytest.fixture
async def world(oauth_platform: None, app_db: Database, clean_redis: Redis) -> World:
    return await make_world(app_db, "OAuth do'kon")


@pytest.fixture
def settings(migrated_db: MigratedDb, redis_url: str):  # type: ignore[no-untyped-def]
    return auth_settings(migrated_db, redis_url)


def _claims(token: str) -> tuple[dict[str, object], dict[str, object]]:
    def part(i: int) -> dict[str, object]:
        raw = token.split(".")[i]
        data: dict[str, object] = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        return data

    return part(0), part(1)


async def _audit_actions(admin_engine: AsyncEngine, tenant_id: UUID) -> list[str]:
    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text(f"SELECT action FROM app.audit_log WHERE tenant_id = :t ORDER BY {TXN_ORDER}, id"),
            {"t": tenant_id},
        )
        return [r[0] for r in rows]


def _idem() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid7())}


def _basic() -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"web-bff:{BFF_SECRET}".encode()).decode()}


async def _web_bff_tokens(client: httpx.AsyncClient, phone: str, basic: dict[str, str]) -> dict[str, str]:
    """web-bff driven by hand (what the BFF does in-process): code + PKCE + client_secret_basic."""
    pkce = Pkce.new()
    params = authorize_params(pkce, client_id="web-bff", redirect_uri=f"{ISSUER}/auth/callback")
    code = query_of(await login_for_code(client, phone, PASSWORD, params))["code"]
    issued = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{ISSUER}/auth/callback",
            "code_verifier": pkce.verifier,
        },
        headers=basic,
    )
    assert issued.status_code == 200, issued.text
    body: dict[str, str] = issued.json()
    return body


# --- metadata, JWKS ----------------------------------------------------------------------------------
async def test_metadata_and_jwks_rfc8414(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        meta = (await client.get("/.well-known/oauth-authorization-server")).json()
        assert meta["issuer"] == ISSUER
        assert meta["code_challenge_methods_supported"] == ["S256"]
        # client_credentials + device_code: the store agent only (14 §2.3, Bosqich 5)
        assert meta["grant_types_supported"] == [
            "authorization_code",
            "refresh_token",
            "client_credentials",
            "urn:ietf:params:oauth:grant-type:device_code",
        ]
        assert "implicit" not in json.dumps(meta) and "password" not in meta["grant_types_supported"]
        jwks = (await client.get("/.well-known/jwks.json")).json()
        assert jwks["keys"] and all(k["kty"] == "OKP" and k["crv"] == "Ed25519" for k in jwks["keys"])
        assert all("d" not in k for k in jwks["keys"])  # never a private part


# --- QT-OAUTH-01 ------------------------------------------------------------------------------------
async def test_qt_oauth_01_plain_code_challenge_is_rejected(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        pkce = Pkce.new()
        for method in ("plain", None):  # explicit plain, and the RFC 7636 default (plain)
            page = await client.get("/oauth/authorize", params=authorize_params(pkce, method=method))
            assert page.status_code == 302
            query = query_of(page)
            assert query["error"] == "invalid_request" and "code" not in query
            posted = await login_for_code(
                client, world.owner_phone, PASSWORD, authorize_params(pkce, method=method)
            )
            assert posted.status_code == 302 and "code" not in query_of(posted)
        no_challenge = authorize_params(pkce)
        no_challenge.pop("code_challenge")
        page = await client.get("/oauth/authorize", params=no_challenge)
        assert query_of(page)["error"] == "invalid_request"
        # unknown redirect_uri: never redirected to (RFC 6749 §4.1.2.1)
        bad = await client.get(
            "/oauth/authorize", params=authorize_params(pkce, redirect_uri="https://evil.example/cb")
        )
        assert bad.status_code == 400 and "location" not in bad.headers
        ok = await client.get("/oauth/authorize", params=authorize_params(pkce))
        assert ok.status_code == 200 and 'name="password"' in ok.text
        assert "frame-ancestors 'none'" in ok.headers["content-security-policy"]


# --- QT-OAUTH-02 ------------------------------------------------------------------------------------
async def test_qt_oauth_02_code_verifier_and_single_use(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        pkce = Pkce.new()
        code = await android_code(client, world.owner_phone, pkce)
        wrong = await exchange_code(client, code, Pkce.new().verifier)
        assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
        # the failed attempt burnt the code (single use, conservative)
        assert (await exchange_code(client, code, pkce.verifier)).status_code == 400

        pkce = Pkce.new()
        code = await android_code(client, world.owner_phone, pkce)
        mismatch = await exchange_code(client, code, pkce.verifier, redirect_uri=f"{ISSUER}/other")
        assert mismatch.status_code == 400 and mismatch.json()["error"] == "invalid_grant"

        pkce = Pkce.new()
        code = await android_code(client, world.owner_phone, pkce)
        ok = await exchange_code(client, code, pkce.verifier)
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["expires_in"] == 900 and body["token_type"] == "Bearer"  # qaror #44
        assert ok.headers["cache-control"] == "no-store"
        header, claims = _claims(body["access_token"])
        assert header["typ"] == "at+jwt" and header["alg"] == "EdDSA" and header["kid"]
        assert claims["iss"] == ISSUER and claims["aud"] == "urn:erp:api"
        assert claims["sub"] == str(world.owner_id) and claims["tenant_id"] == str(world.tenant_id)
        assert claims["client_id"] == "android-pos" and claims["roles"] == ["owner"]
        assert claims["exp"] - claims["iat"] == 900 and claims["jti"] and claims["sub_status"] == "trial"
        assert "sid" not in claims  # public client: no BFF session
        scopes = set(str(claims["scope"]).split())
        assert {"sales", "settings", "billing", "sync", "pos"} <= scopes and "platform" not in scopes

        again = await exchange_code(client, code, pkce.verifier)
        assert again.status_code == 400 and again.json()["error"] == "invalid_grant"


async def test_end_to_end_android_bearer_and_cashier_scope(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        cashier = await android_tokens(client, world.cashier_phone)
        _, claims = _claims(cashier["access_token"])
        assert claims["roles"] == ["cashier"]
        assert "settings" not in str(claims["scope"]).split()
        # scope is the fast first filter: no settings.* prefix → 403 before any DB lookup
        r = await client.patch(
            f"/api/v1/admin/users/{world.owner_id}",
            json={"status": "blocked"},
            headers={**bearer(cashier["access_token"]), **_idem()},
        )
        assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED"
        # no token / garbage token
        assert (await client.get("/auth/session")).status_code == 401
        r = await client.get("/auth/session", headers=bearer("abc.def.ghi"))
        assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Bearer")


# --- QT-OAUTH-03 / 04 -------------------------------------------------------------------------------
async def test_qt_oauth_03_refresh_reuse_revokes_family(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine
) -> None:
    async with running_app(settings) as (_, client):
        tokens = await android_tokens(client, world.owner_phone)
        rt1 = tokens["refresh_token"]
        rotated = await refresh(client, rt1)
        assert rotated.status_code == 200, rotated.text
        rt2, at2 = rotated.json()["refresh_token"], rotated.json()["access_token"]
        assert rt2 != rt1
        assert (await client.get("/auth/session", headers=bearer(at2))).status_code == 200
        # RT1 comes back after the 30 s grace window (stolen copy)
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE auth.refresh_tokens SET used_at = used_at - interval '31 seconds' WHERE token_hash = :h"
                ),
                {"h": token_hash(rt1)},
            )
        reuse = await refresh(client, rt1)
        assert reuse.status_code == 400 and reuse.json()["error"] == "invalid_grant"
        # the whole family is dead: the legitimate holder of RT2 must log in again
        assert (await refresh(client, rt2)).status_code == 400
        r = await client.get("/auth/session", headers=bearer(at2))
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        async with admin_engine.connect() as conn:
            alive = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM auth.refresh_tokens t JOIN auth.refresh_tokens o "
                        "ON o.family_id = t.family_id WHERE o.token_hash = :h AND t.revoked_at IS NULL"
                    ),
                    {"h": token_hash(rt1)},
                )
            ).scalar()
        assert alive == 0
        assert "refresh_token_reuse_detected" in await _audit_actions(admin_engine, world.tenant_id)


async def test_qt_oauth_03_reuse_also_revokes_bff_session(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine
) -> None:
    basic = _basic()
    async with running_app(settings) as (_, client):
        tokens = await _web_bff_tokens(client, world.owner_phone, basic)
        sid = _claims(tokens["access_token"])[1]["sid"]
        rt1 = tokens["refresh_token"]
        rotated = await client.post(
            "/oauth/token", data={"grant_type": "refresh_token", "refresh_token": rt1}, headers=basic
        )
        assert rotated.status_code == 200, rotated.text
        at2 = rotated.json()["access_token"]
        assert _claims(at2)[1]["sid"] == sid  # same session, new token pair
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE auth.refresh_tokens SET used_at = used_at - interval '31 seconds' WHERE token_hash = :h"
                ),
                {"h": token_hash(rt1)},
            )
        reuse = await client.post(
            "/oauth/token", data={"grant_type": "refresh_token", "refresh_token": rt1}, headers=basic
        )
        assert reuse.status_code == 400 and reuse.json()["error"] == "invalid_grant"
        async with admin_engine.connect() as conn:
            revoked = (
                await conn.execute(
                    text("SELECT revoked_reason FROM auth.sessions WHERE id = CAST(:s AS uuid)"), {"s": sid}
                )
            ).scalar_one()
        assert revoked == "reuse_detected"
        r = await client.get("/auth/session", headers=bearer(at2))
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"


async def test_qt_oauth_04_retry_within_grace_keeps_family(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        tokens = await android_tokens(client, world.owner_phone)
        rt1 = tokens["refresh_token"]
        first = await refresh(client, rt1)
        assert first.status_code == 200
        # the response was lost on the network: the device retries RT1 within 30 s
        retry = await refresh(client, rt1)
        assert retry.status_code == 200, retry.text
        assert retry.json()["refresh_token"] == first.json()["refresh_token"]  # RT2, not a new one
        assert (
            await client.get("/auth/session", headers=bearer(retry.json()["access_token"]))
        ).status_code == 200
        # the family is intact: RT2 rotates normally
        third = await refresh(client, first.json()["refresh_token"])
        assert third.status_code == 200, third.text


async def test_parallel_bff_refresh_is_single_flight(  # type: ignore[no-untyped-def]
    world: World, migrated_db: MigratedDb, redis_url: str
) -> None:
    # TTL 60 s = refresh skew: every request finds the access token "due", so all 5 race to refresh
    settings = auth_settings(migrated_db, redis_url, access_token_ttl_s=60)
    async with running_app(settings) as (_, client):
        await bff_login(client, world.owner_phone)
        results = await asyncio.gather(*(client.get("/auth/session") for _ in range(5)))
        assert [r.status_code for r in results] == [200] * 5
        assert (await client.get("/auth/session")).status_code == 200  # session survived (no reuse)


# --- QT-OAUTH-05 / 06 -------------------------------------------------------------------------------
async def test_qt_oauth_05_bff_cookie_writes_need_csrf(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        sid_cookie = await bff_login(client, world.owner_phone)
        session = await client.get("/auth/session")
        assert session.status_code == 200
        assert session.json()["tenant"]["id"] == str(world.tenant_id)
        assert "access_token" not in session.text  # tokens never reach the browser
        url = f"/api/v1/admin/users/{world.cashier_id}"
        no_token = await client.patch(url, json={"status": "active"}, headers=_idem())
        assert no_token.status_code == 403 and no_token.json()["error"]["code"] == "CSRF_INVALID"
        # a token bound to another session is "stale"
        async with httpx.AsyncClient(transport=client._transport, base_url=ISSUER) as other:
            await bff_login(other, world.owner_phone)
            foreign = await csrf_token(other)
        stale = await client.patch(
            url, json={"status": "active"}, headers={"X-CSRF-Token": foreign, **_idem()}
        )
        assert stale.status_code == 403 and stale.json()["error"]["code"] == "CSRF_INVALID"
        token = await csrf_token(client)
        ok = await client.patch(url, json={"status": "active"}, headers={"X-CSRF-Token": token, **_idem()})
        assert ok.status_code == 200, ok.text
        # logout is a cookie write too
        assert (await client.post("/auth/logout")).status_code == 403
        out = await client.post("/auth/logout", headers={"X-CSRF-Token": token})
        assert out.status_code == 204
        client.cookies.set("__Host-sid", sid_cookie)
        assert (await client.get("/auth/session")).status_code == 401


async def test_qt_oauth_06_android_bearer_is_csrf_exempt(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        owner = await android_tokens(client, world.owner_phone)
        r = await client.patch(
            f"/api/v1/admin/users/{world.cashier_id}",
            json={"status": "active"},
            headers={**bearer(owner["access_token"]), **_idem()},
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"user_id": str(world.cashier_id), "status": "active", "sessions_revoked": 0}


# --- QT-OAUTH-07 ------------------------------------------------------------------------------------
async def test_qt_oauth_07_block_revokes_everything_immediately(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (app, owner_client):
        owner = await android_tokens(owner_client, world.owner_phone)
        async with client_at(app, "10.0.0.7") as cashier_web:
            await bff_login(cashier_web, world.cashier_phone)
            cashier_android = await android_tokens(owner_client, world.cashier_phone)
            assert (await cashier_web.get("/auth/session")).status_code == 200
            assert (
                await owner_client.get("/auth/session", headers=bearer(cashier_android["access_token"]))
            ).status_code == 200

            blocked = await owner_client.patch(
                f"/api/v1/admin/users/{world.cashier_id}",
                json={"status": "blocked"},
                headers={**bearer(owner["access_token"]), **_idem()},
            )
            assert blocked.status_code == 200, blocked.text
            assert blocked.json()["sessions_revoked"] >= 1

            # immediately — not on the next refresh
            web = await cashier_web.get("/auth/session")
            assert web.status_code == 401
            r = await owner_client.get("/auth/session", headers=bearer(cashier_android["access_token"]))
            assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
            assert (await refresh(owner_client, cashier_android["refresh_token"])).status_code == 400
            async with admin_engine.connect() as conn:
                live = (
                    await conn.execute(
                        text(
                            "SELECT (SELECT count(*) FROM auth.sessions WHERE user_id = :u AND revoked_at IS NULL) "
                            "+ (SELECT count(*) FROM auth.refresh_tokens WHERE user_id = :u AND revoked_at IS NULL)"
                        ),
                        {"u": world.cashier_id},
                    )
                ).scalar()
            assert live == 0
            sids = await clean_redis.keys("auth:sid_revoked:*")
            assert sids, "Redis sid-revoke cache must be updated"
            # and the blocked user cannot log in again
            pkce = Pkce.new()
            denied = await login_for_code(owner_client, world.cashier_phone, PASSWORD, authorize_params(pkce))
            assert denied.status_code == 403
            actions = await _audit_actions(admin_engine, world.tenant_id)
            assert "membership_status_changed" in actions and "all_sessions_revoked" in actions


# --- revoke / introspect (RFC 7009 / 7662) ----------------------------------------------------------
async def test_revoke_and_introspect(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    basic = _basic()
    async with running_app(settings) as (_, client):
        issued = await _web_bff_tokens(client, world.owner_phone, basic)
        access, refresh_token = issued["access_token"], issued["refresh_token"]
        assert "sid" in _claims(access)[1]
        # public clients may not introspect; confidential clients see their own tokens
        public = await client.post("/oauth/introspect", data={"token": access, "client_id": "android-pos"})
        assert public.status_code in (400, 401)
        live = await client.post("/oauth/introspect", data={"token": access}, headers=basic)
        assert live.json()["active"] is True and live.json()["client_id"] == "web-bff"
        rt_live = await client.post("/oauth/introspect", data={"token": refresh_token}, headers=basic)
        assert rt_live.json()["active"] is True and rt_live.json()["token_type"] == "refresh_token"

        revoked = await client.post(
            "/oauth/revoke", data={"token": refresh_token, "token_type_hint": "refresh_token"}, headers=basic
        )
        assert revoked.status_code == 200
        # the not-yet-expired JWT of that session is rejected through the sid-revoke cache (14 §21)
        r = await client.get("/auth/session", headers=bearer(access))
        assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"
        dead = await client.post("/oauth/introspect", data={"token": access}, headers=basic)
        assert dead.json() == {"active": False}
        dead_rt = await client.post("/oauth/introspect", data={"token": refresh_token}, headers=basic)
        assert dead_rt.json() == {"active": False}
        # android-pos may not revoke a web-bff token
        other = await client.post("/oauth/revoke", data={"token": access, "client_id": "android-pos"})
        assert other.status_code == 400


async def test_android_revoke_access_token_without_sid(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        tokens = await android_tokens(client, world.owner_phone)
        r = await client.post(
            "/oauth/revoke", data={"token": tokens["access_token"], "client_id": "android-pos"}
        )
        assert r.status_code == 200
        assert (await client.get("/auth/session", headers=bearer(tokens["access_token"]))).status_code == 401
        r = await client.post(
            "/oauth/revoke", data={"token": tokens["refresh_token"], "client_id": "android-pos"}
        )
        assert r.status_code == 200
        assert (await refresh(client, tokens["refresh_token"])).status_code == 400


# --- brute force (14 §12) ---------------------------------------------------------------------------
async def test_login_lockout_is_per_phone_and_ip(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine
) -> None:
    async with running_app(settings) as (app, client):
        params = authorize_params(Pkce.new())
        for _ in range(5):
            r = await login_for_code(client, world.owner_phone, "wrong-password", params)
            assert r.status_code == 401 and "noto&#x27;g&#x27;ri" in r.text
        locked = await login_for_code(client, world.owner_phone, PASSWORD, params)
        assert locked.status_code == 423 and int(locked.headers["retry-after"]) > 0
        # another source with the right password is not locked out (anti lockout-DoS)
        async with client_at(app, "10.9.9.9") as elsewhere:
            ok = await login_for_code(elsewhere, world.owner_phone, PASSWORD, params)
            assert ok.status_code == 302 and "code" in query_of(ok)
        # unknown phone: same answer as a wrong password (no enumeration)
        unknown = await login_for_code(client, new_phone(), "whatever-123", params)
        assert unknown.status_code == 401
        async with admin_engine.connect() as conn:
            attempts = (
                await conn.execute(
                    text("SELECT count(*) FROM auth.login_attempts WHERE phone = :p AND NOT success"),
                    {"p": world.owner_phone},
                )
            ).scalar()
        assert attempts == 5
        actions = await _audit_actions(admin_engine, world.tenant_id)
        assert (
            actions.count("login_failed") == 5 and "account_locked" in actions and "login_success" in actions
        )


async def test_login_post_requires_same_origin(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        params = {**authorize_params(Pkce.new()), "phone": world.owner_phone, "password": PASSWORD}
        cross = await client.post("/oauth/authorize", data=params, headers={"Origin": "https://evil.example"})
        assert cross.status_code == 403
        missing = await client.post("/oauth/authorize", data=params)
        assert missing.status_code == 403


async def test_local_vite_login_origin_is_local_only(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    params = {**authorize_params(Pkce.new()), "phone": world.owner_phone, "password": PASSWORD}
    local_settings = settings.model_copy(update={"environment": "local"})
    async with running_app(local_settings) as (_, client):
        proxied = await client.post(
            "/oauth/authorize", data=params, headers={"Origin": "http://localhost:5173"}
        )
        assert proxied.status_code == 302 and "code" in query_of(proxied)
        cross = await client.post("/oauth/authorize", data=params, headers={"Origin": "https://evil.example"})
        assert cross.status_code == 403

    # A Vite origin is not trusted in test, staging, or production environments.
    async with running_app(settings) as (_, client):
        proxied = await client.post(
            "/oauth/authorize", data=params, headers={"Origin": "http://localhost:5173"}
        )
        assert proxied.status_code == 403


# --- subscription lockout (14 §16) ------------------------------------------------------------------
async def test_subscription_lockout_and_sync_drain(  # type: ignore[no-untyped-def]
    world: World, settings, admin_engine: AsyncEngine, clean_redis: Redis
) -> None:
    async with running_app(settings) as (_, client):
        tokens = await android_tokens(client, world.owner_phone)
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE app.subscriptions SET status = 'restricted' WHERE tenant_id = :t"),
                {"t": world.tenant_id},
            )
        await clean_redis.set(f"sub_status:{world.tenant_id}", "restricted")
        # (b) a still-valid access token is rejected through the Redis cache
        r = await client.get("/auth/session", headers=bearer(tokens["access_token"]))
        assert r.status_code == 403 and r.json()["error"]["code"] == "SUBSCRIPTION_RESTRICTED"
        # (a) refresh is refused while the family is not suspended yet
        denied = await refresh(client, tokens["refresh_token"])
        assert denied.status_code == 403 and denied.json()["error_description"] == "subscription_restricted"
        # login is refused
        locked = await login_for_code(client, world.owner_phone, PASSWORD, authorize_params(Pkce.new()))
        assert locked.status_code == 403
        # scheduler suspends the tenant: the same RT now yields only a short sync.drain token
        async with admin_engine.begin() as conn:
            await conn.execute(text("SELECT app.auth_suspend_tenant(:t, true)"), {"t": world.tenant_id})
        drain = await refresh(client, tokens["refresh_token"])
        assert drain.status_code == 200, drain.text
        assert drain.json()["scope"] == "sync.drain" and drain.json()["expires_in"] == 300
        r = await client.get("/auth/session", headers=bearer(drain.json()["access_token"]))
        assert r.status_code == 403  # sync.drain opens only /sync/push
        # (c) payment: status active again, cache updated, tokens back to normal (no re-login)
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE app.subscriptions SET status = 'active' WHERE tenant_id = :t"),
                {"t": world.tenant_id},
            )
            await conn.execute(text("SELECT app.auth_suspend_tenant(:t, false)"), {"t": world.tenant_id})
        await clean_redis.set(f"sub_status:{world.tenant_id}", "active")
        normal = await refresh(client, drain.json()["refresh_token"])
        assert normal.status_code == 200, normal.text
        assert "sales" in normal.json()["scope"].split()
        assert (
            await client.get("/auth/session", headers=bearer(normal.json()["access_token"]))
        ).status_code == 200


# --- signing key rotation (14 §6, §21) --------------------------------------------------------------
async def test_signing_key_rotation_keeps_old_tokens_valid(  # type: ignore[no-untyped-def]
    world: World, settings, migrator_engine: AsyncEngine
) -> None:
    from app.modules.auth.infrastructure.key_admin import rotate_signing_key
    from app.modules.auth.wiring import build_cipher

    async with running_app(settings) as (app, client):
        old = await android_tokens(client, world.owner_phone)
        old_kid = _claims(old["access_token"])[0]["kid"]
        new_kid = str(await rotate_signing_key(migrator_engine, build_cipher(settings)))
        app.state.auth_module.ring.invalidate()
        assert (await client.get("/auth/session", headers=bearer(old["access_token"]))).status_code == 200
        fresh = await android_tokens(client, world.owner_phone)
        assert _claims(fresh["access_token"])[0]["kid"] == new_kid != old_kid
        kids = {k["kid"] for k in (await client.get("/.well-known/jwks.json")).json()["keys"]}
        assert {old_kid, new_kid} <= kids


async def test_token_endpoint_rejects_wrong_client_secret(world: World, settings) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        bad = {"Authorization": "Basic " + base64.b64encode(b"web-bff:not-the-secret").decode()}
        r = await client.post(
            "/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "x"}, headers=bad
        )
        assert r.status_code == 401 and r.json()["error"] == "invalid_client"
        # a confidential client cannot pretend to be public
        r = await client.post(
            "/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "x", "client_id": "web-bff"}
        )
        assert r.status_code in (400, 401) and r.json()["error"] == "invalid_client"
        assert ANDROID_CALLBACK.startswith(ISSUER)


# --- GET /auth/session shape (14 §20) ----------------------------------------------------------------
async def test_auth_session_profile(world: World, settings, clean_redis: Redis) -> None:  # type: ignore[no-untyped-def]
    async with running_app(settings) as (_, client):
        await bff_login(client, world.cashier_phone)
        r = await client.get("/auth/session")
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "no-store"
        body = r.json()
        assert set(body) == {
            "user", "tenant", "branches", "roles", "permissions", "scope", "client_id", "sub_status",
            "access_expires_at", "device",
        }  # fmt: skip
        assert body["device"] is None  # an unbound (non-device) session (14 §7.2)
        phone = world.cashier_phone
        assert body["user"] == {
            "id": str(world.cashier_id),
            "full_name": "Kassir",
            "phone_masked": f"+998 {phone[4:6]} *** ** {phone[-2:]}",
        }
        assert body["tenant"] == {"id": str(world.tenant_id), "name": "OAuth do'kon"}
        assert body["branches"] and all(set(b) == {"id", "name"} for b in body["branches"])
        assert body["roles"] == ["cashier"]
        assert "sales.create" in body["permissions"] and "settings.users" not in body["permissions"]
        assert body["permissions"] == sorted(body["permissions"])
        assert {"sync", "pos"} <= set(body["scope"])  # web-bff runs the web POS (14 §10)
        assert body["client_id"] == "web-bff"
        # the profile part is cached for the ~30 s heartbeat (14 §16.1.4)
        assert await clean_redis.ttl(f"auth:profile:{world.tenant_id}:{world.cashier_id}") > 0
        again = await client.get("/auth/session")
        assert again.json() == body
