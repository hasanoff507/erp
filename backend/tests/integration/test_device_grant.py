"""Store-agent OAuth (14 §2.3, §21; 33 §9.2): RFC 8628 device grant and ``private_key_jwt`` (RFC 7523).
Real app, real PG + Redis; the agent is the protocol-level fake of ``tests/support/agent.py``."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from tests.conftest import MigratedDb
from tests.support.agent import (
    AgentKey,
    agent_platform,
    approve,
    assertion_token,
    client_assertion,
    device_authorize,
    pair_agent,
    poll_token,
    reset_poll_clock,
)
from tests.support.auth import bearer
from tests.support.branches import api, make_shop

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def client(
    oauth_platform: None,
    migrated_db: MigratedDb,
    redis_url: str,
    clean_redis: Redis,
    migrator_engine: AsyncEngine,
) -> AsyncIterator[httpx.AsyncClient]:
    await agent_platform(migrator_engine)
    async with api(migrated_db, redis_url) as (_, c):
        yield c


async def _status(admin_engine: AsyncEngine, user_code: str) -> str:
    async with admin_engine.connect() as conn:
        value = (
            await conn.execute(
                text(
                    "SELECT status FROM auth.onec_device_authorizations WHERE user_code = :c "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"c": user_code.replace("-", "")},
            )
        ).scalar()
    return str(value)


async def test_device_grant_authorization_response_shape(
    client: httpx.AsyncClient, admin_engine: AsyncEngine
) -> None:
    key = AgentKey()
    r = await device_authorize(client, key)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert len(body["device_code"]) == 43 and body["expires_in"] == 600 and body["interval"] == 5
    code = body["user_code"]
    assert len(code) == 9 and code[4] == "-" and set(code.replace("-", "")) <= set("BCDFGHJKLMNPQRSTVWXZ")
    assert body["verification_uri"].endswith("/app/settings/onec/pair")
    assert body["verification_uri_complete"].endswith(f"?user_code={code.replace('-', '')}")
    # only the SHA-256 of the device code is stored (14 §2.3)
    async with admin_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT device_code_hash, public_key_thumbprint, status FROM auth.onec_device_authorizations "
                    "WHERE user_code = :c"
                ),
                {"c": code.replace("-", "")},
            )
        ).one()
    assert row[0] != body["device_code"] and len(row[0]) == 64
    assert row[1] == key.thumbprint and row[2] == "pending"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("client_id", "android-pos", "invalid_client"),
        ("scope", "onec.agent sync", "invalid_scope"),
        ("public_jwk", '{"kty":"RSA","n":"x","e":"AQAB"}', "invalid_request"),
        ("public_jwk", '{"kty":"OKP","crv":"Ed25519","x":"short"}', "invalid_request"),
        ("machine_hash", "XYZ", "invalid_request"),
        ("pc_name", "", "invalid_request"),
    ],
)
async def test_device_grant_authorization_rejects_bad_input(
    client: httpx.AsyncClient, field: str, value: str, error: str
) -> None:
    r = await device_authorize(client, AgentKey(), **{field: value})
    assert r.status_code == 400 and r.json()["error"] == error


async def test_device_grant_private_key_material_refused(client: httpx.AsyncClient) -> None:
    key = AgentKey()
    jwk = {**key.public_jwk, "d": "AAAA"}
    r = await device_authorize(client, key, public_jwk=json.dumps(jwk))
    assert r.status_code == 400 and r.json()["error_description"] == "public_jwk"


async def test_device_grant_rate_limited_per_ip(
    migrated_db: MigratedDb, redis_url: str, oauth_platform: None, clean_redis: Redis
) -> None:
    async with api(migrated_db, redis_url) as (app, _):
        transport = httpx.ASGITransport(app=app, client=("10.9.8.7", 50002))
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as c:
            for _ in range(10):
                assert (await device_authorize(c, AgentKey())).status_code == 200
            limited = await device_authorize(c, AgentKey())
    assert limited.status_code == 429 and limited.json()["error_description"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0


async def test_qt_m19_01_device_grant_pairing_one_token(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M19-01 (device part): pending → slow_down → approved → one token; the second poll is refused."""
    shop = await make_shop(app_db, client)
    started = (await device_authorize(client, AgentKey())).json()
    pending = await poll_token(client, started["device_code"])
    assert pending.status_code == 400 and pending.json()["error"] == "authorization_pending"
    fast = await poll_token(client, started["device_code"])  # < interval: slow_down, state unchanged
    assert fast.status_code == 400 and fast.json()["error"] == "slow_down"
    assert await _status(admin_engine, started["user_code"]) == "pending"
    paired = await approve(client, shop.owner, started["user_code"].lower())  # case/dash-insensitive
    assert paired.status_code == 201, paired.text
    await reset_poll_clock(admin_engine, started["user_code"])
    token = await poll_token(client, started["device_code"])
    assert token.status_code == 200, token.text
    body = token.json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 600 and body["scope"] == "onec.agent"
    assert "refresh_token" not in body
    assert body["agent_client_id"] == f"onec-agent:{body['agent_id']}" and body["tenant_name"] == "Do'kon"
    assert body["task_keyset"] and body["task_keyset"].count(".") == 2
    await reset_poll_clock(admin_engine, started["user_code"])
    again = await poll_token(client, started["device_code"])
    assert again.status_code == 400 and again.json()["error"] == "invalid_grant"
    assert await _status(admin_engine, started["user_code"]) == "consumed"


