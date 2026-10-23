"""Helpers for the offline sync tests (16, 18 §2) — real app, Postgres, Redis, real OAuth tokens.

A POS device = ``app.devices`` row on a cash register of the shop's branch + a device-bound access token
(the refresh family is bound to the device the way the device registration of Bosqich 3 binds it, then
rotated — the new access token carries the ``device_id`` claim).
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.tokens import token_hash
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncEventHandler
from scripts.seed import seed_demo_user
from tests.conftest import MigratedDb
from tests.support.auth import PASSWORD, android_tokens, bearer, new_phone, refresh
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings

API = "/api/v1"
PUSH = f"{API}/sync/push"
PULL = f"{API}/sync/pull"
EXCEPTIONS = f"{API}/sync-exceptions"


@dataclass
class SyncEnv(Env):
    admin: AsyncEngine | None = None

    @property
    def module(self) -> Any:
        return self.app.state.sync


@dataclass
class Pos:
    """One POS device of a shop and the user logged in on it."""

    shop: Shop
    device_id: UUID
    register_id: UUID | None
    branch_id: UUID
    user_id: UUID
    phone: str
    token: str
    _seq: itertools.count[int] = field(default_factory=lambda: itertools.count(1))

    def h(self) -> dict[str, str]:
        return bearer(self.token)

    def next_seq(self) -> int:
        return next(self._seq)


def sync_settings(migrated_db: MigratedDb, redis_url: str, storage: Path, **overrides: Any) -> Any:
    # the production settle window (2 s) — the test DB clock steps back ≈1 s now and then (settle_clock)
    values: dict[str, Any] = {"einvoice_provider": "fake", **overrides}
    return catalog_settings(migrated_db, redis_url, storage, **values)


@pytest.fixture(name="env")
async def sync_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
    admin_engine: AsyncEngine,
) -> AsyncIterator[SyncEnv]:
    settings = sync_settings(migrated_db, redis_url, tmp_path / "files")
    async with catalog_app(settings) as (app, client):
        yield SyncEnv(settings, app, client, app_db, admin_engine)


async def execute(db: Database, tenant_id: UUID, sql: str, **params: Any) -> None:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        await s.execute(text(sql), params)


async def rows(db: Database, tenant_id: UUID, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        return [dict(r._mapping) for r in await s.execute(text(sql), params)]


async def scalar(db: Database, tenant_id: UUID, sql: str, **params: Any) -> Any:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        return (await s.execute(text(sql), params)).scalar()


async def add_register(env: Env, shop: Shop, branch_id: UUID | None = None, name: str = "Kassa 1") -> UUID:
    register_id = uuid7()
    await execute(
        env.db,
        shop.tenant_id,
        "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) VALUES (:id, :t, :b, :n, 'web')",
        id=register_id,
        t=shop.tenant_id,
        b=branch_id or shop.branch_id,
        n=name,
    )
    return register_id


async def bind_token(env: SyncEnv, refresh_token: str, device_id: UUID) -> str:
    """Bind the refresh family to the device (14 §7) and rotate → device-bound access token."""
    assert env.admin is not None
    async with env.admin.begin() as conn:
        await conn.execute(
            text(
                "UPDATE auth.refresh_tokens SET device_id = :d WHERE family_id = "
                "(SELECT family_id FROM auth.refresh_tokens WHERE token_hash = :h)"
            ),
            {"d": device_id, "h": token_hash(refresh_token)},
        )
    rotated = await refresh(env.client, refresh_token)
    assert rotated.status_code == 200, rotated.text
    access: str = rotated.json()["access_token"]
    return access


async def pos_device(
    env: SyncEnv,
    shop: Shop,
    role: SystemRole = SystemRole.OWNER,
    *,
    branch_id: UUID | None = None,
    register_id: UUID | None = None,
    kind: str = "web",
    branch_ids: tuple[UUID, ...] = (),
) -> Pos:
    branch = branch_id or shop.branch_id
    register = register_id or await add_register(env, shop, branch)
    device_id = uuid7()
    await execute(
        env.db,
        shop.tenant_id,
        "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind, app_version) "
        "VALUES (:id, :t, :cr, :k, '1.0.0')",
        id=device_id,
        t=shop.tenant_id,
        cr=register,
        k=kind,
    )
    phone = new_phone()
    uid = await seed_demo_user(
        env.db,
        tenant_id=shop.tenant_id,
        phone=phone,
        name=f"POS {role.value}",
        password=PASSWORD,
        role=role,
        branch_ids=branch_ids,
    )
    tokens = await android_tokens(env.client, phone)
    access = await bind_token(env, tokens["refresh_token"], device_id)
    return Pos(shop, device_id, register, branch, uid, phone, access)


async def add_actor(env: SyncEnv, pos: Pos, role: SystemRole, branch_ids: tuple[UUID, ...] = ()) -> UUID:
    """Another employee of the shop (logs in on the POS with a PIN — only ``actor_user_id``)."""
    return await seed_demo_user(
        env.db,
        tenant_id=pos.shop.tenant_id,
        phone=new_phone(),
        name=f"Xodim {role.value}",
        password=PASSWORD,
        role=role,
        branch_ids=branch_ids,
    )


CLOCK_STEP_MARGIN_S = 2.0


async def settle_clock(env: Env, tenant_id: UUID, timeout_s: float = 15.0) -> None:
    """Wait until every change of the tenant's pull sources is settled (``now() − settle > updated_at``).

    ``/sync/pull`` delivers a row only once it is older than ``ERP_SYNC_PULL_SETTLE_S`` (16 §3.2): this also
    absorbs wall-clock steps backwards — the Docker Desktop VM clock of the test Postgres steps back ≈1 s
    now and then, and with a zero window a row written after such a step could land behind the cursor.
    Tests that assert a delta right after writing wait here first; the assertion itself stays exact."""
    import asyncio

    newest_sql = (
        "SELECT GREATEST((SELECT max(updated_at) FROM app.products), (SELECT max(updated_at) FROM "
        "app.product_categories), (SELECT max(created_at) FROM app.product_prices), (SELECT max(updated_at) "
        "FROM app.counterparties), (SELECT max(updated_at) FROM app.debt_balances), (SELECT max(updated_at) "
        "FROM app.stock_balances), (SELECT max(updated_at) FROM app.marking_codes)) AS newest, now() AS now"
    )
    deadline = datetime.now(UTC).timestamp() + timeout_s
    while True:
        found = (await rows(env.db, tenant_id, newest_sql))[0]
        # + a margin for the next clock step back (≈1.1 s measured) between this check and the pull
        window = timedelta(seconds=env.settings.sync_pull_settle_s + CLOCK_STEP_MARGIN_S)
        if found["newest"] is None or found["now"] - window > found["newest"]:
            return
        if datetime.now(UTC).timestamp() > deadline:
            raise AssertionError(f"database clock never passed {found['newest']} (now {found['now']})")
        await asyncio.sleep(0.05)


def iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event(
    pos: Pos,
    type_: str,
    payload: dict[str, Any],
    *,
    seq: int | None = None,
    created_at: datetime | None = None,
    actor: UUID | None = None,
    client_event_id: UUID | None = None,
) -> dict[str, Any]:
    return {
        "client_event_id": str(client_event_id or uuid7()),
        "device_id": str(pos.device_id),
        "seq": seq if seq is not None else pos.next_seq(),
        "type": type_,
        "created_at": iso(created_at or datetime.now(UTC)),
        "actor_user_id": str(actor or pos.user_id),
        "payload": payload,
    }


async def push(
    env: Env,
    pos: Pos,
    events: Sequence[dict[str, Any]],
    *,
    pending: int = 0,
    oldest: datetime | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    body = {
        "device_id": str(pos.device_id),
        "events": list(events),
        "outbox_state": {
            "pending_count": pending,
            "oldest_pending_created_at": iso(oldest) if oldest else None,
        },
    }
    return await env.client.post(PUSH, json=body, headers=headers or pos.h())


async def push_ok(env: Env, pos: Pos, events: Sequence[dict[str, Any]], **kw: Any) -> list[dict[str, Any]]:
    response = await push(env, pos, events, **kw)
    assert response.status_code == 200, response.text
    results: list[dict[str, Any]] = response.json()["results"]
    return results


async def pull(
    env: Env, pos: Pos, scope: str = "all", cursor: str | None = None, page_size: int | None = None
) -> httpx.Response:
    params: dict[str, Any] = {"scope": scope}
    if cursor is not None:
        params["cursor"] = cursor
    if page_size is not None:
        params["page_size"] = page_size
    return await env.client.get(PULL, params=params, headers=pos.h())


async def pull_ok(
    env: Env, pos: Pos, scope: str = "all", cursor: str | None = None, **kw: Any
) -> dict[str, Any]:
    response = await pull(env, pos, scope, cursor, **kw)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def pull_all(
    env: Env, pos: Pos, scope: str = "all", cursor: str | None = None, **kw: Any
) -> list[dict[str, Any]]:
    """Follow ``has_more`` to the end; returns every page."""
    pages: list[dict[str, Any]] = []
    while True:
        page = await pull_ok(env, pos, scope, cursor, **kw)
        pages.append(page)
        cursor = page["cursor"]
        if not page["has_more"]:
            return pages


def sent_payload(
    src: UUID, dst: UUID, lines: Sequence[tuple[UUID, str]], *, mode: str = "on_foot_or_public"
) -> dict[str, Any]:
    """A new-document ``transfer.sent`` payload (19 §13)."""
    from tests.support.inventory_docs import today

    body: dict[str, Any] = {
        "id": str(uuid7()),
        "temp_number": f"T-{uuid7().hex[-8:]}",
        "doc_date": str(today()),
        "from_warehouse_id": str(src),
        "to_warehouse_id": str(dst),
        "transport_mode": mode,
        "lines": [{"line_id": str(uuid7()), "product_id": str(p), "qty_sent": q} for p, q in lines],
    }
    if mode == "vehicle":
        body["vehicle_plate"] = "01A123BC"
    return body


# --- test-only handlers (registered through the real registry — no DB mocks) ------------------------
def echo_handler(
    *, server: dict[str, Any] | None = None, warnings: tuple[str, ...] = (), exceptions: tuple[Any, ...] = ()
) -> SyncEventHandler:
    """Writes one audit row per call (proves the per-event transaction) and echoes the payload."""
    from app.core.audit import record_audit

    async def handler(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="test.echo",
            entity="test",
            entity_id=ctx.client_event_id,
            device_id=ctx.device_id,
            after={"seq": ctx.seq, "payload": dict(payload), "created_at": ctx.created_at.isoformat()},
        )
        body = server if server is not None else {"id": str(ctx.client_event_id), "seq": ctx.seq}
        return HandlerResult(server=body, warnings=warnings, sync_exceptions=exceptions)

    return handler


def register(env: SyncEnv, event_type: str, handler: SyncEventHandler) -> None:
    env.module.registry.register(event_type, handler, replace=True)
