"""``current_cost`` and ``markup_pct`` on ``GET /products`` (19 §1 addition, BO-05 «Tannarx» / «Ustama %»)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.modules.accounting.wiring import business_today
from tests.support.catalog import Env, Shop, catalog_env_fixture, set_price
from tests.support.inventory import (
    API,
    add_branch,
    execute,
    issue,
    new_product,
    receive,
    set_method,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]


async def _items(env: Env, shop: Shop, branch: Any = None) -> dict[str, dict[str, Any]]:
    response = await env.client.get(f"{API}/products", headers=shop.h(key=None, branch=branch))
    assert response.status_code == 200, response.text
    return {i["name"]: i for i in response.json()["items"]}


async def test_aveco_cost_and_markup_net_of_vat(env: Env) -> None:
    """avg 8333.3333; net price 12000 × 100/112 = 10714.2857 → (10714.2857 − 8333.3333)/8333.3333 = 28.57 %."""
    shop = await env.shop("Ustama AVECO")
    await set_method(env, shop, "aveco")
    wh = await use_account(env, shop)
    cola = await new_product(env, shop, "Coca-Cola 1.5L")
    await new_product(env, shop, "Yangi tovar")  # no stock, no price
    juice = await new_product(env, shop, "Sharbat")  # stock, no price
    await set_price(env.client, shop, str(cola), "12000.0000")
    await receive(env, shop, wh, cola, "100.000", "800000.00")
    await receive(env, shop, wh, cola, "50.000", "450000.00")
    await receive(env, shop, wh, juice, "2.000", "15000.00")
    items = await _items(env, shop)
    assert (items["Coca-Cola 1.5L"]["current_cost"], items["Coca-Cola 1.5L"]["markup_pct"]) == (
        "8333.3333",
        "28.57",
    )
    assert (items["Yangi tovar"]["current_cost"], items["Yangi tovar"]["markup_pct"]) == (None, None)
    assert (items["Sharbat"]["current_cost"], items["Sharbat"]["markup_pct"]) == ("7500.0000", None)


async def test_fifo_cost_and_markup_for_turnover_tax_payer(env: Env) -> None:
    """FIFO: 30 left of the 9000.0000 lot → cost 9000.0000; turnover regime → full price:
    (12000 − 9000) / 9000 = 33.33 %."""
    shop = await env.shop("Ustama FIFO")
    await set_method(env, shop, "fifo")
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) VALUES (:t, :v, 'turnover', :u)",
        t=shop.tenant_id, v=date(business_today().year, 1, 1), u=shop.user_ids["owner"],
    )  # fmt: skip
    wh = await use_account(env, shop)
    cola = await new_product(env, shop, "Coca-Cola 1.5L")
    await set_price(env.client, shop, str(cola), "12000.0000")
    await receive(env, shop, wh, cola, "100.000", "800000.00")
    await receive(env, shop, wh, cola, "50.000", "450000.00")
    await issue(env, shop, wh, cola, "120.000")
    item = (await _items(env, shop))["Coca-Cola 1.5L"]
    assert (item["current_cost"], item["markup_pct"]) == ("9000.0000", "33.33")
    await issue(env, shop, wh, cola, "30.000")  # empty → last purchase cost (13 §2.11)
    item = (await _items(env, shop))["Coca-Cola 1.5L"]
    assert (item["current_cost"], item["markup_pct"]) == ("9000.0000", "33.33")


async def test_cost_follows_the_branch_warehouse(env: Env) -> None:
    shop = await env.shop("Ustama filial")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    branch_b, wh_b = await add_branch(env, shop, "02")
    p = await new_product(env, shop, "Non")
    await receive(env, shop, wh, p, "1.000", "3000.00")
    await receive(env, shop, wh_b, p, "1.000", "3500.00")
    assert (await _items(env, shop))["Non"]["current_cost"] == "3000.0000"
    assert (await _items(env, shop, branch_b))["Non"]["current_cost"] == "3500.0000"
