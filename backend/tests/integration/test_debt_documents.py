"""Debt openings, write-offs, doubtful flags (18 §12.4–§12.6, §12.5a; 13 §2.13, §2.14 row 1a, §2.15, §2.15a).

QT-M08-10, QT-M08-13, B4-T02, B4-T08 (payment of written-off debt → Kt 9390), 13 §2.13/§2.15 examples."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.core.db.base import uuid7
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
    execute,
    item,
    ledger,
    one,
    open_docs,
    rows,
    set_go_live,
)
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
    await set_go_live(env, pos, TODAY.replace(day=1))
    return pos


async def _post(env: Env, pos: Pos, path: str, body: dict[str, Any], role: str = "owner") -> dict[str, Any]:
    created = await env.client.post(f"{API}/{path}", json=body, headers=pos.shop.h(role))
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    posted = await env.client.post(f"{API}/{path}/{doc_id}/post", headers=pos.shop.h(role))
    assert posted.status_code == 200, posted.text
    result: dict[str, Any] = posted.json()
    return result


async def test_qt_m08_10_opening_receivable_dt_4010_kt_0000(env: Env) -> None:
    """13 §2.13: receivable opening ``Dt 4010 / Kt 0000`` on ``go_live_date − 1``, no goods, no receipt."""
    pos = await _pos(env)
    body = {
        "counterparty": {"name": "Daftardagi mijoz", "phone": "+998 90 111-22-33"},
        "amount": "150000.00",
        "direction": "receivable",
        "due_date": (TODAY + timedelta(days=10)).isoformat(),
    }
    doc = await _post(env, pos, "debt-openings", body)
    assert doc["status"] == "posted" and doc["number"].startswith("OD-")
    entries = await rows(
        env.db,
        pos.tenant_id,
        "SELECT account_dt, account_kt, amount, entry_date FROM app.ledger_entries WHERE doc_id = :d",
        d=doc["id"],
    )
    assert [(e["account_dt"], e["account_kt"], e["amount"]) for e in entries] == [
        ("4010", "0000", D("150000.00"))
    ]
    assert entries[0]["entry_date"] == TODAY.replace(day=1) - timedelta(days=1)
    cid = doc["counterparty_id"]
    moves = await rows(
        env.db,
        pos.tenant_id,
        "SELECT direction, amount, due_date FROM app.debt_moves WHERE doc_id = :d",
        d=doc["id"],
    )
    assert moves == [
        {"direction": "receivable", "amount": D("150000.00"), "due_date": TODAY + timedelta(days=10)}
    ]
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.fiscal_receipts") == 0
    assert await one(env.db, pos.tenant_id, "SELECT phone FROM app.counterparties WHERE id = :c", c=cid) == (
        "+998901112233"
    )
    # the opening is paid like any debt; the receipt has one general line without goods
    pay = debt_payment(pos, uuid_of(cid), "150000.00", await open_docs(env, pos, uuid_of(cid)))
    res = await deliver_debt(env, pos, "debt_payment.created", pay)
    assert res.error is None
    items = (
        await rows(
            env.db,
            pos.tenant_id,
            "SELECT payload FROM app.fiscal_receipts WHERE debt_payment_id = :p",
            p=pay["id"],
        )
    )[0]["payload"]["items"]
    assert [(i["sale_line_id"], i["amount"], i["vat_amount"]) for i in items] == [(None, "150000.00", "0.00")]
    assert items[0]["name"].startswith("Qarz to'lovi (boshlang'ich qoldiq)")
    # a paid opening cannot be cancelled any more
    cancel = await env.client.post(
        f"{API}/debt-openings/{doc['id']}/cancel", json={"reason": "x"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 409 and cancel.json()["error"]["params"]["reason"] == "has_allocations"


def uuid_of(value: str) -> Any:
    from uuid import UUID

    return UUID(value)


async def test_13_2_13_payable_opening_and_cancel(env: Env) -> None:
    pos = await _pos(env)
    sup = uuid7()
    await execute(
        env.db,
        pos.tenant_id,
        "INSERT INTO app.counterparties (id, tenant_id, kind, name, is_supplier, "
        "is_customer) VALUES (:i, :t, 'person', 'Mega Trade', true, false)",
        i=sup,
        t=pos.tenant_id,
    )
    doc = await _post(
        env, pos, "debt-openings", {"counterparty_id": str(sup), "amount": "80000.00", "direction": "payable"}
    )
    assert await ledger(env, pos, doc["id"]) == {("0000", "6010"): D("80000.00")}
    assert await one(
        env.db,
        pos.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'payable'",
        c=sup,
    ) == D("80000.00")
    cancel = await env.client.post(
        f"{API}/debt-openings/{doc['id']}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 200 and cancel.json()["status"] == "cancelled"
    assert await ledger(env, pos, doc["id"]) == {
        ("0000", "6010"): D("80000.00"),
        ("6010", "0000"): D("80000.00"),
    }
    assert await one(
        env.db,
        pos.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'payable'",
        c=sup,
    ) == D("0.00")


async def test_payable_opening_with_supplier_payment_cannot_be_cancelled(env: Env) -> None:
    pos = await _pos(env)
    sup = uuid7()
    await execute(
        env.db,
        pos.tenant_id,
        "INSERT INTO app.counterparties (id, tenant_id, kind, name, is_supplier, "
        "is_customer) VALUES (:i, :t, 'person', 'Yetkazuvchi', true, false)",
        i=sup,
        t=pos.tenant_id,
    )
    doc = await _post(
        env, pos, "debt-openings", {"counterparty_id": str(sup), "amount": "50000.00", "direction": "payable"}
    )
    sp = uuid7()
    await execute(
        env.db,
        pos.tenant_id,
        "INSERT INTO app.supplier_payments (id, tenant_id, branch_id, doc_date, status, supplier_id, method, amount, "
        "created_by) VALUES (:i, :t, :b, CURRENT_DATE, 'posted', :s, 'bank', 20000, :u)",
        i=sp,
        t=pos.tenant_id,
        b=pos.branch_id,
        s=sup,
        u=pos.shop.user_ids["owner"],
    )
    await execute(
        env.db,
        pos.tenant_id,
        "INSERT INTO app.supplier_payment_allocations (id, tenant_id, supplier_payment_id, target_doc_type, "
        "target_doc_id, amount) VALUES (:i, :t, :p, 'debt_openings', :d, 20000)",
        i=uuid7(),
        t=pos.tenant_id,
        p=sp,
        d=doc["id"],
    )
    cancel = await env.client.post(
        f"{API}/debt-openings/{doc['id']}/cancel", json={"reason": "x"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 409
    assert cancel.json()["error"]["params"]["reason"] == "supplier_payment_allocated"


async def test_opening_needs_go_live_date(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    await execute(env.db, pos.tenant_id, "UPDATE app.tenants SET go_live_date = NULL")
    cid = await customer(env, pos)
    created = await env.client.post(
        f"{API}/debt-openings",
        json={"counterparty_id": str(cid), "amount": "1.00"},
        headers=pos.shop.h("owner"),
    )
    posted = await env.client.post(
        f"{API}/debt-openings/{created.json()['id']}/post", headers=pos.shop.h("owner")
    )
    assert posted.status_code == 422
    assert posted.json()["error"]["details"][0]["message_key"] == "validation.go_live_date_missing"


async def test_qt_m08_13_writeoff_owner_only_9430_and_audit(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "100000.0000")
    s1 = await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    s2 = await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    body = {"counterparty_id": str(cid), "amount": "150000.00", "reason": "Mijoz ko'chib ketdi"}
    denied = await env.client.post(f"{API}/debt-writeoffs", json=body, headers=pos.shop.h("manager"))
    assert denied.status_code == 403
    doc = await _post(env, pos, "debt-writeoffs", body)
    assert doc["approved_by"] == str(pos.shop.user_ids["owner"]) and doc["account_choice"] == "9430"
    assert await ledger(env, pos, doc["id"]) == {("9430", "4010"): D("150000.00")}
    assert [(a["target_doc_id"], a["amount"]) for a in doc["allocations"]] == [
        (s1["id"], "100000.00"),
        (s2["id"], "50000.00"),
    ]
    audit = await rows(
        env.db, pos.tenant_id, "SELECT action, user_id FROM app.audit_log WHERE entity_id = :d", d=doc["id"]
    )
    assert {a["action"] for a in audit} == {"debt_writeoff.created", "debt_writeoff.posted"}
    docs = await open_docs(env, pos, cid)
    assert [(d["doc_type"], d["open_amount"]) for d in docs] == [
        ("sales", "50000.00"),
        ("debt_writeoffs", "150000.00"),
    ]


async def test_writeoff_4910_needs_reserve_and_nothing_open_is_already_paid(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    nothing = await env.client.post(
        f"{API}/debt-writeoffs",
        json={"counterparty_id": str(cid), "amount": "1.00", "reason": "x"},
        headers=pos.shop.h("owner"),
    )
    assert nothing.status_code == 409 and nothing.json()["error"]["code"] == "DEBT_ALREADY_PAID"
    a = await item(env, pos, "100000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    body = {"counterparty_id": str(cid), "amount": "60000.00", "reason": "umidsiz", "account_choice": "4910"}
    no_reserve = await env.client.post(f"{API}/debt-writeoffs", json=body, headers=pos.shop.h("owner"))
    assert no_reserve.status_code == 422
    assert no_reserve.json()["error"]["details"][0]["message_key"] == "validation.reserve_4910_insufficient"
    too_much = await env.client.post(
        f"{API}/debt-writeoffs",
        json=body | {"amount": "100000.01", "account_choice": "9430"},
        headers=pos.shop.h("owner"),
    )
    assert too_much.status_code == 422
    # 13 §2.15a: the year-end reserve Dt 9430 / Kt 4910 per counterparty (a ledger adjustment)
    await execute(
        env.db,
        pos.tenant_id,
        "INSERT INTO app.ledger_entries (id, tenant_id, entry_date, branch_id, account_dt, account_kt, amount, doc_type, "
        "doc_id, analytics) VALUES (:i, :t, CURRENT_DATE, :b, '9430', '4910', 70000, 'ledger_adjustments', :d, "
        "CAST(:a AS jsonb))",
        i=uuid7(),
        t=pos.tenant_id,
        b=pos.branch_id,
        d=uuid7(),
        a=f'{{"counterparty_id": "{cid}"}}',
    )
    doc = await _post(env, pos, "debt-writeoffs", body)
    assert await ledger(env, pos, doc["id"]) == {("4910", "4010"): D("60000.00")}


async def test_b4_t08_payment_of_written_off_debt_goes_to_9390(env: Env) -> None:
    """13 §2.14 row 1a: a written-off debt that comes back — ``Dt 5010 / Kt 9390``, no debt_moves."""
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "100000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    wo = await _post(
        env, pos, "debt-writeoffs", {"counterparty_id": str(cid), "amount": "70000.00", "reason": "x"}
    )
    # balance 30 000 + written-off 70 000 open: an online payment of 100 000 is allowed (18 §12.2), 100 001 is not
    over = debt_payment(pos, cid, "100000.01", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", over)).code == "VALIDATION_ERROR"
    pay = debt_payment(pos, cid, "100000.00", await open_docs(env, pos, cid))
    res = await deliver_debt(env, pos, "debt_payment.created", pay)
    assert res.error is None
    assert await ledger(env, pos, pay["id"]) == {
        ("5010", "4010"): D("30000.00"),
        ("5010", "9390"): D("70000.00"),
    }
    moves = await rows(
        env.db, pos.tenant_id, "SELECT amount FROM app.debt_moves WHERE doc_id = :d", d=pay["id"]
    )
    assert [m["amount"] for m in moves] == [D("-30000.00")]
    assert res.server["allocations"][-1] == {
        "target_doc_type": "debt_writeoffs",
        "target_doc_id": wo["id"],
        "amount": "70000.00",
    }
    cancel = await env.client.post(
        f"{API}/debt-writeoffs/{wo['id']}/cancel", json={"reason": "x"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 409 and cancel.json()["error"]["params"]["reason"] == "has_allocations"


async def test_writeoff_cancel_restores_the_debt(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    a = await item(env, pos, "100000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    wo = await _post(
        env, pos, "debt-writeoffs", {"counterparty_id": str(cid), "amount": "100000.00", "reason": "x"}
    )
    assert await open_docs(env, pos, cid) == [
        {
            "doc_type": "debt_writeoffs",
            "doc_id": wo["id"],
            "number": wo["number"],
            "doc_date": wo["doc_date"],
            "due_date": None,
            "open_amount": "100000.00",
            "lines": [],
        }
    ]
    cancel = await env.client.post(
        f"{API}/debt-writeoffs/{wo['id']}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert cancel.status_code == 200
    assert [d["doc_type"] for d in await open_docs(env, pos, cid)] == ["sales"]
    assert await ledger(env, pos, wo["id"]) == {
        ("9430", "4010"): D("100000.00"),
        ("4010", "9430"): D("100000.00"),
    }


async def test_doubtful_flag_owner_only_no_posting(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    body = {"counterparty_id": str(cid), "reason": "Telefon o'chiq, 3 oy"}
    denied = await env.client.post(f"{API}/debt-doubtful-flags", json=body, headers=pos.shop.h("manager"))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "DOUBTFUL_FLAG_REQUIRES_OWNER"
    created = await env.client.post(f"{API}/debt-doubtful-flags", json=body, headers=pos.shop.h("owner"))
    assert created.status_code == 201 and created.json()["active"] is True
    twice = await env.client.post(f"{API}/debt-doubtful-flags", json=body, headers=pos.shop.h("owner"))
    assert twice.status_code == 409
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.ledger_entries") == 0
    flag_id = created.json()["id"]
    off = await env.client.post(f"{API}/debt-doubtful-flags/{flag_id}/unflag", headers=pos.shop.h("owner"))
    assert off.status_code == 200 and off.json()["active"] is False
    again = await env.client.post(f"{API}/debt-doubtful-flags/{flag_id}/unflag", headers=pos.shop.h("owner"))
    assert again.status_code == 409
    actions = await rows(
        env.db, pos.tenant_id, "SELECT action FROM app.audit_log WHERE entity = 'debt_doubtful_flags'"
    )
    assert sorted(a["action"] for a in actions) == ["debt_doubtful_flagged", "debt_doubtful_unflagged"]


async def test_document_lists_and_reads(env: Env) -> None:
    pos = await _pos(env)
    cid = await customer(env, pos)
    for amount in ("1000.00", "2000.00", "3000.00"):
        await _post(env, pos, "debt-openings", {"counterparty_id": str(cid), "amount": amount})
    first = await env.client.get(
        f"{API}/debt-openings",
        params={"limit": 2, "counterparty_id": str(cid)},
        headers=pos.shop.h("owner", key=None),
    )
    assert first.status_code == 200 and len(first.json()["items"]) == 2 and first.json()["next_cursor"]
    second = await env.client.get(
        f"{API}/debt-openings",
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
        headers=pos.shop.h("owner", key=None),
    )
    ids = [i["id"] for i in first.json()["items"] + second.json()["items"]]
    assert len(set(ids)) == 3
    one_doc = await env.client.get(
        f"{API}/debt-openings/{ids[0]}", headers=pos.shop.h("accountant", key=None)
    )
    assert one_doc.status_code == 200
    denied = await env.client.post(
        f"{API}/debt-openings",
        json={"counterparty_id": str(cid), "amount": "1.00"},
        headers=pos.shop.h("cashier"),
    )
    assert denied.status_code == 403
