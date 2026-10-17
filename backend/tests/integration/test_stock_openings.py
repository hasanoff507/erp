"""Opening stock — ``stock-openings`` documents and the ``opening_stock`` import (19 §6, §16; 13 §2.21;
US-M04-04; QT-M04-04): lots + balances, ``Dt 2910 / Kt 0000`` = the entered cost, ``entry_date =
go_live_date − 1``, no VAT; storno on cancel."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today, day_end
from tests.support.catalog import Env, Shop, catalog_env_fixture, create_product
from tests.support.inventory import (
    API,
    D,
    balance,
    close_period,
    err,
    issue,
    ledger,
    lots,
    new_product,
    receive,
    rows,
    scalar,
    set_go_live,
    set_method,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

URL = f"{API}/stock-openings"


def _go_live() -> date:
    return business_today().replace(day=1)


async def _draft(env: Env, shop: Shop, wh: Any, lines: list[dict[str, Any]], role: str = "owner") -> Any:
    return await env.client.post(
        URL, json={"warehouse_id": str(wh), "doc_date": str(_go_live()), "lines": lines}, headers=shop.h(role)
    )


async def test_qt_m04_04_opening_posts_lots_balances_and_dt_inv_kt_0000(env: Env) -> None:
    shop = await env.shop("QT-M04-04")
    await set_go_live(env, shop, _go_live())
    wh = await use_account(env, shop, "2910")
    cola, sugar = await new_product(env, shop, "Coca-Cola 1.5L"), await new_product(env, shop, "Shakar")
    created = await _draft(
        env, shop, wh,
        [
            {"product_id": str(cola), "qty": "10.000", "unit_cost": "5000.0000", "expiry_date": "2027-03-01"},
            {"product_id": str(sugar), "qty": "3.000", "unit_cost": "1234.5678"},
        ],
    )  # fmt: skip
    assert created.status_code == 201, created.text
    doc = created.json()
    assert (doc["status"], doc["number"], doc["total_amount"], doc["line_count"]) == (
        "draft",
        None,
        "53703.70",
        2,
    )
    assert created.headers["Location"].endswith(doc["id"])
    assert [ln["amount"] for ln in doc["lines"]] == ["50000.00", "3703.70"]  # 3 × 1234.5678 = 3703.7034
    assert await ledger(env, shop) == []

    key = "opening-post-1"
    posted = await env.client.post(f"{URL}/{doc['id']}/post", headers=shop.h(key=key))
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert body["status"] == "posted" and body["number"] == f"OO-01-{_go_live().year}-000001"
    replay = await env.client.post(f"{URL}/{doc['id']}/post", headers=shop.h(key=key))
    assert (
        replay.status_code == 200
        and replay.json() == body
        and replay.headers["Idempotent-Replayed"] == "true"
    )

    entry_date = _go_live() - timedelta(days=1)
    entries = await ledger(env, shop)
    assert [(e["account_dt"], e["account_kt"], e["amount"], e["entry_date"]) for e in entries] == [
        ("2910", "0000", D("50000.00"), entry_date),
        ("2910", "0000", D("3703.70"), entry_date),
    ]
    assert all(e["doc_type"] == "stock_openings" and str(e["doc_id"]) == doc["id"] for e in entries)
    assert entries[0]["analytics"]["product_id"] == str(cola)
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.vat_moves") == 0
    [lot] = await lots(env, shop, cola)
    assert (lot["qty_in"], lot["qty_left"], lot["unit_cost"], lot["source_doc_type"]) == (
        D("10.000"), D("10.000"), D("5000.0000"), "stock_openings",
    )  # fmt: skip
    assert lot["expiry_date"] == date(2027, 3, 1)
    assert lot["received_at"] == day_end(entry_date)  # sorts before every go-live receipt
    assert await balance(env, shop, wh, cola) == (D("10.000"), D("50000.00"))
    assert await balance(env, shop, wh, sugar) == (D("3.000"), D("3703.70"))
    actions = await rows(
        env, shop.tenant_id, "SELECT action FROM app.audit_log WHERE entity = 'stock_openings'"
    )
    assert sorted(a["action"] for a in actions) == ["stock_opening.created", "stock_opening.posted"]

    again = await env.client.post(f"{URL}/{doc['id']}/post", headers=shop.h())
    assert again.status_code == 409 and err(again) == "DOC_NOT_DRAFT"
    got = (await env.client.get(f"{URL}/{doc['id']}", headers=shop.h(key=None))).json()
    assert got == body
    listed = (await env.client.get(URL, params={"status": "posted"}, headers=shop.h(key=None))).json()
    assert [d["id"] for d in listed["items"]] == [doc["id"]] and "lines" not in listed["items"][0]


async def test_opening_lots_come_first_in_fifo(env: Env) -> None:
    shop = await env.shop("Opening FIFO")
    await set_method(env, shop, "fifo")
    await set_go_live(env, shop, _go_live())
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "5.000", "50000.00")  # a go-live receipt posted BEFORE the opening
    doc = (
        await _draft(env, shop, wh, [{"product_id": str(p), "qty": "2.000", "unit_cost": "7000.0000"}])
    ).json()
    assert (await env.client.post(f"{URL}/{doc['id']}/post", headers=shop.h())).status_code == 200
    res, _, _ = await issue(env, shop, wh, p, "3.000")
    assert res.cost == D("24000.00")  # 2 × 7000 (opening) + 1 × 10000


async def test_go_live_date_missing_and_closed_period(env: Env) -> None:
    shop = await env.shop("No go-live")
    await set_go_live(env, shop, None)  # signup sets it; a legacy tenant may lack it
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    doc = (
        await _draft(env, shop, wh, [{"product_id": str(p), "qty": "1.000", "unit_cost": "1.0000"}])
    ).json()
    missing = await env.client.post(f"{URL}/{doc['id']}/post", headers=shop.h())
    assert missing.status_code == 422 and err(missing) == "VALIDATION_ERROR"
    assert missing.json()["error"]["details"] == [
        {"field": "go_live_date", "message_key": "validation.go_live_date_missing"}
    ]
    await set_go_live(env, shop, _go_live())
    await close_period(env, shop, _go_live() - timedelta(days=1))
    closed = await env.client.post(f"{URL}/{doc['id']}/post", headers=shop.h())
    assert closed.status_code == 409 and err(closed) == "PERIOD_CLOSED"
    prev = _go_live() - timedelta(days=1)
    assert closed.json()["error"]["params"] == {"period": f"{prev.year:04d}-{prev.month:02d}"}
    assert await balance(env, shop, wh, p) == (D("0.000"), D("0.00"))


async def test_cancel_posted_opening_storno_and_lot_consumed(env: Env) -> None:
    shop = await env.shop("Opening cancel")
    await set_go_live(env, shop, _go_live())
    wh = await use_account(env, shop)
    a, b = await new_product(env, shop, "A"), await new_product(env, shop, "B")
    doc_a = (
        await _draft(env, shop, wh, [{"product_id": str(a), "qty": "4.000", "unit_cost": "2500.0000"}])
    ).json()
    doc_b = (
        await _draft(env, shop, wh, [{"product_id": str(b), "qty": "4.000", "unit_cost": "100.0000"}])
    ).json()
    for d in (doc_a, doc_b):
        assert (await env.client.post(f"{URL}/{d['id']}/post", headers=shop.h())).status_code == 200
    await issue(env, shop, wh, b, "1.000")
    consumed = await env.client.post(f"{URL}/{doc_b['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    assert consumed.status_code == 409 and err(consumed) == "LOT_ALREADY_CONSUMED"

    cancelled = await env.client.post(
        f"{URL}/{doc_a['id']}/cancel", json={"reason": "noto'g'ri narx"}, headers=shop.h()
    )
    assert cancelled.status_code == 200, cancelled.text
    assert (cancelled.json()["status"], cancelled.json()["cancel_reason"]) == ("cancelled", "noto'g'ri narx")
    original, storno = await ledger(env, shop, doc_a["id"])
    assert (storno["account_dt"], storno["account_kt"], storno["amount"]) == ("0000", "2910", D("10000.00"))
    assert storno["reversal_of_id"] == original["id"] and storno["entry_date"] == business_today()
    assert await balance(env, shop, wh, a) == (D("0.000"), D("0.00"))
    assert (await lots(env, shop, a))[0]["qty_left"] == D("0.000")
    twice = await env.client.post(f"{URL}/{doc_a['id']}/cancel", json={"reason": "x"}, headers=shop.h())
    assert twice.status_code == 409 and err(twice) == "DOC_ALREADY_CANCELLED"
    draft = (
        await _draft(env, shop, wh, [{"product_id": str(a), "qty": "1.000", "unit_cost": "1.0000"}])
    ).json()
    gone = await env.client.post(
        f"{URL}/{draft['id']}/cancel", json={"reason": "kerak emas"}, headers=shop.h()
    )
    assert gone.status_code == 200 and gone.json()["status"] == "cancelled"
    assert await ledger(env, shop, draft["id"]) == []


async def test_opening_validation_permission_and_scope(env: Env) -> None:
    shop = await env.shop("Opening rules", SystemRole.OWNER, SystemRole.CASHIER)
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    denied = await _draft(
        env, shop, wh, [{"product_id": str(p), "qty": "1.000", "unit_cost": "1.0000"}], "cashier"
    )
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    zero = await _draft(env, shop, wh, [{"product_id": str(p), "qty": "0.000", "unit_cost": "1.0000"}])
    assert zero.status_code == 422 and zero.json()["error"]["details"][0]["field"] == "lines[0].qty"
    unknown = await _draft(env, shop, wh, [{"product_id": str(wh), "qty": "1.000", "unit_cost": "1.0000"}])
    assert unknown.status_code == 422
    other = await env.shop("Opening other tenant")
    foreign = await _draft(env, other, wh, [{"product_id": str(p), "qty": "1.000", "unit_cost": "1.0000"}])
    assert foreign.status_code == 422  # another tenant's warehouse is invisible (RLS)
    assert (await env.client.get(f"{URL}", headers=other.h(key=None))).json()["items"] == []


async def _upload(env: Env, shop: Shop, content: bytes) -> Any:
    return await env.client.post(
        f"{API}/import-jobs",
        data={"kind": "opening_stock"},
        files={"file": ("opening.csv", content, "text/csv")},
        headers=shop.h(),
    )


async def test_opening_stock_import_creates_and_posts_one_document(env: Env) -> None:
    shop = await env.shop("Import opening")
    await set_go_live(env, shop, _go_live())
    wh = await use_account(env, shop, "2910")
    p = await create_product(env.client, shop, "Pepsi 1L", barcode="4870000000017")
    content = (
        b"barcode;qty;unit_cost;expiry_date\r\n"
        b"4870000000017;12;6500.5;2027-01-31\r\n"
        b"0000000000000;1;1;\r\n"
        b"4870000000017;0;1;\r\n"
    )
    job = (await _upload(env, shop, content)).json()
    assert job["kind"] == "opening_stock"
    assert (
        await env.client.post(f"{API}/import-jobs/{job['id']}/validate", headers=shop.h())
    ).status_code == 202
    await env.drain()
    state = (await env.client.get(f"{API}/import-jobs/{job['id']}", headers=shop.h(key=None))).json()
    assert (state["status"], state["total_rows"], state["ok_rows"], state["error_rows"]) == (
        "validated",
        3,
        1,
        2,
    )
    errors = (await env.client.get(f"{API}/import-jobs/{job['id']}/errors", headers=shop.h(key=None))).json()
    assert [(e["row"], e["field"], e["code"]) for e in errors["items"]] == [
        (3, "barcode", "BARCODE_NOT_IN_CATALOG"),
        (4, "qty", "VALIDATION_ERROR"),
    ]
    commit = await env.client.post(
        f"{API}/import-jobs/{job['id']}/commit", json={"skip_error_rows": True}, headers=shop.h()
    )
    assert commit.status_code == 202
    await env.drain()
    state = (await env.client.get(f"{API}/import-jobs/{job['id']}", headers=shop.h(key=None))).json()
    assert state["status"] == "committed", state
    [doc_id] = state["result"]["created_doc_ids"]
    doc = (await env.client.get(f"{URL}/{doc_id}", headers=shop.h(key=None))).json()
    assert (doc["status"], doc["warehouse_id"], doc["total_amount"]) == ("posted", str(wh), "78006.00")
    [entry] = await ledger(env, shop, doc_id)
    assert (entry["account_dt"], entry["account_kt"], entry["amount"]) == ("2910", "0000", D("78006.00"))
    assert entry["entry_date"] == _go_live() - timedelta(days=1)
    assert await balance(env, shop, wh, UUID(p["id"])) == (D("12.000"), D("78006.00"))


async def test_opening_stock_import_fails_cleanly_without_go_live_date(env: Env) -> None:
    shop = await env.shop("Import no go-live")
    await set_go_live(env, shop, None)
    await use_account(env, shop)
    await create_product(env.client, shop, "Fanta", barcode="4870000000024")
    job = (await _upload(env, shop, b"barcode;qty;unit_cost\r\n4870000000024;1;1\r\n")).json()
    await env.client.post(f"{API}/import-jobs/{job['id']}/validate", headers=shop.h())
    await env.drain()
    await env.client.post(f"{API}/import-jobs/{job['id']}/commit", headers=shop.h())
    await env.drain()
    state = (await env.client.get(f"{API}/import-jobs/{job['id']}", headers=shop.h(key=None))).json()
    assert state["status"] == "failed"
    errors = (await env.client.get(f"{API}/import-jobs/{job['id']}/errors", headers=shop.h(key=None))).json()
    assert errors["items"] == [
        {"row": 0, "field": "file", "code": "VALIDATION_ERROR", "message": "validation.go_live_date_missing"}
    ]
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.stock_openings") == 0


async def test_opening_doc_date_in_the_future_is_refused(env: Env) -> None:
    """ACC-13 (13 §5.2, 19 §0): ``doc_date`` after the business day → 422 ``validation.doc_date_in_future``."""
    shop = await env.shop("Opening future")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    lines = [{"product_id": str(p), "qty": "1.000", "unit_cost": "1.0000"}]
    tomorrow = business_today() + timedelta(days=1)
    resp = await env.client.post(
        URL, json={"warehouse_id": str(wh), "doc_date": str(tomorrow), "lines": lines}, headers=shop.h()
    )
    assert resp.status_code == 422 and err(resp) == "VALIDATION_ERROR"
    assert resp.json()["error"]["details"][0] == {
        **resp.json()["error"]["details"][0], "field": "doc_date", "message_key": "validation.doc_date_in_future",
    }  # fmt: skip
    today = await env.client.post(
        URL,
        json={"warehouse_id": str(wh), "doc_date": str(business_today()), "lines": lines},
        headers=shop.h(),
    )
    assert today.status_code == 201, today.text


async def test_opening_page_cursor_out_of_range_is_422(env: Env) -> None:
    """SEC-06: a forged cursor with an instant that overflows on UTC conversion → 422, not 500."""
    import base64
    import json

    from app.core.db.base import uuid7

    shop = await env.shop("Opening cursor")
    for raw in (["9999-12-31T23:59:59+14:00", str(uuid7())], ["2026-01-01T00:00:00", str(uuid7())]):
        cursor = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")
        for url in (URL, f"{API}/recost-jobs"):
            resp = await env.client.get(url, params={"cursor": cursor}, headers=shop.h(key=None))
            assert resp.status_code == 422, (url, resp.text)
            assert resp.json()["error"]["details"][0]["message_key"] == "validation.cursor_invalid"
