"""Debt balances stay equal to the 4010 ledger across other modules' documents (B4 follow-ups):

* a return of a written-off debt sale above its still-open debt is refused (``validation.sale_debt_written_off``,
  ACC-04 / F2) instead of reducing the receivable a second time;
* a cash movement on account 4010 for a customer is only ``out`` up to his 4010 credit (13 §2.18, ACC-02) — the
  money back of a ``debt_adjustment`` credit; it moves ``debt_balances`` too, and its cancel reverses it;
* the open documents of a customer always sum to his balance (ACC-02 reconcile invariant).
"""

from __future__ import annotations

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
    one,
    open_docs,
    set_go_live,
)
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


async def _balance(env: Env, pos: Pos, cid: Any) -> D:
    value = await one(
        env.db,
        pos.tenant_id,
        "SELECT COALESCE(sum(balance), 0) FROM app.debt_balances WHERE counterparty_id = :c "
        "AND direction = 'receivable'",
        c=cid,
    )
    return D(value)


async def _ledger_4010(env: Env, pos: Pos, cid: Any) -> D:
    value = await one(
        env.db,
        pos.tenant_id,
        "SELECT COALESCE(sum(CASE WHEN account_dt = '4010' THEN amount ELSE -amount END), 0) FROM "
        "app.ledger_entries WHERE '4010' IN (account_dt, account_kt) AND analytics->>'counterparty_id' = :c",
        c=str(cid),
    )
    return D(value)


async def test_return_of_written_off_sale_does_not_reduce_receivable_twice(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    await set_go_live(env, pos, business_today().replace(day=1))
    cid = await customer(env, pos)
    product = await item(env, pos, "12000.0000")
    sale = await debt_sale(env, pos, cid, [(product, "1.000", "12000.0000")])
    created = await env.client.post(
        f"{API}/debt-writeoffs",
        json={"counterparty_id": str(cid), "amount": "12000.00", "reason": "umidsiz"},
        headers=pos.shop.h("owner"),
    )
    posted = await env.client.post(
        f"{API}/debt-writeoffs/{created.json()['id']}/post", headers=pos.shop.h("owner")
    )
    assert posted.status_code == 200, posted.text
    assert await _balance(env, pos, cid) == D("0.00")
    lines = await sold_lines(env, pos, sale["id"])
    ret = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale["id"])
    res = await deliver(env, pos, "return.created", ret, actor="owner")
    # the whole debt of the sale was written off: the return exceeds its still-open debt (0) — refused until
    # the Owner cancels the write-off (ACC-04, F2)
    assert res.code == "VALIDATION_ERROR" and res.keys == ["validation.sale_debt_written_off"]
    assert await _balance(env, pos, cid) == D("0.00")
    assert await _balance(env, pos, cid) == await _ledger_4010(env, pos, cid)


async def _debt_adjustment_credit(env: Env, pos: Pos, cid: Any, amount: str) -> None:
    """A cash sale of ``amount`` to the customer returned with ``refund_method='debt_adjustment'`` — Kt 4010
    with no open document (13 §2.5): the customer's balance drops by ``amount``."""
    product = await item(env, pos, f"{amount}00")
    sale = sale_payload(
        pos,
        [sale_line(product, qty="1.000", price=f"{amount}00")],
        [{"method": "cash", "amount": amount}],
        counterparty_id=str(cid),
    )
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
    assert res.error is None, (res.error.code, res.error.details) if res.error else None


async def test_cash_movement_on_4010_moves_debt_balance_and_cancel_reverses(env: Env) -> None:
    """ACC-02: a ``debt_adjustment`` credit (−12 000) is paid back by a 4010 ``out`` cash movement — the
    balance goes to 0 with the ledger; the cancel restores the credit."""
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos)
    await _debt_adjustment_credit(env, pos, cid, "12000.00")
    assert await _balance(env, pos, cid) == D("-12000.00")
    assert await _balance(env, pos, cid) == await _ledger_4010(env, pos, cid)
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
    doc = created.json()
    assert await _balance(env, pos, cid) == D("0.00")
    assert await _balance(env, pos, cid) == await _ledger_4010(env, pos, cid)
    cancel = await env.client.post(
        f"{API}/cash-movements/{doc['id']}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 200, cancel.text
    assert await _balance(env, pos, cid) == D("-12000.00")
    assert await _balance(env, pos, cid) == await _ledger_4010(env, pos, cid)


async def test_acc02_open_docs_equal_balance_invariant(env: Env) -> None:
    """ACC-02: Σ reconciled open (sales + openings) == max(balance, 0) after a credit without a document,
    a partial payment and a credit larger than the whole debt; ``balance ≤ Σ raw open`` always."""
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos)
    a = await item(env, pos, "30000.0000")
    b = await item(env, pos, "45000.0000")
    first = await debt_sale(env, pos, cid, [(a, "1.000", "30000.0000")], due="2026-01-05")
    second = await debt_sale(env, pos, cid, [(b, "1.000", "45000.0000")])

    async def check() -> list[tuple[str, str]]:
        docs = await open_docs(env, pos, cid)
        balance = await _balance(env, pos, cid)
        assert sum((D(d["open_amount"]) for d in docs), D("0.00")) == max(balance, D("0.00"))
        return [(d["doc_id"], d["open_amount"]) for d in docs]

    assert await check() == [(first["id"], "30000.00"), (second["id"], "45000.00")]
    await _debt_adjustment_credit(env, pos, cid, "10000.00")  # the oldest (due 2026-01-05) absorbs it
    assert await check() == [(first["id"], "20000.00"), (second["id"], "45000.00")]
    pay = debt_payment(pos, cid, "25000.00", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", pay)).error is None
    assert await check() == [(second["id"], "40000.00")]
    await _debt_adjustment_credit(env, pos, cid, "50000.00")  # more than the whole debt: a 4010 credit
    assert await _balance(env, pos, cid) == D("-10000.00")
    assert await check() == []