async def test_device_grant_denied_gives_access_denied(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    started = (await device_authorize(client, AgentKey())).json()
    code = started["user_code"]
    denied = await client.post(
        f"/api/v1/onec-agents/pairing-requests/{code}/deny", headers=shop.owner.headers(write=True)
    )
    assert denied.status_code == 204, denied.text
    r = await poll_token(client, started["device_code"])
    assert r.status_code == 400 and r.json()["error"] == "access_denied"
    again = await approve(client, shop.owner, code)
    assert again.status_code == 404 and again.json()["error"]["code"] == "ONEC_PAIRING_CODE_INVALID"


async def test_device_grant_expired_code(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    started = (await device_authorize(client, AgentKey())).json()
    code = started["user_code"].replace("-", "")
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE auth.onec_device_authorizations SET expires_at = now() - interval '1 second' "
                "WHERE user_code = :c"
            ),
            {"c": code},
        )
    lookup = await client.get(f"/api/v1/onec-agents/pairing-requests/{code}", headers=shop.owner.headers())
    assert lookup.status_code == 409 and lookup.json()["error"]["code"] == "ONEC_PAIRING_CODE_EXPIRED"
    pair = await approve(client, shop.owner, code)
    assert pair.status_code == 409 and pair.json()["error"]["code"] == "ONEC_PAIRING_CODE_EXPIRED"
    r = await poll_token(client, started["device_code"])
    assert r.status_code == 400 and r.json()["error"] == "expired_token"
    unknown = await poll_token(client, "x" * 43)
    assert unknown.status_code == 400 and unknown.json()["error"] == "invalid_grant"


