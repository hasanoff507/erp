"""Goods receipts (19 §8; 13 §2.6–§2.8, §2.16, §4.3, §5.2; US-M04-01, US-M07-02/03; QT-M04-01,
QT-M07-02/03/04/07/08/09) — real app + PostgreSQL/Redis; every posting asserted to the tiyin."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from tests.support.catalog import set_limit
from tests.support.inventory import (
    D,
    add_branch,
    add_user,
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
from tests.support.ordering import TXN_ORDER
from tests.support.purchasing import (
    GR,
    Env,
    Shop,
    create_po,
    create_product,
    create_receipt,
    create_supplier,
    err,
    gr_line,
    post_gr,
    posted_receipt,
    purchasing_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["purchasing_env_fixture"]


async def _setup(env: Env, name: str, *roles: SystemRole) -> tuple[Shop, str, UUID]:
    shop = await env.shop(name, *(roles or (SystemRole.OWNER,)))
    supplier = await create_supplier(env.client, shop)
    wh = await use_account(env, shop, "2910")
    await set_method(env, shop, "fifo")
    return shop, supplier["id"], wh


async def _product(env: Env, shop: Shop, name: str = "Coca-Cola 1.5L", **extra: Any) -> str:
    created = await create_product(env.client, shop, name, **extra)
    return str(created["id"])


def _rows(entries: list[dict[str, Any]]) -> list[tuple[str, str, Any]]:
    return [(e["account_dt"], e["account_kt"], e["amount"]) for e in entries]


async def _vat_moves(env: Env, shop: Shop, doc_id: str) -> list[tuple[str, Any, Any, Any]]:
    found = await rows(
        env, shop.tenant_id,
        "SELECT kind, base_amount, vat_amount, reversal_of_id FROM app.vat_moves WHERE doc_id = :d "
        f"ORDER BY {TXN_ORDER}, id",
        d=UUID(doc_id),
    )  # fmt: skip
    return [(r["kind"], r["base_amount"], r["vat_amount"], r["reversal_of_id"]) for r in found]


async def _debt(env: Env, shop: Shop, doc_id: str) -> list[Any]:
    found = await rows(
        env, shop.tenant_id, f"SELECT amount FROM app.debt_moves WHERE doc_id = :d ORDER BY {TXN_ORDER}, id",
        d=UUID(doc_id),
    )  # fmt: skip
    return [r["amount"] for r in found]


async def _payable(env: Env, shop: Shop, supplier_id: str) -> Any:
    value = await scalar(
        env, shop.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'payable'",
        c=UUID(supplier_id),
    )  # fmt: skip
    return value if value is not None else D("0.00")


async def _link_einvoice(env: Env, shop: Shop, receipt_id: str, supplier_id: str, risk_flag: str) -> UUID:
    """An accepted incoming e-invoice with ``risk_flag`` linked to the draft (from-einvoice is Bosqich 5)."""
    einvoice_id = uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.einvoices (id, tenant_id, direction, operator, counterparty_id, status, risk_flag, "
        "total_amount, vat_amount) VALUES (:id, :t, 'in', 'faktura', :c, 'accepted', :r, 1120000.00, 120000.00)",
        id=einvoice_id, t=shop.tenant_id, c=UUID(supplier_id), r=risk_flag,
    )  # fmt: skip
    await execute(
        env, shop.tenant_id, "UPDATE app.goods_receipts SET einvoice_id = :e WHERE id = :id",
        e=einvoice_id, id=UUID(receipt_id),
    )  # fmt: skip
    return einvoice_id


# --- QT-M04-01 / QT-M07-03 --------------------------------------------------------------------------
async def test_qt_m04_01_post_raises_balance_and_creates_lot(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "QT-M04-01")
    cola = await _product(env, shop)
    expiry = (business_today() + timedelta(days=90)).isoformat()
    draft = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "24.000", "5000.0000", expiry_date=expiry)]
    )
    assert (draft["status"], draft["number"], draft["total"]) == ("draft", None, "134400.00")
    assert draft["lines"][0]["lot_id"] is None and draft["ettn_status"] == "none"
    assert await balance(env, shop, wh, UUID(cola)) == (D("0.000"), D("0.00"))  # a draft moves nothing

    key = "gr-post-qt-m04-01"
    posted = await post_gr(env.client, shop, draft["id"], key=key)
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert body["status"] == "posted" and body["number"] == f"M-01-{business_today().year}-000001"
    assert body["posted_at"] is not None
    (lot,) = body["lots_created"]
    assert (lot["product_id"], lot["qty_in"], lot["unit_cost"]) == (cola, "24.000", "5000.0000")
    assert body["lines"][0]["lot_id"] == lot["lot_id"] and body["lines"][0]["lot_qty_left"] == "24.000"
    replay = await post_gr(env.client, shop, draft["id"], key=key)
    assert replay.status_code == 200 and replay.json() == body
    assert replay.headers["Idempotent-Replayed"] == "true"

    assert await balance(env, shop, wh, UUID(cola)) == (D("24.000"), D("120000.00"))
    (row,) = await lots(env, shop, UUID(cola))
    assert (row["qty_in"], row["qty_left"], row["unit_cost"], row["source_doc_type"]) == (
        D("24.000"), D("24.000"), D("5000.0000"), "goods_receipts",
    )  # fmt: skip
    assert row["expiry_date"] == date.fromisoformat(expiry) and str(row["id"]) == lot["lot_id"]
    again = await post_gr(env.client, shop, draft["id"])
    assert again.status_code == 409 and err(again) == "DOC_NOT_DRAFT"
    audit = await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE entity_id = :d AND action = :a",
        d=UUID(draft["id"]), a="goods_receipt.posted",
    )  # fmt: skip
    assert audit == 1


async def test_qt_m07_03_vat_ledger_vat_moves_and_payable(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "QT-M07-03")
    cola = await _product(env, shop)
    body = await posted_receipt(env.client, shop, supplier, wh, [gr_line(cola, "100.000", "10000.0000")])
    assert (body["net_total"], body["vat_total"], body["total"]) == ("1000000.00", "120000.00", "1120000.00")
    entries = await ledger(env, shop, UUID(body["id"]))
    assert _rows(entries) == [("2910", "6010", D("1000000.00")), ("4410", "6010", D("120000.00"))]
    assert sum(e["amount"] for e in entries if e["account_kt"] == "6010") == D("1120000.00")
    assert all(e["entry_date"] == business_today() and e["doc_type"] == "goods_receipts" for e in entries)
    lot_id = body["lots_created"][0]["lot_id"]
    assert entries[0]["analytics"] == {
        "product_id": cola, "warehouse_id": str(wh), "counterparty_id": supplier,
        "line_id": body["lines"][0]["id"], "lot_id": lot_id,
    }  # fmt: skip
    assert entries[1]["analytics"] == {"tax_type": "vat", "counterparty_id": supplier}
    assert await _vat_moves(env, shop, body["id"]) == [("input", D("1000000.00"), D("120000.00"), None)]
    assert await _debt(env, shop, body["id"]) == [D("1120000.00")]
    assert await _payable(env, shop, supplier) == D("1120000.00")
    assert await balance(env, shop, wh, UUID(cola)) == (D("100.000"), D("1000000.00"))


@pytest.mark.parametrize(("flag", "qt"), [("red", "QT-M07-04"), ("unknown", "QT-M07-09")])
async def test_qt_m07_04_09_risky_einvoice_defers_input_vat(env: Env, flag: str, qt: str) -> None:
    shop, supplier, wh = await _setup(env, qt)
    cola = await _product(env, shop)
    draft = await create_receipt(env.client, shop, supplier, wh, [gr_line(cola, "100.000", "10000.0000")])
    einvoice_id = await _link_einvoice(env, shop, draft["id"], supplier, flag)
    posted = await post_gr(env.client, shop, draft["id"])
    assert posted.status_code == 200, posted.text
    assert posted.json()["einvoice_risk_flag"] == flag and posted.json()["einvoice_id"] == str(einvoice_id)
    entries = await ledger(env, shop, UUID(draft["id"]))
    # 13 §2.8: 4410 is posted (flagged deferred) — ledger 6010 = the gross payable; only vat_moves wait
    assert _rows(entries) == [("2910", "6010", D("1000000.00")), ("4410", "6010", D("120000.00"))]
    assert sum(e["amount"] for e in entries if e["account_kt"] == "6010") == D("1120000.00")
    assert entries[1]["analytics"] == {
        "tax_type": "vat", "counterparty_id": supplier, "einvoice_id": str(einvoice_id), "vat_credit": "deferred",
    }  # fmt: skip
    assert await _vat_moves(env, shop, draft["id"]) == []
    assert await _debt(env, shop, draft["id"]) == [D("1120000.00")]  # the liability is the full invoice
    assert await _payable(env, shop, supplier) == D("1120000.00")


async def test_green_einvoice_records_vat_with_einvoice_link(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "Green EHF")
    cola = await _product(env, shop)
    draft = await create_receipt(env.client, shop, supplier, wh, [gr_line(cola, "100.000", "10000.0000")])
    einvoice_id = await _link_einvoice(env, shop, draft["id"], supplier, "green")
    assert (await post_gr(env.client, shop, draft["id"])).status_code == 200
    entries = await ledger(env, shop, UUID(draft["id"]))
    assert _rows(entries)[1] == ("4410", "6010", D("120000.00"))
    assert entries[1]["analytics"] == {
        "tax_type": "vat",
        "counterparty_id": supplier,
        "einvoice_id": str(einvoice_id),
    }  # no vat_credit flag
    assert await _vat_moves(env, shop, draft["id"]) == [("input", D("1000000.00"), D("120000.00"), None)]
    vat_einvoice = await scalar(
        env, shop.tenant_id, "SELECT einvoice_id FROM app.vat_moves WHERE doc_id = :d", d=UUID(draft["id"])
    )
    assert vat_einvoice == einvoice_id


# --- QT-M07-02 / QT-M07-07 (purchase orders) ---------------------------------------------------------
async def test_qt_m07_02_po_receipt_with_discrepancy(env: Env) -> None:
    shop, supplier, wh = await _setup(
        env, "QT-M07-02", SystemRole.OWNER, SystemRole.STOREKEEPER, SystemRole.ACCOUNTANT
    )
    cola = await _product(env, shop)
    po = await create_po(
        env.client, shop, supplier, wh, [{"product_id": cola, "qty": "50.000", "price": "12000.0000"}]
    )
    sent = await env.client.post(
        f"/api/v1/purchase-orders/{po['id']}/send", headers=shop.h(branch=shop.branch_id)
    )
    assert sent.status_code == 200, sent.text

    no_reason = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "48.000"}], role="storekeeper",
        po_id=po["id"], expect=422,
    )  # fmt: skip
    assert no_reason["error"]["details"][0]["field"] == "lines[0].discrepancy_reason"
    draft = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "48.000", "discrepancy_reason": "short"}],
        role="storekeeper", po_id=po["id"],
    )  # fmt: skip
    line = draft["lines"][0]
    # supplier, cost and VAT rate come from the PO and the product card
    assert (draft["supplier_id"], draft["po_id"], draft["source"]) == (supplier, po["id"], "purchase_order")
    assert (line["qty"], line["cost"], line["vat_rate"], line["discrepancy_reason"]) == (
        "48.000", "12000.0000", "12.00", "short",
    )  # fmt: skip
    assert (line["net_amount"], line["vat_amount"], draft["total"]) == ("576000.00", "69120.00", "645120.00")
    assert await balance(env, shop, wh, UUID(cola)) == (D("0.000"), D("0.00"))

    denied = await post_gr(env.client, shop, draft["id"], role="storekeeper")  # qaror #49
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    posted = await post_gr(env.client, shop, draft["id"], role="accountant")
    assert posted.status_code == 200, posted.text
    assert await balance(env, shop, wh, UUID(cola)) == (D("48.000"), D("576000.00"))
    po_now = (await env.client.get(f"/api/v1/purchase-orders/{po['id']}", headers=shop.h())).json()
    assert po_now["status"] == "partially_received"
    assert po_now["received_lines"] == [
        {"product_id": cola, "ordered_qty": "50.000", "received_qty": "48.000"}
    ]

    # the rest (2) matches what the PO still expects → no reason needed; the PO closes
    rest = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "2.000"}], po_id=po["id"]
    )
    assert (await post_gr(env.client, shop, rest["id"])).status_code == 200
    po_now = (await env.client.get(f"/api/v1/purchase-orders/{po['id']}", headers=shop.h())).json()
    assert po_now["status"] == "closed"
    # cancelling the second receipt re-opens the PO in the same transaction
    cancelled = await env.client.post(f"{GR}/{rest['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    assert cancelled.status_code == 200, cancelled.text
    po_now = (await env.client.get(f"/api/v1/purchase-orders/{po['id']}", headers=shop.h())).json()
    assert po_now["status"] == "partially_received"


async def test_qt_m07_07_closed_or_cancelled_po_rejects_receipts(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "QT-M07-07")
    cola = await _product(env, shop)
    line = [{"product_id": cola, "qty": "5.000", "price": "1000.0000"}]
    po = await create_po(env.client, shop, supplier, wh, line)
    draft_po = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "5.000"}], po_id=po["id"], expect=409
    )  # a draft PO takes no receipts
    assert draft_po["error"]["code"] == "PURCHASE_ORDER_CLOSED"
    await env.client.post(f"/api/v1/purchase-orders/{po['id']}/send", headers=shop.h())
    draft = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "5.000"}], po_id=po["id"]
    )
    cancel = await env.client.post(
        f"/api/v1/purchase-orders/{po['id']}/cancel", json={"reason": "x"}, headers=shop.h()
    )
    assert cancel.status_code == 200
    blocked = await post_gr(env.client, shop, draft["id"])
    assert blocked.status_code == 409 and err(blocked) == "PURCHASE_ORDER_CLOSED"
    assert await balance(env, shop, wh, UUID(cola)) == (D("0.000"), D("0.00"))
    again = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "5.000"}], po_id=po["id"], expect=409
    )
    assert again["error"]["code"] == "PURCHASE_ORDER_CLOSED"


# --- 13 §2.6 bonus, §2.6a, §2.7, §2.8, §4.3, §2.16 ---------------------------------------------------
async def test_qt_m07_08_bonus_units_share_the_invoice(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "QT-M07-08")
    await set_method(env, shop, "aveco")
    cola = await _product(env, shop)
    body = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "11.000", "10909.0909", "0.00")]
    )
    assert body["lines"][0]["net_amount"] == "120000.00" and body["total"] == "120000.00"
    assert body["lots_created"][0]["unit_cost"] == "10909.0909"
    (lot,) = await lots(env, shop, UUID(cola))
    assert (lot["qty_in"], lot["unit_cost"]) == (D("11.000"), D("10909.0909"))  # no separate 0-cost lot
    assert _rows(await ledger(env, shop, UUID(body["id"]))) == [("2910", "6010", D("120000.00"))]
    state = await avg(env, shop, wh, UUID(cola))
    assert state is not None and (state["qty"], state["avg_cost"], state["total_value"]) == (
        D("11.000"), D("10909.0909"), D("120000.00"),
    )  # fmt: skip


async def test_2_6a_gratuitous_receipt(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "2.6a")
    cola = await _product(env, shop)
    paid = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "5.000", "2000.0000")], kind="gratuitous",
        paid_immediately=True, expect=422,
    )  # fmt: skip
    assert paid["error"]["details"][0]["field"] == "paid_immediately"
    body = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "5.000", "2000.0000")], kind="gratuitous"
    )
    assert (body["kind"], body["vat_total"], body["total"]) == ("gratuitous", "0.00", "10000.00")
    assert _rows(await ledger(env, shop, UUID(body["id"]))) == [("2910", "8530", D("10000.00"))]
    assert await _vat_moves(env, shop, body["id"]) == [] and await _debt(env, shop, body["id"]) == []
    assert await balance(env, shop, wh, UUID(cola)) == (D("5.000"), D("10000.00"))


async def test_2_7_zero_rate_and_exempt_lines(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "2.7")
    bread = await _product(env, shop, "Non", vat_rate=None, vat_exemption_code="10001")
    sugar = await _product(env, shop, "Shakar")
    body = await posted_receipt(
        env.client, shop, supplier, wh,
        [gr_line(bread, "10.000", "5000.0000", vat_rate=None), gr_line(sugar, "2.000", "1000.0000", "0.00")],
    )  # fmt: skip
    assert [(ln["vat_rate"], ln["vat_exemption_code"], ln["vat_amount"]) for ln in body["lines"]] == [
        ("0.00", "10001", "0.00"), ("0.00", None, "0.00"),
    ]  # fmt: skip
    assert _rows(await ledger(env, shop, UUID(body["id"]))) == [
        ("2910", "6010", D("50000.00")), ("2910", "6010", D("2000.00")),
    ]  # fmt: skip
    assert await _vat_moves(env, shop, body["id"]) == []
    assert await _debt(env, shop, body["id"]) == [D("52000.00")]


async def test_2_8_paid_immediately_from_bank(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "2.8")
    cola = await _product(env, shop)
    body = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "100.000", "10000.0000")], paid_immediately=True
    )
    assert _rows(await ledger(env, shop, UUID(body["id"]))) == [
        ("2910", "5110", D("1000000.00")), ("4410", "5110", D("120000.00")),
    ]  # fmt: skip
    assert await _vat_moves(env, shop, body["id"]) == [("input", D("1000000.00"), D("120000.00"), None)]
    assert await _debt(env, shop, body["id"]) == [] and await _payable(env, shop, supplier) == D("0.00")


async def test_4_3_turnover_regime_vat_in_lot_cost(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "4.3")
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) VALUES (:t, :v, 'turnover', :u)",
        t=shop.tenant_id, v=date(2026, 1, 1), u=shop.user_ids["owner"],
    )  # fmt: skip
    cola = await _product(env, shop)
    body = await posted_receipt(env.client, shop, supplier, wh, [gr_line(cola, "100.000", "10000.0000")])
    assert body["lots_created"][0]["unit_cost"] == "11200.0000"
    assert _rows(await ledger(env, shop, UUID(body["id"]))) == [("2910", "6010", D("1120000.00"))]
    assert await _vat_moves(env, shop, body["id"]) == []
    assert await _debt(env, shop, body["id"]) == [D("1120000.00")]
    assert await balance(env, shop, wh, UUID(cola)) == (D("100.000"), D("1120000.00"))


async def test_2_16_supplier_advance_is_offset(env: Env) -> None:
    """13 §2.16 example: advance 200000.00, receipt 500000.00 (0%) → Dt 6010 / Kt 4310 200000.00."""
    shop, supplier, wh = await _setup(env, "2.16")
    cola = await _product(env, shop)
    # the overpayment of a supplier payment (Bosqich 4): Dt 4310 / Kt 5110 200000.00, payable −200000.00
    payment = uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.ledger_entries (tenant_id, entry_date, branch_id, account_dt, account_kt, amount, "
        "doc_type, doc_id, analytics) VALUES (:t, :d, :b, '4310', '5110', 200000.00, 'supplier_payments', :p, "
        "CAST(:a AS jsonb))",
        t=shop.tenant_id, d=business_today(), b=shop.branch_id, p=payment, a=f'{{"counterparty_id": "{supplier}"}}',
    )  # fmt: skip
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.debt_moves (tenant_id, counterparty_id, direction, amount, doc_type, doc_id) "
        "VALUES (:t, :c, 'payable', -200000.00, 'supplier_payments', :p)",
        t=shop.tenant_id, c=UUID(supplier), p=payment,
    )  # fmt: skip
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.debt_balances (tenant_id, counterparty_id, direction, balance) "
        "VALUES (:t, :c, 'payable', -200000.00)",
        t=shop.tenant_id, c=UUID(supplier),
    )  # fmt: skip
    body = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "1.000", "500000.0000", "0.00")]
    )
    entries = await ledger(env, shop, UUID(body["id"]))
    assert _rows(entries) == [("2910", "6010", D("500000.00")), ("6010", "4310", D("200000.00"))]
    assert entries[1]["analytics"] == {"counterparty_id": supplier}
    assert await _payable(env, shop, supplier) == D("300000.00")
    advance_left = await scalar(
        env, shop.tenant_id,
        "SELECT sum(CASE WHEN account_dt = '4310' THEN amount ELSE -amount END) FROM app.ledger_entries "
        "WHERE '4310' IN (account_dt, account_kt)",
    )  # fmt: skip
    assert advance_left == D("0.00")
    second = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1000.0000", "0.00")]
    )
    assert _rows(await ledger(env, shop, UUID(second["id"]))) == [("2910", "6010", D("1000.00"))]


# --- cancel / period / permissions / scope / idempotency / RLS ---------------------------------------
async def test_cancel_posted_receipt_is_a_full_storno(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR cancel")
    cola = await _product(env, shop)
    body = await posted_receipt(env.client, shop, supplier, wh, [gr_line(cola, "100.000", "10000.0000")])
    key = "gr-cancel-1"
    cancelled = await env.client.post(
        f"{GR}/{body['id']}/cancel", json={"reason": "noto'g'ri"}, headers=shop.h(key=key)
    )
    assert cancelled.status_code == 200, cancelled.text
    out = cancelled.json()
    assert (out["status"], out["cancel_reason"], out["number"]) == ("cancelled", "noto'g'ri", body["number"])
    replay = await env.client.post(
        f"{GR}/{body['id']}/cancel", json={"reason": "noto'g'ri"}, headers=shop.h(key=key)
    )
    assert (
        replay.status_code == 200 and replay.json() == out and replay.headers["Idempotent-Replayed"] == "true"
    )

    entries = await ledger(env, shop, UUID(body["id"]))
    originals = {e["id"]: e for e in entries if e["reversal_of_id"] is None}
    stornos = [e for e in entries if e["reversal_of_id"] is not None]
    assert len(originals) == 2 and len(stornos) == 2
    for st in stornos:
        orig = originals[st["reversal_of_id"]]
        assert (st["account_dt"], st["account_kt"], st["amount"]) == (
            orig["account_kt"],
            orig["account_dt"],
            orig["amount"],
        )
    assert await _vat_moves(env, shop, body["id"]) == [
        ("input", D("1000000.00"), D("120000.00"), None),
        ("input", D("-1000000.00"), D("-120000.00"), (await _vat_ids(env, shop, body["id"]))[0]),
    ]
    assert await _debt(env, shop, body["id"]) == [D("1120000.00"), D("-1120000.00")]
    assert await _payable(env, shop, supplier) == D("0.00")
    assert await balance(env, shop, wh, UUID(cola)) == (D("0.000"), D("0.00"))
    (lot,) = await lots(env, shop, UUID(cola))
    assert lot["qty_left"] == D("0.000")
    twice = await env.client.post(f"{GR}/{body['id']}/cancel", json={"reason": "x"}, headers=shop.h())
    assert twice.status_code == 409 and err(twice) == "DOC_ALREADY_CANCELLED"


async def _vat_ids(env: Env, shop: Shop, doc_id: str) -> list[UUID]:
    found = await rows(
        env,
        shop.tenant_id,
        f"SELECT id FROM app.vat_moves WHERE doc_id = :d ORDER BY {TXN_ORDER}, id",
        d=UUID(doc_id),
    )
    return [r["id"] for r in found]


async def test_cancel_refused_when_lot_consumed_and_draft_cancel(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR consumed")
    cola = await _product(env, shop)
    body = await posted_receipt(env.client, shop, supplier, wh, [gr_line(cola, "10.000", "1000.0000")])
    await issue(env, shop, wh, UUID(cola), "1.000", account_dt="9430")  # a write-off consumed the lot
    refused = await env.client.post(f"{GR}/{body['id']}/cancel", json={"reason": "x"}, headers=shop.h())
    assert refused.status_code == 409 and err(refused) == "LOT_ALREADY_CONSUMED"
    assert len(await ledger(env, shop, UUID(body["id"]))) == 2  # nothing reversed
    draft = await create_receipt(env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1.0000")])
    done = await env.client.post(f"{GR}/{draft['id']}/cancel", json={"reason": "keraksiz"}, headers=shop.h())
    assert done.status_code == 200 and done.json()["status"] == "cancelled"
    assert await ledger(env, shop, UUID(draft["id"])) == []
    after = await post_gr(env.client, shop, draft["id"])
    assert after.status_code == 409 and err(after) == "DOC_NOT_DRAFT"


async def test_period_closed_refuses_post(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR period")
    cola = await _product(env, shop)
    last_month = business_today().replace(day=1) - timedelta(days=1)
    draft = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1000.0000")], doc_date=last_month
    )
    await close_period(env, shop, last_month)
    closed = await post_gr(env.client, shop, draft["id"])
    assert closed.status_code == 409 and err(closed) == "PERIOD_CLOSED"
    assert closed.json()["error"]["params"]["period"] == last_month.strftime("%Y-%m")
    assert await balance(env, shop, wh, UUID(cola)) == (D("0.000"), D("0.00"))
    assert (await env.client.get(f"{GR}/{draft['id']}", headers=shop.h())).json()["status"] == "draft"


async def test_permissions_storekeeper_drafts_accountant_posts(env: Env) -> None:
    """qaror #49: Omborchi creates the draft; posting needs purchases.post (or the Owner grants it)."""
    shop, supplier, wh = await _setup(
        env, "GR perms", SystemRole.OWNER, SystemRole.STOREKEEPER, SystemRole.ACCOUNTANT, SystemRole.CASHIER
    )
    cola = await _product(env, shop)
    lines = [gr_line(cola, "1.000", "1000.0000")]
    no_receive = await env.client.post(
        GR, json={"supplier_id": supplier, "warehouse_id": str(wh), "doc_date": str(business_today()), "lines": lines},
        headers=shop.h("cashier"),
    )  # fmt: skip
    assert no_receive.status_code == 403 and err(no_receive) == "PERMISSION_DENIED"
    draft = await create_receipt(env.client, shop, supplier, wh, lines, role="storekeeper")
    assert (await post_gr(env.client, shop, draft["id"], role="storekeeper")).status_code == 403
    cancel = await env.client.post(
        f"{GR}/{draft['id']}/cancel", json={"reason": "x"}, headers=shop.h("storekeeper")
    )
    assert cancel.status_code == 403
    await set_limit(env.db, shop.tenant_id, "storekeeper", "purchases.post", None)  # BO-11 grant
    granted = await post_gr(env.client, shop, draft["id"], role="storekeeper")
    assert granted.status_code == 200, granted.text
    listed = await env.client.get(GR, headers=shop.h("accountant"))
    assert listed.status_code == 200 and [x["id"] for x in listed.json()["items"]] == [draft["id"]]


