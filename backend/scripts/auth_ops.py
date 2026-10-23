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
import os
from typing import Annotated

import typer
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db.session import make_engine
from app.modules.auth.domain.constants import PURPOSE_ACCESS
from app.modules.auth.infrastructure.key_admin import configure_client, rotate_signing_key, stage_next_key
from app.modules.auth.wiring import build_cipher

cli = typer.Typer(add_completion=False, no_args_is_help=True)


def _engine() -> AsyncEngine:
    return make_engine(get_settings().migrator_database_url.get_secret_value(), pool_size=1, max_overflow=0)


@cli.command("rotate-signing-key")
def rotate_cmd(purpose: Annotated[str, typer.Option(help="access | license")] = PURPOSE_ACCESS) -> None:
    async def run() -> str:
        engine = _engine()
        try:
            return str(await rotate_signing_key(engine, build_cipher(get_settings()), purpose))
        finally:
            await engine.dispose()

    typer.echo(f"active {purpose} key: {asyncio.run(run())}")


@cli.command("stage-signing-key")
def stage_cmd(purpose: Annotated[str, typer.Option(help="access | license")] = PURPOSE_ACCESS) -> None:
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
            await configure_client(
                engine, build_cipher(get_settings()), client_id, secret=secret, redirect_uris=redirect_uri
            )
        finally:
            await engine.dispose()

    asyncio.run(run())
    typer.echo(f"client {client_id}: configured")


if __name__ == "__main__":
    cli()
