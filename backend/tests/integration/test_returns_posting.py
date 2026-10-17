"""``return.created`` (18 §7.1; 13 §2.5, §3.2a; US-M02-01…03; qaror #48) — QT-M02-01…08, QT-PERM-04."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.accounting.wiring import business_today
from tests.support.debts import customer, debt_sale, item, set_go_live
from tests.support.inventory import receive, set_method
from tests.support.sales import (
    D,
    Env,
    Pos,
    add_customer,
    bind_terminal,
    card_result,
    deliver,
    ledger_rows,
    make_pos,
    new_item,
    one,
    return_line,
    return_payload,
    rows,
    sale_line,
    sale_payload,
    sales_env_fixture,
    sell,
    sold_lines,
    sums,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


def _pin(user_id: object) -> dict[str, Any]:
    return {"mode": "local_pin", "approved_by": str(user_id), "pin_verified_locally": True}


async def _sold(env: Env, pos: Pos, product: Any, *, qty: str = "1.000", price: str = "12000.0000",
                payments: Any = None, **extra: Any) -> tuple[str, list[dict[str, Any]]]:  # fmt: skip
    payload = sale_payload(pos, [sale_line(product, qty=qty, price=price)], payments, **extra)
    await sell(env, pos, payload, actor="owner")
    return payload["id"], await sold_lines(env, pos, payload["id"])


async def test_qt_m02_01_return_with_receipt(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    product = await new_item(env, pos, stock="5.000", cost="8000.00")
    sale_id, lines = await _sold(env, pos, product)
    payload = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id)
    res = await deliver(env, pos, "return.created", payload)
    assert res.error is None, (res.code, res.keys)
    assert res.server["number"].startswith("V-") and res.server["money_part"] == "12000.00"
    totals = sums(await ledger_rows(env, pos, payload["id"]))
    assert totals == {
        ("9040", "5010"): D("10714.29"),
        ("6410", "5010"): D("1285.71"),
        ("2910", "9120"): D("8000.00"),
    }
    moves = await rows(
        env.db, pos.tenant_id, "SELECT qty, lot_id FROM app.stock_moves WHERE doc_id = :d", d=payload["id"]
    )
    issued = await rows(
        env.db, pos.tenant_id, "SELECT lot_id FROM app.stock_moves WHERE doc_id = :d", d=sale_id
    )
    assert [(m["qty"], m["lot_id"]) for m in moves] == [(D("1.000"), issued[0]["lot_id"])]
    cash = await rows(
        env.db, pos.tenant_id, "SELECT method, amount FROM app.cash_moves WHERE doc_id = :d", d=payload["id"]
    )
    assert cash == [{"method": "cash", "amount": D("-12000.00")}]
    receipt = await rows(env.db, pos.tenant_id, "SELECT kind, payment_form, payload FROM app.fiscal_receipts WHERE return_id = :d",
                         d=payload["id"])  # fmt: skip
    assert receipt[0]["kind"] == "return" and receipt[0]["payload"]["total"] == "12000.00"


async def test_qt_m02_02_no_receipt_always_needs_approval(env: Env) -> None:
    """Also QT-PERM-04 (``return_no_receipt`` regardless of the amount)."""
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    await _sold(env, pos, product)
    cheap = return_payload(pos, [return_line(product, price="10000.0000")])
    res = await deliver(env, pos, "return.created", cheap)
    assert res.error is not None and res.code in (
        "APPROVAL_INVALID",
        "APPROVAL_REQUIRED",
        "RETURN_LIMIT_EXCEEDED",
    )
    approved = return_payload(
        pos, [return_line(product, price="10000.0000")], approval=_pin(pos.shop.user_ids["manager"])
    )
    ok = await deliver(env, pos, "return.created", approved)
    assert ok.error is None, (ok.code, ok.keys)
    head = (
        await rows(
            env.db,
            pos.tenant_id,
            "SELECT sale_id, approved_by FROM app.returns WHERE id = :d",
            d=approved["id"],
        )
    )[0]
    assert head == {"sale_id": None, "approved_by": pos.shop.user_ids["manager"]}
    kinds = await rows(
        env.db, pos.tenant_id, "SELECT kind FROM app.doc_approvals WHERE doc_id = :d", d=approved["id"]
    )
    assert kinds == [{"kind": "return_no_receipt"}]


async def test_qt_perm_04_no_receipt_small_amount(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="10000.00", stock="5.000")
    await _sold(env, pos, product, price="10000.0000")
    res = await deliver(
        env, pos, "return.created", return_payload(pos, [return_line(product, price="10000.0000")])
    )
    assert res.error is not None
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.returns") == 0


async def test_qt_m02_03_within_limit_no_approval(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="100000.00", stock="2.000", cost="50000.00")
    sale_id, lines = await _sold(env, pos, product, price="100000.0000")
    payload = return_payload(
        pos, [return_line(product, sale_line_id=lines[0]["id"], price="100000.0000")], sale_id=sale_id
    )
    res = await deliver(env, pos, "return.created", payload)
    assert (
        res.error is None and await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.doc_approvals") == 0
    )


async def test_qt_m02_04_over_limit_needs_approval(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="150000.00", stock="2.000", cost="50000.00")
    sale_id, lines = await _sold(env, pos, product, price="150000.0000")
    line = return_line(product, sale_line_id=lines[0]["id"], price="150000.0000")
    res = await deliver(env, pos, "return.created", return_payload(pos, [line], sale_id=sale_id))
    assert res.code == "RETURN_LIMIT_EXCEEDED"
    ok = await deliver(env, pos, "return.created",
                       return_payload(pos, [line], sale_id=sale_id, approval=_pin(pos.shop.user_ids["manager"])))  # fmt: skip
    assert ok.error is None
    assert await one(env.db, pos.tenant_id, "SELECT kind FROM app.doc_approvals") == "return_over_limit"


async def test_qt_m02_05_original_sale_untouched_vat_reduced(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    sale_id, lines = await _sold(env, pos, product)
    before = await ledger_rows(env, pos, sale_id)
    payload = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id, refund_method="card",
                             refund_card={"card_entry_mode": "manual", "manual_reason": "standalone_terminal"})  # fmt: skip
    res = await deliver(env, pos, "return.created", payload)
    assert res.error is None, (res.code, res.keys)
    assert await ledger_rows(env, pos, sale_id) == before
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.ledger_entries WHERE reversal_of_id IS NOT NULL"
        )
        == 0
    )
    totals = sums(await ledger_rows(env, pos, payload["id"]))
    assert totals[("9040", "5710")] == D("10714.29") and totals[("6410", "5710")] == D("1285.71")
    vat = await rows(env.db, pos.tenant_id, "SELECT kind, base_amount, vat_amount FROM app.vat_moves WHERE doc_id = :d",
                     d=payload["id"])  # fmt: skip
    assert vat == [{"kind": "output", "base_amount": D("-10714.29"), "vat_amount": D("-1285.71")}]
    head = (await rows(env.db, pos.tenant_id, "SELECT card_entry_mode, manual_reason, rrn, card_mask FROM app.returns WHERE id = :d",
                       d=payload["id"]))[0]  # fmt: skip
    assert head == {
        "card_entry_mode": "manual",
        "manual_reason": "standalone_terminal",
        "rrn": None,
        "card_mask": None,
    }


async def test_qt_m02_06_marked_return_offline_rejected(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(
        env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages"
    )
    code = "0104600000000001215abcdefgh\x1d93AbCd"
    payload = sale_payload(pos, [sale_line(product, marking_code=code)])
    await sell(env, pos, payload)
    lines = await sold_lines(env, pos, payload["id"])
    line = return_line(product, sale_line_id=lines[0]["id"], marking_code=code)
    res = await deliver(
        env, pos, "return.created", return_payload(pos, [line], sale_id=payload["id"], is_offline=True)
    )
    assert res.code == "MARKING_RETURN_REQUIRES_ONLINE"
    online = await deliver(env, pos, "return.created", return_payload(pos, [line], sale_id=payload["id"]))
    assert online.error is None
    assert (
        await one(env.db, pos.tenant_id, "SELECT status FROM app.marking_codes WHERE code = :c", c=code)
        == "returned"
    )


async def test_qt_m02_07_expired_goods_return(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    product = await new_item(env, pos, stock=None)
    await receive(env, pos.shop, pos.warehouse_id, product, "3.000", "24000.00",
                  expiry=business_today() - timedelta(days=1))  # fmt: skip
    sale_id, lines = await _sold(env, pos, product)
    line = return_line(product, sale_line_id=lines[0]["id"])
    res = await deliver(env, pos, "return.created", return_payload(pos, [line], sale_id=sale_id))
    assert res.code == "APPROVAL_REQUIRED"
    payload = return_payload(pos, [line], sale_id=sale_id, approval=_pin(pos.shop.user_ids["manager"]))
    ok = await deliver(env, pos, "return.created", payload)
    assert ok.error is None, (ok.code, ok.keys)
    assert (
        await one(
            env.db,
            pos.tenant_id,
            "SELECT restock FROM app.return_lines WHERE return_id = :d",
            d=payload["id"],
        )
        is False
    )
    lot = (
        await rows(
            env.db,
            pos.tenant_id,
            "SELECT qty_left, blocked_qty FROM app.stock_lots WHERE product_id = :p",
            p=product,
        )
    )[0]
    assert lot == {"qty_left": D("3.000"), "blocked_qty": D("1.000")}
    wo = await rows(env.db, pos.tenant_id,
                    "SELECT w.id, w.status, l.reason, l.qty FROM app.write_offs w JOIN app.write_off_lines l "
                    "ON l.write_off_id = w.id WHERE w.source_return_id = :d", d=payload["id"])  # fmt: skip
    assert [(w["status"], w["reason"], w["qty"]) for w in wo] == [("draft", "expired_return", D("1.000"))]
    assert ok.server["write_off_id"] == str(wo[0]["id"])


async def test_qt_m02_qty_exceeded_and_sale_not_synced(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    sale_id, lines = await _sold(env, pos, product, qty="2.000")
    line = return_line(product, sale_line_id=lines[0]["id"], qty="3.000")
    assert (
        await deliver(env, pos, "return.created", return_payload(pos, [line], sale_id=sale_id))
    ).code == "RETURN_QTY_EXCEEDED"
    first = return_line(product, sale_line_id=lines[0]["id"], qty="1.000")
    assert (
        await deliver(env, pos, "return.created", return_payload(pos, [first], sale_id=sale_id))
    ).error is None
    rest = return_line(product, sale_line_id=lines[0]["id"], qty="2.000")
    assert (
        await deliver(env, pos, "return.created", return_payload(pos, [rest], sale_id=sale_id))
    ).code == "RETURN_QTY_EXCEEDED"
    unknown = await deliver(
        env,
        pos,
        "return.created",
        return_payload(pos, [first], sale_id="01999999-0000-7000-8000-000000000000"),
    )
    assert unknown.code == "SALE_NOT_FOUND"


async def test_qt_m02_last_return_takes_the_rest(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="1000.00", stock="5.000", cost="500.00")
    sale_id, lines = await _sold(env, pos, product, qty="3.000", price="333.3333")
    assert lines[0]["line_total"] == D("1000.00")
    refunds = []
    for _ in range(3):
        payload = return_payload(
            pos, [return_line(product, sale_line_id=lines[0]["id"], price="333.3333")], sale_id=sale_id
        )
        assert (await deliver(env, pos, "return.created", payload)).error is None
        refunds.append(
            await one(
                env.db,
                pos.tenant_id,
                "SELECT line_total FROM app.return_lines WHERE return_id = :d",
                d=payload["id"],
            )
        )
    assert refunds == [D("333.00"), D("333.00"), D("334.00")]


async def test_dod_05_return_cost_fifo_original_lot(env: Env) -> None:
    """13 §3.2a FIFO: the unit goes back to the original lot (reverse allocation order) at its unit cost."""
    pos = await make_pos(env, account="2910")
    await set_method(env, pos.shop, "fifo")
    product = await new_item(env, pos, stock=None)
    await receive(env, pos.shop, pos.warehouse_id, product, "1.000", "8000.00")
    await receive(env, pos.shop, pos.warehouse_id, product, "1.000", "9000.00")
    sale_id, lines = await _sold(env, pos, product, qty="2.000")
    payload = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id)
    assert (await deliver(env, pos, "return.created", payload)).error is None
    assert sums(await ledger_rows(env, pos, payload["id"]))[("2910", "9120")] == D("9000.00")


async def test_dod_05_return_cost_aveco(env: Env) -> None:
    """13 §3.2a AVECO: the return is valued at the original line's unit cost, not the current average."""
    pos = await make_pos(env, account="2910")
    await set_method(env, pos.shop, "aveco")
    product = await new_item(env, pos, stock=None)
    await receive(env, pos.shop, pos.warehouse_id, product, "100.000", "800000.00")
    await receive(env, pos.shop, pos.warehouse_id, product, "50.000", "450000.00")
    sale_id, lines = await _sold(env, pos, product, qty="120.000", price="12000.0000")
    assert sums(await ledger_rows(env, pos, sale_id))[("9120", "2910")] == D("1000000.00")
    await receive(env, pos.shop, pos.warehouse_id, product, "10.000", "120000.00")  # moves the average
    payload = return_payload(
        pos, [return_line(product, sale_line_id=lines[0]["id"], qty="3.000")], sale_id=sale_id
    )
    assert (await deliver(env, pos, "return.created", payload, actor="owner")).error is None
    assert sums(await ledger_rows(env, pos, payload["id"]))[("2910", "9120")] == D("25000.00")


