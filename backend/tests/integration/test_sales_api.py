"""``GET /sales`` (18 §4.8), ``GET /returns`` (18 §7.2), ``GET /fiscal-receipts`` (18 §14.1) — read API."""

from __future__ import annotations

from typing import Any

import pytest

from tests.support.sales import (
    API,
    Env,
    deliver,
    make_pos,
    new_item,
    return_line,
    return_payload,
    sale_line,
    sale_payload,
    sales_env_fixture,
    sell,
    sold_lines,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


def _pin(user_id: object) -> dict[str, Any]:
    return {"mode": "local_pin", "approved_by": str(user_id), "pin_verified_locally": True}


async def test_sales_list_and_detail(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    first = sale_payload(pos, [sale_line(product, qty="2.000")])
    await sell(env, pos, first)
    second = sale_payload(pos, [sale_line(product)], [{"method": "cash", "amount": "12000.00"}])
    await sell(env, pos, second)
    lines = await sold_lines(env, pos, first["id"])
    ret = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=first["id"])
    assert (await deliver(env, pos, "return.created", ret)).error is None

    page = await env.client.get(f"{API}/sales", params={"limit": 1}, headers=pos.shop.h("cashier"))
    assert page.status_code == 200, page.text
    body = page.json()
    assert len(body["items"]) == 1 and body["next_cursor"] and body["items"][0]["id"] == second["id"]
    rest = await env.client.get(
        f"{API}/sales", params={"cursor": body["next_cursor"]}, headers=pos.shop.h("cashier")
    )
    item = rest.json()["items"][0]
    assert item["id"] == first["id"] and item["has_returns"] is True and item["total_amount"] == "24000.00"
    assert item["payments_summary"] == [{"method": "cash", "amount": "24000.00"}]
    by_seq = await env.client.get(f"{API}/sales", params={"fiscal_receipt_seq": first["receipt_seq"]},
                                  headers=pos.shop.h("accountant"))  # fmt: skip
    assert [i["id"] for i in by_seq.json()["items"]] == [first["id"]]

    detail = await env.client.get(f"{API}/sales/{first['id']}", headers=pos.shop.h("cashier"))
    assert detail.status_code == 200, detail.text
    got = detail.json()
    assert got["lines"][0]["returned_qty"] == "1.000" and got["lines"][0]["qty"] == "2.000"
    assert (
        got["lines"][0]["sale_line_id"] == str(lines[0]["id"]) and got["fiscal_receipts"][0]["kind"] == "sale"
    )
    accountant_list = await env.client.get(f"{API}/sales", headers=pos.shop.h("accountant", key=None))
    assert accountant_list.status_code == 200  # accountant holds reports.sales.view

    returns = await env.client.get(f"{API}/returns", headers=pos.shop.h("accountant"))
    assert returns.status_code == 200 and returns.json()["items"][0]["without_receipt"] is False
    one_return = await env.client.get(f"{API}/returns/{ret['id']}", headers=pos.shop.h("manager"))
    assert one_return.status_code == 200 and one_return.json()["total_amount"] == "12000.00"
    cashier_returns = await env.client.get(f"{API}/returns", headers=pos.shop.h("cashier"))
    assert cashier_returns.status_code == 403

    receipts = await env.client.get(
        f"{API}/fiscal-receipts", params={"sale_id": first["id"]}, headers=pos.shop.h("cashier")
    )
    assert receipts.status_code == 200 and receipts.json()["items"][0]["payment_form"] == "cash"
    missing = await env.client.get(f"{API}/sales/{ret['id']}", headers=pos.shop.h("cashier"))
    assert missing.status_code == 404


async def test_returns_without_receipt_filter(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    await sell(env, pos, sale_payload(pos, [sale_line(product)]))
    ret = return_payload(pos, [return_line(product)], approval=_pin(pos.shop.user_ids["manager"]))
    assert (await deliver(env, pos, "return.created", ret)).error is None
    listed = await env.client.get(
        f"{API}/returns", params={"without_receipt": "true"}, headers=pos.shop.h("owner")
    )
    assert [i["id"] for i in listed.json()["items"]] == [ret["id"]]
    assert listed.json()["items"][0]["without_receipt"] is True
