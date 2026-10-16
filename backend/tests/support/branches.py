"""Helpers for the access / branches / devices / tenant-settings tests (Bosqich 1, slice B).

A *shop* is a real tenant provisioned by the seed (system roles, default branch ``01`` with its
warehouse, trial subscription) plus users that log in through the real OAuth flow (Android
Bearer tokens — CSRF-exempt). Rows the API cannot create yet (devices, shifts, sales, stock)
are inserted through the ``erp_app`` role inside a tenant transaction, i.e. under RLS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.core.permissions import PermissionGrant, require_permission
from app.main import create_app
from app.modules.access.domain.permissions import SystemRole
from scripts.seed import seed_demo_tenant, seed_demo_user
from tests.conftest import MigratedDb
from tests.support.auth import ISSUER, PASSWORD, android_tokens, auth_settings, bearer, new_phone


@dataclass(frozen=True)
class Member:
    user_id: UUID
    phone: str
    token: str

    def headers(self, *, write: bool = False, **extra: str) -> dict[str, str]:
        headers = {**bearer(self.token), **extra}
        if write:
            headers["Idempotency-Key"] = str(uuid7())
        return headers


@dataclass(frozen=True)
class Shop:
    tenant_id: UUID
    branch_id: UUID  # default branch "01"
    warehouse_id: UUID
    owner: Member


@asynccontextmanager
async def api(
    migrated_db: MigratedDb, redis_url: str, *routers: APIRouter
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    """The real app (lifespan included); ``routers`` (test probes) are mounted under ``/api/v1``."""
    app = create_app(auth_settings(migrated_db, redis_url))
    for router in routers:
        app.include_router(router, prefix="/api/v1")
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url=ISSUER) as client:
            yield app, client


def permission_probe(*codes: str) -> APIRouter:
    """``GET /probe/{code}`` guarded by the real ``require_permission(code)``; returns the effective limit."""
    router = APIRouter(prefix="/probe")
    for code in codes:

        def endpoint_for(permission: str) -> Any:
            # a default (not Annotated): string annotations cannot see this closure's ``permission``
            async def endpoint(
                grant: PermissionGrant = Depends(require_permission(permission)),  # noqa: B008
            ) -> dict[str, str | None]:
                return {"limit": None if grant.limit_value is None else str(grant.limit_value)}

            return endpoint

        router.add_api_route(f"/{code}", endpoint_for(code), methods=["GET"])
    return router


async def _one(db: Database, tenant_id: UUID, sql: str, **params: Any) -> Any:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        return (await s.execute(text(sql), params)).scalar()


async def execute(db: Database, tenant_id: UUID, sql: str, **params: Any) -> None:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        await s.execute(text(sql), params)


async def scalar(db: Database, tenant_id: UUID, sql: str, **params: Any) -> Any:
    return await _one(db, tenant_id, sql, **params)


async def role_id(db: Database, tenant_id: UUID, role: SystemRole) -> UUID:
    value: UUID = await _one(
        db,
        tenant_id,
        "SELECT id FROM app.roles WHERE tenant_id = :t AND system_code = :c",
        t=tenant_id,
        c=role.value,
    )
    return value


async def login(client: httpx.AsyncClient, phone: str) -> str:
    token: str = (await android_tokens(client, phone))["access_token"]
    return token


async def make_shop(db: Database, client: httpx.AsyncClient, name: str = "Do'kon") -> Shop:
    tenant_id = uuid7()
    await seed_demo_tenant(db, tenant_id=tenant_id, name=name, phone=new_phone())
    phone = new_phone()
    owner_id = await seed_demo_user(db, tenant_id=tenant_id, phone=phone, name="Egasi", password=PASSWORD)
    branch_id: UUID = await _one(
        db, tenant_id, "SELECT id FROM app.branches WHERE tenant_id = :t", t=tenant_id
    )
    warehouse_id: UUID = await _one(
        db, tenant_id, "SELECT id FROM app.warehouses WHERE branch_id = :b", b=branch_id
    )
    owner = Member(owner_id, phone, await login(client, phone))
    return Shop(tenant_id, branch_id, warehouse_id, owner)


async def add_member(
    db: Database,
    client: httpx.AsyncClient,
    shop: Shop,
    role: SystemRole,
    *,
    extra_role_ids: tuple[UUID, ...] = (),
    branch_ids: tuple[UUID, ...] = (),
    name: str = "Xodim",
) -> Member:
    """A staff member with ``role`` (+ extra roles) — role assignment itself is the auth slice's API."""
    phone = new_phone()
    user_id = await seed_demo_user(
        db,
        tenant_id=shop.tenant_id,
        phone=phone,
        name=name,
        password=PASSWORD,
        role=role,
        branch_ids=branch_ids,
    )
    if extra_role_ids:
        await execute(
            db,
            shop.tenant_id,
            "UPDATE app.memberships SET role_ids = role_ids || CAST(:extra AS uuid[]) "
            "WHERE tenant_id = :t AND user_id = :u",
            extra=[str(r) for r in extra_role_ids],
            t=shop.tenant_id,
            u=user_id,
        )
    return Member(user_id, phone, await login(client, phone))