async def test_qt_m02_debt_sale_return_reduces_debt_first(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    customer = await add_customer(env, pos)
    sale_id, lines = await _sold(
        env, pos, product, qty="2.000",
        payments=[{"method": "cash", "amount": "10000.00"}, {"method": "debt", "amount": "14000.00"}],
        counterparty_id=str(customer),
    )  # fmt: skip
    payload = return_payload(
        pos, [return_line(product, sale_line_id=lines[0]["id"], qty="2.000")], sale_id=sale_id
    )
    res = await deliver(env, pos, "return.created", payload)
    assert (
        res.error is None and res.server["debt_part"] == "14000.00" and res.server["money_part"] == "10000.00"
    )
    totals = sums(await ledger_rows(env, pos, payload["id"]))
    assert totals[("9040", "4010")] + totals[("6410", "4010")] == D("14000.00")
    assert totals[("9040", "5010")] + totals[("6410", "5010")] == D("10000.00")
    debt = await one(
        env.db, pos.tenant_id, "SELECT sum(amount) FROM app.debt_moves WHERE counterparty_id = :c", c=customer
    )
    assert debt == D("0.00")
    receipt_total = await one(env.db, pos.tenant_id, "SELECT payload->>'total' FROM app.fiscal_receipts WHERE return_id = :d",
                              d=payload["id"])  # fmt: skip
    assert receipt_total == "10000.00"


async def test_qt_m02_08_integrated_card_refund(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    terminal = await bind_terminal(env, pos)
    purchase = await card_result(pos, terminal, "12000.00")
    sale = sale_payload(pos, [sale_line(product)],
                        [{"method": "card", "amount": "12000.00", "card_entry_mode": "integrated", "card_result": purchase}])  # fmt: skip
    await sell(env, pos, sale)
    lines = await sold_lines(env, pos, sale["id"])
    refund = await card_result(
        pos, terminal, "12000.00", kind="refund", original=__import__("uuid").UUID(purchase["attempt_id"])
    )
    payload = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale["id"], refund_method="card",
                             refund_card={"card_entry_mode": "integrated", "card_result": refund})  # fmt: skip
    res = await deliver(env, pos, "return.created", payload)
    assert res.error is None, (res.code, res.keys, res.error and res.error.params)
    head = (await rows(env.db, pos.tenant_id, "SELECT card_entry_mode, card_terminal_transaction_id, rrn, card_mask FROM app.returns "
                       "WHERE id = :d", d=payload["id"]))[0]  # fmt: skip
    assert (
        head["card_entry_mode"] == "integrated"
        and str(head["card_terminal_transaction_id"]) == refund["attempt_id"]
    )
    assert head["rrn"] is not None and head["card_mask"] is not None
    manual = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale["id"], refund_method="card",
                            refund_card={"card_entry_mode": "manual", "manual_reason": "terminal_offline", "rrn": "123456"})  # fmt: skip
    rejected = await deliver(env, pos, "return.created", manual)
    assert rejected.code == "VALIDATION_ERROR" and rejected.keys == [
        "validation.card_manual_details_forbidden"
    ]


