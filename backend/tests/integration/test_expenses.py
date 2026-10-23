"""Expenses (M15): REST ``draft → post → cancel`` (20 #41–#44) and POS ``expense.created`` (18 §13.2).

US-M15-01; QT-M15-01, QT-M15-04, QT-M15-05, QT-M15-06; 13 §2.17 / §2.26 worked examples (B4-DoD-06).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.accounting.wiring import business_today, day_start, month_start
from tests.support.cash import (
    PIN,
    Till,
    cash_env_fixture,  # noqa: F401 - fixture "env"
    make_till,
    one,
    open_shift,
    push,
    sql,
)
from tests.support.catalog import Env, set_limit
from tests.support.expenses import (
    API,
    cash_moves,
    category_id,
    expense_body,
    ledger_lines,
    pos_payload,
    push_expense,
)

pytestmark = pytest.mark.asyncio
EXP = f"{API}/expenses"


async def _create(env: Env, till: Till, role: str = "owner", **over: Any) -> dict[str, Any]:
    cat = over.pop("category", None) or await category_id(env, till.shop.tenant_id, "rent_store")
    r = await env.client.post(
        EXP, json=expense_body(cat, **over), headers=till.shop.h(role, branch=till.shop.branch_id)
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def _post(env: Env, till: Till, expense_id: str, role: str = "owner") -> Any:
    return await env.client.post(
        f"{EXP}/{expense_id}/post", headers=till.shop.h(role, branch=till.shop.branch_id)
    )


async def _status(env: Env, till: Till, expense_id: str) -> str:
    return str(
        await one(env.db, till.shop.tenant_id, "SELECT status FROM app.expenses WHERE id = :i", i=expense_id)
    )


# --- QT-M15-01 / 13 §2.17 --------------------------------------------------------------------------------
async def test_qt_m15_01_cash_expense_posts_9410_and_cash_moves_without_cash_movement(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    created = await _create(
        env,
        till,
        amount="500000.00",
        source="cash",
        cash_register_id=str(till.register_id),
        shift_id=str(shift_id),
    )
    assert created["status"] == "draft" and created["account"] == "9410" and created["number"] is None
    assert created["category_name"].startswith("Ijara")
    r = await _post(env, till, created["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "posted" and r.json()["number"].startswith("E-01-")
    doc = UUID(created["id"])
    assert await cash_moves(env, till.shop.tenant_id, doc) == [("-500000.00", "cash", "expenses")]
    assert await ledger_lines(env, till.shop.tenant_id, doc) == [("9410", "5010", "500000.00", False)]
    analytics = await one(
        env.db, till.shop.tenant_id,
        "SELECT analytics FROM app.ledger_entries WHERE doc_type = 'expenses' AND doc_id = :d", d=doc,
    )  # fmt: skip
    assert analytics["cash_register_id"] == str(till.register_id)
    assert analytics["expense_category_id"] == created["category_id"] and analytics["source"] == "cash"
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.cash_movements") == 0
    actions = [
        r[0]
        for r in await sql(
            env.db,
            till.shop.tenant_id,
            "SELECT action FROM app.audit_log WHERE entity_id = :d ORDER BY id",
            d=doc,
        )
    ]
    assert actions == ["expense.created", "expense.posted"]


async def test_13_2_17_bank_and_corporate_card_credit_5110_without_cash_moves(env: Env) -> None:
    till = await make_till(env)
    office = await category_id(env, till.shop.tenant_id, "rent_office")
    bank = await _create(env, till, category=office, amount="1200000.00", source="bank")
    card = await _create(env, till, category=office, amount="35000.50", source="card", comment="Domen")
    for created, amount in ((bank, "1200000.00"), (card, "35000.50")):
        assert (await _post(env, till, created["id"])).status_code == 200
        doc = UUID(created["id"])
        assert await ledger_lines(env, till.shop.tenant_id, doc) == [("9420", "5110", amount, False)]
        assert await cash_moves(env, till.shop.tenant_id, doc) == []


async def test_qt_m15_06_tax_payment_requires_tax_type_and_posts_6410(env: Env) -> None:
    """13 §2.26 example: VAT payable "36000.00" paid from the bank → Dt 6410 / Kt 5110, never 94xx."""
    till = await make_till(env)
    tax = await category_id(env, till.shop.tenant_id, "tax_payment")
    h = till.shop.h("owner", branch=till.shop.branch_id)
    r = await env.client.post(EXP, json=expense_body(tax, amount="36000.00"), headers=h)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["details"] == [{"field": "tax_type", "message_key": "validation.required"}]
    rent = await category_id(env, till.shop.tenant_id, "rent_store")
    r = await env.client.post(EXP, json=expense_body(rent, tax_type="vat"), headers=h)
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [{"field": "tax_type", "message_key": "validation.must_be_null"}]
    created = await _create(env, till, category=tax, amount="36000.00", source="bank", tax_type="vat")
    assert created["tax_type"] == "vat" and created["account"] == "6410"
    assert (await _post(env, till, created["id"])).status_code == 200
    doc = UUID(created["id"])
    assert await ledger_lines(env, till.shop.tenant_id, doc) == [("6410", "5110", "36000.00", False)]
    analytics = await one(
        env.db, till.shop.tenant_id,
        "SELECT analytics FROM app.ledger_entries WHERE doc_type = 'expenses' AND doc_id = :d", d=doc,
    )  # fmt: skip
    assert analytics["tax_type"] == "vat"
    expense_turnover = await one(
        env.db, till.shop.tenant_id,
        "SELECT count(*) FROM app.ledger_entries WHERE doc_id = :d AND account_dt LIKE '94%'", d=doc,
    )  # fmt: skip
    assert expense_turnover == 0


# --- QT-M15-04: cancel = storno ---------------------------------------------------------------------------
async def test_qt_m15_04_cancel_posted_expense_is_storno_and_audited(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    created = await _create(
        env,
        till,
        amount="70000.00",
        source="cash",
        cash_register_id=str(till.register_id),
        shift_id=str(shift_id),
    )
    assert (await _post(env, till, created["id"])).status_code == 200
    h = till.shop.h("owner", branch=till.shop.branch_id)
    r = await env.client.post(f"{EXP}/{created['id']}/cancel", json={"reason": "Xato summa"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled" and r.json()["cancelled_at"]
    doc = UUID(created["id"])
    assert await _status(env, till, created["id"]) == "cancelled"  # never deleted
    assert await ledger_lines(env, till.shop.tenant_id, doc) == [
        ("9410", "5010", "70000.00", False),
        ("5010", "9410", "70000.00", True),
    ]
    assert await cash_moves(env, till.shop.tenant_id, doc) == [
        ("-70000.00", "cash", "expenses"),
        ("70000.00", "cash", "expenses"),
    ]
    audit = await one(
        env.db, till.shop.tenant_id,
        "SELECT after FROM app.audit_log WHERE entity_id = :d AND action = 'expense.cancelled'", d=doc,
    )  # fmt: skip
    assert audit["reason"] == "Xato summa" and audit["status"] == "cancelled"
    again = await env.client.post(
        f"{EXP}/{created['id']}/cancel", json={"reason": "Yana"}, headers=till.shop.h()
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "DOC_ALREADY_CANCELLED"
    repost = await _post(env, till, created["id"])
    assert repost.status_code == 409 and repost.json()["error"]["code"] == "DOC_NOT_DRAFT"
    listed = (await env.client.get(EXP, params={"status": "cancelled"}, headers=till.shop.h(key=None))).json()
    assert [i["id"] for i in listed["items"]] == [created["id"]]
    assert listed["items"][0]["cancel_reason"] == "Xato summa" and listed["items"][0]["account"] == "9410"


async def test_cancel_draft_and_closed_shift_cash_expense(env: Env) -> None:
    till = await make_till(env)
    draft = await _create(env, till, source="bank")
    r = await env.client.post(
        f"{EXP}/{draft['id']}/cancel", json={"reason": "Kerak emas"}, headers=till.shop.h()
    )
    assert r.status_code == 200 and await _status(env, till, draft["id"]) == "cancelled"
    assert await ledger_lines(env, till.shop.tenant_id, UUID(draft["id"])) == []
    shift_id = await open_shift(env, till, "100000.00")
    cash = await _create(
        env,
        till,
        amount="30000.00",
        source="cash",
        cash_register_id=str(till.register_id),
        shift_id=str(shift_id),
    )
    assert (await _post(env, till, cash["id"])).status_code == 200
    closed = await push(
        env, till, "shift.closed", {"shift_id": str(shift_id), "counted_cash": "70000.00"}, actor="cashier"
    )
    assert closed.error is None, closed.error and (closed.error.code, closed.error.details)
    r = await env.client.post(f"{EXP}/{cash['id']}/cancel", json={"reason": "Kech"}, headers=till.shop.h())
    assert r.status_code == 409 and r.json()["error"]["code"] == "DOC_INVALID_STATE"
    assert await _status(env, till, cash["id"]) == "posted"


# --- QT-M15-05: expenses.approve limit ---------------------------------------------------------------------
async def test_qt_m15_05_manager_over_expenses_approve_limit_gets_202_owner_unlimited(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    await set_limit(env.db, tenant, "manager", "expenses.approve", "1000000.00")
    small = await _create(env, till, "manager", amount="900000.00")
    assert (await _post(env, till, small["id"], "manager")).status_code == 200
    big = await _create(env, till, "manager", amount="2000000.00")
    r = await _post(env, till, big["id"], "manager")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "draft" and body["approval_request_id"]
    req = (
        await sql(
            env.db,
            tenant,
            "SELECT kind, permission_code, requested_value, linked_doc_type, linked_doc_id, status "
            "FROM app.approval_requests WHERE id = :i",
            i=body["approval_request_id"],
        )
    )[0]
    assert req[0] == "expense_over_limit" and req[1] == "expenses.approve"
    assert format(req[2], "f") == "2000000.0000" and req[3] == "expenses" and str(req[4]) == big["id"]
    assert await ledger_lines(env, tenant, UUID(big["id"])) == []
    # a second post while pending returns the same request (no duplicates)
    again = await _post(env, till, big["id"], "manager")
    assert again.status_code == 202 and again.json()["approval_request_id"] == body["approval_request_id"]
    listed = (await env.client.get(EXP, params={"status": "draft"}, headers=till.shop.h(key=None))).json()
    assert listed["items"][0]["approval_status"] == "pending"
    # owner approves (BO-16, PIN) → the expenses hook posts the draft in the approve transaction
    ok = await env.client.post(
        f"{API}/approval-requests/{body['approval_request_id']}/approve",
        json={"pin": PIN},
        headers=till.shop.h(),
    )
    assert ok.status_code == 200, ok.text
    assert await _status(env, till, big["id"]) == "posted"
    done = await _post(env, till, big["id"], "manager")
    assert done.status_code == 409 and done.json()["error"]["code"] == "DOC_NOT_DRAFT"
    assert await ledger_lines(env, tenant, UUID(big["id"])) == [("9410", "5110", "2000000.00", False)]
    approval = await sql(
        env.db, tenant, "SELECT kind, mode, approved_by FROM app.doc_approvals WHERE doc_id = :d", d=big["id"]
    )
    assert [(a[0], a[1], a[2]) for a in approval] == [
        ("expense_over_limit", "remote_request", till.shop.user_ids["owner"])
    ]
    assert await one(env.db, tenant, "SELECT status FROM app.approval_requests WHERE id = :i",
                     i=body["approval_request_id"]) == "consumed"  # fmt: skip
    # an approved, unused request (approved outside the hook) is consumed by the next post
    other = await _create(env, till, "manager", amount="1500000.00")
    pending = (await _post(env, till, other["id"], "manager")).json()["approval_request_id"]
    await sql(
        env.db, tenant,
        "UPDATE app.approval_requests SET status = 'approved', resolved_by = :o, resolved_at = now() WHERE id = :i",
        o=till.shop.user_ids["owner"], i=pending,
    )  # fmt: skip
    consumed = await _post(env, till, other["id"], "manager")
    assert consumed.status_code == 200, consumed.text
    assert (
        await one(env.db, tenant, "SELECT status FROM app.approval_requests WHERE id = :i", i=pending)
        == "consumed"
    )
    # QT-PERM-01: the owner posts any amount directly
    huge = await _create(env, till, amount="50000000.00")
    assert (await _post(env, till, huge["id"])).status_code == 200


async def test_accountant_without_expenses_approve_needs_approval_bo16_approve_posts(env: Env) -> None:
    """Accountant: ``expenses.create`` (kiritish) only — every post goes to the owner; approving posts it."""
    till = await make_till(env)
    tenant = till.shop.tenant_id
    draft = await _create(env, till, "accountant", amount="10000.00")
    r = await _post(env, till, draft["id"], "accountant")
    assert r.status_code == 202
    request_id = r.json()["approval_request_id"]
    ok = await env.client.post(
        f"{API}/approval-requests/{request_id}/approve", json={"pin": PIN}, headers=till.shop.h()
    )
    assert ok.status_code == 200, ok.text
    # BO-16 approve runs the expenses hook: the draft is posted in the approve transaction
    assert await _status(env, till, draft["id"]) == "posted"
    assert await ledger_lines(env, tenant, UUID(draft["id"])) == [("9410", "5110", "10000.00", False)]


# --- REST validation ---------------------------------------------------------------------------------------
async def test_create_validation_and_permissions(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    rent = await category_id(env, tenant, "rent_store")
    h = till.shop.h("owner", branch=till.shop.branch_id)
    future = (business_today() + timedelta(days=1)).isoformat()
    r = await env.client.post(EXP, json=expense_body(rent, doc_date=future), headers=h)
    assert (
        r.status_code == 422
        and r.json()["error"]["details"][0]["message_key"] == "validation.doc_date_in_future"
    )
    r = await env.client.post(
        EXP, json=expense_body(rent, source="cash"), headers=till.shop.h(branch=till.shop.branch_id)
    )
    assert r.status_code == 422
    assert {d["field"] for d in r.json()["error"]["details"]} == {"cash_register_id", "shift_id"}
    r = await env.client.post(EXP, json=expense_body(rent, amount="0.00"), headers=till.shop.h())
    assert r.status_code == 422
    r = await env.client.post(EXP, json=expense_body(rent, extra=1), headers=till.shop.h())
    assert r.status_code == 422
    r = await env.client.post(
        EXP, json=expense_body(UUID(int=7)), headers=till.shop.h(branch=till.shop.branch_id)
    )
    assert r.status_code == 404 and r.json()["error"]["params"]["resource"] == "expense_category"
    # cash: the shift must be open
    shift_id = await open_shift(env, till)
    await sql(env.db, tenant, "UPDATE app.shifts SET status = 'closed', expected_cash = 0, counted_cash = 0, "
              "closed_at = now() WHERE id = :s", s=shift_id)  # fmt: skip
    r = await env.client.post(
        EXP,
        json=expense_body(
            rent, source="cash", cash_register_id=str(till.register_id), shift_id=str(shift_id)
        ),
        headers=till.shop.h(branch=till.shop.branch_id),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "SHIFT_NOT_OPEN"
    # archived category
    await sql(env.db, tenant, "UPDATE app.expense_categories SET archived_at = now() WHERE id = :c", c=rent)
    r = await env.client.post(EXP, json=expense_body(rent), headers=till.shop.h(branch=till.shop.branch_id))
    assert r.status_code == 422 and r.json()["error"]["details"][0]["message_key"] == "validation.archived"
    # cashier has no expenses.create (POS uses expense.created)
    r = await env.client.get(EXP, headers=till.shop.h("cashier", key=None))
    assert r.status_code == 403


async def test_list_filters_cursor_and_totals(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    office = await category_id(env, tenant, "rent_office")
    ids = []
    for amount in ("100.00", "200.00", "300.00"):
        ids.append((await _create(env, till, amount=amount))["id"])
    other = await _create(env, till, category=office, amount="50.00", source="card")
    assert (await _post(env, till, ids[0])).status_code == 200
    h = till.shop.h(key=None)
    page = (await env.client.get(EXP, params={"limit": 2}, headers=h)).json()
    assert [i["id"] for i in page["items"]] == [other["id"], ids[2]]
    assert page["totals"] == {"posted": "100.00", "draft": "550.00"}
    rest = (await env.client.get(EXP, params={"limit": 2, "cursor": page["next_cursor"]}, headers=h)).json()
    assert [i["id"] for i in rest["items"]] == [ids[1], ids[0]] and rest["next_cursor"] is None
    by_cat = (await env.client.get(EXP, params={"category_id": str(office)}, headers=h)).json()
    assert [i["id"] for i in by_cat["items"]] == [other["id"]]
    by_source = (await env.client.get(EXP, params={"source": "card"}, headers=h)).json()
    assert [i["source"] for i in by_source["items"]] == ["card"]
    posted = (await env.client.get(EXP, params={"status": "posted"}, headers=h)).json()
    assert [i["number"][:2] for i in posted["items"]] == ["E-"]
    today = business_today().isoformat()
    ranged = (
        await env.client.get(EXP, params={"doc_date__gte": today, "doc_date__lte": today}, headers=h)
    ).json()
    assert len(ranged["items"]) == 4
    # another tenant sees nothing
    stranger = await make_till(env, "Boshqa do'kon")
    assert (await env.client.get(EXP, headers=stranger.shop.h(key=None))).json()["items"] == []


# --- POS expense.created (18 §13.2) -----------------------------------------------------------------------
async def test_18_13_2_pos_cash_expense_posts_immediately(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    shift_id = await open_shift(env, till)
    supplies = await category_id(env, tenant, "supplies")
    payload = pos_payload(till, shift_id, supplies, amount="40000.00")
    res = await push_expense(env, till, payload)
    assert res.error is None, res.error and (res.error.code, res.error.details)
    assert res.server == {"id": payload["id"], "status": "posted"}
    doc = UUID(payload["id"])
    assert await ledger_lines(env, tenant, doc) == [("9410", "5010", "40000.00", False)]
    assert await cash_moves(env, tenant, doc) == [("-40000.00", "cash", "expenses")]
    row = (await sql(env.db, tenant, "SELECT status, source, device_id, created_by, client_event_id, number, comment "
                     "FROM app.expenses WHERE id = :d", d=doc))[0]  # fmt: skip
    assert row[0] == "posted" and row[1] == "cash" and row[2] == till.device_id
    assert row[3] == till.shop.user_ids["cashier"] and row[4] is not None and row[5].startswith("E-")
    assert row[6] == "Suv"
    # same id again → duplicate
    dup = await push_expense(env, till, payload)
    assert dup.code == "VALIDATION_ERROR" and dup.error is not None
    assert dup.error.details[0].message_key == "validation.duplicate"


async def test_18_13_2_pos_expense_over_cash_withdraw_limit_needs_approval(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    shift_id = await open_shift(env, till)
    supplies = await category_id(env, tenant, "supplies")
    over = pos_payload(till, shift_id, supplies, amount="60000.00")
    res = await push_expense(env, till, over)
    assert res.code == "CASH_WITHDRAW_LIMIT_EXCEEDED"
    assert await one(env.db, tenant, "SELECT count(*) FROM app.expenses") == 0
    approved = pos_payload(
        till, shift_id, supplies, amount="60000.00",
        approval={"mode": "local_pin", "approved_by": str(till.shop.user_ids["owner"]), "pin_verified_locally": True},
    )  # fmt: skip
    res = await push_expense(env, till, approved)
    assert res.error is None, res.error and (res.error.code, res.error.params)
    rows = await sql(
        env.db, tenant, "SELECT kind, mode FROM app.doc_approvals WHERE doc_id = :d", d=approved["id"]
    )
    assert [(r[0], r[1]) for r in rows] == [("cash_withdrawal_over_limit", "local_pin")]


async def test_pos_expense_offline_approver_limit_too_small_is_accepted_with_exception(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    await set_limit(env.db, tenant, "manager", "cash.withdraw", "70000.00")
    shift_id = await open_shift(env, till)
    supplies = await category_id(env, tenant, "supplies")
    payload = pos_payload(
        till, shift_id, supplies, amount="100000.00",
        approval={"mode": "local_pin", "approved_by": str(till.shop.user_ids["manager"]), "pin_verified_locally": True},
    )  # fmt: skip
    now = datetime.now(UTC)
    res = await push_expense(env, till, payload, created_at=now - timedelta(hours=1), received_at=now)
    assert res.error is None, res.error and (res.error.code, res.error.params)
    assert res.result is not None
    assert [x.kind for x in res.result.sync_exceptions] == ["approval_limit_exceeded_offline"]
    online = pos_payload(
        till, shift_id, supplies, amount="100000.00",
        approval={"mode": "local_pin", "approved_by": str(till.shop.user_ids["manager"]), "pin_verified_locally": True},
    )  # fmt: skip
    assert (await push_expense(env, till, online)).code == "APPROVAL_INVALID"


async def test_pos_expense_validation_and_rights(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    shift_id = await open_shift(env, till)
    supplies = await category_id(env, tenant, "supplies")
    tax = await category_id(env, tenant, "tax_payment")
    extra = pos_payload(till, shift_id, supplies, source="cash")
    assert (await push_expense(env, till, extra)).code == "VALIDATION_ERROR"
    missing = await push_expense(env, till, pos_payload(till, shift_id, UUID(int=9)))
    assert missing.code == "NOT_FOUND" and missing.error is not None
    assert missing.error.params["resource"] == "expense_category"
    no_tax = await push_expense(env, till, pos_payload(till, shift_id, tax, amount="10000.00"))
    assert no_tax.code == "VALIDATION_ERROR"
    with_tax = await push_expense(
        env, till, pos_payload(till, shift_id, tax, amount="10000.00", tax_type="turnover")
    )
    assert with_tax.error is None
    assert await ledger_lines(env, tenant, UUID(with_tax.server["id"])) == [
        ("6410", "5010", "10000.00", False)
    ]
    # accountant has no cash.withdraw
    denied = await push_expense(env, till, pos_payload(till, shift_id, supplies), actor="accountant")
    assert denied.code == "PERMISSION_DENIED"
    wrong_branch = await push_expense(
        env, till, pos_payload(till, shift_id, supplies, branch_id=str(UUID(int=3)))
    )
    assert wrong_branch.code == "VALIDATION_ERROR"
    unknown_shift = await push_expense(env, till, pos_payload(till, UUID(int=5), supplies))
    assert unknown_shift.code == "DEPENDENCY_NOT_SYNCED"
    assert await one(env.db, tenant, "SELECT count(*) FROM app.expenses") == 1


async def test_pos_expense_in_closed_period_goes_to_first_open_date(env: Env) -> None:
    """qaror #69: a late POS expense is never refused with PERIOD_CLOSED."""
    till = await make_till(env)
    tenant = till.shop.tenant_id
    shift_id = await open_shift(env, till)
    supplies = await category_id(env, tenant, "supplies")
    last_month = month_start(business_today()) - timedelta(days=1)
    await sql(env.db, tenant, "INSERT INTO app.period_closings (tenant_id, period, closed_by) VALUES (:t, :p, :u)",
              t=tenant, p=month_start(last_month), u=till.shop.user_ids["owner"])  # fmt: skip
    payload = pos_payload(till, shift_id, supplies, doc_date=last_month.isoformat())
    # SYNC-02: the day comes from the (clamped) event time, so the expense really happened last month
    created = day_start(last_month) + timedelta(hours=12)
    res = await push_expense(env, till, payload, created_at=created, received_at=datetime.now(UTC))
    assert res.error is None, res.error and (res.error.code, res.error.details)
    assert res.result is not None
    assert [x.kind for x in res.result.sync_exceptions] == ["late_in_closed_period"]
    row = (await sql(env.db, tenant, "SELECT entry_date, analytics FROM app.ledger_entries WHERE doc_id = :d",
                     d=payload["id"]))[0]  # fmt: skip
    assert row[0] == month_start(business_today())
    assert row[1]["correction_of_period"] == last_month.strftime("%Y-%m")
    # back-office REST in the closed period → 409 PERIOD_CLOSED
    r = await env.client.post(
        EXP,
        json=expense_body(supplies, doc_date=last_month.isoformat()),
        headers=till.shop.h(branch=till.shop.branch_id),
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "PERIOD_CLOSED"


async def test_acc08_tax_payment_for_unaccrued_tax_refused(env: Env) -> None:
    """ACC-08 / F5: 6410 is credited only by VAT (sale) and turnover (``tax_settlements``) in MVP — any other
    tax paid "to 6410" would leave a debit balance; it is booked as an expense (9430 / payroll) instead."""
    till = await make_till(env)
    tenant = till.shop.tenant_id
    tax = await category_id(env, tenant, "tax_payment")
    h = till.shop.h("owner", branch=till.shop.branch_id)
    for tax_type in ("pit", "social", "property", "land", "other"):
        r = await env.client.post(
            EXP, json=expense_body(tax, amount="10000.00", tax_type=tax_type), headers=h
        )
        assert r.status_code == 422, (tax_type, r.text)
        assert r.json()["error"]["details"] == [
            {"field": "tax_type", "message_key": "validation.tax_type_not_accrued"}
        ]
    turnover = await _create(env, till, category=tax, amount="10000.00", tax_type="turnover")
    assert (await _post(env, till, turnover["id"])).status_code == 200
    # the same rule on the POS
    shift_id = await open_shift(env, till)
    pos = await push_expense(env, till, pos_payload(till, shift_id, tax, amount="10000.00", tax_type="land"))
    assert pos.code == "VALIDATION_ERROR" and pos.error is not None
    assert pos.error.details[0].message_key == "validation.tax_type_not_accrued"
    assert await one(env.db, tenant, "SELECT count(*) FROM app.expenses WHERE tax_type <> 'turnover'") == 0


async def test_sync02_pos_expense_doc_date_from_created_at(env: Env) -> None:
    """SYNC-02 / F8: like cash movements, the server takes ``business_date(created_at)`` — the device
    ``doc_date`` is ignored (not rejected: the cash already left the drawer)."""
    till = await make_till(env)
    tenant = till.shop.tenant_id
    shift_id = await open_shift(env, till)
    supplies = await category_id(env, tenant, "supplies")
    today = business_today()
    # a device claiming an older day → today's date
    stale = pos_payload(till, shift_id, supplies, doc_date=(today - timedelta(days=5)).isoformat())
    res = await push_expense(env, till, stale)
    assert res.error is None, res.error and (res.error.code, res.error.details)
    # 00:30 Tashkent = 19:30 UTC of the previous day: the Tashkent day wins
    early = day_start(today) + timedelta(minutes=30)
    fresh = pos_payload(till, shift_id, supplies, doc_date=(today - timedelta(days=1)).isoformat())
    res = await push_expense(env, till, fresh, created_at=early, received_at=datetime.now(UTC))
    assert res.error is None, res.error and (res.error.code, res.error.details)
    for doc in (stale["id"], fresh["id"]):
        row = (await sql(env.db, tenant, "SELECT e.doc_date, l.entry_date FROM app.expenses e "
                         "JOIN app.ledger_entries l ON l.doc_id = e.id WHERE e.id = :d", d=doc))[0]  # fmt: skip
        assert (row[0], row[1]) == (today, today)


async def test_18_31_expense_created_handler_is_registered_with_sync(env: Env) -> None:
    """B4-EP-18#31: ``/sync/push`` collects ``expense.created`` from ``expenses.wiring.sync_handlers``."""
    from app.modules.sync.wiring import collect_handlers

    assert "expense.created" in collect_handlers(env.settings, env.db)
