"""Deploy-time auth operations (12 §5.1, 14 §6, §15) — run as ``erp_migrator``.

    uv run python -m scripts.auth_ops rotate-signing-key            # next → active → retired
    uv run python -m scripts.auth_ops stage-signing-key             # publish a 'next' key early
    uv run python -m scripts.auth_ops configure-client --client-id web-bff \\
        --secret-env ERP_WEB_BFF_CLIENT_SECRET --redirect-uri https://app.example.uz/auth/callback

Secrets are read from environment variables (never from argv/shell history)
and stored envelope-encrypted with the KEK (15 §4.2).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

import typer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db.session import make_engine
from app.modules.auth.application.compact_jws import public_jwk_of, root_kid
from app.modules.auth.domain.constants import PURPOSE_ACCESS
from app.modules.auth.infrastructure.key_admin import (
    configure_client,
    publish_agent_manifest,
    publish_task_keyset,
    rotate_signing_key,
    stage_next_key,
)
from app.modules.auth.wiring import build_cipher

cli = typer.Typer(add_completion=False, no_args_is_help=True)


ONLINE_PURPOSES = ("access", "license", "onec_task")


def _online_purpose(purpose: str) -> None:
    """``agent_update`` is the offline root key (33 §9.4) — never generated into ``signing_keys``."""
    if purpose not in ONLINE_PURPOSES:
        raise typer.BadParameter(f"purpose must be one of {', '.join(ONLINE_PURPOSES)}")


def _root_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise typer.BadParameter("the root key must be an Ed25519 PEM private key")
    return key


def _engine() -> AsyncEngine:
    return make_engine(get_settings().migrator_database_url.get_secret_value(), pool_size=1, max_overflow=0)


@cli.command("rotate-signing-key")
def rotate_cmd(
    purpose: Annotated[str, typer.Option(help="access | license | onec_task")] = PURPOSE_ACCESS,
) -> None:
    _online_purpose(purpose)

    async def run() -> str:
        engine = _engine()
        try:
            return str(await rotate_signing_key(engine, build_cipher(get_settings()), purpose))
        finally:
            await engine.dispose()

    typer.echo(f"active {purpose} key: {asyncio.run(run())}")


@cli.command("stage-signing-key")
def stage_cmd(
    purpose: Annotated[str, typer.Option(help="access | license | onec_task")] = PURPOSE_ACCESS,
) -> None:
    _online_purpose(purpose)

    async def run() -> str:
        engine = _engine()
        try:
            return str(await stage_next_key(engine, build_cipher(get_settings()), purpose))
        finally:
            await engine.dispose()

    typer.echo(f"next {purpose} key: {asyncio.run(run())}")


@cli.command("configure-client")
def configure_cmd(
    client_id: Annotated[str, typer.Option(help="oauth_clients.client_id")],
    secret_env: Annotated[str | None, typer.Option(help="env var holding the client secret")] = None,
    redirect_uri: Annotated[
        list[str] | None, typer.Option(help="exact https redirect URI (repeatable)")
    ] = None,
) -> None:
    secret = None
    if secret_env:
        secret = os.environ.get(secret_env)
        if not secret:
            raise typer.BadParameter(f"{secret_env} is empty")

    async def run() -> None:
        engine = _engine()
        try:
            settings = get_settings()
            await configure_client(
                engine,
                build_cipher(settings),
                client_id,
                secret=secret,
                redirect_uris=redirect_uri,
                environment=settings.environment,
            )
        finally:
            await engine.dispose()

    asyncio.run(run())
    typer.echo(f"client {client_id}: configured")


@cli.command("gen-agent-root-key")
def gen_root_cmd(out: Annotated[Path, typer.Option(help="PEM file to create (offline machine)")]) -> None:
    """Create the offline ``agent_update`` root key; prints ``{kid, x}`` for the agent's ``RootKeys``."""
    if out.exists():
        raise typer.BadParameter(f"{out} exists — never overwrite a root key")
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pem)
    typer.echo(json.dumps({"kid": root_kid(key.public_key()), "x": public_jwk_of(key.public_key())["x"]}))


@cli.command("sign-task-keyset")
def sign_keyset_cmd(root_key: Annotated[Path, typer.Option(help="agent_update root key PEM")]) -> None:
    """Sign the active/next ``onec_task`` public keys into a new ``task_keyset`` (A-08)."""
    key = _root_key(root_key)

    async def run() -> int:
        engine = _engine()
        try:
            version, _ = await publish_task_keyset(engine, key)
            return version
        finally:
            await engine.dispose()

    typer.echo(f"task_keyset ver {asyncio.run(run())}: published")


@cli.command("publish-agent-manifest")
def publish_manifest_cmd(
    root_key: Annotated[Path, typer.Option(help="agent_update root key PEM")],
    manifest: Annotated[Path, typer.Option(help="manifest JSON (33 §9.3 A-09); its exact bytes are signed")],
) -> None:
    key = _root_key(root_key)
    raw = manifest.read_bytes()

    async def run() -> str:
        engine = _engine()
        try:
            return await publish_agent_manifest(engine, key, raw)
        finally:
            await engine.dispose()

    typer.echo(f"agent manifest {asyncio.run(run())}: published")


if __name__ == "__main__":
    cli()
