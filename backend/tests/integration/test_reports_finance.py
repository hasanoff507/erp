"""Profit and loss, net profit and the discount/margin report (20 #12, #19a; US-M15-03, US-M03-03, US-M11-03) —
QT-M15-03, QT-M03-03. Figures come from ``ledger_entries`` (13 §1: 9020/9040/9050/9120/9390, 94xx/9820)."""

from __future__ import annotations

import pytest

from tests.support.inventory import issue, set_setting
from tests.support.reports import doc_day, ok, post_expense, second_pos, sell_lines, sell_one, stock_in
from tests.support.sales import (
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


def _period() -> str:
    return doc_day().strftime("%Y-%m")


async def test_qt_m15_03_net_profit_revenue_minus_cogs_minus_expenses(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="10.000", cost="8000.00")
    await sell_one(env, pos, product)  # 12000 incl. VAT 1285.71 → Kt 9020 10714.29, Dt 9120 8000
    rent = await post_expense(env, pos, "1000.00", account="9410", category="Ijara")
    phone = await post_expense(env, pos, "500.00", account="9420", category="Aloqa")

    pnl = await ok(env, pos.shop, "/reports/profit-and-loss", period=_period())
    assert pnl["period"] == _period() and pnl["date_from"].endswith("-01")
    assert (pnl["revenue"], pnl["returns"], pnl["discounts"]) == ("10714.29", "0.00", "0.00")
    assert (pnl["net_revenue"], pnl["cogs"], pnl["gross_profit"]) == ("10714.29", "8000.00", "2714.29")
    by_category = {c["category_id"]: c for c in pnl["expenses_by_category"]}
    assert by_category[str(rent)]["amount"] == "1000.00" and by_category[str(rent)]["account"] == "9410"
    assert by_category[str(phone)]["amount"] == "500.00" and by_category[str(phone)]["source"] == "expenses"
    assert by_category[str(rent)]["category"].startswith("Ijara")
    assert pnl["expenses_total"] == "1500.00"
    # US-M15-03: Sof foyda = Sotuv tushumi − COGS − Xarajatlar
    assert pnl["net_profit"] == "1214.29"

    dash = await ok(env, pos.shop, "/reports/dashboard")
    assert dash["net_profit"] == "1214.29"
    assert dash["cash_on_hand"] == "10500.00"  # 12000 cash sale − 1500 cash expenses


async def test_profit_and_loss_returns_write_offs_and_branches(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos, stock="10.000", cost="8000.00")
    await stock_in(env, pos_b, product, "5.000")
    sale_id = await sell_one(env, pos, product, qty="2.000")
    lines = await sold_lines(env, pos, sale_id)
    ret = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id)
    assert (await deliver(env, pos, "return.created", ret)).error is None
    await sell_one(env, pos_b, product)
    await issue(env, pos_b.shop, pos_b.warehouse_id, product, "1.000", account_dt="9430")  # write-off at cost

    pnl = await ok(env, pos.shop, "/reports/profit-and-loss")  # default = current month
    # A: Kt 9020 21428.57, Dt 9040 10714.29, COGS 16000 − 8000; B: 10714.29, COGS 8000
    assert (pnl["revenue"], pnl["returns"], pnl["cogs"]) == ("32142.86", "10714.29", "16000.00")
    assert pnl["net_revenue"] == "21428.57" and pnl["gross_profit"] == "5428.57"
    write_off = [c for c in pnl["expenses_by_category"] if c["source"] == "write_offs"]
    assert write_off == [
        {
            "category_id": None,
            "category": None,
            "account": "9430",
            "source": "write_offs",
            "amount": "8000.00",
        }
    ]
    assert pnl["net_profit"] == "-2571.43"
    branches = {b["branch_id"]: b for b in pnl["by_branch"]}
    assert branches[str(pos.branch_id)]["net_profit"] == "2714.28"
    assert branches[str(pos_b.branch_id)]["net_profit"] == "-5285.71"
    assert branches[str(pos_b.branch_id)]["expenses_total"] == "8000.00"

    only_a = await ok(env, pos.shop, "/reports/profit-and-loss", branch_id=pos.branch_id)
    assert only_a["by_branch"] == [] and only_a["net_profit"] == "2714.28"


async def test_qt_m03_03_discounts_and_lost_margin(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, "Choy", stock="10.000", cost="8000.00")
    # 10 % manual discount: 12000 − 1200 = 10800 paid
    await sell_lines(env, pos, [sale_line(product, discount="1200.00")])
    await sell_one(env, pos, product)
    day = doc_day().isoformat()

    report = await ok(env, pos.shop, "/reports/discounts", date_from=day, date_to=day, group_by="product")
    row = report["rows"][0]
    assert (row["group_label"], row["sales_total"], row["discount_total"]) == ("Choy", "22800.00", "1200.00")
    assert row["discount_net"] == "1071.43"  # 1200 × 100 / 112 — the margin the discount cost
    assert (row["revenue_net"], row["cost"]) == ("20357.15", "16000.00")
    assert (row["margin"], row["margin_without_discounts"]) == ("4357.15", "5428.58")
    assert (row["margin_pct"], row["margin_pct_without_discounts"]) == ("21.40", "25.33")
    assert report["total"]["discount_total"] == "1200.00"

    # gross_9050 (13 §2.1a): Dt 9050 = list net − discounted net = 10714.29 − 9642.86
    pnl = await ok(env, pos.shop, "/reports/profit-and-loss", period=_period())
    assert pnl["discount_posting"] == "gross_9050"
    assert (pnl["revenue"], pnl["discounts"], pnl["net_revenue"]) == ("21428.58", "1071.43", "20357.15")


async def test_profit_and_loss_net_discount_mode_reports_line_discounts(env: Env) -> None:
    pos = await make_pos(env)
    await set_setting(env, pos.shop, "discount_posting", "net")
    product = await new_item(env, pos, stock="10.000", cost="8000.00")
    await sell_lines(env, pos, [sale_line(product, discount="1200.00")])
    pnl = await ok(env, pos.shop, "/reports/profit-and-loss", period=_period())
    assert pnl["discount_posting"] == "net"
    # net: 9020 already carries the discounted amount; discounts = Σ discount_amount excl. VAT (20 #12)
    assert (pnl["revenue"], pnl["discounts"], pnl["net_revenue"]) == ("9642.86", "1071.43", "9642.86")
    assert pnl["net_profit"] == "1642.86"


async def test_profit_and_loss_validation(env: Env) -> None:
    pos = await make_pos(env)
    from tests.support.reports import get

    bad = await get(env, pos.shop, "/reports/profit-and-loss", period="2026-13")
    assert bad.status_code == 422 and bad.json()["error"]["details"][0]["field"] == "period"
    denied = await get(env, pos.shop, "/reports/discounts", role="cashier")
    assert denied.status_code == 403
