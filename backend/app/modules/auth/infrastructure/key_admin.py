"""Deploy-time key and client administration (12 §5.1, 14 §6, §15) — runs as ``erp_migrator``.

The runtime role only reads ``platform.signing_keys``/``platform.oauth_clients``;
writes happen here, from ``scripts/auth_ops.py`` (and test fixtures).
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Sequence
from uuid import UUID

import structlog
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.secrets import EnvelopeCipher
from app.modules.auth.application.compact_jws import root_kid, sign_compact, sign_detached_b64
from app.modules.auth.application.keys import new_signing_key, private_key_aad
from app.modules.auth.domain.constants import ACCESS_ALG, PURPOSE_ACCESS
from app.modules.auth.domain.redirects import validate_redirect_uri
from app.modules.onec_integration.domain.envelope import (
    KEYSET_TTL_S,
    KEYSET_TYP,
    keyset_payload,
    validate_manifest,
)

log = structlog.get_logger(__name__)

_INSERT_KEY = text(
    "INSERT INTO platform.signing_keys (kid, algorithm, purpose, public_key, private_key_encrypted, status, "
    "activated_at) VALUES (:kid, :alg, :purpose, :public_key, :private_key, :status, "
    "CASE WHEN CAST(:activate AS boolean) THEN now() END)"
)
_NEXT_KEY = text(
    "SELECT kid FROM platform.signing_keys WHERE purpose = :purpose AND status = 'next' "
    "ORDER BY created_at DESC LIMIT 1 FOR UPDATE"
)
_RETIRE_ACTIVE = text(
    "UPDATE platform.signing_keys SET status = 'retired', retired_at = now() "
    "WHERE purpose = :purpose AND status = 'active'"
)
_ACTIVATE = text("UPDATE platform.signing_keys SET status = 'active', activated_at = now() WHERE kid = :kid")


def _key_values(cipher: EnvelopeCipher, kid: UUID) -> tuple[str, str]:
    key, public = new_signing_key()
    sealed = cipher.encrypt(key.as_pem(private=True), private_key_aad(str(kid)))
    return json.dumps(public), sealed


async def stage_next_key(engine: AsyncEngine, cipher: EnvelopeCipher, purpose: str = PURPOSE_ACCESS) -> UUID:
    """Create a ``next`` key (published for verification ahead of the switch)."""
    kid = uuid7()
    public, sealed = _key_values(cipher, kid)
    async with engine.begin() as conn:
        await conn.execute(
            _INSERT_KEY,
            {
                "kid": kid,
                "alg": ACCESS_ALG,
                "purpose": purpose,
                "public_key": public,
                "private_key": sealed,
                "status": "next",
                "activate": False,
            },
        )
    return kid


async def rotate_signing_key(
    engine: AsyncEngine, cipher: EnvelopeCipher, purpose: str = PURPOSE_ACCESS
) -> UUID:
    """``next → active → retired`` (14 §6): promote the staged key or create one, retire the old one."""
    async with engine.begin() as conn:
        kid = (await conn.execute(_NEXT_KEY, {"purpose": purpose})).scalar()
        await conn.execute(_RETIRE_ACTIVE, {"purpose": purpose})
        if kid is None:
            kid = uuid7()
            public, sealed = _key_values(cipher, kid)
            await conn.execute(
                _INSERT_KEY,
                {
                    "kid": kid,
                    "alg": ACCESS_ALG,
                    "purpose": purpose,
                    "public_key": public,
                    "private_key": sealed,
                    "status": "active",
                    "activate": True,
                },
            )
        else:
            await conn.execute(_ACTIVATE, {"kid": kid})
    # platform event: audit_log needs a tenant, so it goes to the structured log (15 §6.1)
    log.info("signing_key_rotated", purpose=purpose, kid=str(kid))
    return UUID(str(kid))


async def configure_client(
    engine: AsyncEngine,
    cipher: EnvelopeCipher,
    client_id: str,
    *,
    secret: str | None = None,
    redirect_uris: Sequence[str] | None = None,
    environment: str = "prod",
) -> None:
    """Write a confidential client's secret (``pending_secret`` → ``active``) and/or its redirect URIs."""
    sets: list[str] = []
    params: dict[str, object] = {"client_id": client_id}
    if secret is not None:
        if len(secret) < 32:
            raise ValueError("client secret must be at least 32 characters")
        sets += ["client_secret_encrypted = :enc", "status = 'active'"]
        params["enc"] = cipher.encrypt(secret.encode(), f"oauth_clients:{client_id}".encode())
    if redirect_uris is not None:
        for uri in redirect_uris:
            validate_redirect_uri(uri, environment)  # InvalidRedirectUriError is a ValueError
        sets.append("redirect_uris = CAST(:uris AS text[])")
        params["uris"] = list(redirect_uris)
    if not sets:
        return
    # fixed column list from this function, values are bound parameters
    statement = "UPDATE platform.oauth_clients SET " + ", ".join(sets)  # noqa: S608
    statement += ", updated_at = now() WHERE client_id = :client_id"
    async with engine.begin() as conn:
        result = await conn.execute(text(statement), params)
        if result.rowcount != 1:
            raise LookupError(f"unknown OAuth client {client_id!r}")
    log.info(
        "oauth_client_configured", client_id=client_id, secret=secret is not None, redirect_uris=redirect_uris
    )


