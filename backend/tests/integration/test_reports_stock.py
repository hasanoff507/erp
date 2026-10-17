"""``GET /reports/stock`` (20 #20; US-M04-03, BO-03 «Barchasi», WEB-10) — QT-M04-03."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from tests.support.inventory import add_user
from tests.support.reports import get, ok, second_pos, stock_in
from tests.support.sales import Env, execute, make_pos, new_item, sales_env_fixture

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]

EAN = "4006381333931"


async def _category(env: Env, tenant_id: UUID, name: str) -> UUID:
    category_id = uuid7()
    await execute(
        env.db, tenant_id, "INSERT INTO app.product_categories (id, tenant_id, name) VALUES (:id, :t, :n)",
        id=category_id, t=tenant_id, n=name,
    )  # fmt: skip
    return category_id


async def test_qt_m04_03_consolidated_stock_each_branch_and_total(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    drinks = await _category(env, pos.tenant_id, "Ichimliklar")
    cola = await new_item(
        env, pos, "Coca-Cola", stock="10.000", cost="8000.00", category_id=str(drinks), barcode=EAN,
        min_stock="5.000",
    )  # fmt: skip
    await stock_in(env, pos_b, cola, "4.000", "8000.00")
    tea = await new_item(env, pos, "Choy", stock="2.000", cost="15000.00")

    body = await ok(env, pos.shop, "/reports/stock")
    assert body["consolidated"] is True and body["branch_id"] is None
    items = {i["product_id"]: i for i in body["items"]}
    row = items[str(cola)]
    assert (row["qty"], row["value"], row["avg_cost"]) == ("14.000", "112000.00", "8000.0000")
    # WEB-10: the row carries unit / category / barcode / marking so the web needs no product cards
    assert (row["unit_code"], row["category_id"], row["category_name"]) == ("box", str(drinks), "Ichimliklar")
    assert (row["barcode"], row["is_marked"], row["is_weighed"], row["min_stock"]) == (
        EAN,
        False,
        False,
        "5.000",
    )
    per_branch = {b["branch_id"]: b for b in row["by_branch"]}
    assert (
        per_branch[str(pos.branch_id)]["qty"] == "10.000"
        and per_branch[str(pos.branch_id)]["below_min"] is False
    )
    assert per_branch[str(pos_b.branch_id)] == {
        "branch_id": str(pos_b.branch_id), "branch_name": "Chilonzor", "qty": "4.000", "value": "32000.00",
        "below_min": True,
    }  # fmt: skip
    assert row["below_min"] is True  # low in one branch
    branches = {b["branch_id"]: b for b in body["branches"]}
    assert branches[str(pos.branch_id)]["value"] == "110000.00"  # 80000 cola + 30000 tea
    assert branches[str(pos_b.branch_id)] == {
        "branch_id": str(pos_b.branch_id), "name": "Chilonzor", "value": "32000.00", "positions": 1,
        "below_min_count": 1,
    }  # fmt: skip
    assert body["total"] == {"value": "142000.00", "positions": 2, "below_min_count": 1}
    assert items[str(tea)]["category_name"] is None and items[str(tea)]["barcode"] is None

    low = await ok(env, pos.shop, "/reports/stock", below_min_only="true")
    assert [i["product_id"] for i in low["items"]] == [str(cola)]
    only_b = await ok(env, pos.shop, "/reports/stock", branch_id=pos_b.branch_id)
    assert only_b["consolidated"] is False and only_b["total"]["value"] == "32000.00"
    assert [i["qty"] for i in only_b["items"]] == ["4.000"]
    by_code = await ok(env, pos.shop, "/reports/stock", search=EAN)
    assert [i["name"] for i in by_code["items"]] == ["Coca-Cola"]
    by_name = await ok(env, pos.shop, "/reports/stock", search="choy")
    assert [i["name"] for i in by_name["items"]] == ["Choy"]
    by_category = await ok(env, pos.shop, "/reports/stock", category_id=drinks)
    assert [i["name"] for i in by_category["items"]] == ["Coca-Cola"]
    by_wh = await ok(env, pos.shop, "/reports/stock", warehouse_id=pos_b.warehouse_id)
    assert by_wh["total"]["value"] == "32000.00"


async def test_stock_report_branch_scope(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos, stock="3.000")
    await stock_in(env, pos_b, product, "2.000")
    await add_user(env, pos.shop, "keeper_b", SystemRole.STOREKEEPER, (pos_b.branch_id,))
    scoped = await ok(env, pos.shop, "/reports/stock", role="keeper_b")
    assert scoped["consolidated"] is False and scoped["total"]["value"] == "16000.00"
    assert [b["branch_id"] for b in scoped["branches"]] == [str(pos_b.branch_id)]
    foreign = await get(env, pos.shop, "/reports/stock", role="keeper_b", warehouse_id=pos.warehouse_id)
    assert foreign.status_code == 403 and foreign.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"
    other = await get(env, pos.shop, "/reports/stock", role="keeper_b", branch_id=pos.branch_id)
    assert other.status_code == 403
