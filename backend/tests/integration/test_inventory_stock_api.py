"""Stock read API — ``/stock-balances``, ``/stock-lots``, ``/stock-moves`` (19 §7), branch scope
(QT-PERM-08/09, 15 §2.4) and tenant isolation (RLS)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from tests.support.catalog import Env, Shop, catalog_env_fixture
from tests.support.inventory import (
    API,
    add_branch,
    add_user,
    err,
    issue,
    new_product,
    receive,
    use_account,
    warehouse_of,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]


async def _get(
    env: Env, shop: Shop, path: str, role: str = "owner", branch: Any = None, **params: Any
) -> Any:
    return await env.client.get(f"{API}/{path}", params=params, headers=shop.h(role, key=None, branch=branch))


async def test_stock_balances_fields_filters_and_cursor(env: Env) -> None:
    shop = await env.shop("Qoldiq")
    wh = await use_account(env, shop, "2910")
    cola = await new_product(env, shop, "Coca-Cola 1.5L", min_stock="5.000")
    fanta = await new_product(env, shop, "Fanta 1L")
    pepsi = await new_product(env, shop, "Pepsi 1L")
    await receive(env, shop, wh, cola, "3.000", "30000.00")
    await receive(env, shop, wh, fanta, "10.000", "70000.00")
    await issue(env, shop, wh, pepsi, "2.000")  # overselling: −2, cost unknown (0)
    body = (await _get(env, shop, "stock-balances")).json()
    by_name = {i["product_name"]: i for i in body["items"]}
    assert list(by_name) == ["Coca-Cola 1.5L", "Fanta 1L", "Pepsi 1L"]
    assert by_name["Coca-Cola 1.5L"] | {"updated_at": None} == {
        "product_id": str(cola), "product_name": "Coca-Cola 1.5L", "warehouse_id": str(wh), "qty": "3.000",
        "value": "30000.00", "avg_cost": "10000.0000", "min_stock": "5.000", "is_low": True,
        "is_negative": False, "updated_at": None,
    }  # fmt: skip
    assert (by_name["Pepsi 1L"]["qty"], by_name["Pepsi 1L"]["is_negative"], by_name["Pepsi 1L"]["avg_cost"]) == (
        "-2.000", True, None,
    )  # fmt: skip
    low = (await _get(env, shop, "stock-balances", low_stock="true")).json()["items"]
    assert [i["product_name"] for i in low] == ["Coca-Cola 1.5L"]
    found = (await _get(env, shop, "stock-balances", search="fan")).json()["items"]
    assert [i["product_name"] for i in found] == ["Fanta 1L"]
    page = (await _get(env, shop, "stock-balances", limit=2)).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = (await _get(env, shop, "stock-balances", limit=2, cursor=page["next_cursor"])).json()
    assert [i["product_name"] for i in rest["items"]] == ["Pepsi 1L"] and rest["next_cursor"] is None
    one = (await _get(env, shop, "stock-balances", product_id=str(fanta))).json()["items"]
    assert [i["qty"] for i in one] == ["10.000"]
    explicit = (await _get(env, shop, "stock-balances", warehouse_id=str(wh))).json()
    assert explicit["items"] == body["items"]


async def test_stock_lots_expiring_and_stock_moves(env: Env) -> None:
    shop = await env.shop("Partiyalar")
    wh = await use_account(env, shop)
    p = await new_product(env, shop, "Sut")
    today = business_today()
    await receive(env, shop, wh, p, "2.000", "20000.00", expiry=today + timedelta(days=3))
    await receive(env, shop, wh, p, "4.000", "40000.00", expiry=today + timedelta(days=30))
    await receive(env, shop, wh, p, "1.000", "10000.00")
    lots = (await _get(env, shop, "stock-lots")).json()["items"]
    assert [x["qty_left"] for x in lots] == ["2.000", "4.000", "1.000"]
    assert lots[0]["unit_cost"] == "10000.0000" and lots[0]["source_doc_type"] == "goods_receipts"
    expiring = (await _get(env, shop, "stock-lots", expiring_within_days=7)).json()["items"]
    assert [x["expiry_date"] for x in expiring] == [str(today + timedelta(days=3))]
    await issue(env, shop, wh, p, "2.000")
    assert len((await _get(env, shop, "stock-lots")).json()["items"]) == 2
    assert len((await _get(env, shop, "stock-lots", include_empty="true")).json()["items"]) == 3
    paged = (await _get(env, shop, "stock-lots", limit=1)).json()
    nxt = (await _get(env, shop, "stock-lots", limit=1, cursor=paged["next_cursor"])).json()
    assert paged["items"][0]["id"] != nxt["items"][0]["id"]
    moves = (await _get(env, shop, "stock-moves")).json()["items"]
    assert moves[0]["qty"] == "-2.000"  # newest first
    assert {m["doc_type"] for m in moves} == {"goods_receipts", "write_offs"}
    issued = (await _get(env, shop, "stock-moves", doc_type="write_offs")).json()["items"]
    assert [(m["qty"], m["cost_amount"]) for m in issued] == [("-2.000", "-20000.00")]
    assert (await _get(env, shop, "stock-moves", **{"from": str(today + timedelta(days=1))})).json()[
        "items"
    ] == []
    page = (await _get(env, shop, "stock-moves", limit=2)).json()
    rest = (await _get(env, shop, "stock-moves", limit=2, cursor=page["next_cursor"])).json()
    assert len(page["items"]) + len(rest["items"]) == 4


async def test_qt_perm_08_restricted_user_other_branch_is_denied(env: Env) -> None:
    """15 §2.4: a cashier bound to branch A asking for branch B → 403 BRANCH_SCOPE_DENIED (app layer,
    independent of RLS) — by header or by ``warehouse_id``."""
    shop = await env.shop("QT-PERM-08")
    branch_b, wh_b = await add_branch(env, shop, "02", "Chilonzor")
    await add_user(env, shop, "cashier_a", SystemRole.CASHIER, (shop.branch_id,))
    by_header = await _get(env, shop, "stock-balances", "cashier_a", branch=branch_b)
    assert by_header.status_code == 403 and err(by_header) == "BRANCH_SCOPE_DENIED"
    by_param = await _get(env, shop, "stock-balances", "cashier_a", warehouse_id=str(wh_b))
    assert by_param.status_code == 403 and err(by_param) == "BRANCH_SCOPE_DENIED"
    for path in ("stock-lots", "stock-moves"):
        denied = await _get(env, shop, path, "cashier_a", warehouse_id=str(wh_b))
        assert denied.status_code == 403 and err(denied) == "BRANCH_SCOPE_DENIED"
    own = await _get(env, shop, "stock-balances", "cashier_a", branch=shop.branch_id)
    assert own.status_code == 200
    no_header = await _get(env, shop, "stock-balances", "cashier_a")  # the only branch is implied
    assert no_header.status_code == 200
    await add_user(env, shop, "two_branches", SystemRole.CASHIER, (shop.branch_id, branch_b))
    ambiguous = await _get(env, shop, "stock-balances", "two_branches")
    assert ambiguous.status_code == 422 and ambiguous.json()["error"]["details"][0]["field"] == "X-Branch-Id"


async def test_qt_perm_09_unrestricted_owner_never_denied(env: Env) -> None:
    shop = await env.shop("QT-PERM-09")
    branch_b, wh_b = await add_branch(env, shop, "02", "Yunusobod")
    p = await new_product(env, shop)
    await receive(env, shop, wh_b, p, "1.000", "100.00")
    for branch in (shop.branch_id, branch_b, None):
        assert (await _get(env, shop, "stock-balances", branch=branch)).status_code == 200
    other_branch = (await _get(env, shop, "stock-balances", branch=branch_b)).json()["items"]
    assert [i["warehouse_id"] for i in other_branch] == [str(wh_b)]
    by_param = (await _get(env, shop, "stock-balances", warehouse_id=str(wh_b))).json()["items"]
    assert len(by_param) == 1


async def test_rls_another_tenant_sees_nothing(env: Env) -> None:
    shop = await env.shop("RLS A")
    wh = await warehouse_of(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "1.000", "100.00")
    await issue(env, shop, wh, p, "1.000")
    other = await env.shop("RLS B")
    for path in ("stock-balances", "stock-lots", "stock-moves"):
        foreign = await _get(env, other, path, warehouse_id=str(wh))
        assert foreign.status_code == 404 and foreign.json()["error"]["params"] == {"resource": "warehouse"}
        assert (await _get(env, other, path)).json()["items"] == []
    assert (await _get(env, other, "recost-jobs")).json()["items"] == []
    ledger = await env.client.get(f"{API}/ledger-entries", headers=other.h(key=None))
    assert ledger.status_code == 200 and ledger.json()["items"] == []
    mine = (await env.client.get(f"{API}/ledger-entries", headers=shop.h(key=None))).json()["items"]
    assert [(e["account_dt"], e["account_kt"], e["amount"]) for e in mine] == [("9120", "2920", "100.00")]
