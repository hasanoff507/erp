"""QT-RLS-01…08 (31-qabul-testlari.md) against a real PostgreSQL 16.

Bosqich 0 has no business endpoints yet (``/sales``, ``/sync/*``,
``/platform/*`` come in later stages), so these tests pin the guarantee at the
layer that exists now: the ``erp_app`` role, RLS policies, ``tenant_transaction``
and the ORM tenant filter. The HTTP-level variants extend these when the
endpoints land.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import Date, Numeric, String, select, text
from sqlalchemy.exc import DBAPIError, InvalidRequestError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base, TenantMixin, uuid7
from app.core.db.rls import db_tenant_id
from app.core.db.session import Database, make_engine, tenant_transaction, unscoped_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from tests.conftest import MigratedDb
from tests.support.factories import TenantWorld, create_sale, create_tenant_world

pytestmark = pytest.mark.db


class SaleRow(TenantMixin, Base):
    """Test-only ORM view of app.sales (the sales module models arrive in Bosqich 3)."""

    __tablename__ = "sales"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    doc_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    total_amount: Mapped[str | None] = mapped_column(Numeric(18, 2))


@pytest.fixture(scope="module")
async def worlds(app_db: Database) -> tuple[TenantWorld, TenantWorld]:
    a = await create_tenant_world(app_db, "Tenant A")
    b = await create_tenant_world(app_db, "Tenant B")
    return a, b


async def _get_sale_or_404(session: AsyncSession, sale_id: UUID) -> SaleRow:
    row = (await session.execute(select(SaleRow).where(SaleRow.id == sale_id))).scalar_one_or_none()
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "sale"})
    return row


async def test_qt_rls_01_other_tenant_sale_is_not_found(
    app_db: Database, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    a, b = worlds
    s1 = await create_sale(app_db, a)
    async with app_db.session_factory() as s, tenant_transaction(s, a.tenant_id):
        assert (await _get_sale_or_404(s, s1)).id == s1
    async with app_db.session_factory() as s, tenant_transaction(s, b.tenant_id):
        with pytest.raises(AppError) as err:
            await _get_sale_or_404(s, s1)
        raw = (await s.execute(text("SELECT count(*) FROM app.sales WHERE id = :id"), {"id": s1})).scalar()
    assert err.value.status_code == 404  # not 403: existence is not disclosed
    assert err.value.code is ErrorCode.NOT_FOUND
    assert raw == 0


async def test_qt_rls_01_orm_filter_protects_even_without_rls(
    admin_engine: AsyncEngine, app_db: Database, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    """Second layer (23 §6): the superuser bypasses RLS, the ORM tenant filter still hides A's sale."""
    a, b = worlds
    s1 = await create_sale(app_db, a)
    factory = async_sessionmaker(admin_engine, expire_on_commit=False, autobegin=False)
    async with factory() as s, tenant_transaction(s, b.tenant_id):
        raw = (await s.execute(text("SELECT count(*) FROM app.sales WHERE id = :id"), {"id": s1})).scalar()
        orm = (await s.execute(select(SaleRow).where(SaleRow.id == s1))).scalar_one_or_none()
    assert raw == 1  # proves RLS is not in play for this connection
    assert orm is None