async def test_acc_02_return_keeps_the_sale_customer(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    customer_a = await add_customer(env, pos)
    customer_b = await add_customer(env, pos)
    sale_id, lines = await _sold(
        env,
        pos,
        product,
        payments=[{"method": "debt", "amount": "12000.00"}],
        counterparty_id=str(customer_a),
    )
    other = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id,
                           receipt_seq=None, counterparty_id=str(customer_b))  # fmt: skip
    res = await deliver(env, pos, "return.created", other)
    assert res.code == "VALIDATION_ERROR" and res.keys == ["validation.counterparty_mismatch"]
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.debt_moves WHERE counterparty_id = :c",
                     c=customer_b) == 0  # fmt: skip
    foreign_pos = await make_pos(env, "Boshqa do'kon")
    foreign = await add_customer(env, foreign_pos)
    no_receipt = return_payload(pos, [return_line(product)], refund_method="debt_adjustment", receipt_seq=None,
                                counterparty_id=str(foreign), approval=_pin(pos.shop.user_ids["manager"]))  # fmt: skip
    res = await deliver(env, pos, "return.created", no_receipt)
    assert res.code == "DEPENDENCY_NOT_SYNCED"
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.returns") == 0


async def test_acc_04_last_return_takes_the_vat_rest(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="1000.00", stock="5.000", cost="500.00")
    sale_id, lines = await _sold(env, pos, product, qty="3.000", price="333.3333")
    assert await one(
        env.db, pos.tenant_id, "SELECT vat_amount FROM app.sale_lines WHERE id = :i", i=lines[0]["id"]
    ) == D("107.14")
    ids = []
    for _ in range(3):
        payload = return_payload(
            pos, [return_line(product, sale_line_id=lines[0]["id"], price="333.3333")], sale_id=sale_id
        )
        assert (await deliver(env, pos, "return.created", payload)).error is None
        ids.append(payload["id"])
    vats = await rows(env.db, pos.tenant_id, "SELECT vat_amount FROM app.return_lines ORDER BY vat_amount")
    assert sum(v["vat_amount"] for v in vats) == D("107.14")
    net = await one(env.db, pos.tenant_id, "SELECT sum(vat_amount) FROM app.vat_moves")
    assert net == D("0.00")
    entries = [e for i in [sale_id, *ids] for e in await ledger_rows(env, pos, i)]
    vat_net = sum(e[2] for e in entries if e[1] == "6410") - sum(e[2] for e in entries if e[0] == "6410")
    assert vat_net == D("0.00")


