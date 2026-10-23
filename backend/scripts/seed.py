"""Seed CLI (23 §11, 12 §5) — idempotent, not an Alembic revision.

    uv run python -m scripts.seed global                 # 12 §5.1, as erp_migrator
    uv run python -m scripts.seed demo-tenant --name ... # local/test only, as erp_app
    uv run python -m scripts.seed demo-user --tenant-id ... --phone ... (password from ERP_DEMO_PASSWORD)

``global`` writes the platform reference data (units, plans/addons, marking
groups, turnover tax rates, label template, OAuth clients). Roles, the
permission matrix and expense categories are tenant-scoped, so they are created
per tenant (12 §5.2, 15 §1.5) — ``demo-tenant`` does that for a local tenant.
The chart of accounts and the permission catalog are code constants (12 §7.17,
23 §11) and need no seed.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Final, Literal
from uuid import UUID

import typer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db.base import uuid7
from app.core.db.session import Database, make_engine, tenant_transaction, unscoped_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.access.wiring import provision_system_roles
from app.modules.auth.wiring import hash_password
from app.modules.branches.wiring import ensure_default_branch, ensure_default_cash_register
from app.modules.expenses.wiring import create_default_categories

cli = typer.Typer(add_completion=False, no_args_is_help=True)

# 12 §5.1, verbatim values; ON CONFLICT makes reruns no-ops
GLOBAL_SEED: Final[tuple[str, ...]] = (
    """INSERT INTO platform.units (code, is_fractional) VALUES
  ('pcs', false), ('kg', true), ('l', true), ('m', true), ('box', false)
ON CONFLICT (code) DO NOTHING""",
    """INSERT INTO platform.plans (code, price_month, price_year, limits) VALUES
  ('standard', 99000.00, 950400.00,
   '{"included_cash_registers": 1, "ai_monthly_tokens": 2500000}'::jsonb)
ON CONFLICT (code) DO NOTHING""",
    """INSERT INTO platform.addons (code, name, price_month) VALUES
  ('extra_register', 'Qo''shimcha virtual kassa', 39000.00)
ON CONFLICT (code) DO NOTHING""",
    """INSERT INTO platform.marking_product_groups (code, name, acceptance_deadline, legal_ref) VALUES
  ('general',         'Umumiy (boshqa markirovkalangan tovarlar)', '3_business_days', 'VM 833 66–67-band'),
  ('water_beverages', 'Suv va ichimliklar',                        '72_hours',        'VM 631'),
  ('medicines',       'Dori vositalari',                           '72_hours',        'VM 149'),
  ('vegetable_oil',   'O''simlik yog''i (pilot)',                  '72_hours',        'VM 23')
ON CONFLICT (code) DO NOTHING""",
    """INSERT INTO platform.turnover_tax_rates (code, rate_pct, valid_from) VALUES
  ('retail_city_100k_plus',  4.00, '2026-01-01'),
  ('retail_other',           2.00, '2026-01-01'),
  ('retail_remote_mountain', 1.00, '2026-01-01'),
  ('general',                4.00, '2026-01-01'),
  ('tobacco',                4.00, '2026-01-01'),
  ('sole_proprietor',        1.00, '2026-01-01')
ON CONFLICT (code, valid_from) DO NOTHING""",
    """INSERT INTO platform.label_templates (code, name, width_mm, height_mm, fields) VALUES
  ('58x40_price', '58×40 narx yorlig''i', 58.00, 40.00,
   '{"fields": ["product_name", "price", "barcode"]}'::jsonb)
ON CONFLICT (code) DO NOTHING""",
    """INSERT INTO platform.oauth_clients (client_id, client_type, name, allowed_grant_types, allowed_scopes, status) VALUES
  ('web-bff',      'confidential', 'Veb BFF (back-office + veb-kassa)', ARRAY['authorization_code','refresh_token'], ARRAY['*','sync','pos'], 'pending_secret'),
  ('admin-bff',    'confidential', 'Platforma admin BFF',               ARRAY['authorization_code','refresh_token'], ARRAY['platform.admin'], 'pending_secret'),
  ('android-pos',  'public',       'Android POS',                       ARRAY['authorization_code','refresh_token'], ARRAY['*','sync','pos'], 'active'),
  ('telegram-bot', 'confidential', 'Telegram bot',                      ARRAY['client_credentials'],                 ARRAY['bot.internal'],   'pending_secret'),
  ('onec-agent',   'public',       'Do''kon agenti (Windows)',               ARRAY['urn:ietf:params:oauth:grant-type:device_code','client_credentials'], ARRAY['onec.agent'], 'active')
