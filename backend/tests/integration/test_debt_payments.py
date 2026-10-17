"""Debt payments — POS ``debt_payment.created`` (18 §12.2) and back-office ``/debt-payments`` (18 §12.3, §12.5a);
13 §2.14; 16 §5; qaror #30, #45, #67. QT-M08-06/07/11/15/16/17/18 + B4-T08 (written-off debt → Kt 9390)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.modules.accounting.wiring import business_today
from tests.support.debts import (
    API,
    D,
    Env,
    Pos,
    customer,
    debt_payment,
    debt_sale,
    deliver_debt,
    item,
    ledger,
    one,
    open_docs,
    rows,
)
from tests.support.sales import fiscalize, make_pos, sales_env_fixture

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def _pos(env: Env) -> Pos:
    return await make_pos(env, account="2910")


async def _balance(env: Env, pos: Pos, cid: Any) -> D:
    value = await one(
        env.db,
        pos.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'receivable'",
        c=cid,
    )
    return D(value)


async def _receipt(env: Env, pos: Pos, payment_id: str) -> dict[str, Any]:
    found = await rows(
        env.db,
        pos.tenant_id,
        "SELECT kind, status, payload, receipt_seq, cash_register_id, shift_id, payment_form FROM app.fiscal_receipts "
        "WHERE debt_payment_id = :p",
        p=payment_id,
    )
    assert len(found) == 1
    return found[0]


async def test_qt_m08_06_full_cash_payment_closes_the_debt(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos, limit="500000.00")
    a = await item(env, pos, "200000.0000")
    b = await item(env, pos, "100000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "200000.0000"), (b, "1.000", "100000.0000")])
    assert await _balance(env, pos, cid) == D("300000.00")
    payload = debt_payment(pos, cid, "300000.00", await open_docs(env, pos, cid))
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None, (res.error.code, res.error.params, res.error.details) if res.error else None
    assert res.server["remaining_balance"] == "0.00" and res.server["unallocated_amount"] == "0.00"
    moves = await rows(
        env.db,
        pos.tenant_id,
        "SELECT direction, amount FROM app.debt_moves WHERE doc_id = :d",
        d=payload["id"],
    )
    assert moves == [{"direction": "receivable", "amount": D("-300000.00")}]
    assert await ledger(env, pos, payload["id"]) == {("5010", "4010"): D("300000.00")}
    receipt = await _receipt(env, pos, payload["id"])
    assert (receipt["kind"], receipt["status"], receipt["payment_form"]) == (
        "debt_settlement",
        "pending",
        "cash",
    )
    assert receipt["receipt_seq"] == payload["receipt_seq"] and receipt["shift_id"] == pos.shift_id
    items = receipt["payload"]["items"]
    assert [i["amount"] for i in items] == ["200000.00", "100000.00"]
    assert {i["sale_id"] for i in items} == {sale["id"]}
    settled = await rows(
        env.db,
        pos.tenant_id,
        "SELECT settled_amount, line_total FROM app.sale_lines WHERE sale_id = :s",
        s=sale["id"],
    )
    assert all(r["settled_amount"] == r["line_total"] for r in settled)
    cash = await rows(
        env.db, pos.tenant_id, "SELECT amount, method FROM app.cash_moves WHERE doc_id = :d", d=payload["id"]
    )
    assert cash == [{"amount": D("300000.00"), "method": "cash"}]
    assert await fiscalize(env, pos) >= 1


async def test_qt_m08_07_partial_payment_keeps_the_rest(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "150000.0000")
    await debt_sale(env, pos, cid, [(a, "2.000", "150000.0000")])
    payload = debt_payment(pos, cid, "100000.00", await open_docs(env, pos, cid))
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None
    assert res.server["remaining_balance"] == "200000.00"
    assert await _balance(env, pos, cid) == D("200000.00")
    receipt = await _receipt(env, pos, payload["id"])
    assert receipt["payload"]["total"] == "100000.00"
    assert [(i["qty"], i["amount"]) for i in receipt["payload"]["items"]] == [("0.667", "100000.00")]


async def test_qt_m08_11_payment_allocated_oldest_first(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "100000.0000")
    b = await item(env, pos, "200000.0000")
    old = await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")], due="2026-01-10")
    new = await debt_sale(env, pos, cid, [(b, "1.000", "200000.0000")])
    payload = debt_payment(pos, cid, "100000.00", await open_docs(env, pos, cid))
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None
    allocs = await rows(
        env.db,
        pos.tenant_id,
        "SELECT target_doc_type, target_doc_id, amount FROM app.debt_payment_allocations WHERE debt_payment_id = :p",
        p=payload["id"],
    )
    assert [(a["target_doc_type"], str(a["target_doc_id"]), a["amount"]) for a in allocs] == [
        ("sales", old["id"], D("100000.00"))
    ]
    docs = await open_docs(env, pos, cid)
    assert [(d["doc_id"], d["open_amount"]) for d in docs] == [(new["id"], "200000.00")]


async def test_qt_m08_15_online_overpayment_rejected(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "300000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "300000.0000")])
    docs = await open_docs(env, pos, cid)
    payload = debt_payment(pos, cid, "350000.00", docs)
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.code == "VALIDATION_ERROR"
    assert res.error is not None and res.error.message_key == "errors.debt_payment_exceeds_balance"
    assert res.error.params["balance"] == "300000.00" and res.error.params["requested"] == "350000.00"
    for table in ("debt_payments", "fiscal_receipts"):
        assert (
            await one(
                env.db,
                pos.tenant_id,
                f"SELECT count(*) FROM app.{table} WHERE "
                + ("id" if table == "debt_payments" else "debt_payment_id")
                + " = :p",
                p=payload["id"],
            )
            == 0
        )
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.debt_moves WHERE doc_id = :p", p=payload["id"]
        )
        == 0
    )
    ok = await deliver_debt(env, pos, "debt_payment.created", debt_payment(pos, cid, "300000.00", docs))
    assert ok.error is None and ok.server["remaining_balance"] == "0.00"


async def test_qt_m08_16_offline_allocation_receipt_lines_and_mismatch(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    p1, p2, p3 = (
        await item(env, pos, "100000.0000"),
        await item(env, pos, "70001.0000"),
        await item(env, pos, "59998.0000"),
    )
    sale_a = await debt_sale(env, pos, cid, [(p1, "3.000", "100000.0000")], due="2026-01-05")
    sale_b = await debt_sale(
        env, pos, cid, [(p2, "1.000", "70001.0000"), (p3, "1.000", "59998.0000"), (p2, "1.000", "70001.0000")]
    )
    cache = await open_docs(env, pos, cid)
    assert [d["doc_id"] for d in cache] == [sale_a["id"], sale_b["id"]]  # A has the early due date
    # the device builds its payment from the cache; meanwhile another device pays 100 000 on A
    offline = debt_payment(pos, cid, "350000.00", cache, is_offline=True)
    assert offline["allocations"] == [
        {"target_doc_type": "sales", "target_doc_id": sale_a["id"], "amount": "300000.00"},
        {"target_doc_type": "sales", "target_doc_id": sale_b["id"], "amount": "50000.00"},
    ]
    b_lines = [ln for ln in offline["fiscal_lines"] if ln["sale_id"] == sale_b["id"]]
    assert [ln["amount"] for ln in b_lines] == ["17500.25", "14999.50", "17500.25"]
    assert sum(D(ln["amount"]) for ln in offline["fiscal_lines"]) == D("350000.00")
    other = debt_payment(pos, cid, "100000.00", cache)
    assert (await deliver_debt(env, pos, "debt_payment.created", other)).error is None
    res = await deliver_debt(env, pos, "debt_payment.created", offline)
    assert res.error is None, res.error and (res.error.code, res.error.details)
    assert res.server["allocations"] == [
        {"target_doc_type": "sales", "target_doc_id": sale_a["id"], "amount": "200000.00"},
        {"target_doc_type": "sales", "target_doc_id": sale_b["id"], "amount": "150000.00"},
    ]
    mismatch = [e for e in res.result.sync_exceptions if e.kind == "debt_allocation_mismatch"]  # type: ignore[union-attr]
    assert len(mismatch) == 1
    assert mismatch[0].details["server"] == res.server["allocations"]
    assert [d["amount"] for d in mismatch[0].details["device"]] == ["300000.00", "50000.00"]
    # SYNC-03: the server fiscalizes (no fiscal_result) — the receipt carries the SERVER lines
    assert mismatch[0].details["server_fiscal_lines"] != offline["fiscal_lines"]
    receipt = await _receipt(env, pos, offline["id"])
    assert [(i["sale_line_id"], i["amount"]) for i in receipt["payload"]["items"]] == [
        (ln["sale_line_id"], ln["amount"]) for ln in mismatch[0].details["server_fiscal_lines"]
    ]
    assert sum(D(i["amount"]) for i in receipt["payload"]["items"]) == D("350000.00")
    settled_b = await rows(
        env.db,
        pos.tenant_id,
        "SELECT settled_amount FROM app.sale_lines WHERE sale_id = :s ORDER BY line_no",
        s=sale_b["id"],
    )
    assert sum(r["settled_amount"] for r in settled_b) == D(
        "150000.00"
    )  # server allocation, not the device one
    assert await ledger(env, pos, offline["id"]) == {("5010", "4010"): D("350000.00")}
    assert await _balance(env, pos, cid) == D("50000.00")


async def test_qt_m08_17_offline_overpayment_goes_to_6310(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "300000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "300000.0000")])
    payload = debt_payment(pos, cid, "350000.00", await open_docs(env, pos, cid), is_offline=True)
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None
    assert res.server["unallocated_amount"] == "50000.00"
    assert await one(
        env.db,
        pos.tenant_id,
        "SELECT unallocated_amount FROM app.debt_payments WHERE id = :p",
        p=payload["id"],
    ) == D("50000.00")
    assert await ledger(env, pos, payload["id"]) == {
        ("5010", "4010"): D("300000.00"),
        ("5010", "6310"): D("50000.00"),
    }
    adv = await rows(
        env.db,
        pos.tenant_id,
        "SELECT analytics FROM app.ledger_entries WHERE doc_id = :d AND account_kt = '6310'",
        d=payload["id"],
    )
    assert adv[0]["analytics"]["counterparty_id"] == str(cid)
    assert "debt_overpayment_offline" in res.exception_kinds
    events = await rows(
        env.db,
        pos.tenant_id,
        "SELECT payload FROM app.outbox_jobs WHERE kind = 'telegram' AND idempotency_key = :k",
        k=f"debt_overpayment_offline:{payload['id']}",
    )
    assert events and events[0]["payload"]["reason"] == "debt_overpayment_offline"
    assert await _balance(env, pos, cid) == D("0.00")


async def test_qt_m08_18_backoffice_payment_bank_only(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "300000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "300000.0000")])
    body = {
        "counterparty_id": str(cid),
        "branch_id": str(pos.branch_id),
        "amount": "100000.00",
        "method": "cash",
        "doc_date": business_today().isoformat(),
    }
    bad = await env.client.post(f"{API}/debt-payments", json=body, headers=pos.shop.h("owner"))
    assert bad.status_code == 422, bad.text
    err = bad.json()["error"]
    assert err["params"]["field"] == "method"
    assert err["details"][0]["message_key"] == "validation.debt_payment_backoffice_bank_only"
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.debt_payments") == 0
    created = await env.client.post(
        f"{API}/debt-payments", json=body | {"method": "bank"}, headers=pos.shop.h("owner")
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    posted = await env.client.post(f"{API}/debt-payments/{pid}/post", headers=pos.shop.h("owner"))
    assert posted.status_code == 200, posted.text
    doc = posted.json()
    assert doc["status"] == "posted" and doc["number"].startswith("DP-")
    assert (doc["cash_register_id"], doc["shift_id"], doc["receipt_seq"], doc["fiscal_receipt"]) == (
        None,
        None,
        None,
        None,
    )
    assert await ledger(env, pos, pid) == {("5110", "4010"): D("100000.00")}
    assert (
        await one(
            env.db,
            pos.tenant_id,
            "SELECT count(*) FROM app.fiscal_receipts WHERE debt_payment_id = :p",
            p=pid,
        )
        == 0
    )
    # the POS cash payment issues the debt_settlement receipt on the register/shift (48 h timer of that register)
    pos_pay = debt_payment(pos, cid, "50000.00", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", pos_pay)).error is None
    receipt = await _receipt(env, pos, pos_pay["id"])
    assert (receipt["cash_register_id"], receipt["shift_id"], receipt["receipt_seq"]) == (
        pos.register_id,
        pos.shift_id,
        pos_pay["receipt_seq"],
    )
    over = await env.client.post(
        f"{API}/debt-payments",
        json=body | {"method": "bank", "amount": "150000.01"},
        headers=pos.shop.h("owner"),
    )
    assert (
        over.status_code == 422
        and over.json()["error"]["message_key"] == "errors.debt_payment_exceeds_balance"
    )


async def test_backoffice_payment_cancel_storno_and_pos_payment_not_cancellable(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "100000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    body = {
        "counterparty_id": str(cid),
        "branch_id": str(pos.branch_id),
        "amount": "40000.00",
        "method": "bank",
        "doc_date": business_today().isoformat(),
        "promise_date": "2030-01-01",
    }
    pid = (await env.client.post(f"{API}/debt-payments", json=body, headers=pos.shop.h("owner"))).json()["id"]
    await env.client.post(f"{API}/debt-payments/{pid}/post", headers=pos.shop.h("owner"))
    assert await _balance(env, pos, cid) == D("60000.00")
    assert await one(
        env.db, pos.tenant_id, "SELECT debt_due_date FROM app.counterparties WHERE id = :c", c=cid
    ) == date(2030, 1, 1)
    cancel = await env.client.post(
        f"{API}/debt-payments/{pid}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 200 and cancel.json()["status"] == "cancelled"
    assert await _balance(env, pos, cid) == D("100000.00")
    assert await ledger(env, pos, pid) == {("5110", "4010"): D("40000.00"), ("4010", "5110"): D("40000.00")}
    again = await env.client.post(
        f"{API}/debt-payments/{pid}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "DOC_INVALID_STATE"
    pos_pay = debt_payment(pos, cid, "10000.00", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", pos_pay)).error is None
    refused = await env.client.post(
        f"{API}/debt-payments/{pos_pay['id']}/cancel", json={"reason": "x"}, headers=pos.shop.h("owner")
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["params"]["reason"] == "pos_fiscal_receipt"
    listed = await env.client.get(
        f"{API}/debt-payments", params={"counterparty_id": str(cid)}, headers=pos.shop.h("owner", key=None)
    )
    assert listed.status_code == 200 and len(listed.json()["items"]) == 2
