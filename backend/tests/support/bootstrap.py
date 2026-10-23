"""DBA bootstrap for test databases — mirrors docker/postgres/initdb.sh (12 §0)."""

from __future__ import annotations

from pathlib import Path

import asyncpg
from alembic.config import Config

from alembic import command

MIGRATOR_PASSWORD = "erp_migrator_test"
APP_PASSWORD = "erp_app_test"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

_ROLES = f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_migrator') THEN
    CREATE ROLE erp_migrator LOGIN NOSUPERUSER CREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_app') THEN
    CREATE ROLE erp_app LOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_system') THEN
    CREATE ROLE erp_system NOLOGIN BYPASSRLS;
  END IF;
END $$;
ALTER ROLE erp_migrator PASSWORD '{MIGRATOR_PASSWORD}';
ALTER ROLE erp_app PASSWORD '{APP_PASSWORD}';
GRANT erp_system TO erp_migrator;
ALTER ROLE erp_app SET search_path = app, platform, public;
ALTER ROLE erp_system SET search_path = app, auth, platform, public;
"""


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def bootstrap_database(admin_url: str, name: str) -> None:
    conn = await asyncpg.connect(_plain(admin_url))
    try:
        await conn.execute(_ROLES)
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{name}" OWNER erp_migrator')
    finally:
        await conn.close()


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_head(url: str) -> None:
    command.upgrade(alembic_config(url), "head")


def downgrade_base(url: str) -> None:
    command.downgrade(alembic_config(url), "base")