async def test_qt_rls_02_no_tenant_context_returns_nothing(
    app_db: Database, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    a, _ = worlds
    await create_sale(app_db, a)
    async with app_db.session_factory() as s, unscoped_transaction(s):
        rows = (await s.execute(text("SELECT * FROM app.sales"))).all()
        assert await db_tenant_id(s) is None
    assert rows == []
    async with app_db.engine.connect() as conn:  # bare connection, nothing set at all
        assert (await conn.execute(text("SELECT count(*) FROM app.sales"))).scalar() == 0


async def test_qt_rls_02_query_outside_transaction_is_impossible(app_db: Database) -> None:
    async with app_db.session_factory() as s:
        with pytest.raises(InvalidRequestError):
            await s.execute(text("SELECT 1"))


async def test_qt_rls_03_foreign_tenant_id_in_payload_is_not_written(
    app_db: Database, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    a, b = worlds

    async def count_in_b() -> int:
        async with app_db.session_factory() as s, tenant_transaction(s, b.tenant_id):
            return int((await s.execute(text("SELECT count(*) FROM app.counterparties"))).scalar_one())

    before = await count_in_b()
    with pytest.raises(DBAPIError) as err:
        async with app_db.session_factory() as s, tenant_transaction(s, a.tenant_id):
            await s.execute(
                text(
                    "INSERT INTO app.counterparties (tenant_id, kind, name) VALUES (:t, 'person', 'Firibgar')"
                ),
                {"t": b.tenant_id},  # tenant id smuggled in the payload
            )
    assert "row-level security" in str(err.value.orig)
    assert await count_in_b() == before


async def test_qt_rls_04_no_platform_bypass_for_the_app_role(
    app_db: Database, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    a, _ = worlds
    async with app_db.session_factory() as s:
        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_transaction(s, a.tenant_id):
                await s.execute(text("SELECT count(*) FROM platform.platform_admins"))
    async with app_db.session_factory() as s, tenant_transaction(s, a.tenant_id):
        tenants = (await s.execute(text("SELECT id FROM app.tenants"))).scalars().all()
    assert tenants == [a.tenant_id]  # a tenant user never lists other tenants


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO platform.units (code, is_fractional) VALUES ('zz', false)",
        "UPDATE platform.plans SET price_month = 1 WHERE code = 'standard'",
        "INSERT INTO platform.addons (code, name, price_month) VALUES ('x', 'x', 1)",
        "DELETE FROM platform.units WHERE code = 'pcs'",
    ],
)
async def test_qt_rls_05_app_role_cannot_write_global_tables(
    app_db: Database, migrator_engine: AsyncEngine, seeded: None, sql: str
) -> None:
    with pytest.raises(ProgrammingError, match="permission denied"):
        async with app_db.engine.begin() as conn:
            await conn.execute(text(sql))
    async with migrator_engine.connect() as conn:  # only the migrator writes them
        trans = await conn.begin()
        await conn.execute(text(sql))
        await trans.rollback()


async def test_qt_rls_06_other_tenant_catalog_and_prices_are_invisible(
    app_db: Database, worlds: tuple[TenantWorld, TenantWorld], seeded: None
) -> None:
    a, b = worlds
    pb1 = uuid7()
    async with app_db.session_factory() as s, tenant_transaction(s, b.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.products (id, tenant_id, name, unit_code, vat_rate) "
                "VALUES (:id, :t, 'B mahsuloti', 'pcs', 12.00)"
            ),
            {"id": pb1, "t": b.tenant_id},
        )
        await s.execute(
            text("INSERT INTO app.product_prices (tenant_id, product_id, price) VALUES (:t, :p, 9999.00)"),
            {"t": b.tenant_id, "p": pb1},
        )
    async with app_db.session_factory() as s, tenant_transaction(s, a.tenant_id):
        products = (await s.execute(text("SELECT id FROM app.products WHERE id = :id"), {"id": pb1})).all()
        prices = (
            await s.execute(text("SELECT id FROM app.product_prices WHERE product_id = :id"), {"id": pb1})
        ).all()
    assert products == []
    assert prices == []


async def test_qt_rls_07_search_does_not_leak_other_tenant_counterparty(
    app_db: Database, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    a, b = worlds
    async with app_db.session_factory() as s, tenant_transaction(s, b.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.counterparties (tenant_id, kind, name) VALUES (:t, 'person', 'Qudratov Shavkat')"
            ),
            {"t": b.tenant_id},
        )
    async with app_db.session_factory() as s, tenant_transaction(s, a.tenant_id):
        found = (
            await s.execute(
                text("SELECT id FROM app.counterparties WHERE name ILIKE :q"), {"q": "%Qudratov%"}
            )
        ).all()
    assert found == []


async def test_qt_rls_08_context_does_not_survive_on_a_pooled_connection(
    migrated_db: MigratedDb, worlds: tuple[TenantWorld, TenantWorld]
) -> None:
    a, b = worlds
    db = Database(make_engine(migrated_db.app_url, pool_size=1, max_overflow=0))  # one physical connection
    try:
        async with db.session_factory() as s, tenant_transaction(s, a.tenant_id):
            pid_a = (await s.execute(text("SELECT pg_backend_pid()"))).scalar()
            assert await db_tenant_id(s) == a.tenant_id
        async with db.session_factory() as s, unscoped_transaction(s):
            pid_between = (await s.execute(text("SELECT pg_backend_pid()"))).scalar()
            assert await db_tenant_id(s) is None  # A's context is gone after commit
        async with db.session_factory() as s, tenant_transaction(s, b.tenant_id):
            pid_b = (await s.execute(text("SELECT pg_backend_pid()"))).scalar()
            assert await db_tenant_id(s) == b.tenant_id
            seen = (await s.execute(text("SELECT DISTINCT tenant_id FROM app.branches"))).scalars().all()
        assert pid_a == pid_between == pid_b
        assert seen == [b.tenant_id]
        with pytest.raises(RuntimeError):
            async with db.session_factory() as s, tenant_transaction(s, a.tenant_id):
                raise RuntimeError("job failed")
        async with db.session_factory() as s, unscoped_transaction(s):
            assert await db_tenant_id(s) is None  # rollback clears it too
    finally:
        await db.dispose()
