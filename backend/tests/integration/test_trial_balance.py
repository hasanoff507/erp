"""M11 statements and owner figures — ``/reports/trial-balance`` (20 #11, BO-07 «6410 qoldig'i»),
``/reports/balance-sheet`` (20 #13, 4910 reserve 13 §2.15a), ``/reports/dashboard`` ``expenses_total``
(US-M11-03, QT-M11-04); 13 §5.1 closed month + storno. Each test owns its tenant and months."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.modules.accounting.wiring import business_today
from tests.support.accounting import (
    ADJ,
    API,
    Env,
    add_ledger,
    adjust,
    adjust_ok,
    close,
    customer,
    err,
    label,
    ledger_of,
    month_end,
    months_ago,
    sales_env_fixture,
    set_go_live,
    shop,
)
from tests.support.inventory import add_branch, add_user

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def test_trial_balance_month_and_6410_after_vat_offset(env: Env) -> None:
    """QT-M10-07 figures: 6410 VAT balance after the offset (Dt 6410 / Kt 4410) is −36 000.00."""
    s = await shop(env)
    m = months_ago(1)
    prev = months_ago(2)
    day = m + timedelta(days=14)
    await add_ledger(env, s, "5010", "9020", "500000.00", prev + timedelta(days=3))  # opening part
    await add_ledger(env, s, "5010", "6410", "120000.00", day, tax_type="vat")
    await add_ledger(env, s, "4410", "6010", "84000.00", day, tax_type="vat")
    await add_ledger(
        env, s, "6410", "4410", "84000.00", month_end(m), doc_type="tax_settlements", tax_type="vat"
    )
    response = await env.client.get(f"{API}/reports/trial-balance", params={"period": label(m)},
                                    headers=s.h(key=None))  # fmt: skip
    assert response.status_code == 200, response.text
    body = response.json()
    rows = {r["account"]: r for r in body["rows"]}
    assert rows["5010"]["opening_balance"] == "500000.00" and rows["5010"]["closing_balance"] == "620000.00"
    assert rows["9020"]["opening_balance"] == "-500000.00" and rows["9020"]["debit_turnover"] == "0.00"
    r6410 = rows["6410"]
    assert (r6410["debit_turnover"], r6410["credit_turnover"], r6410["closing_balance"]) == (
        "84000.00", "120000.00", "-36000.00",
    )  # fmt: skip
    assert r6410["by_tax_type"] == [{"tax_type": "vat", "opening_balance": "0.00", "debit_turnover": "84000.00",
                                     "credit_turnover": "120000.00", "closing_balance": "-36000.00"}]  # fmt: skip
    assert rows["4410"]["closing_balance"] == "0.00" and r6410["type"] == "P"
    assert body["totals"]["debit_turnover"] == body["totals"]["credit_turnover"] == "288000.00"
    only = await env.client.get(f"{API}/reports/trial-balance", params={"period": label(m), "account": "6410"},
                                headers=s.h(key=None))  # fmt: skip
    assert [r["account"] for r in only.json()["rows"]] == ["6410"]
    bad = await env.client.get(
        f"{API}/reports/trial-balance", params={"period": "2026-13"}, headers=s.h(key=None)
    )
    assert bad.status_code == 422
    cashier = await env.client.get(f"{API}/reports/trial-balance", params={"period": label(m)},
                                   headers=s.h("cashier", key=None))  # fmt: skip
    assert cashier.status_code == 403


async def test_statements_branch_scope(env: Env) -> None:
    from app.modules.access.domain.permissions import SystemRole

    s = await shop(env)
    other, _ = await add_branch(env, s, "02", "Yunusobod")
    await add_user(env, s, "branch_accountant", SystemRole.ACCOUNTANT, (s.branch_id,))
    response = await env.client.get(f"{API}/reports/balance-sheet", params={"branch_id": str(other)},
                                    headers=s.h("branch_accountant", key=None))  # fmt: skip
    assert response.status_code == 403 and err(response) == "BRANCH_SCOPE_DENIED"
    own = await env.client.get(f"{API}/reports/trial-balance", params={"period": label(months_ago(1))},
                               headers=s.h("branch_accountant", key=None))  # fmt: skip
    assert own.status_code == 200


async def test_13_2_15a_doubtful_debt_reserve_4910_in_balance_sheet(env: Env) -> None:
    """Year-end reserve via ``ledger_adjustments`` (Dt 9430 / Kt 4910) — a contra-asset line."""
    s = await shop(env)
    cid = await customer(env, s)
    await set_go_live(env, s, business_today() - timedelta(days=20))
    await adjust_ok(env, s, "4010", "0000", "400000.00", day=business_today() - timedelta(days=21),
                    analytics={"counterparty_id": str(cid)})  # fmt: skip
    await adjust_ok(env, s, "0000", "8330", "400000.00", day=business_today() - timedelta(days=21))
    await adjust_ok(env, s, "9430", "4910", "150000.00", analytics={"counterparty_id": str(cid)},
                    comment="Shubhali qarz rezervi")  # fmt: skip
    sheet = (await env.client.get(f"{API}/reports/balance-sheet", headers=s.h(key=None))).json()
    assets = {x["account"]: x["amount"] for x in sheet["assets"]}
    assert assets == {"4010": "400000.00", "4910": "-150000.00"}
    equity = {x["account"]: x["amount"] for x in sheet["equity"]}
    assert equity == {"8330": "400000.00", "9910": "-150000.00"}
    assert sheet["total_assets"] == sheet["total_liabilities_and_equity"] == "250000.00"


async def test_13_5_1_closed_month_locked_storno_in_open_month(env: Env) -> None:
    s = await shop(env)
    m = months_ago(2)
    await set_go_live(env, s, m + timedelta(days=1))
    doc = await adjust_ok(env, s, "9430", "5010", "7000.00", day=m + timedelta(days=6))
    assert (await close(env, s, m)).status_code == 201
    late = await adjust(env, s, "9430", "5010", "1.00", day=m + timedelta(days=7))
    assert late.status_code == 409 and err(late) == "PERIOD_CLOSED"
    cancel = await env.client.post(
        f"{ADJ}/{doc['id']}/cancel", json={"reason": "Xato"}, headers=s.h("accountant")
    )
    assert cancel.status_code == 200
    lines = await ledger_of(env, s, doc["id"])
    assert [(x["entry_date"] <= month_end(m), x["account_dt"]) for x in lines] == [
        (True, "9430"),
        (False, "5010"),
    ]
    tb = await env.client.get(
        f"{API}/reports/trial-balance", params={"period": label(m)}, headers=s.h(key=None)
    )
    assert {r["account"]: r["closing_balance"] for r in tb.json()["rows"]}["9430"] == "7000.00"  # unchanged


async def test_qt_m11_04_dashboard_simple_figures(env: Env) -> None:
    s = await shop(env)
    today = business_today()
    await add_ledger(env, s, "5010", "9020", "200000.00", today)
    created = await env.client.post(f"{API}/expense-categories", json={"name": "Ijara", "default_account": "9420"},
                                    headers=s.h())  # fmt: skip
    assert created.status_code == 201, created.text
    draft = await env.client.post(
        f"{API}/expenses",
        json={
            "doc_date": str(today),
            "category_id": created.json()["id"],
            "amount": "50000.00",
            "source": "bank",
        },
        headers=s.h(branch=s.branch_id),
    )
    assert draft.status_code == 201, draft.text
    posted = await env.client.post(
        f"{API}/expenses/{draft.json()['id']}/post", headers=s.h(branch=s.branch_id)
    )
    assert posted.status_code == 200, posted.text
    dash = await env.client.get(f"{API}/reports/dashboard", params={"period": "today"}, headers=s.h(key=None))
    assert dash.status_code == 200, dash.text
    body = dash.json()
    assert body["expenses_total"] == "50000.00" and body["net_profit"] == "150000.00"
    manager = (await env.client.get(f"{API}/reports/dashboard", headers=s.h("manager", key=None))).json()
    assert (manager["expenses_total"] is None) == (manager["net_profit"] is None)  # finance-only figures