async def add_device(
    db: Database,
    tenant_id: UUID,
    cash_register_id: UUID | None,
    *,
    kind: str = "android",
    pending: int | None = None,
) -> UUID:
    device_id = uuid7()
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind, app_version, last_seen_at, "
        "outbox_pending_count, outbox_oldest_pending_at) VALUES (:id, :t, :cr, :kind, '1.0.0', now(), :pending, "
        "CASE WHEN :pending > 0 THEN now() END)",
        id=device_id,
        t=tenant_id,
        cr=cash_register_id,
        kind=kind,
        pending=pending,
    )
    return device_id


async def add_cash_register(db: Database, tenant_id: UUID, branch_id: UUID, name: str = "Kassa") -> UUID:
    register_id = uuid7()
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) VALUES (:id, :t, :b, :n, 'android')",
        id=register_id,
        t=tenant_id,
        b=branch_id,
        n=name,
    )
    return register_id


async def open_shift(
    db: Database, tenant_id: UUID, branch_id: UUID, register_id: UUID, device_id: UUID, user_id: UUID
) -> UUID:
    shift_id = uuid7()
    shift_no = await _one(
        db,
        tenant_id,
        "SELECT COALESCE(max(shift_no), 0) + 1 FROM app.shifts WHERE cash_register_id = :c",
        c=register_id,
    )
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.shifts (id, tenant_id, branch_id, cash_register_id, device_id, shift_no, opened_by) "
        "VALUES (:id, :t, :b, :c, :d, :n, :u)",
        id=shift_id,
        t=tenant_id,
        b=branch_id,
        c=register_id,
        d=device_id,
        n=shift_no,
        u=user_id,
    )
    return shift_id


async def add_posted_sale(
    db: Database,
    tenant_id: UUID,
    branch_id: UUID,
    shift_id: UUID,
    register_id: UUID,
    user_id: UUID,
    total: str,
    doc_date: date,
) -> None:
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.sales (id, tenant_id, branch_id, doc_date, status, shift_id, cash_register_id, "
        "total_amount, created_by, posted_at) VALUES (:id, :t, :b, :d, 'posted', :s, :c, :total, :u, now())",
        id=uuid7(),
        t=tenant_id,
        b=branch_id,
        d=doc_date,
        s=shift_id,
        c=register_id,
        total=total,
        u=user_id,
    )


async def add_product(db: Database, tenant_id: UUID, name: str = "Non") -> UUID:
    product_id = uuid7()
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.products (id, tenant_id, name, unit_code, vat_rate) VALUES (:id, :t, :n, 'box', 12)",
        id=product_id,
        t=tenant_id,
        n=name,
    )
    return product_id


async def add_stock(
    db: Database, tenant_id: UUID, warehouse_id: UUID, product_id: UUID, qty: str, value: str
) -> None:
    """A receipt-like stock move plus the balance row it maintains."""
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.stock_moves (id, tenant_id, warehouse_id, product_id, qty, cost_amount, doc_type, doc_id) "
        "VALUES (:id, :t, :w, :p, :q, :v, 'stock_openings', :doc)",
        id=uuid7(),
        t=tenant_id,
        w=warehouse_id,
        p=product_id,
        q=qty,
        v=value,
        doc=uuid7(),
    )
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.stock_balances (tenant_id, warehouse_id, product_id, qty, value) "
        "VALUES (:t, :w, :p, :q, :v)",
        t=tenant_id,
        w=warehouse_id,
        p=product_id,
        q=qty,
        v=value,
    )


async def add_extra_registers(db: Database, tenant_id: UUID, quantity: int) -> None:
    await execute(
        db,
        tenant_id,
        "INSERT INTO app.tenant_addons (id, tenant_id, addon_code, quantity, price_month_snapshot) "
        "VALUES (:id, :t, 'extra_register', :q, 39000.00)",
        id=uuid7(),
        t=tenant_id,
        q=quantity,
    )


async def ensure_current_terms(admin_engine: AsyncEngine, kind: str = "ai_cross_border") -> str:
    """The current ``platform.terms_versions`` row of ``kind`` (deploy-time data, superuser fixture)."""
    async with admin_engine.begin() as conn:
        current = (
            await conn.execute(
                text("SELECT version FROM platform.terms_versions WHERE kind = :k AND is_current"),
                {"k": kind},
            )
        ).scalar()
        if current is not None:
            return str(current)
        version = f"{kind}-v1"
        await conn.execute(
            text(
                "INSERT INTO platform.terms_versions (version, kind, text_url, text_sha256, effective_from, is_current) "
                "VALUES (:v, :k, 'https://example.uz/terms', :sha, :at, true)"
            ),
            {"v": version, "k": kind, "sha": "0" * 64, "at": datetime(2026, 1, 1)},  # noqa: DTZ001
        )
        return version


async def audit_rows(admin_engine: AsyncEngine, tenant_id: UUID, action: str) -> list[dict[str, Any]]:
    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT user_id, entity, entity_id, before, after, device_id FROM app.audit_log "
                "WHERE tenant_id = :t AND action = :a ORDER BY at"
            ),
            {"t": tenant_id, "a": action},
        )
        return [dict(r._mapping) for r in rows]
