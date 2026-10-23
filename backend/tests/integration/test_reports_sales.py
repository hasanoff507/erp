"""M12 sales reports and the dashboard (20 #17–#19; US-M12-01/02, US-M14-01) — QT-M12-01/02/04, QT-M14-01.

Sales go through the real ``sale.created`` handler; the day is the Asia/Tashkent business day.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.access.domain.permissions import SystemRole
from tests.support.inventory import add_user
from tests.support.reports import (
    doc_day,
    get,
    mark_unsynced,
    ok,
    second_pos,
    sell_lines,
    sell_one,
    stock_in,
)
from tests.support.sales import (
    D,
    Env,
    deliver,
    make_pos,
    new_item,
    return_line,
    return_payload,
    sale_line,
    sales_env_fixture,
    sold_lines,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


def _by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["group_key"]: r for r in rows}


async def test_qt_m12_01_daily_sales_by_branch_and_total(env: Env) -> None:
    pos = await make_pos(env, "Do'kon A")
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos, stock="10.000")
    await stock_in(env, pos_b, product, "5.000")
    await sell_one(env, pos, product)
    await sell_one(env, pos, product, qty="2.000")
    await sell_one(env, pos_b, product)
    day = doc_day().isoformat()

    body = await ok(env, pos.shop, "/reports/sales", group_by="branch", date_from=day, date_to=day)
    rows = _by_key(body["rows"])
    a, b = rows[str(pos.branch_id)], rows[str(pos_b.branch_id)]
    assert (a["total_sales"], a["receipt_count"], a["avg_receipt"]) == ("36000.00", 2, "18000.00")
    assert (b["total_sales"], b["receipt_count"], b["avg_receipt"]) == ("12000.00", 1, "12000.00")
    assert b["group_label"] == "Chilonzor"
    total = body["total"]
    assert (total["total_sales"], total["receipt_count"], total["avg_receipt"]) == ("48000.00", 3, "16000.00")
    assert body["data_complete"] is True and body["unsynced_devices"] == 0

    by_day = await ok(env, pos.shop, "/reports/sales", group_by="day", date_from=day, date_to=day)
    assert [(r["group_key"], r["total_sales"], r["receipt_count"]) for r in by_day["rows"]] == [
        (day, "48000.00", 3)
    ]

    only_b = await ok(env, pos.shop, "/reports/sales", group_by="branch", branch_id=pos_b.branch_id)
    assert [r["group_key"] for r in only_b["rows"]] == [str(pos_b.branch_id)]
    assert only_b["total"]["total_sales"] == "12000.00"

    cashiers = await ok(env, pos.shop, "/reports/sales", group_by="cashier", date_from=day, date_to=day)
    assert [(r["group_key"], r["receipt_count"]) for r in cashiers["rows"]] == [
        (str(pos.shop.user_ids["owner"]), 3)
    ]


async def test_qt_m12_01_returns_reduce_total_sales_not_receipt_average(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    sale_id = await sell_one(env, pos, product, qty="2.000")
    lines = await sold_lines(env, pos, sale_id)
    ret = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id)
    res = await deliver(env, pos, "return.created", ret)
    assert res.error is None, (res.code, res.keys)
    body = await ok(env, pos.shop, "/reports/sales", group_by="day")
    total = body["total"]
    # 20 #18: total_sales = Σ posted sales − Σ posted returns; avg_receipt is the average receipt
    assert (total["gross_sales"], total["returns_total"], total["total_sales"]) == (
        "24000.00",
        "12000.00",
        "12000.00",
    )
    assert (total["receipt_count"], total["avg_receipt"]) == (1, "24000.00")


async def test_sales_report_range_validation_and_empty_days(env: Env) -> None:
    pos = await make_pos(env)
    bad = await get(env, pos.shop, "/reports/sales", date_from="2026-10-10", date_to="2026-10-01")
    assert (
        bad.status_code == 422 and bad.json()["error"]["details"][0]["message_key"] == "validation.date_range"
    )
    too_long = await get(env, pos.shop, "/reports/sales", date_from="2025-01-01", date_to="2026-10-01")
    assert too_long.json()["error"]["details"][0]["message_key"] == "validation.date_range_too_long"
    week = await ok(env, pos.shop, "/reports/sales", date_from="2026-10-01", date_to="2026-10-07")
    assert len(week["rows"]) == 7 and all(r["total_sales"] == "0.00" for r in week["rows"])


async def test_qt_m12_02_products_by_quantity_descending(env: Env) -> None:
    pos = await make_pos(env)
    fast = await new_item(env, pos, "Non", price="4000.00", stock="20.000", cost="3000.00")
    slow = await new_item(env, pos, "Sut", price="9000.00", stock="20.000", cost="7000.00")
    mid = await new_item(env, pos, "Choy", price="15000.00", stock="20.000", cost="10000.00")
    await sell_lines(
        env, pos, [sale_line(fast, qty="5.000", price="4000.0000"), sale_line(slow, price="9000.0000")]
    )
    await sell_lines(env, pos, [sale_line(mid, qty="3.000", price="15000.0000")])
    day = doc_day().isoformat()

    top = await ok(env, pos.shop, "/reports/top-products", role="manager", date_from=day, date_to=day)
    assert [(i["name"], i["qty_sold"], i["revenue"]) for i in top["items"]] == [
        ("Non", "5.000", "20000.00"), ("Choy", "3.000", "45000.00"), ("Sut", "1.000", "9000.00"),
    ]  # fmt: skip
    bottom = await ok(env, pos.shop, "/reports/top-products", order="bottom", limit=2)
    assert [i["name"] for i in bottom["items"]] == ["Sut", "Choy"]


async def test_qt_m12_04_unsynced_devices_mark_reports_incomplete(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos)
    await sell_one(env, pos, product)
    await mark_unsynced(env, pos, pending=4)

    sales = await ok(env, pos.shop, "/reports/sales")
    assert sales["data_complete"] is False and sales["unsynced_devices"] == 1
    top = await ok(env, pos.shop, "/reports/top-products")
    assert top["data_complete"] is False
    dash = await ok(env, pos.shop, "/reports/dashboard")
    assert dash["data_complete"] is False and dash["unsynced_devices"] == 1
    alert = next(a for a in dash["alerts"] if a["type"] == "unsynced_devices")
    assert alert["count"] == 1 and alert["message_key"] == "reports.alerts.unsynced_devices"
    assert alert["severity"] == "warning" and alert["route"].startswith("/app/settings")
    other = await ok(env, pos.shop, "/reports/sales", branch_id=pos_b.branch_id)
    assert other["data_complete"] is True  # the unsynced device belongs to the other branch


async def test_qt_m14_01_dashboard_each_branch_and_total(env: Env) -> None:
    pos = await make_pos(env, "Do'kon B")
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos, "Coca-Cola", stock="10.000")
    await stock_in(env, pos_b, product, "5.000")
    await sell_one(env, pos, product, qty="2.000")
    await sell_one(env, pos_b, product)

    dash = await ok(env, pos.shop, "/reports/dashboard", period="today")
    assert dash["period"] == "today" and dash["date_from"] == dash["date_to"] == doc_day().isoformat()
    branches = {b["branch_id"]: b for b in dash["by_branch"]}
    assert set(branches) == {str(pos.branch_id), str(pos_b.branch_id)}
    a, b = branches[str(pos.branch_id)], branches[str(pos_b.branch_id)]
    assert (a["sales"], a["receipt_count"]) == ("24000.00", 1)
    assert (b["sales"], b["receipt_count"], b["name"]) == ("12000.00", 1, "Chilonzor")
    assert (dash["total_sales"], dash["receipt_count"], dash["avg_receipt"]) == ("36000.00", 2, "18000.00")
    # revenue excl. VAT − COGS: A 21428.57 − 16000, B 10714.29 − 8000
    assert a["profit"] == "5428.57" and b["profit"] == "2714.29" and dash["net_profit"] == "8142.86"
    assert dash["top_products"] == [
        {"product_id": str(product), "name": "Coca-Cola", "unit_code": "box", "qty": "3.000"}
    ]
    assert dash["cash_on_hand"] == "36000.00" and a["cash_on_hand"] == "24000.00"
    assert dash["stock"]["value"] == "96000.00" and dash["stock"]["positions"] == 1
    assert dash["receivables"] == {
        "total": "0.00",
        "debtors_count": 0,
        "overdue_count": 0,
        "overdue_amount": "0.00",
    }

    one_branch = await ok(env, pos.shop, "/reports/dashboard", branch_id=pos_b.branch_id)
    assert [b["branch_id"] for b in one_branch["by_branch"]] == [str(pos_b.branch_id)]
    assert one_branch["total_sales"] == "12000.00" and one_branch["branch_id"] == str(pos_b.branch_id)


async def test_dashboard_previous_period_and_week(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await sell_one(env, pos, product)
    week = await ok(env, pos.shop, "/reports/dashboard", period="week")
    assert week["total_sales"] == "12000.00" and week["previous_total_sales"] == "0.00"
    month = await ok(env, pos.shop, "/reports/dashboard", period="month")
    assert month["date_from"].endswith("-01") and month["receipt_count"] == 1


async def test_reports_permissions_and_branch_scope(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos)
    await stock_in(env, pos_b, product, "5.000")
    await sell_one(env, pos, product)
    await sell_one(env, pos_b, product)

    for path in ("/reports/dashboard", "/reports/sales", "/reports/top-products"):
        denied = await get(env, pos.shop, path, role="cashier")
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "PERMISSION_DENIED", path
    await add_user(env, pos.shop, "keeper", SystemRole.STOREKEEPER)
    assert (await get(env, pos.shop, "/reports/stock", role="keeper")).status_code == 200
    assert (await get(env, pos.shop, "/reports/sales", role="keeper")).status_code == 403
    assert (await get(env, pos.shop, "/reports/profit-and-loss", role="keeper")).status_code == 403

    await add_user(env, pos.shop, "manager_b", SystemRole.MANAGER, (pos_b.branch_id,))
    scoped = await ok(env, pos.shop, "/reports/sales", role="manager_b", group_by="branch")
    assert [r["group_key"] for r in scoped["rows"]] == [str(pos_b.branch_id)]
    assert scoped["total"]["total_sales"] == "12000.00"
    other = await get(env, pos.shop, "/reports/dashboard", role="manager_b", branch_id=pos.branch_id)
    assert other.status_code == 403 and other.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"
    dash = await ok(env, pos.shop, "/reports/dashboard", role="manager_b")
    assert [b["branch_id"] for b in dash["by_branch"]] == [str(pos_b.branch_id)]
    assert dash["total_sales"] == "12000.00"


async def test_dashboard_hides_finance_fields_without_permission(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await sell_one(env, pos, product)
    from tests.support.catalog import set_limit
    from tests.support.sales import execute

    await execute(
        env.db, pos.tenant_id,
        "DELETE FROM app.role_permissions WHERE permission_code IN ('reports.finance.view', 'stock.view', "
        "'debts.payment.accept') AND role_id = (SELECT id FROM app.roles WHERE system_code = 'manager')",
    )  # fmt: skip
    await set_limit(env.db, pos.tenant_id, "manager", "reports.sales.view", None)
    dash = await ok(env, pos.shop, "/reports/dashboard", role="manager")
    assert dash["net_profit"] is None and dash["by_branch"][0]["profit"] is None
    assert dash["receivables"] is None and dash["stock"] is None
    assert dash["total_sales"] == "12000.00"
    assert D(dash["cash_on_hand"]) == D("12000.00")