# --- B5 agent-auth: pre-signed store-agent artefacts (33 §9.4, A-08/A-09; 0028a agent_signed_artifacts) ---
# The agent_update root key is OFFLINE: the ops CLI reads it from a file, signs, and stores only the result.

_ONEC_TASK_KEYS = text(
    "SELECT kid, public_key, status, created_at, activated_at FROM platform.signing_keys "
    "WHERE purpose = 'onec_task' AND status IN ('active', 'next') ORDER BY created_at"
)
_MAX_KEYSET = text(
    "SELECT max(CAST(version AS int)) FROM platform.agent_signed_artifacts WHERE kind = 'task_keyset'"
)
_INSERT_ARTIFACT = text(
    "INSERT INTO platform.agent_signed_artifacts (kind, channel, version, body, signature, kid) "
    "VALUES (:kind, :channel, :version, :body, :signature, :kid)"
)


async def publish_task_keyset(
    engine: AsyncEngine, root_key: Ed25519PrivateKey, *, now: int | None = None
) -> tuple[int, str]:
    """Sign the ``onec_task`` public keys (``active`` + ``next``) as keyset ``ver = previous + 1``."""
    issued = int(now if now is not None else time.time())
    async with engine.begin() as conn:
        rows = (await conn.execute(_ONEC_TASK_KEYS)).all()
        if not rows:
            raise LookupError("no onec_task signing key — run rotate-signing-key --purpose onec_task first")
        keys: list[dict[str, object]] = []
        for kid, public_key, _status, created_at, activated_at in rows:
            jwk = json.loads(public_key)
            start = activated_at or created_at
            keys.append(
                {
                    "kid": str(kid),
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": jwk["x"],
                    "nbf": int(start.timestamp()) - 300,
                    "exp": issued + KEYSET_TTL_S,
                }
            )
        version = int((await conn.execute(_MAX_KEYSET)).scalar() or 0) + 1
        kid = root_kid(root_key.public_key())
        token = sign_compact(
            {"alg": "EdDSA", "typ": KEYSET_TYP, "kid": kid}, keyset_payload(version, issued, keys), root_key
        )
        await conn.execute(
            _INSERT_ARTIFACT,
            {
                "kind": "task_keyset",
                "channel": None,
                "version": str(version),
                "body": token,
                "signature": None,
                "kid": kid,
            },
        )
    log.info("agent_task_keyset_published", version=version, keys=len(keys))
    return version, token


async def publish_agent_manifest(engine: AsyncEngine, root_key: Ed25519PrivateKey, manifest: bytes) -> str:
    """Sign the exact manifest bytes (33 §9.3 A-09) and store them for the channel; returns the version."""
    data = validate_manifest(json.loads(manifest))
    kid = root_kid(root_key.public_key())
    async with engine.begin() as conn:
        await conn.execute(
            _INSERT_ARTIFACT,
            {
                "kind": "update_manifest",
                "channel": data["channel"],
                "version": str(data["version"]),
                "body": base64.b64encode(manifest).decode("ascii"),
                "signature": sign_detached_b64(manifest, root_key),
                "kid": kid,
            },
        )
    log.info("agent_manifest_published", channel=data["channel"], version=data["version"])
    return str(data["version"])
