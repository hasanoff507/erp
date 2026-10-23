"""Debt ledger (18 §12.1), debts aging (20 #21 = 18 §12.8) and the daily debt check (US-M08-03/09/10).

QT-M08-05, QT-M08-09, QT-M08-12, QT-M08-14 (payable ledger half — supplier payments come from b4-supplier-tax)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.session import tenant_transaction
from app.modules.accounting.wiring import business_today
from app.modules.debts.wiring import debt_daily_check
from tests.support.debts import (
    API,
    Env,
    Pos,
    customer,
    debt_payment,
    debt_sale,
    deliver_debt,
    item,
    one,
    open_docs,
    rows,
    set_go_live,
)
from tests.support.purchasing import create_supplier, gr_line, posted_receipt
from tests.support.sales import make_pos, sales_env_fixture

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]

TODAY = business_today()


@pytest.fixture(autouse=True)
def _fresh_business_day() -> None:
    """The suite can cross midnight (Asia/Tashkent): take the business day when each test starts."""
    global TODAY
    TODAY = business_today()


async def _pos(env: Env) -> Pos:
    pos = await make_pos(env, account="2910")
    await set_go_live(env, pos, TODAY.replace(day=1) - timedelta(days=90))
    return pos


async def _opening(env: Env, pos: Pos, cid: UUID, amount: str, due: date | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"counterparty_id": str(cid), "amount": amount}
    if due:
        body["due_date"] = due.isoformat()
    created = await env.client.post(f"{API}/debt-openings", json=body, headers=pos.shop.h("owner"))
    assert created.status_code == 201, created.text
    posted = await env.client.post(
        f"{API}/debt-openings/{created.json()['id']}/post", headers=pos.shop.h("owner")
    )
    assert posted.status_code == 200, posted.text
    result: dict[str, Any] = posted.json()
    return result


async def _ledger(env: Env, pos: Pos, cid: UUID, role: str = "owner", **params: Any) -> dict[str, Any]:
    response = await env.client.get(
        f"{API}/counterparties/{cid}/debt-ledger", params=params, headers=pos.shop.h(role, key=None)
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_qt_m08_09_paper_book_entries_status_goods_and_balance(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    cola = await item(env, pos, "12000.0000", "Coca-Cola 1.5L")
    bread = await item(env, pos, "4000.0000", "Non")
    s1 = await debt_sale(env, pos, cid, [(cola, "5.000", "12000.0000")], due="2026-01-01")  # 60 000
    s2 = await debt_sale(env, pos, cid, [(bread, "10.000", "4000.0000")])  # 40 000
    pay = debt_payment(pos, cid, "70000.00", await open_docs(env, pos, cid), promise_date="2030-05-01")
    assert (await deliver_debt(env, pos, "debt_payment.created", pay)).error is None
    book = await _ledger(env, pos, cid, role="cashier")
    assert book["balance"] == "30000.00" and book["counterparty"]["debt_due_date"] == "2030-05-01"
    by_doc = {e["doc_id"]: e for e in book["entries"]}
    assert by_doc[s1["id"]]["status"] == "paid" and by_doc[s1["id"]]["open_amount"] == "0.00"
    assert by_doc[s2["id"]]["status"] == "partially_paid" and by_doc[s2["id"]]["open_amount"] == "30000.00"
    assert by_doc[s2["id"]]["promise_date"] == "2030-05-01"
    assert by_doc[s1["id"]]["products"][0]["name"] == "Coca-Cola 1.5L"
    assert by_doc[s1["id"]]["created_by_name"]  # «kim berdi»
    payment = by_doc[pay["id"]]
    assert (
        payment["amount"] == "-70000.00"
        and payment["kind"] == "payment"
        and payment["paid_amount"] == "70000.00"
    )
    assert [a["amount"] for a in payment["allocations"]] == ["60000.00", "10000.00"]
    assert book["entries"][0]["running_balance"] == "30000.00"  # newest first
    paged = await _ledger(env, pos, cid, limit=2)
    assert len(paged["entries"]) == 2 and paged["next_cursor"]
    rest = await _ledger(env, pos, cid, limit=2, cursor=paged["next_cursor"])
    assert len(rest["entries"]) == 1 and rest["next_cursor"] is None
    denied = await env.client.get(
        f"{API}/counterparties/{cid}/debt-ledger",
        params={"direction": "payable"},
        headers=pos.shop.h("cashier", key=None),
    )
    assert denied.status_code == 403


async def test_qt_m08_14_payable_ledger_men_qarzdorman(env: Env) -> None:
    pos = await _pos(env)
    supplier = await create_supplier(env.client, pos.shop)
    product = await item(env, pos, "10000.0000")
    gr = await posted_receipt(
        env.client, pos.shop, supplier["id"], pos.warehouse_id, [gr_line(product, "10.000", "5600.0000")]
    )
    payable = await one(
        env.db,
        pos.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'payable'",
        c=supplier["id"],
    )
    assert payable > 0
    book = await _ledger(env, pos, UUID(supplier["id"]), direction="payable")
    assert book["direction"] == "payable" and book["balance"] == format(payable, "f")
    entry = book["entries"][0]
    assert (entry["doc_type"], entry["doc_id"], entry["status"]) == ("goods_receipts", gr["id"], "open")
    assert entry["number"] == gr["number"]
    paid = await env.client.post(
        f"{API}/supplier-payments",
        json={
            "supplier_id": supplier["id"],
            "amount": "10000.00",
            "method": "bank",
            "doc_date": TODAY.isoformat(),
        },
        headers=pos.shop.h("owner", branch=pos.branch_id),
    )
    assert paid.status_code == 201, paid.text  # the supplier payment (b4-supplier-tax) is a book row too
    book = await _ledger(env, pos, UUID(supplier["id"]), direction="payable")
    kinds = {e["doc_type"]: e for e in book["entries"]}
    assert (
        kinds["supplier_payments"]["amount"] == "-10000.00"
        and kinds["supplier_payments"]["kind"] == "payment"
    )
    assert kinds["supplier_payments"]["number"] == paid.json()["number"]
    assert kinds["goods_receipts"]["status"] == "partially_paid"
    aging = await env.client.get(
        f"{API}/reports/debts-aging", params={"direction": "payable"}, headers=pos.shop.h("owner", key=None)
    )
    assert aging.status_code == 200
    rows_ = [r for r in aging.json()["rows"] if r["counterparty_id"] == supplier["id"]]
    assert rows_ and rows_[0]["overdue_since"] == gr["doc_date"]


async def test_us_m08_10_debts_aging_buckets_flags_and_filters(env: Env) -> None:
    pos = await _pos(env)
    fresh, mid, old = (
        await customer(env, pos, name="A"),
        await customer(env, pos, name="B"),
        await customer(env, pos, name="C"),
    )
    await _opening(env, pos, fresh, "10000.00", TODAY - timedelta(days=5))
    await _opening(env, pos, mid, "20000.00", TODAY - timedelta(days=45))
    await _opening(env, pos, old, "30000.00", TODAY - timedelta(days=65))
    flag = await env.client.post(
        f"{API}/debt-doubtful-flags",
        json={"counterparty_id": str(old), "reason": "yo'q"},
        headers=pos.shop.h("owner"),
    )
    assert flag.status_code == 201
    response = await env.client.get(f"{API}/reports/debts-aging", headers=pos.shop.h("owner", key=None))
    assert response.status_code == 200, response.text
    body = response.json()
    by_cp = {r["counterparty_id"]: r for r in body["rows"]}
    assert (by_cp[str(fresh)]["bucket"], by_cp[str(mid)]["bucket"], by_cp[str(old)]["bucket"]) == (
        "0-30",
        "31-60",
        "60+",
    )
    assert by_cp[str(old)]["days_overdue"] == 65 and by_cp[str(old)]["doubtful_flag"] is True
    assert by_cp[str(old)]["doubtful_flag_id"] == flag.json()["id"]
    assert {b["bucket"]: b["count"] for b in body["summary"]["buckets"]} == {"0-30": 1, "31-60": 1, "60+": 1}
    assert body["summary"]["total"] == "60000.00"
    only_old = await env.client.get(
        f"{API}/reports/debts-aging", params={"bucket": "60+"}, headers=pos.shop.h("owner", key=None)
    )
    assert [r["counterparty_id"] for r in only_old.json()["rows"]] == [str(old)]
    cashier = await env.client.get(f"{API}/reports/debts-aging", headers=pos.shop.h("cashier", key=None))
    assert cashier.status_code == 403
    manager = await env.client.get(f"{API}/reports/debts-aging", headers=pos.shop.h("manager", key=None))
    assert manager.status_code == 200  # debts.approve


async def test_aging_limit_exceeded_offline_rows(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos, limit="10000.00")
    product = await item(env, pos, "12000.0000")
    await debt_sale(env, pos, cid, [(product, "1.000", "12000.0000")], is_offline=True)
    response = await env.client.get(
        f"{API}/reports/debts-aging",
        params={"limit_exceeded_offline": "true"},
        headers=pos.shop.h("owner", key=None),
    )
    assert [r["counterparty_id"] for r in response.json()["rows"]] == [str(cid)]


async def _daily(env: Env, pos: Pos, day: date) -> dict[str, Any]:
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        return (await debt_daily_check().run(s, pos.tenant_id, day)).as_json()


async def _events(env: Env, pos: Pos, kind: str) -> list[dict[str, Any]]:
    found = await rows(
        env.db,
        pos.tenant_id,
        "SELECT payload FROM app.outbox_jobs WHERE kind = 'telegram' AND payload->>'event' = :k",
        k=kind,
    )
    return [r["payload"] for r in found]


async def test_qt_m08_05_overdue_debt_gets_a_reminder_draft_for_confirmation(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos, name="Aliyev Vali")
    await _opening(env, pos, cid, "45000.00", TODAY - timedelta(days=2))
    await _opening(env, pos, await customer(env, pos, name="Later"), "1000.00", TODAY + timedelta(days=5))
    result = await _daily(env, pos, TODAY)
    assert result["due_today"] == 1 and "debt_due_today" in result["recorded"]
    (event,) = await _events(env, pos, "debt_due_today")
    assert event["count"] == 1 and event["total"] == "45000.00"
    reminder = event["items"][0]["reminder"]
    assert reminder["requires_confirmation"] is True and reminder["source"] == "template"
    assert "Aliyev Vali" in reminder["text"] and "45000.00" in reminder["text"]
    assert (await _daily(env, pos, TODAY))["recorded"] == []  # once per day
    assert (
        await one(
            env.db,
            pos.tenant_id,
            "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'telegram' "
            "AND payload->>'event' = 'debt_due_today'",
        )
        == 1
    )


async def test_qt_m08_12_aging_60_reminder_never_flags_automatically(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    await _opening(env, pos, cid, "30000.00", TODAY - timedelta(days=65))
    result = await _daily(env, pos, TODAY)
    assert result["aging_60"] == 1 and "debt_aging_60" in result["recorded"]
    (event,) = await _events(env, pos, "debt_aging_60")
    assert event["items"][0]["counterparty_id"] == str(cid) and event["auto_flagged"] is False
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.debt_doubtful_flags") == 0
