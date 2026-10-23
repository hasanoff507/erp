"""0027a web_pos — device-auth DDL: new SECURITY DEFINER functions, signatures, and the exact down path."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from app.core.db.rls import (
    SECURITY_DEFINER_FUNCTIONS_0027,
    SECURITY_DEFINER_FUNCTIONS_0027A_DEVICE_AUTH,
    missing_security_definer_functions,
)
from app.core.db.session import make_engine
from tests.conftest import PgUrls
from tests.support.bootstrap import MIGRATOR_PASSWORD, alembic_config, bootstrap_database, upgrade_head

pytestmark = pytest.mark.db

_SIGNATURES = text(
    "SELECT p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')' FROM pg_proc p "
    "JOIN pg_namespace n ON n.oid = p.pronamespace "
    "WHERE n.nspname = 'app' AND p.proname IN ('auth_issue_code', 'auth_consume_code') ORDER BY 1"
)
_CONSUME_RESULT = text(
    "SELECT pg_get_function_result(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
    "WHERE n.nspname = 'app' AND p.proname = 'auth_consume_code'"
)
_COLUMNS = text(
    "SELECT table_schema || '.' || table_name || '.' || column_name FROM information_schema.columns "
    "WHERE (table_schema, table_name, column_name) IN "
    "(('auth','authorization_codes','device_id'), ('auth','user_credentials','pin_local_hash'), "
    "('app','memberships','pin_reset_at')) ORDER BY 1"
)
_APP_EXECUTE = text(
    "SELECT has_function_privilege('erp_app', p.oid, 'EXECUTE') FROM pg_proc p "
    "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'app' AND p.proname = :name"
)


async def test_device_auth_security_definer_functions_exist(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as conn:
        assert (
            await missing_security_definer_functions(conn, SECURITY_DEFINER_FUNCTIONS_0027A_DEVICE_AUTH) == []
        )
        assert await missing_security_definer_functions(conn) == []
        for name in (*SECURITY_DEFINER_FUNCTIONS_0027A_DEVICE_AUTH, "auth_issue_code", "auth_consume_code"):
            assert (await conn.execute(_APP_EXECUTE, {"name": name})).scalar_one() is True, name
        signatures = (await conn.execute(_SIGNATURES)).scalars().all()
        assert signatures == [
            "auth_consume_code(p_code_hash text)",
            "auth_issue_code(p_code_hash text, p_client_id uuid, p_user_id uuid, p_tenant_id uuid, "
            "p_code_challenge text, p_redirect_uri text, p_scope text, p_ttl_s integer, p_device_id uuid)",
        ]
        assert "device_id uuid" in (await conn.execute(_CONSUME_RESULT)).scalar_one()
        assert len((await conn.execute(_COLUMNS)).scalars().all()) == 3


async def test_0027a_downgrade_restores_0027_functions_and_upgrades_again(pg_server: PgUrls) -> None:
    name = "erp_test_0027a_roundtrip"
    await bootstrap_database(pg_server.admin, name)
    url = pg_server.url("erp_migrator", MIGRATOR_PASSWORD, name)
    await asyncio.to_thread(upgrade_head, url)
    await asyncio.to_thread(command.downgrade, alembic_config(url), "0027")
    engine = make_engine(url, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            assert await missing_security_definer_functions(conn, SECURITY_DEFINER_FUNCTIONS_0027) == []
            assert await missing_security_definer_functions(
                conn, SECURITY_DEFINER_FUNCTIONS_0027A_DEVICE_AUTH
            ) == sorted(SECURITY_DEFINER_FUNCTIONS_0027A_DEVICE_AUTH)
            signatures = (await conn.execute(_SIGNATURES)).scalars().all()
            assert signatures == [
                "auth_consume_code(p_code_hash text)",
                "auth_issue_code(p_code_hash text, p_client_id uuid, p_user_id uuid, p_tenant_id uuid, "
                "p_code_challenge text, p_redirect_uri text, p_scope text, p_ttl_s integer)",
            ]
            assert "device_id" not in (await conn.execute(_CONSUME_RESULT)).scalar_one()
            assert (await conn.execute(_COLUMNS)).scalars().all() == []
            owners = (
                (
                    await conn.execute(
                        text(
                            "SELECT DISTINCT pg_get_userbyid(p.proowner) FROM pg_proc p JOIN pg_namespace n "
                            "ON n.oid = p.pronamespace WHERE n.nspname = 'app' AND p.prosecdef"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert owners == ["erp_system"]
            for fn in (
                "auth_issue_code",
                "auth_consume_code",
                "auth_set_credentials",
                "auth_reset_credentials",
            ):
                assert (await conn.execute(_APP_EXECUTE, {"name": fn})).scalar_one() is True, fn
    finally:
        await engine.dispose()
    await asyncio.to_thread(upgrade_head, url)
