"""``current_price`` on ``GET /products`` (19 §1) and ``set_by_name`` in price history (19 §4)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import event, text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from tests.support.catalog import Env, Shop, catalog_env_fixture, create_product, set_price

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

API = "/api/v1"


async def _prices(env: Env, shop: Shop, **headers: Any) -> dict[str, str | None]:
    response = await env.client.get(f"{API}/products", headers=shop.h(key=None, **headers))
    assert response.status_code == 200, response.text
    return {item["name"]: item["current_price"] for item in response.json()["items"]}


async def _add_branch(env: Env, shop: Shop, code: str) -> UUID:
    branch_id = uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.branches (id, tenant_id, code, name, settlement_category, activity_type) "
                "VALUES (:id, :t, :code, :name, 'other', 'retail')"
            ),
            {"id": branch_id, "t": shop.tenant_id, "code": code, "name": f"Filial {code}"},
        )
    return branch_id


@contextmanager
def _price_queries(env: Env) -> Iterator[list[str]]:
    seen: list[str] = []
    engine = env.app.state.db.engine.sync_engine

    def listener(*args: Any) -> None:
        statement = str(args[2])
        if "app.product_prices" in statement:
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", listener)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", listener)


async def test_current_price_present_null_and_after_posted_change(env: Env) -> None:
    shop = await env.shop("Joriy narx", SystemRole.OWNER, SystemRole.MANAGER)
    names = ["Non", "Sut", "Choy", "Shakar"]
    products = {n: await create_product(env.client, shop, n) for n in names}
    for n, price in zip(names[:3], ["4000.0000", "12000.0000", "25000.5000"], strict=True):
        await set_price(env.client, shop, products[n]["id"], price)

    with _price_queries(env) as queries:
        prices = await _prices(env, shop)
    assert prices == {"Non": "4000.0000", "Sut": "12000.0000", "Choy": "25000.5000", "Shakar": None}
    assert len(queries) == 1  # one batched query per page — no N+1

    await set_price(env.client, shop, products["Sut"]["id"], "13000.0000", role="manager")
    assert (await _prices(env, shop))["Sut"] == "13000.0000"

    # a future valid_from is not yet effective
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    await set_price(env.client, shop, products["Non"]["id"], "4200.0000", valid_from=future)
    assert (await _prices(env, shop))["Non"] == "4000.0000"

    # GET /products/{id} and the write responses keep their shape (current_price is a list field)
    one = await env.client.get(f"{API}/products/{products['Non']['id']}", headers=shop.h(key=None))
    assert "current_price" not in one.json()


async def test_current_price_is_branch_specific(env: Env) -> None:
    shop = await env.shop("Filial joriy narx", SystemRole.OWNER)
    other = await _add_branch(env, shop, "02")
    p = await create_product(env.client, shop, "Olma")
    await set_price(env.client, shop, p["id"], "12000.0000")
    await set_price(env.client, shop, p["id"], "11500.0000", branch_id=str(shop.branch_id))

    assert (await _prices(env, shop, branch=shop.branch_id))["Olma"] == "11500.0000"
    assert (await _prices(env, shop))["Olma"] == "11500.0000"  # no header → default branch
    assert (await _prices(env, shop, branch=other))["Olma"] == "12000.0000"  # global fallback

    await set_price(env.client, shop, p["id"], "13000.0000", branch_id=str(other))
    assert (await _prices(env, shop, branch=other))["Olma"] == "13000.0000"
    assert (await _prices(env, shop, branch=shop.branch_id))["Olma"] == "11500.0000"


async def test_restricted_user_sees_own_branch_price(env: Env) -> None:
    shop = await env.shop("Cheklangan joriy", SystemRole.OWNER, SystemRole.MANAGER)
    other = await _add_branch(env, shop, "02")
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.memberships SET branch_ids = ARRAY[CAST(:b AS uuid)] WHERE user_id = :u"),
            {"b": str(other), "u": shop.user_ids["manager"]},
        )
    p = await create_product(env.client, shop, "Nok")
    await set_price(env.client, shop, p["id"], "9000.0000")
    await set_price(env.client, shop, p["id"], "9500.0000", branch_id=str(other))
    response = await env.client.get(f"{API}/products", headers=shop.h("manager", key=None))
    assert response.status_code == 200
    assert response.json()["items"][0]["current_price"] == "9500.0000"


async def test_price_history_set_by_name(env: Env) -> None:
    shop = await env.shop("Kim o'rnatdi", SystemRole.OWNER, SystemRole.MANAGER)
    p = await create_product(env.client, shop, "Guruch")
    await set_price(env.client, shop, p["id"], "15000.0000")
    await set_price(env.client, shop, p["id"], "15500.0000", role="manager")
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(  # a system/legacy row without an author
            text(
                "INSERT INTO app.product_prices (id, tenant_id, product_id, branch_id, price, valid_from) "
                "VALUES (:id, :t, :p, NULL, 16000, now() + interval '1 hour')"
            ),
            {"id": uuid7(), "t": shop.tenant_id, "p": p["id"]},
        )

    history = await env.client.get(f"{API}/products/{p['id']}/prices", headers=shop.h(key=None))
    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert [(i["price"], i["set_by_name"]) for i in items] == [
        ("16000.0000", None),
        ("15500.0000", "Kim o'rnatdi manager"),
        ("15000.0000", "Kim o'rnatdi owner"),
    ]
    assert items[0]["set_by"] is None and items[1]["set_by"] == str(shop.user_ids["manager"])
