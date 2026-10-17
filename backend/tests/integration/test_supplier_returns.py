"""Supplier returns (19 §12; 13 §2.20, §4.3, §5.2; US-M07-05; QT-M07-06) — real app + PostgreSQL/Redis;
FIFO and AVECO rows (3a ``invoice > book`` → 9390, 3b ``invoice < book`` → 9430) asserted to the tiyin."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from tests.support.inventory import (
    D,
    avg,
    balance,
    close_period,
    execute,
    issue,
    ledger,
    lots,
    rows,
    scalar,
    set_method,
    use_account,
)
from tests.support.purchasing import (
    GR,
    SR,
    Env,
    Shop,
    create_product,
    create_receipt,
    create_return,
    create_supplier,
    err,
    gr_line,
    post_sr,
    posted_receipt,
    purchasing_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["purchasing_env_fixture"]


async def _setup(env: Env, name: str, method: str = "fifo", *roles: SystemRole) -> tuple[Shop, str, UUID]:
    shop = await env.shop(name, *(roles or (SystemRole.OWNER,)))
    supplier = await create_supplier(env.client, shop)
    wh = await use_account(env, shop, "2910")
    await set_method(env, shop, method)
    return shop, supplier["id"], wh


async def _product(env: Env, shop: Shop, name: str = "Yogurt") -> str:
    return str((await create_product(env.client, shop, name))["id"])


def _rows(entries: list[dict[str, Any]]) -> list[tuple[str, str, Any]]:
    return [(e["account_dt"], e["account_kt"], e["amount"]) for e in entries]


async def _payable(env: Env, shop: Shop, supplier_id: str) -> Any:
    value = await scalar(
        env, shop.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'payable'",
        c=UUID(supplier_id),
    )  # fmt: skip
    return value if value is not None else D("0.00")


async def _debt(env: Env, shop: Shop, doc_id: str) -> list[Any]:
    found = await rows(
        env, shop.tenant_id, "SELECT amount FROM app.debt_moves WHERE doc_id = :d ORDER BY created_at, id",
        d=UUID(doc_id),
    )  # fmt: skip
    return [r["amount"] for r in found]


async def _posted(env: Env, shop: Shop, draft: dict[str, Any], **kw: Any) -> dict[str, Any]:
    response = await post_sr(env.client, shop, draft["id"], **kw)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_qt_m07_06_expired_goods_returned_fifo(env: Env) -> None:
    """QT-M07-06: stock goes down, our payable goes down by the returned (net) value; VAT share derived."""
    shop, supplier, wh = await _setup(env, "QT-M07-06")
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    assert await _payable(env, shop, supplier) == D("11200.00")

    draft = await create_return(env.client, shop, receipt, [(0, "4.000")], reason="expired")
    line = draft["lines"][0]
    assert (draft["status"], draft["reason"], draft["supplier_id"], draft["receipt_id"]) == (
        "draft", "expired", supplier, receipt["id"],
    )  # fmt: skip
    assert (line["cost"], line["vat_amount"], line["net_amount"], line["invoice_amount"]) == (
        "1000.0000", "480.00", "4000.00", "4000.00",
    )  # fmt: skip
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("10.000"), D("10000.00"))

    key = "sr-post-1"
    body = await _posted(env, shop, draft, key=key)
    assert body["status"] == "posted" and body["number"] == f"MV-01-{business_today().year}-000001"
    assert (body["invoice_total"], body["vat_total"], body["vat_adjustment_status"]) == (
        "4000.00", "480.00", "awaiting_einvoice",
    )  # fmt: skip
    replay = await post_sr(env.client, shop, draft["id"], key=key)
    assert (
        replay.status_code == 200
        and replay.json() == body
        and replay.headers["Idempotent-Replayed"] == "true"
    )

    entries = await ledger(env, shop, UUID(draft["id"]))
    assert _rows(entries) == [("6010", "2910", D("4000.00"))]  # FIFO: invoice = book; no 4410 row yet
    assert entries[0]["analytics"] == {
        "stock_cost": True, "product_id": yogurt, "warehouse_id": str(wh), "line_id": line["id"],
        "lot_ids": [line["lot_id"]], "counterparty_id": supplier,
    }  # fmt: skip
    assert entries[0]["entry_date"] == business_today() and entries[0]["doc_type"] == "supplier_returns"
    vat = await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.vat_moves WHERE doc_id = :d", d=UUID(draft["id"])
    )
    assert vat == 0
    assert await _debt(env, shop, draft["id"]) == [D("-4000.00")]
    assert await _payable(env, shop, supplier) == D("7200.00")
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("6.000"), D("6000.00"))
    moved = await rows(
        env, shop.tenant_id, "SELECT lot_id, qty, cost_amount FROM app.stock_moves WHERE doc_id = :d",
        d=UUID(draft["id"]),
    )  # fmt: skip
    assert [(str(m["lot_id"]), m["qty"], m["cost_amount"]) for m in moved] == [
        (line["lot_id"], D("-4.000"), D("-4000.00")),
    ]  # fmt: skip
    got = (await env.client.get(f"{GR}/{receipt['id']}", headers=shop.h())).json()["lines"][0]
    assert (got["returned_qty"], got["lot_qty_left"]) == ("4.000", "6.000")

    # the return completing the line takes the VAT remainder (480.00 + 720.00 = 1200.00)
    rest = await _posted(env, shop, await create_return(env.client, shop, receipt, [(0, "6.000")]))
    assert (rest["lines"][0]["vat_amount"], rest["invoice_total"]) == ("720.00", "6000.00")
    assert await _payable(env, shop, supplier) == D("1200.00")  # the VAT part waits for the additional EHF
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("0.000"), D("0.00"))


async def test_2_20_aveco_invoice_below_book_3b_and_above_book_3a(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "2.20 AVECO", "aveco")
    yogurt = await _product(env, shop)
    cheap = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000", "0.00")]
    )
    dear = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "2000.0000", "0.00")]
    )
    state = await avg(env, shop, wh, UUID(yogurt))
    assert state is not None and (state["qty"], state["avg_cost"], state["total_value"]) == (
        D("20.000"), D("1500.0000"), D("30000.00"),
    )  # fmt: skip
    assert await _payable(env, shop, supplier) == D("30000.00")

    # 3b: 5 units of the 1000.00 lot — invoice 5000.00 < book 5 × 1500.00 = 7500.00
    low = await _posted(env, shop, await create_return(env.client, shop, cheap, [(0, "5.000")]))
    entries = await ledger(env, shop, UUID(low["id"]))
    assert _rows(entries) == [("6010", "2910", D("5000.00")), ("9430", "2910", D("2500.00"))]
    assert all(e["analytics"]["stock_cost"] is True for e in entries)  # Σ Kt inv_acct = book = 7500.00
    assert await _debt(env, shop, low["id"]) == [D("-5000.00")]
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("15.000"), D("22500.00"))

    # 3a: 5 units of the 2000.00 lot — invoice 10000.00 > book 5 × 1500.00 = 7500.00
    high = await _posted(env, shop, await create_return(env.client, shop, dear, [(0, "5.000")]))
    entries = await ledger(env, shop, UUID(high["id"]))
    assert _rows(entries) == [("6010", "2910", D("7500.00")), ("6010", "9390", D("2500.00"))]
    assert entries[1]["analytics"] == {"counterparty_id": supplier}
    assert await _debt(env, shop, high["id"]) == [D("-10000.00")]
    assert await _payable(env, shop, supplier) == D("15000.00")
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("10.000"), D("15000.00"))
    # check: Dt 6010 = invoice, Kt 2910 = book for both documents
    all_rows = _rows(await ledger(env, shop, UUID(low["id"]))) + _rows(entries)
    assert sum(a for dt, _, a in all_rows if dt == "6010") == D("15000.00")
    assert sum(a for _, kt, a in all_rows if kt == "2910") == D("15000.00")


async def test_2_20_turnover_regime_returns_vat_inclusive_value(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "2.20 turnover")
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) VALUES (:t, :v, 'turnover', :u)",
        t=shop.tenant_id, v=date(2026, 1, 1), u=shop.user_ids["owner"],
    )  # fmt: skip
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    body = await _posted(env, shop, await create_return(env.client, shop, receipt, [(0, "4.000")]))
    assert (body["lines"][0]["invoice_amount"], body["invoice_total"], body["vat_adjustment_status"]) == (
        "4480.00", "4480.00", "not_required",
    )  # fmt: skip
    assert _rows(await ledger(env, shop, UUID(body["id"]))) == [("6010", "2910", D("4480.00"))]
    assert await _payable(env, shop, supplier) == D("6720.00")
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("6.000"), D("6720.00"))


async def test_insufficient_stock_at_create_and_after_consumption(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "SR stock")
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    lot_id = receipt["lines"][0]["lot_id"]
    too_much = await create_return(env.client, shop, receipt, [(0, "11.000")], expect=422)
    assert too_much["error"]["code"] == "INSUFFICIENT_STOCK"
    assert too_much["error"]["params"] == {"lot_id": lot_id, "available": "10.000"}
    draft = await create_return(env.client, shop, receipt, [(0, "10.000")])
    await issue(env, shop, wh, UUID(yogurt), "5.000")  # a sale/write-off took 5 from the lot
    refused = await post_sr(env.client, shop, draft["id"])
    assert refused.status_code == 422 and err(refused) == "INSUFFICIENT_STOCK"
    assert refused.json()["error"]["params"] == {"lot_id": lot_id, "available": "5.000"}
    assert await ledger(env, shop, UUID(draft["id"])) == [] and await _debt(env, shop, draft["id"]) == []


async def test_concurrent_returns_of_one_lot_never_over_issue(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "SR race")
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    one = await create_return(env.client, shop, receipt, [(0, "7.000")])
    two = await create_return(env.client, shop, receipt, [(0, "7.000")])
    results = await asyncio.gather(post_sr(env.client, shop, one["id"]), post_sr(env.client, shop, two["id"]))
    assert sorted(r.status_code for r in results) == [200, 422], [r.text for r in results]
    (lot,) = await lots(env, shop, UUID(yogurt))
    assert lot["qty_left"] == D("3.000")
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("3.000"), D("3000.00"))
    assert await _payable(env, shop, supplier) == D("4200.00")  # 11200.00 − 7000.00


async def test_cancel_return_storno_and_receipt_interplay(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "SR cancel")
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    body = await _posted(env, shop, await create_return(env.client, shop, receipt, [(0, "4.000")]))
    blocked = await env.client.post(f"{GR}/{receipt['id']}/cancel", json={"reason": "x"}, headers=shop.h())
    assert blocked.status_code == 409 and err(blocked) == "LOT_ALREADY_CONSUMED"

    key = "sr-cancel-1"
    cancelled = await env.client.post(
        f"{SR}/{body['id']}/cancel", json={"reason": "adashildi"}, headers=shop.h(key=key)
    )
    assert cancelled.status_code == 200, cancelled.text
    assert (cancelled.json()["status"], cancelled.json()["cancel_reason"]) == ("cancelled", "adashildi")
    replay = await env.client.post(
        f"{SR}/{body['id']}/cancel", json={"reason": "adashildi"}, headers=shop.h(key=key)
    )
    assert replay.status_code == 200 and replay.json() == cancelled.json()
    entries = await ledger(env, shop, UUID(body["id"]))
    assert _rows(entries) == [("6010", "2910", D("4000.00")), ("2910", "6010", D("4000.00"))]
    assert (
        entries[1]["reversal_of_id"] == entries[0]["id"]
        and entries[1]["analytics"] == entries[0]["analytics"]
    )
    assert await _debt(env, shop, body["id"]) == [D("-4000.00"), D("4000.00")]
    assert await _payable(env, shop, supplier) == D("11200.00")
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("10.000"), D("10000.00"))
    (lot,) = await lots(env, shop, UUID(yogurt))
    assert lot["qty_left"] == D("10.000")
    again = await env.client.post(f"{SR}/{body['id']}/cancel", json={"reason": "x"}, headers=shop.h())
    assert again.status_code == 409 and err(again) == "DOC_INVALID_STATE"
    # the lot is whole again → the receipt can now be cancelled; a draft return of it can no longer post
    late = await create_return(env.client, shop, receipt, [(0, "1.000")])
    ok = await env.client.post(f"{GR}/{receipt['id']}/cancel", json={"reason": "x"}, headers=shop.h())
    assert ok.status_code == 200, ok.text
    refused = await post_sr(env.client, shop, late["id"])
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"
    assert refused.json()["error"]["params"]["reason"] == "receipt_not_posted"


async def test_twelve_month_rule_requires_reverse_sale(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "SR 12 months")
    yogurt = await _product(env, shop)
    old_day = date(business_today().year - 1, business_today().month, 1)
    receipt = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")], doc_date=old_day
    )
    draft = await create_return(env.client, shop, receipt, [(0, "1.000")])
    refused = await post_sr(env.client, shop, draft["id"])
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"
    assert refused.json()["error"]["params"]["reason"] == "reverse_sale_required"
    within = await create_return(
        env.client, shop, receipt, [(0, "1.000")], doc_date=date(old_day.year + 1, old_day.month, 1)
    )
    assert (
        await post_sr(env.client, shop, within["id"])
    ).status_code == 200  # exactly 12 months — still a return


async def test_validation_and_state_errors(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "SR validation")
    yogurt, milk = await _product(env, shop), await _product(env, shop, "Sut")
    draft_receipt = await create_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "1.000", "1.0000")])
    response = await env.client.post(
        SR, json={"receipt_id": draft_receipt["id"], "doc_date": str(business_today()), "reason": "damaged",
                  "lines": [{"receipt_line_id": draft_receipt["lines"][0]["id"], "lot_id": draft_receipt["id"], "qty": "1.000"}]},
        headers=shop.h(),
    )  # fmt: skip
    assert (
        response.status_code == 409 and response.json()["error"]["params"]["reason"] == "receipt_not_posted"
    )
    receipt = await posted_receipt(
        env.client,
        shop,
        supplier,
        wh,
        [gr_line(yogurt, "5.000", "100.0000"), gr_line(milk, "5.000", "100.0000")],
    )
    crossed = await env.client.post(
        SR, json={"receipt_id": receipt["id"], "doc_date": str(business_today()), "reason": "other",
                  "lines": [{"receipt_line_id": receipt["lines"][0]["id"], "lot_id": receipt["lines"][1]["lot_id"], "qty": "1.000"}]},
        headers=shop.h(),
    )  # fmt: skip
    assert crossed.status_code == 422 and crossed.json()["error"]["details"][0]["field"] == "lines[0].lot_id"
    gift = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(yogurt, "1.000", "100.0000")], kind="gratuitous"
    )
    refused = await create_return(env.client, shop, gift, [(0, "1.000")], expect=409)
    assert refused["error"]["params"]["reason"] == "gratuitous_receipt"
    mine = await create_return(env.client, shop, receipt, [(1, "1.000")])
    other = await env.shop("SR validation other")
    hidden = await env.client.get(f"{SR}/{mine['id']}", headers=other.h())
    assert hidden.status_code == 404 and err(hidden) == "NOT_FOUND"
    assert (await env.client.get(f"{SR}/{mine['id']}", headers=shop.h())).status_code == 200


async def test_permissions_period_and_list(env: Env) -> None:
    shop, supplier, wh = await _setup(
        env, "SR perms", "fifo", SystemRole.OWNER, SystemRole.STOREKEEPER, SystemRole.CASHIER
    )
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    cashier = await env.client.post(
        SR, json={"receipt_id": receipt["id"], "doc_date": str(business_today()), "reason": "expired",
                  "lines": [{"receipt_line_id": receipt["lines"][0]["id"], "lot_id": receipt["lines"][0]["lot_id"], "qty": "1.000"}]},
        headers=shop.h("cashier"),
    )  # fmt: skip
    assert cashier.status_code == 403
    draft = await create_return(
        env.client, shop, receipt, [(0, "1.000")], role="storekeeper"
    )  # purchases.return
    denied = await post_sr(env.client, shop, draft["id"], role="storekeeper")
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"

    last_month = (business_today().replace(day=1) - timedelta(days=1)).replace(day=1)
    old = await create_return(env.client, shop, receipt, [(0, "1.000")], doc_date=last_month.replace(day=28))
    await close_period(env, shop, last_month)
    closed = await post_sr(env.client, shop, old["id"])
    assert closed.status_code == 409 and err(closed) == "PERIOD_CLOSED"

    listed = await env.client.get(
        SR, params={"receipt_id": receipt["id"], "status": "draft"}, headers=shop.h()
    )
    assert listed.status_code == 200 and [x["id"] for x in listed.json()["items"]] == [old["id"], draft["id"]]
    assert listed.json()["items"][0]["receipt_number"] == receipt["number"]
    assert (await env.client.get(SR, params={"status": "posted"}, headers=shop.h())).json()["items"] == []


async def test_acc_13_doc_date_in_future_refused(env: Env) -> None:
    """13 §5.2 / 19 §1: create and post with ``doc_date`` > business today → 422, nothing issued."""
    shop, supplier, wh = await _setup(env, "ACC-13 SR")
    yogurt = await _product(env, shop)
    receipt = await posted_receipt(env.client, shop, supplier, wh, [gr_line(yogurt, "10.000", "1000.0000")])
    tomorrow = business_today() + timedelta(days=1)
    future = await create_return(env.client, shop, receipt, [(0, "1.000")], doc_date=tomorrow, expect=422)
    detail = future["error"]["details"][0]
    assert (future["error"]["code"], detail["field"], detail["message_key"]) == (
        "VALIDATION_ERROR", "doc_date", "validation.doc_date_in_future",
    )  # fmt: skip
    draft = await create_return(env.client, shop, receipt, [(0, "1.000")])
    await execute(
        env, shop.tenant_id, "UPDATE app.supplier_returns SET doc_date = :d WHERE id = :id",
        d=tomorrow, id=UUID(draft["id"]),
    )  # fmt: skip
    posted = await post_sr(env.client, shop, draft["id"])
    assert posted.status_code == 422, posted.text
    assert posted.json()["error"]["details"][0]["message_key"] == "validation.doc_date_in_future"
    assert await ledger(env, shop, UUID(draft["id"])) == []
    assert await balance(env, shop, wh, UUID(yogurt)) == (D("10.000"), D("10000.00"))
