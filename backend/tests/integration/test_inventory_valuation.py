"""Valuation settings and the FIFO ↔ AVECO switch (19 §17, US-M04-05, 13 §3.1)."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from app.modules.inventory.wiring import CostPosting
from tests.support.catalog import Env, Shop, catalog_env_fixture
from tests.support.inventory import (
    API,
    D,
    avg,
    err,
    issue,
    lots,
    new_product,
    receive,
    rows,
    scalar,
    set_method,
    stock_txn,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

URL = f"{API}/valuation-settings"
THIS_YEAR = business_today().year
LAST_YEAR_AT = datetime(THIS_YEAR - 1, 6, 1, 7, 0, tzinfo=UTC)


async def _patch(env: Env, shop: Shop, method: str, role: str = "owner") -> Any:
    return await env.client.patch(URL, json={"method": method}, headers=shop.h(role))


async def _last_year_receipt(env: Env, shop: Shop, wh: UUID, p: UUID, quantity: str, amount: str) -> None:
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.receive(
            wh, p, D(quantity), D(amount), source_doc_type="goods_receipts", source_doc_id=uuid7(),
            source_line_id=uuid7(), received_at=LAST_YEAR_AT, moved_at=LAST_YEAR_AT,
        )  # fmt: skip


async def _last_year_issue(env: Env, shop: Shop, wh: UUID, p: UUID, quantity: str) -> None:
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.issue(
            wh, p, D(quantity), doc_type="write_offs", doc_id=uuid7(), line_id=uuid7(), moved_at=LAST_YEAR_AT,
            cost=CostPosting(account_dt="9430", entry_date=date(THIS_YEAR - 1, 6, 1)),
        )  # fmt: skip


async def test_get_defaults_to_aveco_and_permissions(env: Env) -> None:
    shop = await env.shop("Baholash", SystemRole.OWNER, SystemRole.STOREKEEPER)
    got = await env.client.get(URL, headers=shop.h("storekeeper", key=None))
    assert got.status_code == 200
    assert got.json() == {"current_method": "aveco", "effective_from": None, "pending_change": None}
    denied = await _patch(env, shop, "fifo", "storekeeper")
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    bad = await env.client.patch(URL, json={"method": "lifo"}, headers=shop.h())
    assert bad.status_code == 422  # LIFO is forbidden (BHMS №4)


async def test_immediate_change_without_moves_this_year_then_one_change_per_year(env: Env) -> None:
    shop = await env.shop("Darhol")
    await set_method(env, shop, "aveco")
    first = await _patch(env, shop, "fifo")
    assert first.status_code == 200, first.text
    assert first.json() == {
        "current_method": "fifo", "effective_from": f"{THIS_YEAR}-01-01", "pending_change": None,
    }  # fmt: skip
    again = await _patch(env, shop, "fifo")  # same method → idempotent 200
    assert again.status_code == 200 and again.json() == first.json()
    back = await _patch(env, shop, "aveco")  # one change per calendar year
    assert back.status_code == 409 and err(back) == "VALUATION_METHOD_CHANGE_NOT_ALLOWED"
    history = await rows(env, shop.tenant_id, "SELECT valid_from, method FROM app.valuation_method_history")
    assert history == [{"valid_from": date(THIS_YEAR, 1, 1), "method": "fifo"}]
    audit = await rows(
        env,
        shop.tenant_id,
        "SELECT before, after FROM app.audit_log WHERE action = 'valuation_method.changed'",
    )
    assert len(audit) == 1 and audit[0]["after"]["mode"] == "immediate"
    assert audit[0]["before"]["current_method"] == "aveco"


async def test_change_with_moves_this_year_is_pending_until_next_january(env: Env) -> None:
    shop = await env.shop("Keyingi yil")
    await set_method(env, shop, "aveco")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "1.000", "100.00")
    pending = await _patch(env, shop, "fifo")
    assert pending.status_code == 200
    assert pending.json() == {
        "current_method": "aveco", "effective_from": f"{THIS_YEAR}-01-01",
        "pending_change": {"method": "fifo", "effective_from": f"{THIS_YEAR + 1}-01-01"},
    }  # fmt: skip
    assert (await _patch(env, shop, "fifo")).json() == pending.json()  # repeat → 200
    conflict = await _patch(env, shop, "aveco")
    assert conflict.status_code == 409 and err(conflict) == "VALUATION_METHOD_CHANGE_NOT_ALLOWED"
    assert (await env.client.get(URL, headers=shop.h(key=None))).json() == pending.json()


async def test_fifo_to_aveco_switch_numbers(env: Env) -> None:
    """13 §3.1: avg = Σ qty_left × unit_cost / Σ qty_left; total_value = Σ qty_left × unit_cost.
    Lots 5 × 1000.0000 + 20 × 1300.0000 → total 31000.00, avg 1240.0000; no ledger entries."""
    shop = await env.shop("FIFO→AVECO")
    await set_method(env, shop, "fifo", date(THIS_YEAR - 1, 1, 1))
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await _last_year_receipt(env, shop, wh, p, "10.000", "10000.00")
    await _last_year_receipt(env, shop, wh, p, "20.000", "26000.00")
    await _last_year_issue(env, shop, wh, p, "5.000")  # FIFO: 5 × 1000 out
    ledger_before = await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.ledger_entries")
    assert await avg(env, shop, wh, p) is None  # FIFO keeps no avg_costs
    switched = await _patch(env, shop, "aveco")  # no moves this year → immediate
    assert switched.json()["current_method"] == "aveco"
    assert await avg(env, shop, wh, p) == {
        "qty": D("25.000"),
        "avg_cost": D("1240.0000"),
        "total_value": D("31000.00"),
    }
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.ledger_entries") == ledger_before
    res, _, _ = await issue(env, shop, wh, p, "10.000")
    assert res.cost == D("12400.00")  # now AVECO: 10 × 1240.0000


async def test_aveco_to_fifo_switch_applies_once_at_new_year_and_reprices_lots(env: Env) -> None:
    """A change recorded last year takes effect on 1 January: the first stock lock of the year re-prices
    the open lots to avg_cost (expiry/blocked kept) exactly once, race-safe."""
    shop = await env.shop("AVECO→FIFO")
    await set_method(env, shop, "aveco", date(THIS_YEAR - 1, 1, 1))
    wh = await use_account(env, shop)
    p, q = await new_product(env, shop, "A"), await new_product(env, shop, "B")
    await _last_year_receipt(env, shop, wh, p, "10.000", "10000.00")
    await _last_year_receipt(env, shop, wh, p, "10.000", "13000.00")  # avg 1150.0000
    await _last_year_issue(env, shop, wh, p, "5.000")  # 5 × 1150 = 5750.00 → 15 left worth 17250.00
    await _last_year_receipt(env, shop, wh, q, "1.000", "500.00")
    await set_method(env, shop, "fifo", date(THIS_YEAR, 1, 1))  # the pending change, now in force
    version = await scalar(env, shop.tenant_id, "SELECT version FROM app.tenants")

    async def touch(product: UUID) -> None:
        async with stock_txn(env, shop.tenant_id, [(wh, product)]) as (_, txn):
            assert txn.method == "fifo"

    await asyncio.gather(touch(p), touch(q))  # two first-of-the-year locks race; one converts
    assert await scalar(env, shop.tenant_id, "SELECT version FROM app.tenants") == version + 1
    state = await scalar(
        env, shop.tenant_id, "SELECT settings -> 'stock_valuation' ->> 'applied_method' FROM app.tenants"
    )
    assert state == "fifo"
    assert [x["unit_cost"] for x in await lots(env, shop, p)] == [D("1150.0000"), D("1150.0000")]
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("5.000"), D("10.000")]
    # FIFO from now on; the last unit out takes exactly the register value
    res, _, _ = await issue(env, shop, wh, p, "15.000")
    assert res.cost == D("17250.00")
    await receive(env, shop, wh, p, "2.000", "3000.00")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]):
        pass  # no second conversion
    assert await scalar(env, shop.tenant_id, "SELECT version FROM app.tenants") == version + 1
    assert (await lots(env, shop, p))[-1]["unit_cost"] == D("1500.0000")
