"""Concurrent stock postings never over-allocate (23 §2.1): the ``stock_balances`` row lock serializes every
path that touches lots; keys are locked in ascending order, so opposite-order documents never deadlock."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from tests.support.catalog import Env, Shop, catalog_env_fixture
from tests.support.inventory import (
    D,
    balance,
    lots,
    moves,
    new_product,
    receive,
    set_method,
    set_setting,
    stock_txn,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]


async def _slow_issue(
    env: Env, shop: Shop, keys: list[tuple[UUID, UUID]], quantity: str, *, lot_id: UUID | None = None
) -> Decimal:
    """Lock, wait a little while holding the lock (so the other transaction queues up), then issue."""
    async with stock_txn(env, shop.tenant_id, keys) as (_, txn):
        await asyncio.sleep(0.2)
        total = Decimal("0.00")
        for wh, product in keys:
            res = await txn.issue(
                wh,
                product,
                D(quantity),
                doc_type="write_offs",
                doc_id=uuid7(),
                line_id=uuid7(),
                lot_id=lot_id,
            )
            total += res.cost
        return total


async def test_two_concurrent_issues_never_over_allocate(env: Env) -> None:
    shop = await env.shop("Parallel block")
    await set_method(env, shop, "fifo")
    await set_setting(env, shop, "negative_stock_policy", "block")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "10.000", "100000.00")
    results = await asyncio.gather(
        _slow_issue(env, shop, [(wh, p)], "7.000"),
        _slow_issue(env, shop, [(wh, p)], "7.000"),
        return_exceptions=True,
    )
    ok = [r for r in results if isinstance(r, Decimal)]
    failed = [r for r in results if isinstance(r, AppError)]
    assert ok == [D("70000.00")] and len(failed) == 1
    assert failed[0].code is ErrorCode.NEGATIVE_STOCK_NOT_ALLOWED and failed[0].params["available"] == "3.000"
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("3.000")]
    assert await balance(env, shop, wh, p) == (D("3.000"), D("30000.00"))


async def test_concurrent_issues_with_allow_policy_split_into_covered_and_pending(env: Env) -> None:
    shop = await env.shop("Parallel allow")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "10.000", "100000.00")
    await asyncio.gather(
        _slow_issue(env, shop, [(wh, p)], "7.000"), _slow_issue(env, shop, [(wh, p)], "7.000")
    )
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("0.000")]
    pending = [m for m in await moves(env, shop, p) if m["lot_id"] is None]
    assert [m["qty"] for m in pending] == [D("-4.000")]  # 10 covered in total, 4 pending — never 14 from lots
    assert await balance(env, shop, wh, p) == (D("-4.000"), D("-40000.00"))


async def test_same_lot_concurrently(env: Env) -> None:
    shop = await env.shop("Parallel lot")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    res, _ = await receive(env, shop, wh, p, "10.000", "100000.00")
    results = await asyncio.gather(
        _slow_issue(env, shop, [(wh, p)], "6.000", lot_id=res.lot_id),
        _slow_issue(env, shop, [(wh, p)], "6.000", lot_id=res.lot_id),
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, AppError)]
    assert len(errors) == 1 and errors[0].code is ErrorCode.INSUFFICIENT_STOCK
    assert errors[0].params == {"lot_id": str(res.lot_id), "available": "4.000"}
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("4.000")]


async def test_opposite_key_order_does_not_deadlock(env: Env) -> None:
    shop = await env.shop("Parallel order")
    wh = await use_account(env, shop)
    a, b = await new_product(env, shop, "A"), await new_product(env, shop, "B")
    for product in (a, b):
        await receive(env, shop, wh, product, "10.000", "1000.00")
    await asyncio.wait_for(
        asyncio.gather(
            _slow_issue(env, shop, [(wh, a), (wh, b)], "1.000"),
            _slow_issue(env, shop, [(wh, b), (wh, a)], "1.000"),
        ),
        timeout=20,
    )
    assert await balance(env, shop, wh, a) == (D("8.000"), D("800.00"))
    assert await balance(env, shop, wh, b) == (D("8.000"), D("800.00"))
