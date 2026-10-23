"""Manual ledger adjustments — ``ledger_adjustments`` (20 #10/#10a/#10b; 13 §2.23, §2.14, §2.15a, §5.2, §5.5;
B5-T14, BO-06 «Keyingi qarzga hisoblash», QT-M11-03, QT-M11-12). Each test owns its tenant and months."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest

from app.modules.accounting.wiring import business_today
from tests.support.accounting import (
    ADJ,
    D,
    Env,
    add_ledger,
    adjust,
    adjust_ok,
    balance,
    close_sql,
    customer,
    err,
    keys,
    label,
    ledger_of,
    months_ago,
    receivable,
    sales_env_fixture,
    set_go_live,
    shop,
)
from tests.support.sales import one, rows

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


# --- 13 §2.23 / 20 #10, #10a, #10b ------------------------------------------------------------------------
async def test_13_2_23_adjustment_one_line_posted_then_storno(env: Env) -> None:
    s = await shop(env)
    employee = str(s.user_ids["cashier"])
    body = await adjust_ok(env, s, "4730", "5910", "20000.00", analytics={"employee_id": employee},
                           comment="Kamomad kassirga")  # fmt: skip
    assert body["status"] == "posted" and body["number"].startswith("BX-")
    assert (body["account_dt"], body["account_kt"], body["amount"]) == ("4730", "5910", "20000.00")
    lines = await ledger_of(env, s, body["id"])
    assert [(x["account_dt"], x["account_kt"], x["amount"]) for x in lines] == [
        ("4730", "5910", D("20000.00"))
    ]
    assert lines[0]["analytics"] == {"employee_id": employee}
    listed = await env.client.get(ADJ, headers=s.h("accountant", key=None))
    assert listed.status_code == 200 and [i["id"] for i in listed.json()["items"]] == [body["id"]]

    cancel = await env.client.post(
        f"{ADJ}/{body['id']}/cancel", json={"reason": "Xato"}, headers=s.h("accountant")
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"
    lines = await ledger_of(env, s, body["id"])
    assert [(x["account_dt"], x["account_kt"], x["amount"]) for x in lines] == [
        ("4730", "5910", D("20000.00")),
        ("5910", "4730", D("20000.00")),
    ]
    assert lines[1]["reversal_of_id"] is not None and lines[1]["entry_date"] == business_today()
    again = await env.client.post(
        f"{ADJ}/{body['id']}/cancel", json={"reason": "x"}, headers=s.h("accountant")
    )
    assert again.status_code == 409 and err(again) == "DOC_ALREADY_CANCELLED"
    audit = await rows(
        env.db, s.tenant_id, "SELECT action FROM app.audit_log WHERE entity = 'ledger_adjustments' AND entity_id = :e "
        "ORDER BY id", e=UUID(body["id"]),
    )  # fmt: skip
    assert [a["action"] for a in audit] == ["ledger_adjustment.posted", "ledger_adjustment.cancelled"]
    status = await env.client.get(ADJ, params={"status": "cancelled"}, headers=s.h("accountant", key=None))
    assert [i["status"] for i in status.json()["items"]] == ["cancelled"]


async def test_ledger_adjustment_validation(env: Env) -> None:
    s = await shop(env)
    await set_go_live(env, s, business_today() - timedelta(days=40))
    same = await adjust(env, s, "9430", "9430", "1.00")
    assert same.status_code == 422 and "validation.same_account" in keys(same)
    stock = await adjust(env, s, "2920", "9390", "1.00")
    assert "validation.account_register_managed" in keys(stock)
    unknown = await adjust(env, s, "1234", "9390", "1.00")
    assert "validation.account_not_allowed" in keys(unknown)
    payroll = await adjust(env, s, "6710", "5010", "1.00")  # qaror #52 — not in use
    assert "validation.account_not_allowed" in keys(payroll)
    future = await adjust(env, s, "9430", "5010", "1.00", day=business_today() + timedelta(days=1))
    assert "validation.doc_date_in_future" in keys(future)
    no_cp = await adjust(env, s, "6310", "4010", "1.00")
    assert "validation.required" in keys(no_cp)
    bad_key = await adjust(env, s, "9430", "5010", "1.00", analytics={"colour": "red"})
    assert "validation.not_allowed" in keys(bad_key)
    opening = await adjust(env, s, "5010", "0000", "1.00")  # 0000 only on go_live_date − 1
    assert "validation.opening_entry_date" in keys(opening)
    assert (
        opening.json()["error"]["params"]["expected"] == (business_today() - timedelta(days=41)).isoformat()
    )
    no_comment = await adjust(env, s, "9430", "5010", "1.00", comment="  ")
    assert "validation.required" in keys(no_comment)
    forbidden = await adjust(env, s, "9430", "5010", "1.00", role="cashier")
    assert forbidden.status_code == 403
    assert await one(env.db, s.tenant_id, "SELECT count(*) FROM app.ledger_adjustments") == 0


# --- QT-M11-03 / 13 §5.1, §5.2 -----------------------------------------------------------------------------
async def test_qt_m11_03_closed_period_rejects_entry_correction_in_open_month(env: Env) -> None:
    s = await shop(env)
    closed = months_ago(2)
    open_day = months_ago(1) + timedelta(days=4)
    original = await adjust_ok(env, s, "9430", "5010", "5000.00", day=closed + timedelta(days=9))
    await close_sql(env, s, closed)
    into_closed = await adjust(env, s, "9430", "5010", "1000.00", day=closed + timedelta(days=20))
    assert into_closed.status_code == 409 and err(into_closed) == "PERIOD_CLOSED"
    assert into_closed.json()["error"]["params"]["period"] == label(closed)
    not_closed = await adjust(
        env, s, "5010", "9430", "1000.00", day=open_day, correction_of_period=label(months_ago(1))
    )
    assert not_closed.status_code == 422 and "validation.correction_period_not_closed" in keys(not_closed)
    fix = await adjust_ok(env, s, "5010", "9430", "1000.00", day=open_day, correction_of_period=label(closed))
    assert fix["correction_of_period"] == label(closed) and fix["doc_date"] == open_day.isoformat()
    lines = await ledger_of(env, s, fix["id"])
    assert lines[0]["entry_date"] == open_day and lines[0]["analytics"] == {
        "correction_of_period": label(closed)
    }
    # 13 §5.2: a document of the closed month may be cancelled — the storno lands in the open period
    cancel = await env.client.post(
        f"{ADJ}/{original['id']}/cancel", json={"reason": "x"}, headers=s.h("accountant")
    )
    assert cancel.status_code == 200, cancel.text
    storno = (await ledger_of(env, s, original["id"]))[1]
    assert storno["entry_date"] == business_today() and storno["entry_date"] > months_ago(1)
    kept = (await ledger_of(env, s, original["id"]))[0]
    assert kept["entry_date"] == closed + timedelta(days=9)  # the closed month is unchanged


async def test_qt_m11_03_ledger_poster_refuses_closed_period(env: Env) -> None:
    """Any ledger write dated in a closed month → 409 PERIOD_CLOSED (LedgerPoster.post / reverse_entries)."""
    from app.core.db.session import tenant_transaction
    from app.core.errors import AppError
    from app.modules.accounting.wiring import LedgerLine, ledger_poster

    s = await shop(env)
    closed = months_ago(2)
    await close_sql(env, s, closed)
    poster = ledger_poster()
    with pytest.raises(AppError) as exc:
        async with env.db.session_factory() as ses, tenant_transaction(ses, s.tenant_id):
            await poster.post(ses, s.tenant_id, "write_offs", UUID(int=1), [
                LedgerLine(closed + timedelta(days=3), s.branch_id, "9430", "2920", D("10.00")),
            ])  # fmt: skip
    assert exc.value.code.value == "PERIOD_CLOSED"
    with pytest.raises(AppError) as exc2:
        async with env.db.session_factory() as ses, tenant_transaction(ses, s.tenant_id):
            await poster.assert_period_open(ses, month_last := closed + timedelta(days=27))
    assert exc2.value.code.value == "PERIOD_CLOSED" and month_last.month == closed.month


# --- BO-06 «Keyingi qarzga hisoblash», 13 §2.14 example ------------------------------------------------
async def test_bo06_offset_advance_to_next_debt_dt6310_kt4010(env: Env) -> None:
    s = await shop(env)
    cid = await customer(env, s)
    go_live = business_today() - timedelta(days=30)
    await set_go_live(env, s, go_live)
    cp = {"counterparty_id": str(cid)}
    # opening receivable 300 000 (Dt 4010 / Kt 0000) and an offline overpayment 50 000 (Dt 5010 / Kt 6310)
    opening = await adjust_ok(
        env, s, "4010", "0000", "300000.00", day=go_live - timedelta(days=1), analytics=cp
    )
    await add_ledger(env, s, "5010", "6310", "50000.00", business_today(), doc_type="debt_payments", **cp)
    assert await receivable(env, s, cid) == D("300000.00")
    moves = await rows(env.db, s.tenant_id, "SELECT direction, amount FROM app.debt_moves WHERE doc_id = :d",
                       d=UUID(opening["id"]))  # fmt: skip
    assert moves == [{"direction": "receivable", "amount": D("300000.00")}]

    too_much = await adjust(env, s, "6310", "4010", "50000.01", analytics=cp)
    assert too_much.status_code == 422 and "validation.adjustment_exceeds_balance" in keys(too_much)
    assert too_much.json()["error"]["params"] == {"available": "50000.00", "balance": "advance_6310"}
    offset = await adjust_ok(
        env, s, "6310", "4010", "50000.00", analytics=cp, comment="Keyingi qarzga hisoblash"
    )
    assert [
        (x["account_dt"], x["account_kt"], x["amount"]) for x in await ledger_of(env, s, offset["id"])
    ] == [("6310", "4010", D("50000.00"))]
    assert await receivable(env, s, cid) == D("250000.00")
    assert await balance(env, s, "6310", counterparty_id=str(cid)) == D("0.00")
    assert await balance(env, s, "4010", counterparty_id=str(cid)) == D("250000.00")
    again = await adjust(env, s, "6310", "4010", "1.00", analytics=cp)
    assert again.status_code == 422  # no advance left
    # cancel = storno: the advance and the receivable come back (debt_moves reversed too)
    cancel = await env.client.post(
        f"{ADJ}/{offset['id']}/cancel", json={"reason": "x"}, headers=s.h("accountant")
    )
    assert cancel.status_code == 200, cancel.text
    assert await receivable(env, s, cid) == D("300000.00")
    assert await balance(env, s, "6310", counterparty_id=str(cid)) == D("-50000.00")


async def test_ledger_adjustment_never_drives_receivable_negative(env: Env) -> None:
    s = await shop(env)
    cid = await customer(env, s)
    response = await adjust(env, s, "9430", "4010", "1.00", analytics={"counterparty_id": str(cid)})
    assert response.status_code == 422 and response.json()["error"]["params"]["balance"] == "receivable"
