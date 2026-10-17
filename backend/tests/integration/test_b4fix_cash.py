"""B4 fix round, FX-cash (ACC-02): a cash movement on account 4010 (13 §2.18).

* ``in`` on 4010 is refused — a customer repays debt only through ``debt_payments`` (qaror #45/#67);
* ``out`` on 4010 pays back the customer's 4010 credit only (``amount ≤ max(−receivable, 0)`` under the
  ``debt_balances`` lock) — a ``debt_adjustment`` return credit is refunded this way (13 §2.5).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.accounting.wiring import business_today
from tests.support.sales import (
    API,
    D,
    Env,
    Pos,
    add_customer,
    deliver,
    make_pos,
    new_item,
    one,
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


def _body(pos: Pos, cid: Any, direction: str, amount: str) -> dict[str, Any]:
    return {
        "cash_register_id": str(pos.register_id), "shift_id": str(pos.shift_id), "direction": direction,
        "reason": "other", "account": "4010", "counterparty_id": str(cid), "amount": amount,
        "comment": "Mijoz hisobi", "doc_date": business_today().isoformat(),
    }  # fmt: skip


async def _credit(env: Env, pos: Pos) -> Any:
    """A paid cash sale returned with ``refund_method='debt_adjustment'`` → the customer's 4010 credit 12000."""
    cid = await add_customer(env, pos)
    product = await new_item(env, pos, stock="5.000")
    sale = sale_payload(pos, [sale_line(product)], counterparty_id=str(cid))
    await sell(env, pos, sale)
    lines = await sold_lines(env, pos, sale["id"])
    ret = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"])], sale_id=sale["id"],
                         refund_method="debt_adjustment", receipt_seq=None)  # fmt: skip
    res = await deliver(env, pos, "return.created", ret)
    assert res.error is None, (res.code, res.keys)
    assert await _receivable(env, pos, cid) == D("-12000.00")
    return cid


async def test_acc02_cash_movement_in_on_4010_refused(env: Env) -> None:
    pos = await make_pos(env)
    cid = await add_customer(env, pos)
    res = await env.client.post(
        f"{API}/cash-movements", json=_body(pos, cid, "in", "20000.00"), headers=pos.shop.h("owner")
    )
    assert res.status_code == 422, res.text
    err = res.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert [(d["field"], d["message_key"]) for d in err["details"]] == [
        ("account", "validation.cash_movement_debt_repayment")
    ]
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.cash_movements") == 0
    assert await _receivable(env, pos, cid) == D("0.00")


async def test_acc02_cash_movement_out_on_4010_limited_to_customer_credit(env: Env) -> None:
    pos = await make_pos(env)
    cid = await _credit(env, pos)
    over = await env.client.post(
        f"{API}/cash-movements", json=_body(pos, cid, "out", "12000.01"), headers=pos.shop.h("owner")
    )
    assert over.status_code == 422, over.text
    err = over.json()["error"]
    assert [(d["field"], d["message_key"]) for d in err["details"]] == [
        ("amount", "validation.cash_movement_exceeds_customer_credit")
    ]
    assert err["params"]["available"] == "12000.00"
    # a customer with no credit (a debtor or nobody) cannot be paid from the drawer against 4010
    debtor = await add_customer(env, pos)
    none = await env.client.post(
        f"{API}/cash-movements", json=_body(pos, debtor, "out", "1.00"), headers=pos.shop.h("owner")
    )
    assert none.status_code == 422 and none.json()["error"]["params"]["available"] == "0.00", none.text
    ok = await env.client.post(
        f"{API}/cash-movements", json=_body(pos, cid, "out", "12000.00"), headers=pos.shop.h("owner")
    )
    assert ok.status_code == 201, ok.text
    assert await _receivable(env, pos, cid) == D("0.00")
    assert await _receivable(env, pos, cid) == await _ledger_4010(env, pos, cid)
    again = await env.client.post(
        f"{API}/cash-movements", json=_body(pos, cid, "out", "1.00"), headers=pos.shop.h("owner")
    )
    assert again.status_code == 422, again.text
    cancel = await env.client.post(
        f"{API}/cash-movements/{ok.json()['id']}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 200, cancel.text
    assert await _receivable(env, pos, cid) == D("-12000.00")
    assert await _receivable(env, pos, cid) == await _ledger_4010(env, pos, cid)
