"""Expense categories (20 #45–#47; 13 §2.17 seed map, US-M15-01 "Egasi o'zgartira oladi")."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.modules.expenses.domain.categories import DEFAULT_EXPENSE_CATEGORIES
from tests.support.cash import (
    cash_env_fixture,  # noqa: F401 - fixture "env"
    make_till,
)
from tests.support.catalog import Env
from tests.support.expenses import API, category_id, expense_body, ledger_lines

pytestmark = pytest.mark.asyncio
CAT = f"{API}/expense-categories"


async def test_seeded_21_categories_listed_with_accounts(env: Env) -> None:
    till = await make_till(env)
    # any member may read the list (POS-14 cache): the cashier too
    r = await env.client.get(CAT, headers=till.shop.h("cashier", key=None))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    by_code = {i["code"]: i for i in items}
    assert len(items) == 21
    assert {c.code: c.default_account for c in DEFAULT_EXPENSE_CATEGORIES} == {
        code: i["default_account"] for code, i in by_code.items()
    }
    assert by_code["tax_payment"]["default_account"] == "6410" and by_code["tax_payment"]["is_system"] is True
    assert by_code["payroll_sales"]["default_account"] == "9410"
    assert by_code["payroll_admin"]["default_account"] == "9420"


async def test_create_update_archive_and_account_change_affects_only_later_postings(env: Env) -> None:
    till = await make_till(env)
    h = till.shop.h
    r = await env.client.post(CAT, json={"name": "Qo'riqlash", "default_account": "9410"}, headers=h())
    assert r.status_code == 201, r.text
    cat = r.json()
    assert cat["code"] is None and cat["is_system"] is False and cat["version"] == 1
    dup = await env.client.post(CAT, json={"name": "qo'riqlash", "default_account": "9430"}, headers=h())
    assert (
        dup.status_code == 422 and dup.json()["error"]["details"][0]["message_key"] == "validation.duplicate"
    )
    bad = await env.client.post(CAT, json={"name": "X", "default_account": "5010"}, headers=h())
    assert bad.status_code == 422
    long = await env.client.post(CAT, json={"name": "x" * 51, "default_account": "9410"}, headers=h())
    assert long.status_code == 422
    # post one expense with 9410, then re-account the category to 9420
    first = await env.client.post(
        f"{API}/expenses", json=expense_body(UUID(cat["id"]), amount="1000.00"),
        headers=h(branch=till.shop.branch_id),
    )  # fmt: skip
    assert first.status_code == 201
    assert (
        await env.client.post(f"{API}/expenses/{first.json()['id']}/post", headers=h())
    ).status_code == 200
    r = await env.client.patch(
        f"{CAT}/{cat['id']}",
        json={"default_account": "9420", "name": "Qo'riqlash xizmati", "version": 1},
        headers=h(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["default_account"] == "9420" and r.json()["version"] == 2
    stale = await env.client.patch(f"{CAT}/{cat['id']}", json={"name": "Z", "version": 1}, headers=h())
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "VERSION_CONFLICT"
    second = await env.client.post(
        f"{API}/expenses", json=expense_body(UUID(cat["id"]), amount="2000.00"),
        headers=h(branch=till.shop.branch_id),
    )  # fmt: skip
    assert (
        await env.client.post(f"{API}/expenses/{second.json()['id']}/post", headers=h())
    ).status_code == 200
    assert await ledger_lines(env, till.shop.tenant_id, UUID(first.json()["id"])) == [
        ("9410", "5110", "1000.00", False)
    ]
    assert await ledger_lines(env, till.shop.tenant_id, UUID(second.json()["id"])) == [
        ("9420", "5110", "2000.00", False)
    ]
    listed = {
        i["id"]: i for i in (await env.client.get(f"{API}/expenses", headers=h(key=None))).json()["items"]
    }
    assert listed[first.json()["id"]]["account"] == "9410"  # the posted line, not today's category account
    # archive / unarchive
    r = await env.client.patch(f"{CAT}/{cat['id']}", json={"archived": True, "version": 2}, headers=h())
    assert r.status_code == 200 and r.json()["archived_at"]
    active = (await env.client.get(CAT, params={"include_archived": "false"}, headers=h(key=None))).json()
    assert cat["id"] not in {i["id"] for i in active["items"]}
    r = await env.client.patch(f"{CAT}/{cat['id']}", json={"archived": False, "version": 3}, headers=h())
    assert r.status_code == 200 and r.json()["archived_at"] is None


async def test_account_never_crosses_the_6410_boundary(env: Env) -> None:
    till = await make_till(env)
    h = till.shop.h
    tax = await category_id(env, till.shop.tenant_id, "tax_payment")
    rent = await category_id(env, till.shop.tenant_id, "rent_store")
    r = await env.client.patch(f"{CAT}/{tax}", json={"default_account": "9430", "version": 1}, headers=h())
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [
        {"field": "default_account", "message_key": "validation.not_allowed"}
    ]
    r = await env.client.patch(f"{CAT}/{rent}", json={"default_account": "6410", "version": 1}, headers=h())
    assert r.status_code == 422
    r = await env.client.patch(f"{CAT}/{rent}", json={"default_account": "9420", "version": 1}, headers=h())
    assert r.status_code == 200
    # the cashier may read but not change categories
    r = await env.client.patch(f"{CAT}/{rent}", json={"name": "X", "version": 2}, headers=h("cashier"))
    assert r.status_code == 403
    missing = await env.client.patch(f"{CAT}/{UUID(int=1)}", json={"name": "X", "version": 1}, headers=h())
    assert missing.status_code == 404