async def _receivable(env: Env, pos: Pos, cid: Any) -> D:
    value = await one(env.db, pos.tenant_id, "SELECT COALESCE(sum(balance), 0) FROM app.debt_balances "
                      "WHERE counterparty_id = :c AND direction = 'receivable'", c=cid)  # fmt: skip
    return D(value)


async def _ledger_4010(env: Env, pos: Pos, cid: Any) -> D:
    value = await one(
        env.db, pos.tenant_id,
        "SELECT COALESCE(sum(CASE WHEN account_dt = '4010' THEN amount ELSE -amount END), 0) FROM "
        "app.ledger_entries WHERE '4010' IN (account_dt, account_kt) AND analytics->>'counterparty_id' = :c",
        c=str(cid),
    )  # fmt: skip
    return D(value)


async def test_acc04_return_of_written_off_sale_refused(env: Env) -> None:
    """ACC-04 (13 §2.5, §2.15; FOUNDER F2): a return may only shrink the still-open part of a sale whose debt
    was partly written off — beyond it the return is refused for every ``refund_method``."""
    pos = await make_pos(env, account="2910")
    await set_go_live(env, pos, business_today().replace(day=1))
    cid = await customer(env, pos)
    product = await item(env, pos, "12000.0000")
    sale = await debt_sale(env, pos, cid, [(product, "2.000", "12000.0000")])
    created = await env.client.post(
        "/api/v1/debt-writeoffs", json={"counterparty_id": str(cid), "amount": "12000.00", "reason": "umidsiz"},
        headers=pos.shop.h("owner"),
    )  # fmt: skip
    assert created.status_code in (200, 201), created.text
    posted = await env.client.post(
        f"/api/v1/debt-writeoffs/{created.json()['id']}/post", headers=pos.shop.h("owner")
    )
    assert posted.status_code == 200, posted.text
    assert await _receivable(env, pos, cid) == D("12000.00")
    lines = await sold_lines(env, pos, sale["id"])
    # inside the still-open part (24000 − 12000 written off): unaffected, the debt part takes it
    fits = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale["id"],
                          receipt_seq=None)  # fmt: skip
    ok = await deliver(env, pos, "return.created", fits, actor="owner")
    assert ok.error is None, (ok.code, ok.keys)
    assert ok.server["debt_part"] == "12000.00" and ok.server["money_part"] == "0.00"
    assert await _receivable(env, pos, cid) == D("0.00")
    # the rest of the sale was written off: refused whatever the refund method
    for method, seq in (("cash", "auto"), ("debt_adjustment", None)):
        over = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale["id"],
                              refund_method=method, receipt_seq=seq)  # fmt: skip
        res = await deliver(env, pos, "return.created", over, actor="owner")
        assert res.code == "VALIDATION_ERROR", (method, res.code, res.keys)
        assert res.fields == ["sale_id"] and res.keys == ["validation.sale_debt_written_off"], method
    assert await _receivable(env, pos, cid) == D("0.00")
    assert await _receivable(env, pos, cid) == await _ledger_4010(env, pos, cid)
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.returns WHERE sale_id = :s",
                     s=sale["id"]) == 1  # fmt: skip


