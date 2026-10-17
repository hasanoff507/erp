"""Alembic on a fresh PostgreSQL 16 + the 12 §6.2 CI checks + qaror #58 c."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.rls import (
    SECURITY_DEFINER_FUNCTIONS_0027,
    app_grants_on_auth,
    missing_security_definer_functions,
    tables_without_rls,
)
from app.core.db.session import make_engine
from app.core.health import alembic_head
from tests.conftest import MigratedDb, PgUrls
from tests.support.bootstrap import MIGRATOR_PASSWORD, bootstrap_database, downgrade_base, upgrade_head

pytestmark = pytest.mark.db


async def test_head_is_0027b(migrated_db: MigratedDb, migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as conn:
        version = (await conn.execute(text("SELECT version_num FROM public.alembic_version"))).scalar()
    assert version == alembic_head() == "0027b"


async def test_every_tenant_table_has_forced_rls_and_a_policy(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as conn:
        assert await tables_without_rls(conn) == []


async def test_erp_app_has_no_grant_on_auth_schema(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as conn:
        assert await app_grants_on_auth(conn) == []


async def test_security_definer_functions_of_0027_exist(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as conn:
        assert await missing_security_definer_functions(conn) == []
        assert len(SECURITY_DEFINER_FUNCTIONS_0027) == 29  # 12 §6.2
        owners = (
            (
                await conn.execute(
                    text(
                        "SELECT DISTINCT pg_get_userbyid(p.proowner) FROM pg_proc p "
                        "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'app' AND p.prosecdef"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert owners == ["erp_system"]


async def test_app_role_cannot_update_append_only_registers(migrator_engine: AsyncEngine) -> None:
    sql = (
        "SELECT table_name FROM information_schema.table_privileges WHERE grantee = 'erp_app' "
        "AND table_schema = 'app' AND privilege_type IN ('UPDATE', 'DELETE') AND table_name = ANY(:t)"
    )
    tables = ["stock_moves", "debt_moves", "cash_moves", "ledger_entries", "vat_moves",
              "audit_log", "sync_receipts", "doc_approvals"]  # fmt: skip
    async with migrator_engine.connect() as conn:
        assert (await conn.execute(text(sql), {"t": tables})).all() == []
        triggers = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_no_update_delete' AND NOT tgisinternal"
                )
            )
        ).scalar()
        guard = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_login_attempts_guard' "
                    "AND tgrelid = 'auth.login_attempts'::regclass"
                )
            )
        ).scalar()
    assert triggers == len(tables)
    assert guard == 1


async def _check_value(engine: AsyncEngine, sql: str, params: dict[str, object]) -> bool:
    """True if the INSERT passes the CHECK constraints (rolled back either way)."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(text(sql), params)
            return True
        except IntegrityError as exc:
            if "check constraint" not in str(exc.orig).lower():
                raise
            return False
        finally:
            await trans.rollback()


@pytest.mark.parametrize("kind", ["web", "android", "onec_agent"])
async def test_devices_kind_accepts_onec_agent_qaror_58c(admin_engine: AsyncEngine, kind: str) -> None:
    tenant = uuid7()
    sql = (
        "WITH t AS (INSERT INTO app.tenants (id, name, phone) VALUES (:t, 'x', '+998900000001') RETURNING id) "
        "INSERT INTO app.devices (tenant_id, kind) SELECT id, :kind FROM t"
    )
    assert await _check_value(admin_engine, sql, {"t": tenant, "kind": kind})


async def test_devices_kind_rejects_unknown_value(admin_engine: AsyncEngine) -> None:
    sql = (
        "WITH t AS (INSERT INTO app.tenants (id, name, phone) VALUES (:t, 'x', '+998900000001') RETURNING id) "
        "INSERT INTO app.devices (tenant_id, kind) SELECT id, 'pos_terminal' FROM t"
    )
    assert not await _check_value(admin_engine, sql, {"t": uuid7()})


@pytest.mark.parametrize(
    ("purpose", "accepted"),
    [("access", True), ("license", True), ("onec_task", True), ("agent_update", True), ("onec", False)],
)
async def test_signing_keys_purpose_qaror_58c(
    migrator_engine: AsyncEngine, purpose: str, accepted: bool
) -> None:
    sql = (
        "INSERT INTO platform.signing_keys (algorithm, purpose, public_key, private_key_encrypted, status) "
        "VALUES ('EdDSA', :purpose, 'pub', 'enc', 'next')"
    )
    assert await _check_value(migrator_engine, sql, {"purpose": purpose}) is accepted


async def test_downgrade_base_and_upgrade_again(pg_server: PgUrls) -> None:
    name = "erp_test_roundtrip"
    await bootstrap_database(pg_server.admin, name)
    url = pg_server.url("erp_migrator", MIGRATOR_PASSWORD, name)
    await asyncio.to_thread(upgrade_head, url)
    await asyncio.to_thread(downgrade_base, url)
    engine = make_engine(url, pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            schemas = (
                (
                    await conn.execute(
                        text("SELECT nspname FROM pg_namespace WHERE nspname IN ('app', 'auth', 'platform')")
                    )
                )
                .scalars()
                .all()
            )
        assert schemas == []
    finally:
        await engine.dispose()
    await asyncio.to_thread(upgrade_head, url)
