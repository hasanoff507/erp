"""Helpers for the inventory / accounting tests (Bosqich 2) — real app, Postgres, Redis, SAQ worker.

Stock documents other than openings are built by later slices, so the costing tests drive the
stock toolkit (``inventory.wiring.stock_service``) directly inside a tenant transaction — exactly as
a posting service does — and assert the rows it writes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.accounting.wiring import business_today
from app.modules.inventory.wiring import (
    CostPosting,
    IssueResult,
    ReceiveResult,
    StockService,
    StockTxn,
    stock_service,
)
from tests.support.catalog import Env, Shop, create_product
from tests.support.ordering import TXN_ORDER

API = "/api/v1"
D = Decimal


def err(response: Any) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def rows(env: Env, tenant_id: UUID, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        return [dict(r._mapping) for r in await s.execute(text(sql), params)]


async def scalar(env: Env, tenant_id: UUID, sql: str, **params: Any) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        return (await s.execute(text(sql), params)).scalar()


async def execute(env: Env, tenant_id: UUID, sql: str, **params: Any) -> None:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        await s.execute(text(sql), params)


async def warehouse_of(env: Env, shop: Shop) -> UUID:
    wh: UUID = await scalar(
        env, shop.tenant_id, "SELECT id FROM app.warehouses WHERE branch_id = :b ORDER BY created_at LIMIT 1",
        b=shop.branch_id,
    )  # fmt: skip
    return wh


async def use_account(env: Env, shop: Shop, account: str = "2910") -> UUID:
    """Make the shop's warehouse a ``stock`` (2910) / ``store`` (2920) one — only before any move."""
    wh = await warehouse_of(env, shop)
    kind = "stock" if account == "2910" else "store"
    await execute(
        env, shop.tenant_id, "UPDATE app.warehouses SET type = :k, inventory_account = :a WHERE id = :w",
        k=kind, a=account, w=wh,
    )  # fmt: skip
    return wh


async def new_product(env: Env, shop: Shop, name: str = "Coca-Cola 1.5L", **extra: Any) -> UUID:
    return UUID((await create_product(env.client, shop, name, **extra))["id"])


async def set_method(env: Env, shop: Shop, method: str, valid_from: date | None = None) -> None:
    """Initial valuation method of a seeded tenant (signup inserts it; the demo seed does not)."""
    start = valid_from or date(business_today().year, 1, 1)
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.valuation_method_history (tenant_id, valid_from, method, created_by) "
        "VALUES (:t, :v, :m, :u) ON CONFLICT (tenant_id, valid_from) DO UPDATE SET method = EXCLUDED.method",
        t=shop.tenant_id, v=start, m=method, u=shop.user_ids["owner"],
    )  # fmt: skip


async def set_go_live(env: Env, shop: Shop, day: date | None) -> None:
    await execute(env, shop.tenant_id, "UPDATE app.tenants SET go_live_date = :d", d=day)


async def set_setting(env: Env, shop: Shop, key: str, value: Any) -> None:
    import json

    await execute(
        env, shop.tenant_id, "UPDATE app.tenants SET settings = settings || CAST(:v AS jsonb)",
        v=json.dumps({key: value}),
    )  # fmt: skip


async def close_period(env: Env, shop: Shop, period: date) -> None:
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.period_closings (tenant_id, period, closed_by) VALUES (:t, :p, :u)",
        t=shop.tenant_id, p=period.replace(day=1), u=shop.user_ids["owner"],
    )  # fmt: skip


@asynccontextmanager
async def stock_txn(
    env: Env, tenant_id: UUID, keys: Sequence[tuple[UUID, UUID]], service: StockService | None = None
) -> AsyncIterator[tuple[AsyncSession, StockTxn]]:
    svc = service or stock_service()
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        txn = await svc.lock(s, tenant_id, keys)
        yield s, txn


async def receive(
    env: Env, shop: Shop, wh: UUID, product: UUID, quantity: str, amount: str, *, expiry: date | None = None,
    source: str = "goods_receipts", doc_id: UUID | None = None,
) -> tuple[ReceiveResult, list[UUID]]:  # fmt: skip
    """A receipt-type credit in its own transaction; returns the result and the recost jobs it queued."""
    async with stock_txn(env, shop.tenant_id, [(wh, product)]) as (_, txn):
        res = await txn.receive(
            wh, product, D(quantity), D(amount), source_doc_type=source, source_doc_id=doc_id or uuid7(),
            source_line_id=uuid7(), expiry_date=expiry,
        )  # fmt: skip
        jobs = list(txn.recost_job_ids)
    return res, jobs


