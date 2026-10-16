"""Async Alembic environment (23 §5). Runs as ``erp_migrator`` (12 §0)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import get_settings

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

# the schema is defined by the SQL revisions (alembic/sql), not by ORM metadata
target_metadata = None

# health readiness compares the schema version as erp_app (23 §8)
_GRANT_VERSION_READ = text(
    "DO $$ BEGIN "
    "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_app') THEN "
    "GRANT SELECT ON public.alembic_version TO erp_app; END IF; END $$"
)


def _url() -> str:
    return config.attributes.get("url") or get_settings().migrator_database_url.get_secret_value()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()
    with connection.begin():
        connection.execute(_GRANT_VERSION_READ)


async def run_async_migrations() -> None:
    engine = create_async_engine(_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
