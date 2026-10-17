"""Bosqich 4 fix round — FX-debts (ACC-01, ACC-02 debts part, SEC-01, SYNC-03; review/ACCEPTED.md).

* ACC-01 — a sale line returned against the debt leaves the debt receipt: the payment fiscalizes the kept goods;
* ACC-02 — the open documents are reconciled to ``debt_balances`` (a ``debt_adjustment`` credit without a
  document closes the oldest debt): the online limit, the offline excess (``Kt 6310``) and the pull rows;
* SEC-01 — the debt ledger and the aging report honour the branch scope;
* SYNC-03 — a receipt the server fiscalizes is built from the SERVER allocation, never from device lines.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.session import tenant_transaction
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
from tests.support.inventory import add_branch
from tests.support.sales import (
    deliver,
    make_pos,
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


async def _pos(env: Env) -> Pos:
    return await make_pos(env, account="2910")


async def _balance(env: Env, pos: Pos, cid: Any) -> D:
    value = await one(
        env.db,
        pos.tenant_id,
        "SELECT COALESCE(sum(balance), 0) FROM app.debt_balances WHERE counterparty_id = :c "
        "AND direction = 'receivable'",
        c=cid,
    )
    return D(value)


async def _settled(env: Env, pos: Pos, sale_id: str) -> list[D]:
    found = await rows(
        env.db,
        pos.tenant_id,
        "SELECT settled_amount FROM app.sale_lines WHERE sale_id = :s ORDER BY line_no",
        s=sale_id,
    )
    return [r["settled_amount"] for r in found]


async def _receipt_items(env: Env, pos: Pos, payment_id: str) -> list[dict[str, Any]]:
    payload = await one(
        env.db,
        pos.tenant_id,
        "SELECT payload FROM app.fiscal_receipts WHERE debt_payment_id = :p",
        p=payment_id,
    )
    items: list[dict[str, Any]] = payload["items"]
    return items


async def _credit_by_debt_adjustment(env: Env, pos: Pos, cid: UUID, amount: str) -> None:
    """A cash sale (no debt) of ``amount`` to the customer, returned with ``refund_method='debt_adjustment'``:
    ``Kt 4010`` with no open document — the customer's balance drops by ``amount`` (13 §2.5)."""
    product = await item(env, pos, f"{amount}00")
    line = sale_line(product, qty="1.000", price=f"{amount}00")
    sale = sale_payload(pos, [line], [{"method": "cash", "amount": amount}], counterparty_id=str(cid))
    await sell(env, pos, sale)
    lines = await sold_lines(env, pos, sale["id"])
    ret = return_payload(
        pos,
        [return_line(product, sale_line_id=lines[0]["id"], price=f"{amount}00")],
        sale_id=sale["id"],
        refund_method="debt_adjustment",
        receipt_seq=None,
    )
    res = await deliver(env, pos, "return.created", ret, actor="owner")
    assert res.error is None, (res.error.code, res.error.params, res.error.details) if res.error else None


