"""Seed (12 §5, 15 §2.2) and the SAQ worker skeleton (23 §4, 15 §3.3 worker tests)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, TenantContextError, make_engine, tenant_transaction
from app.workers.cron import active_tenant_ids, fan_out
from app.workers.jobs.system import noop
from scripts.seed import seed_demo_tenant, seed_global
from tests.conftest import MigratedDb
from tests.support.factories import create_tenant_world

pytestmark = pytest.mark.db


async def test_global_seed_values_and_rerun(migrator_engine: AsyncEngine, seeded: None) -> None:
    await seed_global(migrator_engine)  # second run is a no-op
    async with migrator_engine.connect() as conn:
        plan = (
            await conn.execute(
                text("SELECT price_month, price_year, limits FROM platform.plans WHERE code='standard'")
            )
        ).one()
        addon = (
            await conn.execute(text("SELECT price_month FROM platform.addons WHERE code='extra_register'"))
        ).one()
        units: dict[str, bool] = dict(
            (await conn.execute(text("SELECT code, is_fractional FROM platform.units"))).all()
        )
        rates: dict[str, Decimal] = dict(
            (await conn.execute(text("SELECT code, rate_pct FROM platform.turnover_tax_rates"))).all()
        )
        clients = (await conn.execute(text("SELECT count(*) FROM platform.oauth_clients"))).scalar()
    assert plan == (
        Decimal("99000.00"),
        Decimal("950400.00"),
        {"included_cash_registers": 1, "ai_monthly_tokens": 2500000},
    )
    assert addon == (Decimal("39000.00"),)
    assert units == {"pcs": False, "kg": True, "l": True, "m": True, "box": False}
    assert rates == {
        "retail_city_100k_plus": Decimal("4.00"), "retail_other": Decimal("2.00"),
        "retail_remote_mountain": Decimal("1.00"), "general": Decimal("4.00"),
        "tobacco": Decimal("4.00"), "sole_proprietor": Decimal("1.00"),
    }  # fmt: skip
    assert clients == 5


async def test_demo_tenant_provisioning(app_db: Database, seeded: None) -> None:
    tid = uuid7()
    await seed_demo_tenant(app_db, tenant_id=tid, name="Demo", phone="+998900000123")
    await seed_demo_tenant(app_db, tenant_id=tid, name="Demo", phone="+998900000123")  # idempotent
    async with app_db.session_factory() as s, tenant_transaction(s, tid):
        roles: dict[str, int] = dict(
            (
                await s.execute(
                    text(
                        "SELECT r.system_code, count(p.id) FROM app.roles r "
                        "LEFT JOIN app.role_permissions p ON p.role_id = r.id GROUP BY r.system_code"
                    )
                )
            ).all()
        )
        cashier: dict[str, Decimal] = dict(
            (
                await s.execute(
                    text(
                        "SELECT p.permission_code, p.limit_value FROM app.role_permissions p "
                        "JOIN app.roles r ON r.id = p.role_id WHERE r.system_code = 'cashier' "
                        "AND p.limit_value IS NOT NULL"
                    )
                )
            ).all()
        )
        categories: dict[str, str] = dict(
            (await s.execute(text("SELECT code, default_account FROM app.expense_categories"))).all()
        )
        warehouse = (
            await s.execute(
                text(
                    "SELECT b.code, b.is_default, w.type, w.inventory_account FROM app.branches b "
                    "JOIN app.warehouses w ON w.branch_id = b.id"
                )
            )
        ).all()
    assert roles == {"owner": 67, "manager": 42, "cashier": 13, "storekeeper": 11, "accountant": 29}
    assert cashier == {
        "discount.give": Decimal("5.0000"),
        "returns.approve": Decimal("100000.0000"),
        "cash.withdraw": Decimal("50000.0000"),
    }
    assert len(categories) == 21
    assert categories["tax_payment"] == "6410" and categories["rent_office"] == "9420"
    assert set(categories.values()) == {"9410", "9420", "9430", "6410"}
    assert warehouse == [("01", True, "store", "2920")]


# --- worker --------------------------------------------------------------------------------------


async def test_job_runs_in_its_tenant_context(app_db: Database) -> None:
    world = await create_tenant_world(app_db, "Job tenant")
    result = await noop({"db": app_db}, tenant_id=str(world.tenant_id))
    assert result == {"tenant_id": str(world.tenant_id)}


@pytest.mark.parametrize("bad", [None, "", "not-a-uuid"])
async def test_job_without_tenant_fails_before_touching_db(bad: Any) -> None:
    class ExplodingDb:
        @property
        def session_factory(self) -> Any:
            raise AssertionError("database must not be touched")

    with pytest.raises(TenantContextError):
        await noop({"db": ExplodingDb()}, tenant_id=bad)


async def test_sequential_jobs_on_one_connection_do_not_leak_context(migrated_db: MigratedDb) -> None:
    db = Database(make_engine(migrated_db.app_url, pool_size=1, max_overflow=0))
    try:
        a = await create_tenant_world(db, "Seq A")
        b = await create_tenant_world(db, "Seq B")
        assert await noop({"db": db}, tenant_id=str(a.tenant_id)) == {"tenant_id": str(a.tenant_id)}
        assert await noop({"db": db}, tenant_id=str(b.tenant_id)) == {"tenant_id": str(b.tenant_id)}
    finally:
        await db.dispose()


class RecordingQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, UUID]] = []

    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> str | None:
        self.jobs.append((job, tenant_id))
        return None


async def test_scheduler_fans_out_per_active_tenant(app_db: Database, seeded: None) -> None:
    active = await create_tenant_world(app_db, "Fan active")
    closed = await create_tenant_world(app_db, "Fan closed")
    for world, status in ((active, "trial"), (closed, "closed")):
        async with app_db.session_factory() as s, tenant_transaction(s, world.tenant_id):
            await s.execute(
                text(
                    "INSERT INTO app.subscriptions (tenant_id, plan_id, period, current_period_end, status) "
                    "SELECT :t, id, 'month', :end, :status FROM platform.plans WHERE code = 'standard'"
                ),
                {"t": world.tenant_id, "end": datetime.now(UTC) + timedelta(days=30), "status": status},
            )
    ids = await active_tenant_ids(app_db)
    assert active.tenant_id in ids and closed.tenant_id not in ids
    queue = RecordingQueue()
    count = await fan_out(app_db, queue, "noop")
    assert count == len(ids)
    assert ("noop", active.tenant_id) in queue.jobs
    assert all(tid != closed.tenant_id for _, tid in queue.jobs)


# --- auth.login_attempts retention (12 §3, §4.5; 14 §19; 23 §4) --------------------------------


async def test_login_attempts_purge_job_deletes_only_expired_rows(
    app_db: Database, admin_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    from app.workers.cron import CRON_JOBS
    from app.workers.jobs.system import purge_login_attempts

    phone = "+998900009090"
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO auth.login_attempts (phone, success, created_at) VALUES "
                "(:p, false, now() - interval '100 days'), (:p, false, now() - interval '91 days'), "
                "(:p, true, now() - interval '10 days')"
            ),
            {"p": phone},
        )

    result = await purge_login_attempts({"db": app_db}, retention_days=90)

    assert result["deleted"] >= 2
    assert result["retention_days"] == 90
    async with admin_engine.connect() as conn:
        left = (
            await conn.execute(
                text("SELECT count(*) FROM auth.login_attempts WHERE phone = :p"), {"p": phone}
            )
        ).scalar()
    assert left == 1
    assert any(job.function is purge_login_attempts for job in CRON_JOBS)


async def test_login_attempts_stay_append_only_outside_the_purge(
    app_db: Database, admin_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO auth.login_attempts (phone, success, created_at) "
                "VALUES ('+998900009191', false, now() - interval '400 days')"
            )
        )
    # even the table owner / a superuser cannot delete or update directly (trigger)
    for engine, sql in (
        (migrator_engine, "DELETE FROM auth.login_attempts WHERE phone = '+998900009191'"),
        (admin_engine, "UPDATE auth.login_attempts SET success = true WHERE phone = '+998900009191'"),
    ):
        async with engine.connect() as conn:
            with pytest.raises(Exception, match="append-only"):
                await conn.execute(text(sql))
            await conn.rollback()
    # the application role has no access to auth.* at all
    async with app_db.engine.connect() as conn:
        with pytest.raises(Exception, match="permission denied"):
            await conn.execute(text("DELETE FROM auth.login_attempts"))
        await conn.rollback()
    # the purge refuses a window shorter than one day (15-minute lock window, 12 §4.5)
    async with app_db.engine.connect() as conn:
        with pytest.raises(Exception, match="at least 1 day"):
            await conn.execute(text("SELECT app.auth_purge_login_attempts(interval '1 hour')"))
        await conn.rollback()