async def test_device_grant_private_key_jwt_token(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M19-01: ``private_key_jwt`` → 10-minute ``aud=urn:erp:onec-agent`` token, no refresh token."""
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    r = await assertion_token(client, fx)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expires_in"] == 600 and body["scope"] == "onec.agent" and "refresh_token" not in body
    payload = json.loads(_b64(body["access_token"].split(".")[1]))
    assert payload["aud"] == "urn:erp:onec-agent" and payload["sub"] == fx.client_id
    assert payload["agent_id"] == str(fx.agent_id) and payload["tenant_id"] == str(fx.tenant_id)
    assert payload["device_id"] == str(fx.device_id) and payload["exp"] - payload["iat"] == 600
    assert "sid" not in payload and "roles" not in payload and "branch_ids" not in payload
    # the agent token works on the agent API …
    ok = await client.get(
        "/api/v1/onec-agent/task-keys", headers=fx.with_token(body["access_token"]).headers()
    )
    assert ok.status_code == 200, ok.text


async def test_device_grant_agent_token_rejected_by_tenant_api(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """14 §2.3 audience separation (confused deputy) — both directions."""
    shop = await make_shop(app_db, client)
    fx = await pair_agent(client, shop, admin_engine)
    tenant_api = await client.get("/api/v1/onec-agents", headers=bearer(fx.token))
    assert tenant_api.status_code == 401
    user_on_agent_api = await client.get(
        "/api/v1/onec-agent/task-keys", headers={**fx.headers(), **bearer(shop.owner.token)}
    )
    assert user_on_agent_api.status_code == 401


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("lifetime", "exp > iat + 60"),
        ("audience", "wrong aud"),
        ("issuer", "iss != client_id"),
        ("expired", "exp in the past"),
        ("future", "iat beyond tolerance"),
        ("foreign_key", "signed by another key"),
    ],
)
async def test_device_grant_private_key_jwt_rejects_bad_assertion(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine, variant: str, reason: str
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    now = int(time.time())
    assertion = {
        "lifetime": lambda: client_assertion(fx, lifetime=61),
        "audience": lambda: client_assertion(fx, aud="https://evil.example/oauth/token"),
        "issuer": lambda: client_assertion(fx, iss="onec-agent:" + str(uuid.uuid4())),
        "expired": lambda: client_assertion(fx, iat=now - 300),
        "future": lambda: client_assertion(fx, iat=now + 600),
        "foreign_key": lambda: client_assertion(fx, key=AgentKey()),
    }[variant]()
    r = await assertion_token(client, fx, assertion)
    assert r.status_code == 401 and r.json()["error"] == "invalid_client", reason


async def test_device_grant_private_key_jwt_jti_single_use(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    assertion = client_assertion(fx, jti="fixed-jti-" + uuid.uuid4().hex)
    first = await assertion_token(client, fx, assertion)
    assert first.status_code == 200, first.text
    replay = await assertion_token(client, fx, assertion)
    assert replay.status_code == 401 and replay.json()["error_description"] == "assertion_replayed"


async def test_device_grant_private_key_jwt_unknown_agent_and_scope(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
    stranger = fx.__class__(fx.shop, fx.key, uuid.uuid4(), fx.device_id, fx.token, fx.machine_hash)
    r = await assertion_token(client, stranger, client_assertion(stranger))
    assert r.status_code == 401 and r.json()["error"] == "invalid_client"
    scope = await assertion_token(client, fx, scope="onec.agent sales")
    assert scope.status_code == 400 and scope.json()["error"] == "invalid_scope"


async def test_device_grant_revoked_agent_gets_invalid_client(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    fx = await pair_agent(client, shop, admin_engine)
    revoked = await client.post(
        f"/api/v1/onec-agents/{fx.agent_id}/revoke",
        json={"reason": "key_compromised"},
        headers=shop.owner.headers(write=True),
    )
    assert revoked.status_code == 200, revoked.text
    r = await assertion_token(client, fx)
    assert r.status_code == 401 and r.json() == {
        "error": "invalid_client",
        "error_description": "agent_revoked",
    }


async def test_device_grant_metadata_advertises_agent_grants(client: httpx.AsyncClient) -> None:
    meta = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert meta["device_authorization_endpoint"].endswith("/oauth/device_authorization")
    assert "urn:ietf:params:oauth:grant-type:device_code" in meta["grant_types_supported"]
    assert "private_key_jwt" in meta["token_endpoint_auth_methods_supported"]


def _b64(segment: str) -> bytes:
    import base64

    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