# --- ACC-01 ---------------------------------------------------------------------------------------------
async def test_acc01_pay_after_return_fiscalizes_kept_goods_only(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "60000.0000")
    b = await item(env, pos, "40000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "60000.0000"), (b, "1.000", "40000.0000")])
    lines = await sold_lines(env, pos, sale["id"])
    ret = return_payload(  # the whole return goes to the open debt: no money part, no receipt
        pos,
        [return_line(b, sale_line_id=lines[1]["id"], price="40000.0000")],
        sale_id=sale["id"],
        receipt_seq=None,
    )
    res = await deliver(env, pos, "return.created", ret, actor="owner")
    assert res.error is None, (res.error.code, res.error.details) if res.error else None
    assert await _balance(env, pos, cid) == D("60000.00")

    (doc,) = await open_docs(env, pos, cid)
    assert doc["open_amount"] == "60000.00"
    assert [(ln["returned_qty"], ln["returned_amount"]) for ln in doc["lines"]] == [
        ("0.000", "0.00"),
        ("1.000", "40000.00"),
    ]
    payload = debt_payment(pos, cid, "60000.00", [doc])
    assert [(ln["sale_line_id"], ln["amount"], ln["qty"]) for ln in payload["fiscal_lines"]] == [
        (str(lines[0]["id"]), "60000.00", "1.000")
    ]
    paid = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert paid.error is None, (paid.error.code, paid.error.details) if paid.error else None
    assert paid.server["remaining_balance"] == "0.00"
    items = await _receipt_items(env, pos, payload["id"])
    assert [(i["sale_line_id"], i["amount"], i["qty"]) for i in items] == [
        (str(lines[0]["id"]), "60000.00", "1.000")
    ]
    assert await _settled(env, pos, sale["id"]) == [D("60000.00"), D("0.00")]


# --- ACC-02 ---------------------------------------------------------------------------------------------
async def test_acc02_payment_limit_uses_reconciled_open_docs(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "50000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "50000.0000")])
    await _credit_by_debt_adjustment(env, pos, cid, "20000.00")
    assert await _balance(env, pos, cid) == D("30000.00")

    (doc,) = await open_docs(env, pos, cid)  # the pull row is already reconciled
    assert (doc["doc_id"], doc["open_amount"]) == (sale["id"], "30000.00")

    online = debt_payment(pos, cid, "50000.00", [{**doc, "open_amount": "50000.00"}])
    res = await deliver_debt(env, pos, "debt_payment.created", online)
    assert res.error is not None and res.error.message_key == "errors.debt_payment_exceeds_balance"
    assert res.error.params["balance"] == "30000.00"

    bank = await env.client.post(
        f"{API}/debt-payments",
        json={"counterparty_id": str(cid), "amount": "50000.00", "method": "bank"},
        headers=pos.shop.h("owner"),
    )
    assert bank.status_code == 422, bank.text

    offline = debt_payment(pos, cid, "50000.00", [{**doc, "open_amount": "50000.00"}], is_offline=True)
    res = await deliver_debt(env, pos, "debt_payment.created", offline)
    assert res.error is None, (res.error.code, res.error.details) if res.error else None
    assert res.server["allocations"] == [
        {"target_doc_type": "sales", "target_doc_id": sale["id"], "amount": "30000.00"}
    ]
    assert res.server["unallocated_amount"] == "20000.00"
    assert res.server["remaining_balance"] == "0.00"
    assert await ledger(env, pos, offline["id"]) == {
        ("5010", "4010"): D("30000.00"),
        ("5010", "6310"): D("20000.00"),
    }
    assert await _balance(env, pos, cid) == D("0.00")
    assert await open_docs(env, pos, cid) == []


async def test_acc02_ledger_and_aging_show_reconciled_open_amounts(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "50000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "50000.0000")])
    await _credit_by_debt_adjustment(env, pos, cid, "20000.00")
    book = await env.client.get(
        f"{API}/counterparties/{cid}/debt-ledger", headers=pos.shop.h("owner", key=None)
    )
    assert book.status_code == 200, book.text
    row = next(e for e in book.json()["entries"] if e["doc_id"] == sale["id"])
    assert (row["open_amount"], row["status"]) == ("30000.00", "partially_paid")
    aging = await env.client.get(f"{API}/reports/debts-aging", headers=pos.shop.h("owner", key=None))
    assert aging.status_code == 200, aging.text
    (mine,) = [r for r in aging.json()["rows"] if r["counterparty_id"] == str(cid)]
    assert mine["balance"] == "30000.00"


# --- SEC-01 ---------------------------------------------------------------------------------------------
async def _restrict(env: Env, pos: Pos, role: str, branch: UUID) -> None:
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await s.execute(
            text("UPDATE app.memberships SET branch_ids = ARRAY[CAST(:b AS uuid)] WHERE user_id = :u"),
            {"b": str(branch), "u": pos.shop.user_ids[role]},
        )


async def test_sec01_aging_and_ledger_respect_branch_scope(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "70000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "70000.0000")])
    other, _ = await add_branch(env, pos.shop, "02", "Ikkinchi")
    h = pos.shop.h("manager", key=None)

    # the manager sees only branch 02: nothing of the branch-01 debt
    await _restrict(env, pos, "manager", other)
    denied = await env.client.get(
        f"{API}/reports/debts-aging", params={"branch_id": str(pos.branch_id)}, headers=h
    )
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"
    aging = await env.client.get(f"{API}/reports/debts-aging", headers=h)
    assert aging.status_code == 200, aging.text
    assert [r for r in aging.json()["rows"] if r["counterparty_id"] == str(cid)] == []
    book = await env.client.get(f"{API}/counterparties/{cid}/debt-ledger", headers=h)
    assert book.status_code == 200, book.text
    body = book.json()
    assert body["entries"] == [] and body["balance"] == "0.00"
    assert body["counterparty"]["receivable_balance"] == "0.00"

    # restricted to branch 01 — the same figures as an unrestricted user
    await _restrict(env, pos, "manager", pos.branch_id)
    aging = await env.client.get(f"{API}/reports/debts-aging", headers=h)
    (row,) = [r for r in aging.json()["rows"] if r["counterparty_id"] == str(cid)]
    assert row["balance"] == "70000.00"
    book = await env.client.get(f"{API}/counterparties/{cid}/debt-ledger", headers=h)
    assert [e["doc_id"] for e in book.json()["entries"]] == [sale["id"]]
    assert book.json()["balance"] == "70000.00"


# --- SYNC-03 --------------------------------------------------------------------------------------------
async def test_sync03_server_fiscalized_receipt_uses_server_allocation(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    stranger = await customer(env, pos, name="Begona")
    a = await item(env, pos, "40000.0000", name="Shakar")
    x = await item(env, pos, "40000.0000", name="Begona tovar")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "40000.0000")])
    foreign = await debt_sale(env, pos, stranger, [(x, "1.000", "40000.0000")])
    foreign_line = (await sold_lines(env, pos, foreign["id"]))[0]
    own_line = (await sold_lines(env, pos, sale["id"]))[0]

    payload = debt_payment(pos, cid, "40000.00", await open_docs(env, pos, cid))
    # the device lies about the goods: another customer's sale line on this customer's receipt
    payload["fiscal_lines"] = [
        {**payload["fiscal_lines"][0], "sale_id": foreign["id"], "sale_line_id": str(foreign_line["id"])}
    ]
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None, (res.error.code, res.error.details) if res.error else None
    assert "debt_allocation_mismatch" in res.exception_kinds
    items = await _receipt_items(env, pos, payload["id"])
    assert [(i["sale_id"], i["sale_line_id"], i["name"]) for i in items] == [
        (sale["id"], str(own_line["id"]), "Shakar")
    ]
    assert await _settled(env, pos, sale["id"]) == [D("40000.00")]
    assert await _settled(env, pos, foreign["id"]) == [D("0.00")]


async def test_acc02_cash_movement_out_on_4010_settles_debt_adjustment_credit(env: Env) -> None:
    """The money of a ``debt_adjustment`` credit is paid back with a 4010 ``out`` cash movement; its
    documents carry number/date/author in the debt ledger (``INFO_TABLES`` += ``cash_movements``)."""
    pos = await _pos(env)
    cid = await customer(env, pos)
    await _credit_by_debt_adjustment(env, pos, cid, "12000.00")
    assert await _balance(env, pos, cid) == D("-12000.00")
    body = {
        "cash_register_id": str(pos.register_id),
        "shift_id": str(pos.shift_id),
        "direction": "out",
        "reason": "other",
        "account": "4010",
        "counterparty_id": str(cid),
        "amount": "12000.00",
        "comment": "Ortiqcha to'lov qaytarildi",
        "doc_date": business_today().isoformat(),
    }
    created = await env.client.post(f"{API}/cash-movements", json=body, headers=pos.shop.h("owner"))
    assert created.status_code in (200, 201), created.text
    assert await _balance(env, pos, cid) == D("0.00")
    book = await env.client.get(
        f"{API}/counterparties/{cid}/debt-ledger", headers=pos.shop.h("owner", key=None)
    )
    row = next(e for e in book.json()["entries"] if e["doc_type"] == "cash_movements")
    assert row["doc_date"] == business_today().isoformat() and row["created_by"] is not None
