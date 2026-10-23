"""Helpers for the catalog/pricing/import tests — real app, real Postgres/Redis, real SAQ worker."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from saq import Worker
from sqlalchemy import text

from app.core.config import Settings
from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.core.queue import make_queue
from app.main import create_app
from app.modules.access.domain.permissions import SystemRole
from app.workers.jobs import FUNCTIONS
from scripts.seed import seed_demo_tenant, seed_demo_user
from tests.conftest import MigratedDb
from tests.support.auth import ISSUER, PASSWORD, android_tokens, auth_settings, bearer, new_phone


def catalog_settings(migrated_db: MigratedDb, redis_url: str, storage: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "mxik_provider": "fake",
        "mxik_retry_base_s": 0.0,
        "file_storage_dir": str(storage),
        "queue_name": f"test-{secrets.token_hex(4)}",
        "token_requests_per_minute": 1000,
        **overrides,
    }
    return auth_settings(migrated_db, redis_url, **values)


@dataclass
class Shop:
    """One tenant with a default branch and users by role (bearer tokens via the real OAuth flow)."""

    tenant_id: UUID
    branch_id: UUID
    tokens: dict[str, str] = field(default_factory=dict)
    user_ids: dict[str, UUID] = field(default_factory=dict)

    def h(
        self, role: str = "owner", *, branch: UUID | None = None, key: str | None = "auto"
    ) -> dict[str, str]:
        headers = bearer(self.tokens[role])
        if key == "auto":
            headers["Idempotency-Key"] = str(uuid7())
        elif key is not None:
            headers["Idempotency-Key"] = key
        if branch is not None:
            headers["X-Branch-Id"] = str(branch)
        return headers


async def make_shop(
    db: Database, client: httpx.AsyncClient, name: str, roles: tuple[SystemRole, ...] = (SystemRole.OWNER,)
) -> Shop:
    tenant_id = uuid7()
    await seed_demo_tenant(db, tenant_id=tenant_id, name=name, phone=new_phone())
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        branch_id = (await s.execute(text("SELECT id FROM app.branches WHERE is_default"))).scalar_one()
    shop = Shop(tenant_id, branch_id)
    for role in roles:
        phone = new_phone()
        uid = await seed_demo_user(
            db, tenant_id=tenant_id, phone=phone, name=f"{name} {role.value}", password=PASSWORD, role=role
        )
        shop.user_ids[role.value] = uid
        shop.tokens[role.value] = (await android_tokens(client, phone))["access_token"]
    return shop


@asynccontextmanager
async def catalog_app(settings: Settings) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url=ISSUER) as client:
            yield app, client


async def run_jobs(settings: Settings, db: Database, *, max_jobs: int = 10) -> int:
    """Drain the test queue with a real SAQ worker (same function registry as production)."""
    queue = make_queue(settings.redis_url.get_secret_value(), settings.queue_name)
    worker = Worker(queue, FUNCTIONS, concurrency=1)
    worker.context["db"] = db
    worker.context["settings"] = settings
    processed = 0
    try:
        await queue.connect()
        # Worker.process() blocks ~5 s on an empty queue: only call it while something is queued
        while processed < max_jobs and await queue.count("queued") > 0:
            await worker.process()
            processed += 1
    finally:
        await queue.disconnect()
    return processed


async def set_limit(db: Database, tenant_id: UUID, role: str, code: str, limit: str | None) -> None:
    """Give ``role`` the permission ``code`` with ``limit_value`` (or change it)."""
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        role_id = (
            await s.execute(text("SELECT id FROM app.roles WHERE system_code = :r"), {"r": role})
        ).scalar_one()
        await s.execute(
            text(
                "INSERT INTO app.role_permissions (tenant_id, role_id, permission_code, limit_value) "
                "VALUES (:t, :r, :c, CAST(:l AS numeric)) ON CONFLICT (role_id, permission_code) "
                "DO UPDATE SET limit_value = EXCLUDED.limit_value"
            ),
            {"t": tenant_id, "r": role_id, "c": code, "l": limit},
        )


def product_body(name: str = "Coca-Cola 1.5L", **extra: Any) -> dict[str, Any]:
    return {"name": name, "unit_code": "box", "vat_rate": "12.00", **extra}


async def create_product(
    client: httpx.AsyncClient, shop: Shop, name: str = "Coca-Cola 1.5L", **extra: Any
) -> dict[str, Any]:
    response = await client.post("/api/v1/products", json=product_body(name, **extra), headers=shop.h())
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def set_price(
    client: httpx.AsyncClient, shop: Shop, product_id: str, price: str, *, role: str = "owner", **line: Any
) -> dict[str, Any]:
    doc = await client.post(
        "/api/v1/price-changes",
        json={"doc_date": "2026-10-16", "lines": [{"product_id": product_id, "new_price": price, **line}]},
        headers=shop.h(role),
    )
    assert doc.status_code == 201, doc.text
    posted = await client.post(f"/api/v1/price-changes/{doc.json()['id']}/post", headers=shop.h(role))
    assert posted.status_code in (200, 202), posted.text
    body: dict[str, Any] = posted.json()
    return body


@dataclass
class Env:
    settings: Settings
    app: FastAPI
    client: httpx.AsyncClient
    db: Database

    async def shop(self, name: str, *roles: SystemRole) -> Shop:
        return await make_shop(self.db, self.client, name, roles or (SystemRole.OWNER,))

    async def drain(self) -> int:
        return await run_jobs(self.settings, self.db)


@pytest.fixture(name="env")
async def catalog_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(migrated_db, redis_url, tmp_path / "files")
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)
