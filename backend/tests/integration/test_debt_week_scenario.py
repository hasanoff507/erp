"""B4-DoD-02 — «bir haftalik qarz daftari» on a demo tenant, as an automated scenario over 7 simulated days.

The staging run with the founder's internal demo tenant is a manual step; this test drives the same story through
the real handlers/REST: paper-book openings, quick customers, debt sales (online + offline over the limit), partial
and full payments with promise dates, an offline payment from the pulled cache that another register raced, an
offline overpayment (6310), a write-off and the repayment of written-off debt (9390), the daily check and the
aging report. Invariants checked every day: ``Σ debt_balances(receivable) = 4010 ledger balance`` and
``Σ open_debt_docs(sales + openings) = receivable balance`` per customer.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.session import tenant_transaction
from app.modules.accounting.wiring import TASHKENT, business_today
from app.modules.debts.wiring import debt_daily_check
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
    rows,
    set_go_live,
)
from tests.support.sales import fiscalize, make_pos, sales_env_fixture

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]

START = business_today() - timedelta(days=6)


@pytest.fixture(autouse=True)
def _fresh_business_day() -> None:
    """The suite can cross midnight (Asia/Tashkent): take the business day when each test starts."""
    global START
    START = business_today() - timedelta(days=6)


def at(day: int, hour: int = 11) -> datetime:
    """Day ``day`` (1..7) of the simulated week, Tashkent business hours."""
    return datetime.combine(START + timedelta(days=day - 1), time(hour), TASHKENT).astimezone(UTC)


async def _rest(env: Env, pos: Pos, path: str, body: dict[str, Any]) -> dict[str, Any]:
    created = await env.client.post(f"{API}/{path}", json=body, headers=pos.shop.h("owner"))
    assert created.status_code == 201, created.text
    posted = await env.client.post(f"{API}/{path}/{created.json()['id']}/post", headers=pos.shop.h("owner"))
    assert posted.status_code == 200, posted.text
    result: dict[str, Any] = posted.json()
    return result


async def _invariants(env: Env, pos: Pos, customers: list[UUID]) -> None:
    balances = D(
        await one(
            env.db,
            pos.tenant_id,
            "SELECT COALESCE(sum(balance), 0) FROM app.debt_balances WHERE direction = 'receivable'",
        )
        or 0
    )
    ledger_4010 = D(
        await one(
            env.db,
            pos.tenant_id,
            "SELECT COALESCE(sum(CASE WHEN account_dt = '4010' THEN amount "
            "ELSE -amount END), 0) FROM app.ledger_entries WHERE '4010' IN (account_dt, account_kt)",
        )
        or 0
    )
    assert balances == ledger_4010
    for cid in customers:
        bal = D(
            await one(
                env.db,
                pos.tenant_id,
                "SELECT COALESCE(sum(balance), 0) FROM app.debt_balances WHERE "
                "counterparty_id = :c AND direction = 'receivable'",
                c=cid,
            )
            or 0
        )
        docs = await open_docs(env, pos, cid)
        assert sum((D(d["open_amount"]) for d in docs if d["doc_type"] != "debt_writeoffs"), D("0.00")) == bal


async def _pay(env: Env, pos: Pos, cid: UUID, amount: str, day: int, **kw: Any) -> dict[str, Any]:
    payload = debt_payment(pos, cid, amount, await open_docs(env, pos, cid), **kw)
    res = await deliver_debt(env, pos, "debt_payment.created", payload, created_at=at(day))
    assert res.error is None, res.error and (res.error.code, res.error.params, res.error.details)
    return {"payload": payload, "server": res.server, "kinds": res.exception_kinds}


async def test_b4_dod_02_one_week_debt_book(env: Env) -> None:
    pos = await make_pos(env, "Demo do'kon", account="2920")
    await set_go_live(env, pos, START)
    cola = await item(env, pos, "12000.0000", "Coca-Cola 1.5L")
    flour = await item(env, pos, "85000.0000", "Un 25kg")
    ali = await customer(env, pos, name="Aliyev Vali", limit="500000.00")
    bek = await customer(env, pos, name="Bekov Sardor", limit="200000.00")
    all_customers = [ali, bek]

    # day 1 — the old paper book moves in; first debt sales
    paper = await _rest(
        env,
        pos,
        "debt-openings",
        {
            "counterparty": {"name": "Daftar: Karimova", "phone": "+998901110000"},
            "amount": "120000.00",
            "due_date": at(3).date().isoformat(),
        },
    )
    kar = UUID(paper["counterparty_id"])
    all_customers.append(kar)
    await debt_sale(
        env, pos, ali, [(cola, "10.000", "12000.0000")], due=at(4).date().isoformat(), created_at=at(1)
    )
    await debt_sale(env, pos, bek, [(flour, "2.000", "85000.0000")], created_at=at(1, 15))
    await fiscalize(env, pos)
    await _invariants(env, pos, all_customers)

    # day 2 — offline sale over Bekov's limit is not blocked; Ali pays part and promises the rest
    await debt_sale(env, pos, bek, [(cola, "3.000", "12000.0000")], is_offline=True, created_at=at(2))
    part = await _pay(env, pos, ali, "50000.00", 2, promise_date=at(6).date().isoformat())
    assert part["server"]["remaining_balance"] == "70000.00"
    assert (
        await one(env.db, pos.tenant_id, "SELECT debt_due_date FROM app.counterparties WHERE id = :c", c=ali)
        == at(6).date()
    )
    await fiscalize(env, pos)
    await _invariants(env, pos, all_customers)

    # day 3 — Karimova's paper debt is due today: the daily check proposes a reminder (nothing auto-sent)
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        check = await debt_daily_check().run(s, pos.tenant_id, at(3).date())
    assert check.due_today == 1 and check.recorded == ("debt_due_today",)
    await _pay(env, pos, kar, "120000.00", 3)
    await fiscalize(env, pos)
    await _invariants(env, pos, all_customers)

    # day 4 — two registers race on Bekov: the offline one allocated from a stale cache (mismatch, accepted)
    stale = await open_docs(env, pos, bek)
    await _pay(env, pos, bek, "100000.00", 4)
    offline = debt_payment(pos, bek, "100000.00", stale, is_offline=True)
    res = await deliver_debt(env, pos, "debt_payment.created", offline, created_at=at(4, 16))
    assert res.error is None and res.exception_kinds == ["debt_allocation_mismatch"]
    assert [a["amount"] for a in res.server["allocations"]] == ["70000.00", "30000.00"]
    await fiscalize(env, pos)
    await _invariants(env, pos, all_customers)

    # day 5 — Bekov's offline payment exceeds what is left: the rest is an advance (6310) + owner notice
    over = await _pay(env, pos, bek, "50000.00", 5, is_offline=True)
    assert over["server"]["unallocated_amount"] == "44000.00"
    assert "debt_overpayment_offline" in over["kinds"]
    await fiscalize(env, pos)
    await _invariants(env, pos, all_customers)

    # day 6 — the owner forgives 20 000 of Ali's debt; Ali later brings it anyway (9390)
    wo = await _rest(
        env,
        pos,
        "debt-writeoffs",
        {"counterparty_id": str(ali), "amount": "20000.00", "reason": "Chegirma sifatida kechildi"},
    )
    assert wo["status"] == "posted"
    final = await _pay(env, pos, ali, "70000.00", 6)
    assert final["server"]["remaining_balance"] == "0.00"
    assert {a["target_doc_type"] for a in final["server"]["allocations"]} == {"sales", "debt_writeoffs"}
    await fiscalize(env, pos)
    await _invariants(env, pos, all_customers)

    # day 7 — the books: aging, ledgers, receipts
    aging = await env.client.get(f"{API}/reports/debts-aging", headers=pos.shop.h("owner", key=None))
    assert aging.status_code == 200
    assert aging.json()["summary"]["total"] == "0.00"
    book = await env.client.get(
        f"{API}/counterparties/{ali}/debt-ledger", headers=pos.shop.h("owner", key=None)
    )
    statuses = {e["status"] for e in book.json()["entries"] if e["doc_type"] == "sales"}
    assert statuses == {"written_off"}  # closed partly by payments, the rest by the write-off
    receipts = await rows(
        env.db, pos.tenant_id, "SELECT kind, status FROM app.fiscal_receipts WHERE kind = 'debt_settlement'"
    )
    assert len(receipts) == 6 and {r["status"] for r in receipts} == {"fiscalized"}
    advance = D(
        await one(
            env.db,
            pos.tenant_id,
            "SELECT COALESCE(sum(amount), 0) FROM app.ledger_entries WHERE account_kt = '6310'",
        )
        or 0
    )
    assert advance == D("44000.00")
    other_income = D(
        await one(
            env.db,
            pos.tenant_id,
            "SELECT COALESCE(sum(amount), 0) FROM app.ledger_entries WHERE account_kt = '9390'",
        )
        or 0
    )
    assert other_income == D("20000.00")
    await _invariants(env, pos, all_customers)
