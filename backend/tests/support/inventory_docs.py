"""Helpers for the stock document tests (transfers, stock counts, write-offs — 19 §13–§15).

The app runs with ``einvoice_provider='fake'`` (27 B2: the fake operator registers an e-TTN at once,
so a vehicle transfer ``post`` queues ``outbox_jobs(kind='ettn_send')``). Opening stock goes in through
the stock toolkit (``tests.support.inventory.receive``) as goods-receipt lots.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis

from app.core.auth.principal import Principal
from app.core.db.session import Database
from app.core.permissions import BranchScope
from app.modules.accounting.wiring import business_today
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings
from tests.support.inventory import API, D, add_branch, ledger, receive, rows, use_account

TRANSFERS = f"{API}/transfers"
COUNTS = f"{API}/stock-counts"
WRITE_OFFS = f"{API}/write-offs"


@pytest.fixture(name="env")
async def docs_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(migrated_db, redis_url, tmp_path / "files", einvoice_provider="fake")
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)


def today() -> date:
    return business_today()


async def two_branches(env: Env, shop: Shop, code: str = "02") -> tuple[UUID, UUID, UUID]:
    """``(from_wh (2910, default branch), to_branch, to_wh (2920))``."""
    src = await use_account(env, shop, "2910")
    branch, dst = await add_branch(env, shop, code, f"Filial {code}")
    return src, branch, dst


async def stock_in(
    env: Env, shop: Shop, wh: UUID, product: UUID, quantity: str, amount: str, *, expiry: date | None = None
) -> UUID:
    res, _ = await receive(env, shop, wh, product, quantity, amount, expiry=expiry)
    return res.lot_id


def entries(rows_: Sequence[dict[str, Any]]) -> list[tuple[str, str, Decimal]]:
    return [(e["account_dt"], e["account_kt"], e["amount"]) for e in rows_]


async def doc_ledger(env: Env, shop: Shop, doc_id: str | UUID) -> list[dict[str, Any]]:
    return await ledger(env, shop, UUID(str(doc_id)))


async def account_balance(env: Env, shop: Shop, account: str) -> Decimal:
    """Σ Dt − Σ Kt of ``account`` over the whole ledger."""
    found = await rows(
        env, shop.tenant_id,
        "SELECT COALESCE(sum(CASE WHEN account_dt = :a THEN amount ELSE 0 END), 0) - "
        "COALESCE(sum(CASE WHEN account_kt = :a THEN amount ELSE 0 END), 0) AS bal FROM app.ledger_entries",
        a=account,
    )  # fmt: skip
    return D(found[0]["bal"]).quantize(D("0.01"))


# --- transfers -------------------------------------------------------------------------------------
async def create_transfer(
    env: Env, shop: Shop, src: UUID, dst: UUID, lines: Sequence[tuple[UUID, str]], *, role: str = "owner",
    mode: str = "vehicle", plate: str | None = "01A123BC", branch: UUID | None = None, **extra: Any,
) -> dict[str, Any]:  # fmt: skip
    body = {
        "from_warehouse_id": str(src), "to_warehouse_id": str(dst), "doc_date": str(today()), "transport_mode": mode,
        "lines": [{"product_id": str(p), "qty_sent": q} for p, q in lines], **extra,
    }  # fmt: skip
    if plate is not None:
        body["vehicle_plate"] = plate
    response = await env.client.post(TRANSFERS, json=body, headers=shop.h(role, branch=branch))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def act(env: Env, shop: Shop, doc_id: str, action: str, *, role: str = "owner", **kw: Any) -> Any:
    return await env.client.post(f"{TRANSFERS}/{doc_id}/{action}", headers=shop.h(role), **kw)


async def ok(response: Any, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    return body


async def sent_transfer(
    env: Env, shop: Shop, src: UUID, dst: UUID, lines: Sequence[tuple[UUID, str]]
) -> dict[str, Any]:
    """An on-foot transfer created, posted and sent (no e-TTN involved)."""
    doc = await create_transfer(env, shop, src, dst, lines, mode="on_foot_or_public", plate=None)
    await ok(await act(env, shop, doc["id"], "post"))
    return await ok(await act(env, shop, doc["id"], "send"))


def receive_body(doc: dict[str, Any], quantities: Sequence[str] | None = None) -> dict[str, Any]:
    qs = quantities or [ln["qty_sent"] for ln in doc["lines"]]
    return {
        "lines": [
            {"transfer_line_id": ln["id"], "qty_received": q} for ln, q in zip(doc["lines"], qs, strict=True)
        ]
    }


async def principal_of(env: Env, shop: Shop, role: str = "owner") -> tuple[Principal, BranchScope]:
    """A service-level caller (all branches) for driving the application services directly."""
    actor = Principal(
        user_id=shop.user_ids[role], tenant_id=shop.tenant_id, client_id="test", scopes=frozenset(),
        roles=(role,), branch_ids=(), sid=None, device_id=None, jti="test", issued_at=0, expires_at=0,
        sub_status=None, via_cookie=False,
    )  # fmt: skip
    del env
    return actor, BranchScope((), None)