async def _lock_waiters(env: Env, pos: Pos) -> int:
    found = await one(env.db, pos.tenant_id, "SELECT count(*) FROM pg_stat_activity "
                      "WHERE datname = current_database() AND wait_event_type = 'Lock'")  # fmt: skip
    return int(found)


async def test_sync01_return_reads_sale_debt_under_debt_lock(env: Env) -> None:
    """SYNC-01 (23 §2.1: stock → debt): a second transaction holds the customer's ``debt_balances`` row and
    closes the sale's debt by a bank payment while the return is delivered. The return must read the sale's
    open debt only after that commit: ``debt_part = 0`` and the balance never goes negative."""
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="5.000")
    cid = await add_customer(env, pos)
    sale_id, lines = await _sold(
        env, pos, product, qty="2.000",
        payments=[{"method": "cash", "amount": "20000.00"}, {"method": "debt", "amount": "4000.00"}],
        counterparty_id=str(cid),
    )  # fmt: skip
    assert await _receivable(env, pos, cid) == D("4000.00")
    owner = pos.shop.user_ids["owner"]
    payment_id = uuid7()
    payload = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale_id)
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id, user_id=owner):
        await s.execute(
            text("SELECT balance FROM app.debt_balances WHERE counterparty_id = :c "
                 "AND direction = 'receivable' FOR UPDATE"), {"c": cid},
        )  # fmt: skip
        returning = asyncio.create_task(deliver(env, pos, "return.created", payload))
        for _ in range(200):  # the return reaches the debt lock and waits on it
            if returning.done() or await _lock_waiters(env, pos) > 0:
                break
            await asyncio.sleep(0.05)
        assert not returning.done(), returning.result().code
        # the concurrent bank payment closes the sale's debt (the rows DebtPaymentService writes, 13 §2.14)
        await s.execute(
            text("INSERT INTO app.debt_payments (id, tenant_id, branch_id, doc_date, status, counterparty_id, "
                 "method, amount, created_by, posted_at) VALUES (:id, :t, :b, :d, 'posted', :c, 'bank', 4000, "
                 ":u, now())"),
            {"id": payment_id, "t": pos.tenant_id, "b": pos.branch_id, "d": business_today(), "c": cid,
             "u": owner},
        )  # fmt: skip
        await s.execute(
            text("INSERT INTO app.debt_payment_allocations (tenant_id, debt_payment_id, target_doc_type, "
                 "target_doc_id, amount) VALUES (:t, :p, 'sales', :s, 4000)"),
            {"t": pos.tenant_id, "p": payment_id, "s": sale_id},
        )  # fmt: skip
        await s.execute(
            text("INSERT INTO app.debt_moves (tenant_id, counterparty_id, direction, amount, doc_type, doc_id) "
                 "VALUES (:t, :c, 'receivable', -4000, 'debt_payments', :p)"),
            {"t": pos.tenant_id, "c": cid, "p": payment_id},
        )  # fmt: skip
        await s.execute(
            text("UPDATE app.debt_balances SET balance = balance - 4000 WHERE counterparty_id = :c "
                 "AND direction = 'receivable'"), {"c": cid},
        )  # fmt: skip
    res = await asyncio.wait_for(returning, timeout=30)
    assert res.error is None, (res.code, res.keys)
    assert res.server["debt_part"] == "0.00" and res.server["money_part"] == "12000.00"
    assert await _receivable(env, pos, cid) == D("0.00")
    moves = await one(env.db, pos.tenant_id, "SELECT COALESCE(sum(amount), 0) FROM app.debt_moves "
                      "WHERE counterparty_id = :c", c=cid)  # fmt: skip
    assert moves == D("0.00")