async def issue(
    env: Env, shop: Shop, wh: UUID, product: UUID, quantity: str, *, account_dt: str = "9120",
    doc_type: str = "write_offs", doc_id: UUID | None = None, line_id: UUID | None = None,
    entry_date: date | None = None, lot_id: UUID | None = None, from_blocked: bool = False,
) -> tuple[IssueResult, UUID, UUID]:  # fmt: skip
    """An issue with its cost ledger line (Dt ``account_dt`` / Kt inv_acct) in its own transaction."""
    doc, line = doc_id or uuid7(), line_id or uuid7()
    async with stock_txn(env, shop.tenant_id, [(wh, product)]) as (_, txn):
        res = await txn.issue(
            wh, product, D(quantity), doc_type=doc_type, doc_id=doc, line_id=line, lot_id=lot_id,
            from_blocked=from_blocked, cost=CostPosting(account_dt=account_dt, entry_date=entry_date or business_today()),
        )  # fmt: skip
    return res, doc, line


async def ledger(env: Env, shop: Shop, doc_id: UUID | None = None) -> list[dict[str, Any]]:
    where = "WHERE doc_id = :d " if doc_id else ""
    return await rows(
        env, shop.tenant_id,
        "SELECT id, entry_date, account_dt, account_kt, amount, branch_id, doc_type, doc_id, analytics, "
        f"reversal_of_id FROM app.ledger_entries {where}ORDER BY {TXN_ORDER}, (reversal_of_id IS NULL), id",
        d=doc_id,
    )  # fmt: skip


async def lots(env: Env, shop: Shop, product: UUID) -> list[dict[str, Any]]:
    return await rows(
        env, shop.tenant_id,
        "SELECT id, qty_in, qty_left, blocked_qty, unit_cost, source_doc_type, expiry_date, received_at "
        "FROM app.stock_lots WHERE product_id = :p ORDER BY received_at, id",
        p=product,
    )  # fmt: skip


async def balance(env: Env, shop: Shop, wh: UUID, product: UUID) -> tuple[Decimal, Decimal]:
    found = await rows(
        env, shop.tenant_id, "SELECT qty, value FROM app.stock_balances WHERE warehouse_id = :w AND product_id = :p",
        w=wh, p=product,
    )  # fmt: skip
    return (found[0]["qty"], found[0]["value"]) if found else (D("0.000"), D("0.00"))


async def avg(env: Env, shop: Shop, wh: UUID, product: UUID) -> dict[str, Any] | None:
    found = await rows(
        env, shop.tenant_id,
        "SELECT qty, avg_cost, total_value FROM app.avg_costs WHERE warehouse_id = :w AND product_id = :p",
        w=wh, p=product,
    )  # fmt: skip
    return found[0] if found else None


async def moves(env: Env, shop: Shop, product: UUID, doc_id: UUID | None = None) -> list[dict[str, Any]]:
    extra = "AND doc_id = :d " if doc_id else ""
    return await rows(
        env, shop.tenant_id,
        "SELECT id, lot_id, qty, cost_amount, doc_type, doc_id, line_id, reversal_of_id, moved_at "
        f"FROM app.stock_moves WHERE product_id = :p {extra}ORDER BY {TXN_ORDER}, moved_at, id",
        p=product, d=doc_id,
    )  # fmt: skip


def money_sum(values: Sequence[Decimal]) -> Decimal:
    return sum(values, D("0.00"))


async def add_branch(env: Env, shop: Shop, code: str, name: str = "Filial") -> tuple[UUID, UUID]:
    """A second branch with its ``store`` warehouse (2920); returns ``(branch_id, warehouse_id)``."""
    branch_id, wh = uuid7(), uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.branches (id, tenant_id, code, name, settlement_category, activity_type) "
                "VALUES (:id, :t, :c, :n, 'city_100k_plus', 'retail')"
            ),
            {"id": branch_id, "t": shop.tenant_id, "c": code, "n": name},
        )
        await s.execute(
            text(
                "INSERT INTO app.warehouses (id, tenant_id, branch_id, name, type, inventory_account) "
                "VALUES (:id, :t, :b, :n, 'store', '2920')"
            ),
            {"id": wh, "t": shop.tenant_id, "b": branch_id, "n": f"{name} ombori"},
        )
    return branch_id, wh


async def add_user(env: Env, shop: Shop, label: str, role: Any, branch_ids: tuple[UUID, ...] = ()) -> None:
    """A user of ``role`` restricted to ``branch_ids`` (empty = all), token under ``shop.tokens[label]``."""
    from scripts.seed import seed_demo_user
    from tests.support.auth import PASSWORD, android_tokens, new_phone

    phone = new_phone()
    uid = await seed_demo_user(
        env.db, tenant_id=shop.tenant_id, phone=phone, name=label, password=PASSWORD, role=role,
        branch_ids=branch_ids,
    )  # fmt: skip
    shop.user_ids[label] = uid
    shop.tokens[label] = (await android_tokens(env.client, phone))["access_token"]
