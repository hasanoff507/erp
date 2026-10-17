"""Stock counts (19 §14, 13 §2.11, X-02, QT-M05-01…07): snapshot at ``started_at``, ``expected`` per line
up to its ``counted_at``, shortage ``Dt 4730|5910 / Kt inv_acct`` at the balance cost, surplus
``Dt inv_acct / Kt 9390`` at ``last_purchase_cost`` as a ``stock_counts`` lot; storno on cancel."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from tests.support.catalog import Env, Shop
from tests.support.inventory import (
    D,
    avg,
    balance,
    err,
    execute,
    issue,
    lots,
    new_product,
    rows,
    set_method,
    set_setting,
    use_account,
)
from tests.support.inventory_docs import (
    COUNTS,
    WRITE_OFFS,
    doc_ledger,
    docs_env_fixture,
    entries,
    ok,
    stock_in,
    today,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["docs_env_fixture"]


async def _start(
    env: Env, shop: Shop, wh: UUID, product_ids: list[UUID] | None = None, *, responsible: UUID | None = None,
    role: str = "owner",
) -> dict[str, Any]:  # fmt: skip
    body: dict[str, Any] = {"warehouse_id": str(wh), "doc_date": str(today())}
    if product_ids is not None:
        body["product_ids"] = [str(p) for p in product_ids]
    if responsible is not None:
        body["responsible_user_id"] = str(responsible)
    return await ok(await env.client.post(COUNTS, json=body, headers=shop.h(role)), 201)


async def _count(env: Env, shop: Shop, doc_id: str, lines: list[dict[str, Any]], role: str = "owner") -> Any:
    return await env.client.post(f"{COUNTS}/{doc_id}/lines", json={"lines": lines}, headers=shop.h(role))


async def _do(env: Env, shop: Shop, doc_id: str, action: str, role: str = "owner", **kw: Any) -> Any:
    return await env.client.post(f"{COUNTS}/{doc_id}/{action}", headers=shop.h(role), **kw)


def _by_product(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {ln["product_id"]: ln for ln in doc["lines"]}


async def _barcode(env: Env, shop: Shop, product: UUID, code: str) -> None:
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.product_barcodes (tenant_id, product_id, barcode, kind) VALUES (:t, :p, :b, 'ean')",
        t=shop.tenant_id, p=product, b=code,
    )  # fmt: skip


async def test_qt_m05_01_count_shows_the_difference_before_posting(env: Env) -> None:
    shop = await env.shop("QT-M05-01")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    cola = await new_product(env, shop, "Coca-Cola 1.5L")
    sugar = await new_product(env, shop, "Shakar")
    empty = await new_product(env, shop, "Bo'sh")
    await stock_in(env, shop, wh, cola, "10.000", "50000.00")
    await stock_in(env, shop, wh, sugar, "5.000", "10000.00")
    await _barcode(env, shop, sugar, "4780000000017")
    doc = await _start(env, shop, wh)
    assert doc["status"] == "counting" and doc["started_at"] is not None
    lines = _by_product(doc)
    assert set(lines) == {str(cola), str(sugar)}  # the whole warehouse = non-zero balances
    assert (lines[str(cola)]["snapshot_qty"], lines[str(cola)]["counted"], lines[str(cola)]["counted_at"]) == (
        "10.000", None, None,
    )  # fmt: skip
    counted = await ok(
        await _count(
            env, shop, doc["id"],
            [{"product_id": str(cola), "counted": "7.000"}, {"barcode": "4780000000017", "counted": "5.000"}],
        )
    )  # fmt: skip
    lines = _by_product(counted)
    assert (lines[str(cola)]["expected"], lines[str(cola)]["counted"], lines[str(cola)]["diff"]) == (
        "10.000", "7.000", "-3.000",
    )  # fmt: skip
    assert lines[str(cola)]["amount"] == "-15000.00" and lines[str(cola)]["counted_at"] is not None
    assert lines[str(sugar)]["diff"] == "0.000"
    got = await ok(await env.client.get(f"{COUNTS}/{doc['id']}", headers=shop.h(key=None)))
    assert _by_product(got)[str(cola)]["diff"] == "-3.000" and got["uncounted_count"] == 0
    assert await doc_ledger(env, shop, doc["id"]) == []
    assert await balance(env, shop, wh, cola) == (D("10.000"), D("50000.00"))  # not posted yet

    unknown = await _count(env, shop, doc["id"], [{"barcode": "0000000000000", "counted": "1.000"}])
    assert unknown.status_code == 422 and err(unknown) == "BARCODE_NOT_IN_CATALOG"
    found = await ok(await _count(env, shop, doc["id"], [{"product_id": str(empty), "counted": "2.000"}]))
    new_line = _by_product(found)[str(empty)]
    assert (new_line["snapshot_qty"], new_line["expected"], new_line["line_no"]) == ("0.000", "0.000", 3)


async def test_qt_m05_02_03_shortage_with_responsible_posts_dt_4730(env: Env) -> None:
    shop = await env.shop("QT-M05-03 4730")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    cola = await new_product(env, shop, "Coca-Cola 1.5L")
    await stock_in(env, shop, wh, cola, "10.000", "50000.00")
    keeper = shop.user_ids["owner"]
    doc = await _start(env, shop, wh, [cola], responsible=keeper)
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(cola), "counted": "7.000"}]))
    early = await _do(env, shop, doc["id"], "post")
    assert early.status_code == 409 and err(early) == "DOC_INVALID_STATE"  # QT-M05-04
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    posted = await ok(await _do(env, shop, doc["id"], "post"))
    assert posted["status"] == "posted" and posted["number"].startswith("I-01-")
    assert posted["shortage_lines"] == [
        {"line_id": doc["lines"][0]["id"], "product_id": str(cola), "expected": "10.000", "counted": "7.000",
         "diff": "-3.000", "amount": "15000.00"}
    ]  # fmt: skip
    assert posted["surplus_lines"] == []
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led) == [("4730", "2910", D("15000.00"))]
    assert led[0]["analytics"]["employee_id"] == str(keeper) and led[0]["entry_date"] == today()
    assert await balance(env, shop, wh, cola) == (D("7.000"), D("35000.00"))  # QT-M05-02
    stored = await rows(env, shop.tenant_id, "SELECT expected, counted, diff FROM app.count_lines")
    assert [(r["expected"], r["counted"], r["diff"]) for r in stored] == [
        (D("10.000"), D("7.000"), D("-3.000"))
    ]
    actions = await rows(
        env, shop.tenant_id, "SELECT action FROM app.audit_log WHERE entity = 'stock_counts'"
    )
    assert "stock_count.posted" in {a["action"] for a in actions}


async def test_qt_m05_04_post_before_submit_for_review_is_refused(env: Env) -> None:
    shop = await env.shop("QT-M05-04")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "2.000", "2000.00")
    doc = await _start(env, shop, wh, [p])
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(p), "counted": "1.000"}]))
    refused = await _do(env, shop, doc["id"], "post")
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"
    assert refused.json()["error"]["params"] == {"expected_status": "review", "actual_status": "counting"}
    assert await doc_ledger(env, shop, doc["id"]) == [] and await balance(env, shop, wh, p) == (
        D("2.000"),
        D("2000.00"),
    )
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    twice = await _do(env, shop, doc["id"], "submit-for-review")
    assert twice.status_code == 409 and err(twice) == "DOC_INVALID_STATE"


async def test_qt_m05_03_shortage_without_responsible_posts_dt_5910_and_aveco_cost(env: Env) -> None:
    shop = await env.shop("QT-M05-03 5910")
    await set_method(env, shop, "aveco")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "100.000", "800000.00")
    await stock_in(env, shop, wh, p, "50.000", "450000.00")  # avg 8333.3333
    doc = await _start(env, shop, wh, [p])
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(p), "counted": "147.000"}]))
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    posted = await ok(await _do(env, shop, doc["id"], "post"))
    assert posted["shortage_lines"][0]["amount"] == "25000.00"  # ROUND(3 × 8333.3333)
    assert entries(await doc_ledger(env, shop, doc["id"])) == [("5910", "2910", D("25000.00"))]
    state = await avg(env, shop, wh, p)
    assert state is not None and state["total_value"] == D("1225000.00") and state["qty"] == D("147.000")


async def test_qt_m05_06_surplus_posts_dt_2910_kt_9390_at_last_purchase_cost(env: Env) -> None:
    shop = await env.shop("QT-M05-06")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    cola = await new_product(env, shop, "Coca-Cola 1.5L")
    await stock_in(env, shop, wh, cola, "5.000", "35000.00")  # 7000
    await stock_in(env, shop, wh, cola, "5.000", "40000.00")  # latest goods-receipt lot: 8000.0000
    doc = await _start(env, shop, wh, [cola])
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(cola), "counted": "12.000"}]))
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    posted = await ok(await _do(env, shop, doc["id"], "post"))
    assert (
        posted["surplus_lines"][0]["amount"] == "16000.00" and posted["surplus_lines"][0]["diff"] == "2.000"
    )
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led) == [("2910", "9390", D("16000.00"))]
    assert led[0]["analytics"]["product_id"] == str(cola)
    surplus = [x for x in await lots(env, shop, cola) if x["source_doc_type"] == "stock_counts"]
    assert [(x["qty_in"], x["unit_cost"]) for x in surplus] == [(D("2.000"), D("8000.0000"))]
    assert await balance(env, shop, wh, cola) == (D("12.000"), D("91000.00"))


async def test_qt_m05_07_expected_follows_each_line_counted_at(env: Env) -> None:
    """X-02: T0 start (snapshot 10); line A counted at T2 > T1 sale → expected 8; line B counted between
    T0 and the sale → expected 10 (the later sale is not a difference); line C counted 9 before → −1."""
    shop = await env.shop("QT-M05-07")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    a = await new_product(env, shop, "A mahsulot")
    b = await new_product(env, shop, "B mahsulot")
    c = await new_product(env, shop, "C mahsulot")
    for p in (a, b, c):
        await stock_in(env, shop, wh, p, "10.000", "10000.00")
    doc = await _start(env, shop, wh, [a, b, c])  # T0
    await ok(
        await _count(env, shop, doc["id"], [{"product_id": str(b), "counted": "10.000"}])
    )  # T0 < T2 < T1
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(c), "counted": "9.000"}]))
    for p in (a, b, c):
        await issue(env, shop, wh, p, "2.000")  # T1: sold 2 each
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(a), "counted": "8.000"}]))  # T2 > T1
    preview = _by_product(await ok(await env.client.get(f"{COUNTS}/{doc['id']}", headers=shop.h(key=None))))
    assert [(preview[str(p)]["expected"], preview[str(p)]["diff"]) for p in (a, b, c)] == [
        ("8.000", "0.000"), ("10.000", "0.000"), ("10.000", "-1.000"),
    ]  # fmt: skip
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    posted = await ok(await _do(env, shop, doc["id"], "post"))
    assert [(x["product_id"], x["expected"], x["diff"]) for x in posted["shortage_lines"]] == [
        (str(c), "10.000", "-1.000")
    ]
    assert entries(await doc_ledger(env, shop, doc["id"])) == [("5910", "2910", D("1000.00"))]
    assert await balance(env, shop, wh, a) == (D("8.000"), D("8000.00"))
    assert await balance(env, shop, wh, b) == (D("8.000"), D("8000.00"))  # the sale stays a sale
    assert await balance(env, shop, wh, c) == (D("7.000"), D("7000.00"))
    stored = await rows(
        env, shop.tenant_id, "SELECT product_id, expected FROM app.count_lines ORDER BY line_no"
    )
    assert [r["expected"] for r in stored] == [D("8.000"), D("10.000"), D("10.000")]


async def test_uncounted_lines_block_the_post_unless_forced(env: Env) -> None:
    shop = await env.shop("Count incomplete")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    p, q = await new_product(env, shop, "P"), await new_product(env, shop, "Q")
    await stock_in(env, shop, wh, p, "4.000", "4000.00")
    await stock_in(env, shop, wh, q, "2.000", "3000.00")
    doc = await _start(env, shop, wh)
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(p), "counted": "4.000"}]))
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    refused = await _do(env, shop, doc["id"], "post")
    assert refused.status_code == 422 and err(refused) == "COUNT_LINES_INCOMPLETE"
    assert refused.json()["error"]["params"]["uncounted_count"] == 1
    counting_only = await _count(env, shop, doc["id"], [{"product_id": str(q), "counted": "1.000"}])
    assert counting_only.status_code == 409 and err(counting_only) == "DOC_INVALID_STATE"
    forced = await env.client.post(
        f"{COUNTS}/{doc['id']}/post", params={"treat_uncounted_as_zero": "true"}, headers=shop.h()
    )
    body = await ok(forced)
    assert [(x["product_id"], x["counted"], x["diff"], x["amount"]) for x in body["shortage_lines"]] == [
        (str(q), "0.000", "-2.000", "3000.00")
    ]
    assert await balance(env, shop, wh, q) == (D("0.000"), D("0.00"))


async def test_cancel_posted_count_reverses_shortage_and_surplus(env: Env) -> None:
    shop = await env.shop("Count cancel")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    short, extra = await new_product(env, shop, "Kam"), await new_product(env, shop, "Ortiq")
    await stock_in(env, shop, wh, short, "10.000", "20000.00")
    await stock_in(env, shop, wh, extra, "10.000", "30000.00")
    doc = await _start(env, shop, wh)
    await ok(
        await _count(
            env, shop, doc["id"],
            [{"product_id": str(short), "counted": "6.000"}, {"product_id": str(extra), "counted": "11.000"}],
        )
    )  # fmt: skip
    line_id = _by_product(doc)[str(extra)]["id"]
    patched = await env.client.patch(
        f"{COUNTS}/{doc['id']}/lines/{line_id}", json={"counted": "13.000"}, headers=shop.h()
    )
    assert _by_product(await ok(patched))[str(extra)]["counted"] == "13.000"
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    await ok(await _do(env, shop, doc["id"], "post"))
    assert entries(await doc_ledger(env, shop, doc["id"])) == [
        ("5910", "2910", D("8000.00")),
        ("2910", "9390", D("9000.00")),
    ]
    cancelled = await ok(await _do(env, shop, doc["id"], "cancel", json={"reason": "qayta sanaymiz"}))
    assert cancelled["status"] == "cancelled"
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led)[2:] == [("2910", "5910", D("8000.00")), ("9390", "2910", D("9000.00"))]
    assert all(e["reversal_of_id"] is not None for e in led[2:])
    assert await balance(env, shop, wh, short) == (D("10.000"), D("20000.00"))
    assert await balance(env, shop, wh, extra) == (D("10.000"), D("30000.00"))
    again = await _do(env, shop, doc["id"], "cancel", json={"reason": "x"})
    assert again.status_code == 409 and err(again) == "DOC_ALREADY_CANCELLED"

    draft = await _start(env, shop, wh)
    assert (await ok(await _do(env, shop, draft["id"], "cancel", json={"reason": "x"})))[
        "status"
    ] == "cancelled"


async def test_permissions_scope_and_rls(env: Env) -> None:
    shop = await env.shop("Count perms", SystemRole.OWNER, SystemRole.STOREKEEPER, SystemRole.CASHIER)
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "3.000", "3000.00")
    cashier = await env.client.post(
        COUNTS, json={"warehouse_id": str(wh), "doc_date": str(today())}, headers=shop.h("cashier")
    )
    assert cashier.status_code == 403 and err(cashier) == "PERMISSION_DENIED"
    doc = await _start(env, shop, wh, role="storekeeper")
    await ok(
        await _count(env, shop, doc["id"], [{"product_id": str(p), "counted": "3.000"}], role="storekeeper")
    )
    await ok(await _do(env, shop, doc["id"], "submit-for-review", role="storekeeper"))
    no_post = await _do(env, shop, doc["id"], "post", role="storekeeper")
    assert no_post.status_code == 403 and err(no_post) == "PERMISSION_DENIED"
    bad_member = await env.client.post(
        COUNTS,
        json={"warehouse_id": str(wh), "doc_date": str(today()), "responsible_user_id": str(doc["id"])},
        headers=shop.h(),
    )
    assert bad_member.status_code == 422
    listed = await ok(await env.client.get(COUNTS, params={"status": "review"}, headers=shop.h(key=None)))
    assert [x["id"] for x in listed["items"]] == [doc["id"]] and "lines" not in listed["items"][0]
    other = await env.shop("Count other tenant")
    assert (await env.client.get(f"{COUNTS}/{doc['id']}", headers=other.h(key=None))).status_code == 404


async def test_count_post_and_write_off_on_one_product_never_over_issue(env: Env) -> None:
    shop = await env.shop("Count vs write-off")
    await set_method(env, shop, "fifo")
    await set_setting(env, shop, "negative_stock_policy", "block")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "10.000", "10000.00")
    doc = await _start(env, shop, wh, [p])
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(p), "counted": "4.000"}]))
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    wo = await ok(
        await env.client.post(
            WRITE_OFFS,
            json={"warehouse_id": str(wh), "doc_date": str(today()),
                  "lines": [{"product_id": str(p), "qty": "7.000", "reason": "damaged"}]},
            headers=shop.h(),
        ),
        201,
    )  # fmt: skip
    results = await asyncio.gather(
        _do(env, shop, doc["id"], "post"),
        env.client.post(f"{WRITE_OFFS}/{wo['id']}/post", headers=shop.h()),
    )
    assert sorted(r.status_code for r in results) == [200, 422]
    assert [err(r) for r in results if r.status_code == 422] == ["NEGATIVE_STOCK_NOT_ALLOWED"]
    qty_left, _ = await balance(env, shop, wh, p)
    assert qty_left in (D("4.000"), D("3.000")) and qty_left >= 0


async def test_doc_date_after_the_business_day_is_refused_on_create_and_post(env: Env) -> None:
    """ACC-13 (13 §5.2, 19 §0): ``doc_date`` > business today → 422 ``validation.doc_date_in_future``."""
    shop = await env.shop("Count future date")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "2.000", "2000.00")
    tomorrow = today() + timedelta(days=1)
    created = await env.client.post(
        COUNTS, json={"warehouse_id": str(wh), "doc_date": str(tomorrow)}, headers=shop.h()
    )
    assert created.status_code == 422, created.text
    detail = created.json()["error"]["details"][0]
    assert (detail["field"], detail["message_key"]) == ("doc_date", "validation.doc_date_in_future")

    doc = await _start(env, shop, wh, [p])
    await ok(await _count(env, shop, doc["id"], [{"product_id": str(p), "counted": "1.000"}]))
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    await execute(
        env,
        shop.tenant_id,
        "UPDATE app.stock_counts SET doc_date = :d WHERE id = :id",
        d=tomorrow,
        id=UUID(doc["id"]),
    )
    posted = await _do(env, shop, doc["id"], "post")
    assert posted.status_code == 422 and err(posted) == "VALIDATION_ERROR", posted.text
    detail = posted.json()["error"]["details"][0]
    assert (detail["field"], detail["message_key"]) == ("doc_date", "validation.doc_date_in_future")
    assert await doc_ledger(env, shop, doc["id"]) == [] and await balance(env, shop, wh, p) == (
        D("2.000"),
        D("2000.00"),
    )


async def test_surplus_cost_ignores_the_lot_of_a_cancelled_receipt(env: Env) -> None:
    """ACC-06 (13 §2.11): ``last_purchase_cost`` is the latest *not cancelled* goods-receipt lot — a
    receipt 5 × 12000 posted then cancelled does not price the surplus; 2 × 8000 = 16000.00."""
    from app.core.db.base import uuid7
    from tests.support.inventory import receive, stock_txn

    shop = await env.shop("ACC-06")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    cola = await new_product(env, shop, "Coca-Cola 1.5L")
    await stock_in(env, shop, wh, cola, "10.000", "80000.00")  # 8000.0000
    dear = uuid7()
    await receive(env, shop, wh, cola, "5.000", "60000.00", doc_id=dear)  # 12000.0000
    async with stock_txn(env, shop.tenant_id, [(wh, cola)]) as (_, txn):
        await txn.reverse_receipt("goods_receipts", dear)
    assert await balance(env, shop, wh, cola) == (D("10.000"), D("80000.00"))
    doc = await _start(env, shop, wh, [cola])
    preview = await ok(await _count(env, shop, doc["id"], [{"product_id": str(cola), "counted": "12.000"}]))
    assert _by_product(preview)[str(cola)]["amount"] == "16000.00"
    await ok(await _do(env, shop, doc["id"], "submit-for-review"))
    posted = await ok(await _do(env, shop, doc["id"], "post"))
    assert posted["surplus_lines"][0]["amount"] == "16000.00"
    assert entries(await doc_ledger(env, shop, doc["id"])) == [("2910", "9390", D("16000.00"))]
    surplus = [x for x in await lots(env, shop, cola) if x["source_doc_type"] == "stock_counts"]
    assert [(x["qty_in"], x["unit_cost"]) for x in surplus] == [(D("2.000"), D("8000.0000"))]
    assert await balance(env, shop, wh, cola) == (D("12.000"), D("96000.00"))
