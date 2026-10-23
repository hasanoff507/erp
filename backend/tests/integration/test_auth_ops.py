"""Deploy CLI (``scripts/auth_ops.py``, 12 §5.1, 14 §6): client redirect URIs per environment (dev gap) and
the offline ``agent_update`` artefacts (33 §9.4) — real PostgreSQL as ``erp_migrator``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.modules.auth.application.compact_jws import verify_compact
from app.modules.auth.domain.redirects import InvalidRedirectUriError
from app.modules.auth.infrastructure.key_admin import configure_client, publish_task_keyset
from app.modules.auth.wiring import build_cipher
from scripts import auth_ops
from tests.support.agent import agent_platform, root_key

pytestmark = [pytest.mark.db]


async def _uris(engine: AsyncEngine, client_id: str) -> list[str]:
    async with engine.connect() as conn:
        value = (
            await conn.execute(
                text("SELECT redirect_uris FROM platform.oauth_clients WHERE client_id = :c"),
                {"c": client_id},
            )
        ).scalar()
    return list(value or [])


async def test_auth_ops_configure_client_localhost_by_environment(
    oauth_platform: None, migrator_engine: AsyncEngine
) -> None:
    cipher = build_cipher(Settings(_env_file=None))
    before = await _uris(migrator_engine, "android-pos")
    try:
        await configure_client(
            migrator_engine,
            cipher,
            "android-pos",
            redirect_uris=["http://localhost:5173/auth/callback", "http://127.0.0.1:8081/cb"],
            environment="local",
        )
        assert await _uris(migrator_engine, "android-pos") == [
            "http://localhost:5173/auth/callback",
            "http://127.0.0.1:8081/cb",
        ]
        for environment in ("staging", "prod"):
            with pytest.raises(InvalidRedirectUriError):
                await configure_client(
                    migrator_engine,
                    cipher,
                    "android-pos",
                    redirect_uris=["http://localhost:5173/cb"],
                    environment=environment,
                )
        with pytest.raises(InvalidRedirectUriError):
            await configure_client(
                migrator_engine,
                cipher,
                "android-pos",
                redirect_uris=["http://localhost@evil.com/cb"],
                environment="local",
            )
    finally:
        await configure_client(migrator_engine, cipher, "android-pos", redirect_uris=before)


async def test_auth_ops_task_keyset_versions_and_offline_root(
    oauth_platform: None, migrator_engine: AsyncEngine
) -> None:
    await agent_platform(migrator_engine)
    version, token = await publish_task_keyset(migrator_engine, root_key())
    again, _ = await publish_task_keyset(migrator_engine, root_key())
    assert again == version + 1
    header, payload = verify_compact(token, root_key().public_key())
    assert header["typ"] == "onec-task-keyset+jwt" and payload["ver"] == version
    assert all(k["kty"] == "OKP" and k["crv"] == "Ed25519" for k in payload["keys"])
    async with migrator_engine.connect() as conn:
        count = (
            await conn.execute(
                text("SELECT count(*) FROM platform.signing_keys WHERE purpose = 'agent_update'")
            )
        ).scalar()
    assert count == 0  # the root key never lives on the server


def test_auth_ops_refuses_online_agent_update_key() -> None:
    with pytest.raises(typer.BadParameter):
        auth_ops._online_purpose("agent_update")
    auth_ops._online_purpose("onec_task")


def test_auth_ops_gen_agent_root_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "root.pem"
    auth_ops.gen_root_cmd(out)
    printed = json.loads(capsys.readouterr().out)
    assert out.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----") and set(printed) == {"kid", "x"}
    with pytest.raises(typer.BadParameter):
        auth_ops.gen_root_cmd(out)  # never overwrite a root key
    assert auth_ops._root_key(out).public_key() is not None
