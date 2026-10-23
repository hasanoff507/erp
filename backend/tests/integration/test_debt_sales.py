"""Sales on debt with a credit limit (US-M08-01, 18 §4.3, 13 §2.3, 16 §5) — QT-M08-01/02/03 — and a card debt
payment through the integrated terminal (US-M08-04, qaror #71)."""

from __future__ import annotations

import pytest

from tests.support.debts import (
    D,
    Env,
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
from tests.support.sales import (
    bind_terminal,
    card_result,
    deliver,
    make_pos,
    sale_line,
    sale_payload,
    sales_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def test_qt_m08_01_debt_sale_within_limit_deferred_receipt(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos, limit="500000.00")
    product = await item(env, pos, "300000.0000")
    sale = await debt_sale(env, pos, cid, [(product, "1.000", "300000.0000")])
    moves = await rows(
        env.db, pos.tenant_id, "SELECT direction, amount FROM app.debt_moves WHERE doc_id = :d", d=sale["id"]
    )
    assert moves == [{"direction": "receivable", "amount": D("300000.00")}]
    assert (
        await one(env.db, pos.tenant_id, "SELECT status FROM app.sales WHERE id = :d", d=sale["id"])
        == "posted"
    )
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.fiscal_receipts WHERE sale_id = :d", d=sale["id"]
        )
        == 0
    )
    totals = await ledger(env, pos, sale["id"])
    assert totals[("4010", "9020")] == D("267857.14") and totals[("4010", "6410")] == D("32142.86")


async def test_qt_m08_02_online_over_limit_needs_approval(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos, limit="500000.00")
    product = await item(env, pos, "50000.0000")
    await debt_sale(env, pos, cid, [(product, "9.000", "50000.0000")])  # 450 000
    debt = [{"method": "debt", "amount": "100000.00"}]
    payload = sale_payload(
        pos, [sale_line(product, qty="2.000", price="50000.0000")], debt, counterparty_id=str(cid)
    )
    res = await deliver(env, pos, "sale.created", payload)
    assert res.code == "DEBT_LIMIT_EXCEEDED"
    assert res.error is not None and res.error.params == {"limit": "500000.00", "requested": "550000.00"}
    approved = sale_payload(
        pos,
        [sale_line(product, qty="2.000", price="50000.0000")],
        [
            {
                "method": "debt",
                "amount": "100000.00",
                "debt_approval": {
                    "mode": "local_pin",
                    "approved_by": str(pos.shop.user_ids["owner"]),
                    "pin_verified_locally": True,
                },
            }
        ],
        counterparty_id=str(cid),
    )
    ok = await deliver(env, pos, "sale.created", approved)
    assert ok.error is None, ok.error and (ok.error.code, ok.error.params)


async def test_qt_m08_03_offline_over_limit_not_blocked_flagged(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos, limit="100000.00")
    product = await item(env, pos, "80000.0000")
    await debt_sale(env, pos, cid, [(product, "1.000", "80000.0000")])
    payload = sale_payload(
        pos,
        [sale_line(product, price="80000.0000")],
        [{"method": "debt", "amount": "80000.00"}],
        counterparty_id=str(cid),
        is_offline=True,
    )
    res = await deliver(env, pos, "sale.created", payload)
    assert res.error is None
    assert "DEBT_LIMIT_EXCEEDED" in res.server["warnings"]
    assert "debt_limit_exceeded_offline" in res.exception_kinds
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT debt_limit_exceeded FROM app.sales WHERE id = :d", d=payload["id"]
        )
        is True
    )
    docs = await open_docs(env, pos, cid)
    assert sum(D(d["open_amount"]) for d in docs) == D("160000.00")


async def test_card_debt_payment_integrated_terminal(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    terminal = await bind_terminal(env, pos)
    cid = await customer(env, pos)
    product = await item(env, pos, "50000.0000")
    await debt_sale(env, pos, cid, [(product, "1.000", "50000.0000")])
    result = await card_result(pos, terminal, "50000.00")
    payload = debt_payment(
        pos,
        cid,
        "50000.00",
        await open_docs(env, pos, cid),
        method="card",
        card_entry_mode="integrated",
        card_result=result,
    )
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None, res.error and (res.error.code, res.error.details)
    row = (
        await rows(
            env.db,
            pos.tenant_id,
            "SELECT card_entry_mode, card_terminal_transaction_id, rrn, card_mask, "
            "card_type FROM app.debt_payments WHERE id = :p",
            p=payload["id"],
        )
    )[0]
    assert row["card_entry_mode"] == "integrated" and row["rrn"] and row["card_mask"] and row["card_type"]
    entries = await rows(
        env.db,
        pos.tenant_id,
        "SELECT account_dt, analytics FROM app.ledger_entries WHERE doc_id = :d",
        d=payload["id"],
    )
    assert entries[0]["account_dt"] == "5710"
    assert (
        entries[0]["analytics"]["payment_method"] == "card" and entries[0]["analytics"]["rrn"] == row["rrn"]
    )
    receipt = await rows(
        env.db,
        pos.tenant_id,
        "SELECT payment_form, payload FROM app.fiscal_receipts WHERE debt_payment_id = :p",
        p=payload["id"],
    )
    assert receipt[0]["payment_form"] == "card"
    assert receipt[0]["payload"]["payments"][0]["rrn"] == row["rrn"]
