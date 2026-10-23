"""Recurring expenses (US-M15-02; 20 #48–#51; QT-M15-02 "Ijara to'lash vaqti: 3 000 000 so'm")."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.queue import make_queue
from app.modules.accounting.wiring import business_today
from app.modules.expenses.domain.expenses import add_period
from app.modules.expenses.wiring import REMIND_JOB, remind_recurring
from tests.support.cash import (
    Till,
    cash_env_fixture,  # noqa: F401 - fixture "env"
    make_till,
    one,
    open_shift,
    outbox_events,
    sql,
)
from tests.support.catalog import Env, set_limit
from tests.support.expenses import API, category_id, ledger_lines

pytestmark = pytest.mark.asyncio
REC = f"{API}/recurring-expenses"


async def _rule(env: Env, till: Till, role: str = "owner", **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Ijara",
        "category_id": str(await category_id(env, till.shop.tenant_id, "rent_store")),
        "amount": "3000000.00",
        "day_of_month": 5,
        "period": "month",
        "source": "bank",
    }
    body.update(over)
    r = await env.client.post(REC, json=body, headers=till.shop.h(role, branch=till.shop.branch_id))
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


async def _make_due(env: Env, till: Till, rule_id: str, days_ago: int = 0) -> None:
    await sql(env.db, till.shop.tenant_id, "UPDATE app.recurring_expenses SET next_due_date = :d WHERE id = :i",
              d=business_today() - timedelta(days=days_ago), i=rule_id)  # fmt: skip


async def test_qt_m15_02_reminder_then_one_click_confirm_never_auto_paid(
    env: Env, admin_engine: AsyncEngine
) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    rule = await _rule(env, till)
    assert rule["is_active"] is True
    assert rule["is_due"] is (rule["next_due_date"] <= business_today().isoformat())
    assert int(rule["next_due_date"][8:10]) == 5
    await _make_due(env, till, rule["id"], days_ago=1)
    # daily cron job (real SAQ worker, same registry as production)
    queue = make_queue(env.settings.redis_url.get_secret_value(), env.settings.queue_name)
    await queue.connect()
    try:
        await queue.enqueue(REMIND_JOB, tenant_id=str(tenant))
    finally:
        await queue.disconnect()
    assert await env.drain() >= 1
    assert await remind_recurring(env.db, tenant) == 0  # once per (rule, due date)
    events = await outbox_events(admin_engine, tenant, "recurring_expense_due")
    assert len(events) == 1
    assert events[0]["text"] == "Ijara to'lash vaqti: 3 000 000 so'm"
    assert events[0]["amount"] == "3000000.00" and events[0]["recurring_expense_id"] == rule["id"]
    # never paid automatically
    assert await one(env.db, tenant, "SELECT count(*) FROM app.expenses") == 0
    listed = (await env.client.get(REC, headers=till.shop.h(key=None))).json()
    assert listed["total"] == 1 and listed["items"][0]["is_due"] is True
    assert listed["items"][0]["last_triggered_at"] is not None
    # one click → posted expense, next period
    r = await env.client.post(f"{REC}/{rule['id']}/confirm", headers=till.shop.h())
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "posted"
    expense_id = r.json()["expense_id"]
    row = (await sql(env.db, tenant, "SELECT recurring_rule_id, amount, doc_date, comment FROM app.expenses "
                     "WHERE id = :i", i=expense_id))[0]  # fmt: skip
    assert str(row[0]) == rule["id"] and format(row[1], "f") == "3000000.00" and row[2] == business_today()
    assert await ledger_lines(env, tenant, UUID(expense_id)) == [("9410", "5110", "3000000.00", False)]
    expected_next = add_period(business_today() - timedelta(days=1), "month", 5)
    after = (await env.client.get(REC, headers=till.shop.h(key=None))).json()["items"][0]
    assert after["next_due_date"] == expected_next.isoformat()
    again = await env.client.post(f"{REC}/{rule['id']}/confirm", headers=till.shop.h())
    assert again.status_code == 422
    assert again.json()["error"]["details"][0]["message_key"] == "validation.recurring_expense_not_due"


async def test_confirm_amount_override_cash_rule_needs_open_shift(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    rule = await _rule(env, till, source="cash", cash_register_id=str(till.register_id), amount="200000.00")
    await _make_due(env, till, rule["id"])
    r = await env.client.post(f"{REC}/{rule['id']}/confirm", headers=till.shop.h())
    assert r.status_code == 409 and r.json()["error"]["code"] == "SHIFT_NOT_OPEN"
    shift_id = await open_shift(env, till)
    r = await env.client.post(
        f"{REC}/{rule['id']}/confirm", json={"amount_override": "210000.00"}, headers=till.shop.h()
    )
    assert r.status_code == 201, r.text
    expense_id = r.json()["expense_id"]
    moves = await sql(
        env.db, tenant, "SELECT amount, shift_id FROM app.cash_moves WHERE doc_id = :d", d=expense_id
    )
    assert [(format(m[0], "f"), m[1]) for m in moves] == [("-210000.00", shift_id)]


async def test_confirm_over_manager_limit_returns_202(env: Env) -> None:
    till = await make_till(env)
    await set_limit(env.db, till.shop.tenant_id, "manager", "expenses.approve", "1000000.00")
    rule = await _rule(env, till, "manager")
    await _make_due(env, till, rule["id"])
    r = await env.client.post(f"{REC}/{rule['id']}/confirm", headers=till.shop.h("manager"))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "draft" and body["approval_request_id"]
    kind = await one(env.db, till.shop.tenant_id, "SELECT kind FROM app.approval_requests WHERE id = :i",
                     i=body["approval_request_id"])  # fmt: skip
    assert kind == "expense_over_limit"


async def test_rule_validation_patch_and_inactive(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    h = till.shop.h
    tax = await category_id(env, tenant, "tax_payment")
    rent = await category_id(env, tenant, "rent_store")
    base = {
        "category_id": str(rent),
        "amount": "100.00",
        "day_of_month": 5,
        "period": "month",
        "source": "bank",
    }
    bad = [
        {**base, "category_id": str(tax)},  # tax payments are not recurring rules
        {**base, "day_of_month": 29},
        {**base, "period": "week"},
        {**base, "source": "cash"},  # register required
        {**base, "cash_register_id": str(till.register_id)},  # register only for cash
    ]
    for body in bad:
        r = await env.client.post(REC, json=body, headers=h(branch=till.shop.branch_id))
        assert r.status_code == 422, (body, r.text)
    rule = await _rule(env, till, period="quarter", day_of_month=10)
    r = await env.client.patch(
        f"{REC}/{rule['id']}", json={"amount": "3500000.00", "day_of_month": 12, "version": 1}, headers=h()
    )
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "3500000.00" and r.json()["next_due_date"][8:10] == "12"
    stale = await env.client.patch(f"{REC}/{rule['id']}", json={"amount": "1.00", "version": 1}, headers=h())
    assert stale.status_code == 409
    off = await env.client.patch(f"{REC}/{rule['id']}", json={"is_active": False, "version": 2}, headers=h())
    assert off.status_code == 200 and off.json()["is_active"] is False
    await _make_due(env, till, rule["id"], days_ago=200)
    assert await remind_recurring(env.db, tenant) == 0  # inactive rules are never reminded
    r = await env.client.post(f"{REC}/{rule['id']}/confirm", headers=h())
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["message_key"] == "validation.recurring_expense_inactive"
    # re-activation rolls the stale due date forward (no reminders for paused periods)
    on = await env.client.patch(f"{REC}/{rule['id']}", json={"is_active": True, "version": 3}, headers=h())
    assert on.status_code == 200 and on.json()["next_due_date"] >= business_today().isoformat()
    filtered = (await env.client.get(REC, params={"is_active": "false"}, headers=h(key=None))).json()
    assert filtered["total"] == 0
    # cashier has no expenses.create
    assert (await env.client.get(REC, headers=h("cashier", key=None))).status_code == 403