ON CONFLICT (client_id) DO NOTHING""",
)


async def seed_global(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for statement in GLOBAL_SEED:
            await conn.execute(text(statement))


_INSERT_TENANT = text(
    "INSERT INTO app.tenants (id, name, phone, legal_form, go_live_date) "
    "VALUES (:id, :name, :phone, :legal_form, CURRENT_DATE) "
    "ON CONFLICT (id) DO NOTHING"
)

_INSERT_TRIAL = text(
    "INSERT INTO app.subscriptions (tenant_id, plan_id, period, current_period_end, status) "
    "SELECT :tenant_id, id, 'month', now() + interval '30 days', 'trial' FROM platform.plans "
    "WHERE code = 'standard' ON CONFLICT (tenant_id) DO NOTHING"
)
_INSERT_USER = text(
    "INSERT INTO app.users (id, phone, name) VALUES (:id, :phone, :name) ON CONFLICT (phone) DO NOTHING"
)
_USER_ID = text("SELECT id FROM app.users WHERE phone = :phone")
_ROLE_BY_CODE = text("SELECT id FROM app.roles WHERE tenant_id = :tenant_id AND system_code = :code")
_INSERT_MEMBERSHIP = text(
    "INSERT INTO app.memberships (tenant_id, user_id, role_ids, branch_ids) "
    "VALUES (:tenant_id, :user_id, CAST(:role_ids AS uuid[]), CAST(:branch_ids AS uuid[])) "
    "ON CONFLICT (tenant_id, user_id) DO NOTHING"
)
_SET_PASSWORD = text("SELECT app.auth_set_credentials(:user_id, :password_hash, NULL)")

Settlement = Literal["city_100k_plus", "other", "remote_mountain"]


async def seed_demo_tenant(
    db: Database,
    *,
    tenant_id: UUID,
    name: str,
    phone: str,
    branch_name: str = "Asosiy filial",
    settlement_category: Settlement = "city_100k_plus",
) -> UUID:
    async with db.session_factory() as session, tenant_transaction(session, tenant_id):
        await session.execute(
            _INSERT_TENANT, {"id": tenant_id, "name": name, "phone": phone, "legal_form": "llc"}
        )
        await provision_system_roles(session, tenant_id)
        await create_default_categories(session, tenant_id)
        branch_id = await ensure_default_branch(session, tenant_id, branch_name, settlement_category)
        # the plan's included web register "Kassa 1" — exactly what real signup provisions (CORR-07b)
        await ensure_default_cash_register(session, tenant_id, branch_id)
        # 15 §1.5: a new tenant starts on a 30-day trial (the RS treats "no subscription" as restricted)
        await session.execute(_INSERT_TRIAL, {"tenant_id": tenant_id})
    return tenant_id


async def seed_demo_user(
    db: Database,
    *,
    tenant_id: UUID,
    phone: str,
    name: str,
    password: str,
    role: SystemRole = SystemRole.OWNER,
    branch_ids: tuple[UUID, ...] = (),
    user_id: UUID | None = None,
) -> UUID:
    """A user with a password and a membership in ``tenant_id`` (login via /oauth/authorize)."""
    uid = user_id or uuid7()
    async with db.session_factory() as session, tenant_transaction(session, tenant_id, user_id=uid):
        await session.execute(_INSERT_USER, {"id": uid, "phone": phone, "name": name})
        existing = (await session.execute(_USER_ID, {"phone": phone})).scalar()
        uid = existing or uid
    async with db.session_factory() as session, tenant_transaction(session, tenant_id, user_id=uid):
        role_id = (
            await session.execute(_ROLE_BY_CODE, {"tenant_id": tenant_id, "code": role.value})
        ).scalar_one()
        await session.execute(
            _INSERT_MEMBERSHIP,
            {
                "tenant_id": tenant_id,
                "user_id": uid,
                "role_ids": [str(role_id)],
                "branch_ids": [str(b) for b in branch_ids],
            },
        )
    async with db.session_factory() as session, unscoped_transaction(session):
        await session.execute(_SET_PASSWORD, {"user_id": uid, "password_hash": hash_password(password)})
    return uid


_PUBLISH_TERMS = (
    text(
        "UPDATE platform.terms_versions SET is_current = false "
        "WHERE kind = :kind AND is_current AND version <> :version"
    ),
    text(
        "INSERT INTO platform.terms_versions (version, kind, text_url, text_sha256, effective_from, is_current) "
        "VALUES (:version, :kind, :text_url, :text_sha256, now(), true) "
        "ON CONFLICT (version) DO UPDATE SET is_current = true "
        "WHERE platform.terms_versions.kind = EXCLUDED.kind"
    ),
)


async def publish_terms(
    engine: AsyncEngine, *, kind: str, version: str, text_url: str, text_sha256: str
) -> None:
    """Make ``version`` the current text of ``kind`` (deploy-time data, qaror #61; 12 terms_versions).

    The legally approved text itself (26 #127) is published at ``text_url``; only its SHA-256 is stored.
    """
    params = {"kind": kind, "version": version, "text_url": text_url, "text_sha256": text_sha256}
    async with engine.begin() as conn:
        for statement in _PUBLISH_TERMS:
            await conn.execute(statement, params)


@cli.command("global")
def global_cmd() -> None:
    """Platform reference data (12 §5.1) — runs as erp_migrator."""

    async def run() -> None:
        engine = make_engine(
            get_settings().migrator_database_url.get_secret_value(), pool_size=1, max_overflow=0
        )
        try:
            await seed_global(engine)
        finally:
            await engine.dispose()

    asyncio.run(run())
    typer.echo("global seed: ok")


@cli.command("demo-tenant")
def demo_tenant_cmd(
    name: Annotated[str, typer.Option(help="Tenant name")] = "Demo do'kon",
    phone: Annotated[str, typer.Option(help="Tenant phone")] = "+998900000000",
    tenant_id: Annotated[str | None, typer.Option(help="Fixed tenant id (UUID)")] = None,
) -> None:
    """Local/test tenant with system roles, matrix, expense categories and branch 01."""
    settings = get_settings()
    if settings.environment in ("staging", "prod"):
        raise typer.BadParameter("demo-tenant is for local/test environments only")
    tid = UUID(tenant_id) if tenant_id else uuid7()

    async def run() -> None:
        db = Database.from_settings(settings)
        try:
            await seed_demo_tenant(db, tenant_id=tid, name=name, phone=phone)
        finally:
            await db.dispose()

    asyncio.run(run())
    typer.echo(f"demo tenant: {tid}")


@cli.command("demo-user")
def demo_user_cmd(
    tenant_id: Annotated[str, typer.Option(help="Tenant id (UUID)")],
    phone: Annotated[str, typer.Option(help="+998XXXXXXXXX")],
    name: Annotated[str, typer.Option(help="Display name")] = "Demo egasi",
    role: Annotated[SystemRole, typer.Option(help="System role")] = SystemRole.OWNER,
) -> None:
    """Local/test user with a password (from ERP_DEMO_PASSWORD) and a membership."""
    import os

    settings = get_settings()
    if settings.environment in ("staging", "prod"):
        raise typer.BadParameter("demo-user is for local/test environments only")
    password = os.environ.get("ERP_DEMO_PASSWORD", "")
    if len(password) < 8:
        raise typer.BadParameter("set ERP_DEMO_PASSWORD (8..128 characters)")

    async def run() -> UUID:
        db = Database.from_settings(settings)
        try:
            return await seed_demo_user(
                db, tenant_id=UUID(tenant_id), phone=phone, name=name, password=password, role=role
            )
        finally:
            await db.dispose()

    typer.echo(f"demo user: {asyncio.run(run())}")


@cli.command("terms")
def terms_cmd(
    version: Annotated[str, typer.Option(help="Version label, e.g. v1")],
    text_url: Annotated[str, typer.Option(help="Public URL of the text")],
    text_sha256: Annotated[str, typer.Option(help="SHA-256 (hex) of the published text")],
    kind: Annotated[str, typer.Option(help="terms | privacy | ai_cross_border")] = "terms",
) -> None:
    """Publish the current Terms/consent text version (runs as erp_migrator; signup needs kind=terms)."""
    if kind not in ("terms", "privacy", "ai_cross_border"):
        raise typer.BadParameter("kind must be terms, privacy or ai_cross_border")

    async def run() -> None:
        engine = make_engine(
            get_settings().migrator_database_url.get_secret_value(), pool_size=1, max_overflow=0
        )
        try:
            await publish_terms(
                engine, kind=kind, version=version, text_url=text_url, text_sha256=text_sha256
            )
        finally:
            await engine.dispose()

    asyncio.run(run())
    typer.echo(f"terms: {kind} {version} is current")


if __name__ == "__main__":
    cli()
