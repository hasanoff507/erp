"""Protocol-level fake store agent (31 M19 "protocol darajasidagi soxta agent"): real app, real PG + Redis.

* :class:`AgentKey` — the agent's Ed25519 key pair (DPAPI on the real PC) and its RFC 7638 thumbprint;
* :func:`pair_agent` — RFC 8628 device authorization → owner W-04 → device-code token (14 §2.3);
* :func:`client_assertion` / :func:`agent_token` — ``private_key_jwt`` (RFC 7523);
* :func:`agent_platform` — the deploy steps the A-API needs: an ``onec_task`` signing key, a task keyset
  and an update manifest signed by the test ``agent_update`` root key (RFC 8032 §7.1 TEST 2 — public).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.auth.application.compact_jws import public_jwk_of, sign_compact
from app.modules.auth.domain.agent_keys import jwk_thumbprint
from tests.support.auth import ISSUER, bearer
from tests.support.branches import Member, Shop

TEST_ROOT_SEED = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"  # RFC 8032 TEST 2
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
JWT_BEARER = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
AGENT_VERSION = "1.4.2"

FULL_CAPABILITIES: dict[str, Any] = {
    "onec": {"enabled": False, "version": 0},
    "fiscal": {
        "enabled": True,
        "version": 1,
        "provider": "multikassa_local",
        "devices": [{"local_id": "fm-1", "status": "ok"}],
    },
    "print": {
        "enabled": True,
        "version": 1,
        "devices": [
            {"local_id": "pr-1", "transport": "tcp9100", "host": "192.168.1.50", "port": 9100, "status": "ok"}
        ],
    },
    "scale": {"enabled": False, "version": 0, "devices": []},
    "card_terminal": {
        "enabled": True,
        "version": 1,
        "devices": [{"local_id": "ct-1", "driver": "fake", "host": "192.168.1.60", "status": "online"}],
    },
}


def root_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(TEST_ROOT_SEED))


@dataclass(frozen=True)
class AgentKey:
    private: Ed25519PrivateKey = field(default_factory=Ed25519PrivateKey.generate)

    @property
    def public_jwk(self) -> dict[str, str]:
        return public_jwk_of(self.private.public_key())

    @property
    def thumbprint(self) -> str:
        return jwk_thumbprint(self.public_jwk)


@dataclass(frozen=True)
class AgentFixture:
    shop: Shop
    key: AgentKey
    agent_id: uuid.UUID
    device_id: uuid.UUID
    token: str
    machine_hash: str

    @property
    def client_id(self) -> str:
        return f"onec-agent:{self.agent_id}"

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.shop.tenant_id

    def headers(self, *, version: str = AGENT_VERSION, protocol: str = "2") -> dict[str, str]:
        return {
            **bearer(self.token),
            "X-Agent-Version": version,
            "X-Agent-Protocol": protocol,
            "User-Agent": f"ErpOneCAgent/{version} (Windows 10.0.19045; x64)",
        }

    def with_token(self, token: str) -> AgentFixture:
        return replace(self, token=token)


def machine_hash() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


async def device_authorize(
    client: httpx.AsyncClient, key: AgentKey, *, mhash: str | None = None, **extra: str
) -> httpx.Response:
    form = {
        "client_id": "onec-agent",
        "scope": "onec.agent",
        "public_jwk": json.dumps(key.public_jwk),
        "machine_hash": mhash or machine_hash(),
        "pc_name": "DOKON-PC",
        "os_version": "Windows 10 Pro 22H2 (19045)",
        "agent_version": AGENT_VERSION,
        **extra,
    }
    return await client.post("/oauth/device_authorization", data=form)


async def poll_token(client: httpx.AsyncClient, device_code: str) -> httpx.Response:
    return await client.post(
        "/oauth/token",
        data={"grant_type": DEVICE_CODE_GRANT, "device_code": device_code, "client_id": "onec-agent"},
    )


async def approve(client: httpx.AsyncClient, owner: Member, user_code: str, **extra: Any) -> httpx.Response:
    return await client.post(
        "/api/v1/onec-agents/pair", json={"user_code": user_code, **extra}, headers=owner.headers(write=True)
    )


async def reset_poll_clock(admin_engine: AsyncEngine, user_code: str) -> None:
    """Skip the 5 s ``interval`` (``slow_down``) in tests: forget the last poll time."""
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE auth.onec_device_authorizations SET last_poll_at = NULL WHERE user_code = :c"),
            {"c": user_code.replace("-", "")},
        )


async def pair_agent(
    client: httpx.AsyncClient, shop: Shop, admin_engine: AsyncEngine, *, key: AgentKey | None = None
) -> AgentFixture:
    key = key or AgentKey()
    mhash = machine_hash()
    started = await device_authorize(client, key, mhash=mhash)
    assert started.status_code == 200, started.text
    data = started.json()
    paired = await approve(client, shop.owner, data["user_code"])
    assert paired.status_code == 201, paired.text
    await reset_poll_clock(admin_engine, data["user_code"])
    token = await poll_token(client, data["device_code"])
    assert token.status_code == 200, token.text
    body = token.json()
    return AgentFixture(
        shop=shop,
        key=key,
        agent_id=uuid.UUID(body["agent_id"]),
        device_id=uuid.UUID(paired.json()["device_id"]),
        token=body["access_token"],
        machine_hash=mhash,
    )


def client_assertion(
    fx: AgentFixture,
    *,
    iat: int | None = None,
    lifetime: int = 60,
    aud: str | list[str] = f"{ISSUER}/oauth/token",
    jti: str | None = None,
    key: AgentKey | None = None,
    **claims: Any,
) -> str:
    issued = int(time.time()) if iat is None else iat
    signer = key or fx.key
    payload = {
        "iss": fx.client_id,
        "sub": fx.client_id,
        "aud": aud,
        "jti": jti or str(uuid.uuid4()),
        "iat": issued,
        "exp": issued + lifetime,
        **claims,
    }
    return sign_compact({"alg": "EdDSA", "typ": "JWT", "kid": signer.thumbprint}, payload, signer.private)


async def assertion_token(
    client: httpx.AsyncClient, fx: AgentFixture, assertion: str | None = None, **form: str
) -> httpx.Response:
    return await client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": fx.client_id,
            "client_assertion_type": JWT_BEARER,
            "client_assertion": assertion or client_assertion(fx),
            "scope": "onec.agent",
            **form,
        },
    )


async def hello(
    client: httpx.AsyncClient, fx: AgentFixture, capabilities: dict[str, Any] | None = None, **body: Any
) -> httpx.Response:
    payload: dict[str, Any] = {
        "agent_version": AGENT_VERSION,
        "protocol": 2,
        "os_version": "Windows 10 Pro 22H2 (19045)",
        "machine_hash": fx.machine_hash,
        "pc_name": "DOKON-PC",
        "worker_bits": [32, 64],
        "platforms": [],
        "bases": [],
        "task_keyset_version": None,
        "busy_base_ids": [],
        "results_outbox_pending": 0,
        "clock": "2026-10-15T18:02:11Z",
        **body,
    }
    if capabilities is not None:
        payload["capabilities"] = capabilities
    return await client.post("/api/v1/onec-agent/hello", json=payload, headers=fx.headers())


async def poll(client: httpx.AsyncClient, fx: AgentFixture, wait_s: int = 0, **body: Any) -> httpx.Response:
    return await client.post(
        "/api/v1/onec-agent/poll",
        json={
            "ready_base_ids": [],
            "busy_base_ids": [],
            "agent_level_busy": False,
            "max_tasks": 1,
            "wait_s": wait_s,
            **body,
        },
        headers=fx.headers(),
    )


async def result(
    client: httpx.AsyncClient, fx: AgentFixture, task: dict[str, Any], outcome: str = "done", **body: Any
) -> httpx.Response:
    payload = {
        "lease_id": task["lease_id"],
        "attempt": task["attempt"],
        "outcome": outcome,
        "data": {},
        "error": None,
        "started_at": "2026-10-15T18:02:20Z",
        "finished_at": "2026-10-15T18:02:21Z",
        "duration_ms": 1000,
        "worker_bits": 64,
        **body,
    }
    return await client.post(
        f"/api/v1/onec-agent/tasks/{task['task_id']}/result", json=payload, headers=fx.headers()
    )


async def agent_platform(migrator_engine: AsyncEngine) -> None:
    """Idempotent per session: ``onec_task`` key, a task keyset and a stable manifest (``1.4.3``, 100 %)."""
    from app.core.config import Settings
    from app.modules.auth.infrastructure.key_admin import (
        publish_agent_manifest,
        publish_task_keyset,
        rotate_signing_key,
    )
    from app.modules.auth.wiring import build_cipher

    async with migrator_engine.connect() as conn:
        ready = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM platform.signing_keys WHERE purpose = 'onec_task' AND status = 'active'"
                )
            )
        ).scalar()
    if ready:
        return
    await rotate_signing_key(migrator_engine, build_cipher(Settings(_env_file=None)), "onec_task")
    await publish_task_keyset(migrator_engine, root_key())
    manifest = {
        "product": "erp-onec-agent",
        "version": "1.4.3",
        "channel": "stable",
        "url": "https://erp.example.uz/downloads/erp-onec-agent-1.4.3-setup.exe",
        "sha256": "ab" * 32,
        "size": 5242880,
        "min_os": "6.1.7601",
        "min_protocol": 1,
        "rollout_pct": 100,
        "released_at": "2026-10-14T10:00:00Z",
        "notes_uz": "Tuzatishlar",
        "notes_ru": "Исправления",
    }
    await publish_agent_manifest(migrator_engine, root_key(), json.dumps(manifest, indent=1).encode())


async def enqueue(
    app_db: Any, tenant_id: uuid.UUID, agent_id: uuid.UUID, kind: str, payload: dict[str, Any], **kw: Any
) -> uuid.UUID:
    """Queue a task through the public :class:`AgentTaskPort` (contracts/agent-tasks.md)."""
    from app.core.db.session import tenant_transaction
    from app.modules.onec_integration.wiring import agent_tasks

    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        task_id: uuid.UUID = await agent_tasks().enqueue(s, tenant_id, agent_id, kind, payload, **kw)
    return task_id