async def test_patch_replaces_the_draft_only(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR patch")
    cola, sugar = await _product(env, shop), await _product(env, shop, "Shakar")
    draft = await create_receipt(env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1000.0000")])
    body = {
        "supplier_id": supplier, "warehouse_id": str(wh), "doc_date": str(business_today()), "comment": "yangi",
        "lines": [gr_line(sugar, "2.000", "500.0000", "0.00"), gr_line(cola, "3.000", "100.0000")],
    }  # fmt: skip
    patched = await env.client.patch(f"{GR}/{draft['id']}", json=body, headers=shop.h())
    assert patched.status_code == 200, patched.text
    out = patched.json()
    assert [(ln["line_no"], ln["product_id"], ln["qty"]) for ln in out["lines"]] == [
        (1, sugar, "2.000"),
        (2, cola, "3.000"),
    ]
    assert (out["comment"], out["total"]) == ("yangi", "1336.00")  # 1000.00 + 300.00 + 36.00
    assert (await post_gr(env.client, shop, draft["id"])).status_code == 200
    late = await env.client.patch(f"{GR}/{draft['id']}", json=body, headers=shop.h())
    assert late.status_code == 409 and err(late) == "DOC_NOT_DRAFT"


async def test_validation_errors(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR validation")
    cola = await _product(env, shop)

    async def bad(lines: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        return await create_receipt(env.client, shop, supplier, wh, lines, expect=422, **extra)

    assert (await bad([{"product_id": cola, "qty": "1.000"}]))["error"]["details"][0][
        "field"
    ] == "lines[0].cost"
    assert (await bad([gr_line(cola, "0.000", "1.0000")]))["error"]["details"][0]["field"] == "lines[0].qty"
    assert (await bad([gr_line(cola, "1.000", "1.0000", "15.00")]))["error"]["details"][0][
        "field"
    ] == "lines[0].vat_rate"
    assert (await bad([gr_line(str(uuid7()), "1.000", "1.0000")]))["error"]["details"][0][
        "field"
    ] == "lines[0].product_id"
    missing = await create_receipt(env.client, shop, None, wh, [gr_line(cola, "1.000", "1.0000")], expect=422)
    assert missing["error"]["details"][0]["field"] == "supplier_id"
    unknown = await create_receipt(
        env.client, shop, str(uuid7()), wh, [gr_line(cola, "1.000", "1.0000")], expect=404
    )
    assert unknown["error"]["params"]["resource"] == "counterparty"


async def test_marking_codes_kept_exactly(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR marking")
    water = await _product(env, shop, "Suv 0.5L", is_marked=True, marking_group_code="water_beverages")
    gs = "\x1d"
    codes = [f"0104780000000001215abc{gs}93dGVz", f"0104780000000001215abd{gs}93dGVz"]
    short = await create_receipt(
        env.client,
        shop,
        supplier,
        wh,
        [gr_line(water, "2.000", "100.0000", marking_codes=codes[:1])],
        expect=422,
    )
    assert short["error"]["details"][0]["message_key"] == "validation.marking_count_mismatch"
    draft = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(water, "2.000", "100.0000", marking_codes=codes)]
    )
    assert draft["lines"][0]["marking_codes"] == codes and draft["marking_acceptance"] is None
    stored = await rows(env, shop.tenant_id, "SELECT code, status FROM app.marking_codes ORDER BY id")
    assert [(r["code"], r["status"]) for r in stored] == [(c, "pending_verification") for c in codes]
    posted = await post_gr(env.client, shop, draft["id"])
    assert posted.status_code == 200, posted.text
    acceptance = posted.json()["marking_acceptance"]  # B5: the CRPT acceptance job's deadline (marking.md §1)
    assert (acceptance["status"], acceptance["deadline_kind"]) == ("pending", "72_hours")
    assert acceptance["due_at"] is not None
    stored = await rows(env, shop.tenant_id, "SELECT status FROM app.marking_codes")
    assert {r["status"] for r in stored} == {"in_stock"}
    dup = await create_receipt(
        env.client,
        shop,
        supplier,
        wh,
        [gr_line(water, "1.000", "100.0000", marking_codes=codes[:1])],
        expect=422,
    )
    assert dup["error"]["code"] == "MARKING_CODE_INVALID"


async def test_branch_scope_and_rls(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR scope")
    cola = await _product(env, shop)
    body = await posted_receipt(env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1000.0000")])
    other_branch, other_wh = await add_branch(env, shop, "02")
    await add_user(env, shop, "branch2", SystemRole.ACCOUNTANT, (other_branch,))
    denied = await env.client.get(f"{GR}/{body['id']}", headers=shop.h("branch2"))
    assert denied.status_code == 403 and err(denied) == "BRANCH_SCOPE_DENIED"
    listed = await env.client.get(GR, headers=shop.h("branch2"))
    assert listed.json()["items"] == []
    foreign_wh = await env.client.post(
        GR, json={"supplier_id": supplier, "warehouse_id": str(wh), "doc_date": str(business_today()),
                  "lines": [gr_line(cola, "1.000", "1.0000")]},
        headers=shop.h("branch2"),
    )  # fmt: skip
    assert foreign_wh.status_code == 403  # no purchases.receive for an accountant / foreign warehouse
    other = await env.shop("GR scope other")
    hidden = await env.client.get(f"{GR}/{body['id']}", headers=other.h())
    assert hidden.status_code == 404 and err(hidden) == "NOT_FOUND"
    assert (await env.client.get(GR, headers=other.h())).json()["items"] == []
    in_branch = await env.client.get(GR, headers=shop.h(branch=shop.branch_id), params={"status": "posted"})
    assert [x["id"] for x in in_branch.json()["items"]] == [body["id"]]
    del other_wh


async def test_list_filters_and_cursor(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR list")
    supplier2 = (await create_supplier(env.client, shop, "Boshqa MChJ", stir="301234568"))["id"]
    cola = await _product(env, shop)
    a = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1.0000")], doc_date="2026-10-01"
    )
    b = await create_receipt(
        env.client, shop, supplier2, wh, [gr_line(cola, "1.000", "1.0000")], doc_date="2026-10-05"
    )
    c = await posted_receipt(
        env.client, shop, supplier, wh, [gr_line(cola, "1.000", "1.0000")], doc_date="2026-10-09"
    )

    async def ids(**params: Any) -> list[str]:
        response = await env.client.get(GR, params=params, headers=shop.h())
        assert response.status_code == 200, response.text
        return [x["id"] for x in response.json()["items"]]

    assert await ids() == [c["id"], b["id"], a["id"]]
    assert await ids(supplier_id=supplier) == [c["id"], a["id"]]
    assert await ids(status="draft") == [b["id"], a["id"]]
    assert await ids(**{"from": "2026-10-02", "to": "2026-10-06"}) == [b["id"]]
    first = (await env.client.get(GR, params={"limit": 2}, headers=shop.h())).json()
    assert [x["id"] for x in first["items"]] == [c["id"], b["id"]] and first["next_cursor"]
    assert await ids(limit=2, cursor=first["next_cursor"]) == [a["id"]]


async def test_concurrent_posts_on_the_same_products(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "GR concurrency")
    cola, sugar = await _product(env, shop), await _product(env, shop, "Shakar")
    one = await create_receipt(
        env.client,
        shop,
        supplier,
        wh,
        [gr_line(cola, "1.000", "100.0000"), gr_line(sugar, "2.000", "100.0000")],
    )
    two = await create_receipt(
        env.client,
        shop,
        supplier,
        wh,
        [gr_line(sugar, "3.000", "100.0000"), gr_line(cola, "4.000", "100.0000")],
    )
    results = await asyncio.gather(post_gr(env.client, shop, one["id"]), post_gr(env.client, shop, two["id"]))
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert await balance(env, shop, wh, UUID(cola)) == (D("5.000"), D("500.00"))
    assert await balance(env, shop, wh, UUID(sugar)) == (D("5.000"), D("500.00"))
    assert sorted(r.json()["number"] for r in results) == [
        f"M-01-{business_today().year}-000001", f"M-01-{business_today().year}-000002",
    ]  # fmt: skip
    assert await _payable(env, shop, supplier) == D("1120.00")


async def test_receipt_settles_pending_issue_and_recost_runs_after_commit(env: Env) -> None:
    """13 §3.1/§3.3: a write-off from empty stock is pending at cost 0; the receipt post settles it and
    enqueues the recost job after commit, which writes Dt 9430 / Kt 2910 = 3 × 1000.00."""
    shop, supplier, wh = await _setup(env, "GR recost")
    cola = await _product(env, shop)
    res, doc, _ = await issue(env, shop, wh, UUID(cola), "3.000", account_dt="9430")
    assert res.pending_qty == D("3.000") and await ledger(env, shop, doc) == []
    body = await posted_receipt(env.client, shop, supplier, wh, [gr_line(cola, "10.000", "1000.0000")])
    job = await rows(
        env, shop.tenant_id, "SELECT status, reason_doc_type, reason_doc_id FROM app.recost_jobs"
    )
    assert [(j["reason_doc_type"], str(j["reason_doc_id"])) for j in job] == [("goods_receipts", body["id"])]
    assert await env.drain() >= 1
    (entry,) = await ledger(env, shop, doc)
    assert (entry["account_dt"], entry["account_kt"], entry["amount"]) == ("9430", "2910", D("3000.00"))
    assert await balance(env, shop, wh, UUID(cola)) == (D("7.000"), D("7000.00"))


# --- review fixes: ACC-13, SEC-01, SEC-06, SEC-08 ---------------------------------------------------
def _invalid(body: dict[str, Any]) -> tuple[str, str, str]:
    detail = body["error"]["details"][0]
    return body["error"]["code"], detail["field"], detail["message_key"]


async def test_acc_13_doc_date_in_future_refused(env: Env) -> None:
    """13 §5.2 / 19 §1: create, PATCH and post with ``doc_date`` > business today → 422, nothing posted."""
    shop, supplier, wh = await _setup(env, "ACC-13 GR")
    cola = await _product(env, shop)
    tomorrow = business_today() + timedelta(days=1)
    line = [gr_line(cola, "1.000", "1000.0000")]
    future = await create_receipt(env.client, shop, supplier, wh, line, doc_date=tomorrow, expect=422)
    assert _invalid(future) == ("VALIDATION_ERROR", "doc_date", "validation.doc_date_in_future")
    draft = await create_receipt(env.client, shop, supplier, wh, line)
    body = {"supplier_id": supplier, "warehouse_id": str(wh), "doc_date": str(tomorrow), "lines": line}
    patched = await env.client.patch(f"{GR}/{draft['id']}", json=body, headers=shop.h())
    assert patched.status_code == 422
    assert _invalid(patched.json()) == ("VALIDATION_ERROR", "doc_date", "validation.doc_date_in_future")
    # a draft dated today that is still a draft when the date moved forward is caught again at post
    await execute(
        env, shop.tenant_id, "UPDATE app.goods_receipts SET doc_date = :d WHERE id = :id",
        d=tomorrow, id=UUID(draft["id"]),
    )  # fmt: skip
    posted = await post_gr(env.client, shop, draft["id"])
    assert posted.status_code == 422
    assert _invalid(posted.json()) == ("VALIDATION_ERROR", "doc_date", "validation.doc_date_in_future")
    assert await ledger(env, shop, UUID(draft["id"])) == []
    assert await balance(env, shop, wh, UUID(cola)) == (D("0.000"), D("0.00"))
    today = await create_receipt(env.client, shop, supplier, wh, line, doc_date=business_today())
    assert today["doc_date"] == business_today().isoformat()


async def test_sec_01_po_branch_scope_and_warehouse(env: Env) -> None:
    """19 §8: a receipt against a PO needs the PO's branch in the user's scope (403) and the PO's
    warehouse (422 ``validation.po_warehouse_mismatch``)."""
    shop, supplier, wh = await _setup(env, "SEC-01", SystemRole.OWNER, SystemRole.STOREKEEPER)
    cola = await _product(env, shop)
    po = await create_po(
        env.client, shop, supplier, wh, [{"product_id": cola, "qty": "5.000", "price": "1000.0000"}]
    )
    sent = await env.client.post(f"/api/v1/purchase-orders/{po['id']}/send", headers=shop.h())
    assert sent.status_code == 200, sent.text
    branch_b, wh_b = await add_branch(env, shop, "02")
    await add_user(env, shop, "keeper_b", SystemRole.STOREKEEPER, (branch_b,))
    foreign = await env.client.post(
        GR,
        json={"warehouse_id": str(wh_b), "doc_date": str(business_today()), "po_id": po["id"],
              "lines": [{"product_id": cola, "qty": "5.000"}]},
        headers=shop.h("keeper_b", branch=branch_b),
    )  # fmt: skip
    assert foreign.status_code == 403 and err(foreign) == "BRANCH_SCOPE_DENIED", foreign.text

    other_wh = uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.warehouses (id, tenant_id, branch_id, name, type, inventory_account) "
        "VALUES (:id, :t, :b, 'Ikkinchi ombor', 'stock', '2910')",
        id=other_wh, t=shop.tenant_id, b=shop.branch_id,
    )  # fmt: skip
    mismatch = await create_receipt(
        env.client, shop, None, other_wh, [{"product_id": cola, "qty": "5.000"}], po_id=po["id"], expect=422
    )
    assert _invalid(mismatch) == ("VALIDATION_ERROR", "warehouse_id", "validation.po_warehouse_mismatch")
    draft = await create_receipt(
        env.client, shop, None, wh, [{"product_id": cola, "qty": "5.000"}], po_id=po["id"]
    )
    assert draft["warehouse_id"] == str(wh) and draft["po_id"] == po["id"]
    receipts = await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.goods_receipts")
    assert receipts == 1


@pytest.mark.parametrize(
    "raw",
    [
        '["9999-12-31T23:59:59+14:00", "{id}"]',  # far-future offset → would overflow in the driver
        '["2026-10-01T10:00:00", "{id}"]',  # naive instant
        '["1999-12-31T23:59:59+00:00", "{id}"]',  # before 2000-01-01 UTC
        '["0001-01-01T00:00:00+14:00", "{id}"]',  # before year 1 in UTC → OverflowError
    ],
)
async def test_sec_06_cursor_out_of_range_is_422(env: Env, raw: str) -> None:
    import base64

    shop, _, _ = await _setup(env, "SEC-06 GR")
    token = base64.urlsafe_b64encode(raw.replace("{id}", str(uuid7())).encode()).decode().rstrip("=")
    for path in (GR, "/api/v1/supplier-returns", "/api/v1/purchase-orders"):
        response = await env.client.get(path, params={"cursor": token}, headers=shop.h(key=None))
        assert response.status_code == 422, (path, response.text)
        assert _invalid(response.json()) == ("VALIDATION_ERROR", "cursor", "validation.cursor_invalid")


async def test_sec_08_marking_code_race_is_422(env: Env) -> None:
    """Two drafts with the same code: the loser gets 422 MARKING_CODE_INVALID (no 500) — both when the
    pre-check sees the code and when it is bypassed (the ``ON CONFLICT DO NOTHING`` path of a race)."""
    shop, supplier, wh = await _setup(env, "SEC-08")
    water = await _product(env, shop, "Suv 0.5L", is_marked=True, marking_group_code="water_beverages")
    code = "0104780000000001215xyz\x1d93dGVz"
    line = [gr_line(water, "1.000", "100.0000", marking_codes=[code])]
    first, second = await asyncio.gather(
        env.client.post(
            GR, json={"supplier_id": supplier, "warehouse_id": str(wh), "doc_date": str(business_today()),
                      "lines": line}, headers=shop.h(branch=shop.branch_id),
        ),
        env.client.post(
            GR, json={"supplier_id": supplier, "warehouse_id": str(wh), "doc_date": str(business_today()),
                      "lines": line}, headers=shop.h(branch=shop.branch_id),
        ),
    )  # fmt: skip
    assert sorted([first.status_code, second.status_code]) == [201, 422], (first.text, second.text)
    loser = first if first.status_code == 422 else second
    assert err(loser) == "MARKING_CODE_INVALID"
    assert loser.json()["error"]["params"] == {"reason": "already_registered", "codes": [code]}

    repo = env.app.state.purchasing.goods_receipts.repo

    async def no_precheck(*_: Any) -> list[str]:
        return []

    original = repo.foreign_codes
    repo.foreign_codes = no_precheck  # force the INSERT … ON CONFLICT path
    try:
        raced = await create_receipt(env.client, shop, supplier, wh, line, expect=422)
    finally:
        repo.foreign_codes = original
    assert raced["error"]["code"] == "MARKING_CODE_INVALID"
    assert raced["error"]["params"] == {"reason": "already_registered", "codes": [code]}
    stored = await rows(env, shop.tenant_id, "SELECT code, status FROM app.marking_codes")
    assert [(r["code"], r["status"]) for r in stored] == [(code, "pending_verification")]
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.goods_receipts") == 1
