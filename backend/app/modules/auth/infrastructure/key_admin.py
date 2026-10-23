"""Deploy-time key and client administration (12 §5.1, 14 §6, §15) — runs as ``erp_migrator``.

The runtime role only reads ``platform.signing_keys``/``platform.oauth_clients``;
writes happen here, from ``scripts/auth_ops.py`` (and test fixtures).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.secrets import EnvelopeCipher
from app.modules.auth.application.keys import new_signing_key, private_key_aad
from app.modules.auth.domain.constants import ACCESS_ALG, PURPOSE_ACCESS

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
                "kid": kid, "alg": ACCESS_ALG, "purpose": purpose, "public_key": public,
                "private_key": sealed, "status": "next", "activate": False,
            },
        )  # fmt: skip
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
                    "kid": kid, "alg": ACCESS_ALG, "purpose": purpose, "public_key": public,
                    "private_key": sealed, "status": "active", "activate": True,
                },
            )  # fmt: skip
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
            if not uri.startswith("https://"):
                raise ValueError(f"redirect URI must be https: {uri}")
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
