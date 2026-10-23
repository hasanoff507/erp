"""Cash movements (M16): ``cash_movement.created`` + back-office REST (18 §13, 20 #52–#54, 13 §2.18).

US-M16-01; QT-M16-01/02/06, QT-PERM-01/05, QT-IDEMP-01/02/03.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.accounting.wiring import business_today
from tests.support.cash import (
    Till,
    cash_env_fixture,  # noqa: F401 - fixture "env"
    ledger,
    make_till,
    movement,
    one,
    open_shift,
    push,
    sql,
)
from tests.support.catalog import Env
from tests.support.ordering import TXN_ORDER

pytestmark = pytest.mark.asyncio
API = "/api/v1/cash-movements"


async def _founder(env: Env, till: Till, founder: bool = True) -> UUID:
    cp = uuid7()
    await sql(
        env.db, till.shop.tenant_id,
        "INSERT INTO app.counterparties (id, tenant_id, kind, name, is_founder) VALUES (:id, :t, 'person', 'Ta''sischi', :f)",
        id=cp, t=till.shop.tenant_id, f=founder,
    )  # fmt: skip
    return cp


async def _cash_moves(env: Env, till: Till, doc_id: UUID) -> list[str]:
    rows = await sql(env.db, till.shop.tenant_id, "SELECT amount, method FROM app.cash_moves WHERE doc_id = :d "
                     f"ORDER BY {TXN_ORDER}, id", d=doc_id)  # fmt: skip
    return [f"{format(r[0], 'f')}:{r[1]}" for r in rows]


def _body(till: Till, shift_id: UUID, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cash_register_id": str(till.register_id), "shift_id": str(shift_id), "direction": "out",
        "reason": "collection", "amount": "50000.00", "doc_date": business_today().isoformat(),
    }  # fmt: skip
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


async def test_qt_m16_01_other_out_within_limit_posts_9430(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    payload = movement(till, shift_id, amount="40000.00")
    res = await push(env, till, "cash_movement.created", payload)
    assert res.error is None, res.error and (res.error.code, res.error.details)
    doc = UUID(payload["id"])
    assert res.server == {"id": payload["id"]}
    assert await _cash_moves(env, till, doc) == ["-40000.00:cash"]
    rows = await ledger(env.db, till.shop.tenant_id, "cash_movements", doc)
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("9430", "5010", "40000.00")]
    row = (await sql(env.db, till.shop.tenant_id, "SELECT status, account, number FROM app.cash_movements WHERE id = :d",
                     d=doc))[0]  # fmt: skip
    assert row[0] == "posted" and row[1] == "9430" and row[2].startswith("CM-")
    assert (
        await one(
            env.db, till.shop.tenant_id, "SELECT count(*) FROM app.doc_approvals WHERE doc_id = :d", d=doc
        )
        == 0
    )
    # other/in → Dt 5010 / Kt 9390
    inflow = movement(till, shift_id, direction="in", amount="15000.00")
    assert (await push(env, till, "cash_movement.created", inflow)).error is None
    rows = await ledger(env.db, till.shop.tenant_id, "cash_movements", UUID(inflow["id"]))
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("5010", "9390", "15000.00")]
    # wrong pair deposit + out → 422
    bad = await push(
        env, till, "cash_movement.created", movement(till, shift_id, reason="deposit", comment=None)
    )
    assert bad.code == "VALIDATION_ERROR"
    assert {d.field for d in bad.error.details} == {"direction"}  # type: ignore[union-attr]
    # other without comment, 4730 without employee, 6310 without counterparty
    for over, field in (({"comment": None}, "comment"), ({"account": "4730"}, "employee_id"),
                        ({"account": "6310"}, "counterparty_id")):  # fmt: skip
        miss = await push(env, till, "cash_movement.created", movement(till, shift_id, **over))
        assert miss.code == "VALIDATION_ERROR" and field in {d.field for d in miss.error.details}  # type: ignore[union-attr]


async def test_qt_m16_02_and_qt_perm_05_withdraw_limit(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    exact = await push(env, till, "cash_movement.created", movement(till, shift_id, amount="50000.00"))
    assert exact.error is None
    over = movement(till, shift_id, amount="50001.00")
    refused = await push(env, till, "cash_movement.created", over)
    assert refused.code == "CASH_WITHDRAW_LIMIT_EXCEEDED"
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.cash_movements WHERE id = :d",
                     d=UUID(over["id"])) == 0  # fmt: skip
    # manager PIN at the till (local_pin) → accepted with a doc_approvals row
    approved = await push(
        env, till, "cash_movement.created",
        {**over, "approval": {"mode": "local_pin", "approved_by": str(till.shop.user_ids["manager"]),
                              "pin_verified_locally": True}},
    )  # fmt: skip
    assert approved.error is None, approved.error and approved.error.params
    row = (await sql(env.db, till.shop.tenant_id, "SELECT kind, mode, approved_by, requested_value FROM app.doc_approvals "
                     "WHERE doc_id = :d", d=UUID(over["id"])))[0]  # fmt: skip
    assert (row[0], row[1], row[2], format(row[3], "f")) == (
        "cash_withdrawal_over_limit",
        "local_pin",
        till.shop.user_ids["manager"],
        "50001.0000",
    )
    # the cashier cannot approve himself; an approver without the right is APPROVAL_INVALID
    self_ok = await push(
        env, till, "cash_movement.created",
        {**movement(till, shift_id, amount="60000.00"),
         "approval": {"mode": "local_pin", "approved_by": str(till.shop.user_ids["cashier"]), "pin_verified_locally": True}},
    )  # fmt: skip
    assert self_ok.code == "APPROVAL_INVALID"
    acct = await push(
        env, till, "cash_movement.created",
        {**movement(till, shift_id, amount="60000.00"),
         "approval": {"mode": "local_pin", "approved_by": str(till.shop.user_ids["accountant"]),
                      "pin_verified_locally": True}},
    )  # fmt: skip
    assert acct.code == "APPROVAL_INVALID"


async def test_offline_local_pin_over_approver_limit_is_accepted_with_exception(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    from tests.support.catalog import set_limit

    await set_limit(env.db, till.shop.tenant_id, "manager", "cash.withdraw", "70000.00")
    payload = {**movement(till, shift_id, amount="90000.00"),
               "approval": {"mode": "local_pin", "approved_by": str(till.shop.user_ids["manager"]),
                            "pin_verified_locally": True}}  # fmt: skip
    online = await push(env, till, "cash_movement.created", payload)
    assert online.code == "APPROVAL_INVALID"
    from datetime import UTC, datetime, timedelta

    made = datetime.now(UTC) - timedelta(hours=3)
    offline = await push(env, till, "cash_movement.created", payload, created_at=made)
    assert offline.error is None
    assert offline.result is not None
    kinds = [e.kind for e in offline.result.sync_exceptions]
    assert kinds == ["approval_limit_exceeded_offline"]
    assert offline.result.sync_exceptions[0].details["limit"] == "70000.0000"
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs "
                     "WHERE payload->>'event' = 'over_limit_action' AND payload->>'offline' = 'true'") == 1  # fmt: skip


async def test_qt_perm_01_owner_withdraws_any_amount_without_approval(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, actor="owner")
    payload = movement(till, shift_id, amount="5000000.00")
    res = await push(env, till, "cash_movement.created", payload, actor="owner")
    assert res.error is None
    tenant = till.shop.tenant_id
    assert await one(env.db, tenant, "SELECT count(*) FROM app.approval_requests") == 0
    assert await one(env.db, tenant, "SELECT count(*) FROM app.doc_approvals") == 0
    rest = await env.client.post(
        API, json=_body(till, shift_id, amount="9000000.00"), headers=till.shop.h("owner")
    )
    assert rest.status_code == 201 and rest.json()["status"] == "posted"
    assert await one(env.db, tenant, "SELECT count(*) FROM app.approval_requests") == 0


async def test_qt_m16_06_owner_withdrawal_llc_founder_and_sole_proprietor(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    tenant = till.shop.tenant_id
    founder = await _founder(env, till)
    no_cp = await push(env, till, "cash_movement.created",
                       movement(till, shift_id, reason="owner_withdrawal", comment=None, amount="10000.00"))  # fmt: skip
    assert no_cp.code == "VALIDATION_ERROR"
    stranger = await _founder(env, till, founder=False)
    not_founder = await push(
        env,
        till,
        "cash_movement.created",
        movement(
            till,
            shift_id,
            reason="owner_withdrawal",
            comment=None,
            amount="10000.00",
            counterparty_id=str(stranger),
        ),
    )
    assert not_founder.code == "VALIDATION_ERROR"
    res = await env.client.post(
        API, json=_body(till, shift_id, reason="owner_withdrawal", amount="100000.00", counterparty_id=str(founder)),
        headers=till.shop.h("owner"),
    )  # fmt: skip
    assert res.status_code == 201, res.text
    doc = UUID(res.json()["id"])
    rows = await ledger(env.db, tenant, "cash_movements", doc)
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("4890", "5010", "100000.00")]
    assert rows[0][3]["counterparty_id"] == str(founder)
    assert (
        await one(env.db, tenant, "SELECT count(*) FROM app.fiscal_receipts WHERE shift_id = :s", s=shift_id)
        == 0
    )
    await sql(env.db, tenant, "UPDATE app.tenants SET legal_form = 'sole_proprietor'")
    yatt = await env.client.post(
        API,
        json=_body(till, shift_id, reason="owner_withdrawal", amount="100000.00"),
        headers=till.shop.h("owner"),
    )
    assert yatt.status_code == 201, yatt.text
    rows = await ledger(env.db, tenant, "cash_movements", UUID(yatt.json()["id"]))
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("8720", "5010", "100000.00")]


async def test_collection_and_deposit_postings_and_list(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    tenant = till.shop.tenant_id
    res = await env.client.post(API, json=_body(till, shift_id), headers=till.shop.h("owner"))
    assert res.status_code == 201
    rows = await ledger(env.db, tenant, "cash_movements", UUID(res.json()["id"]))
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("5710", "5010", "50000.00")]
    assert rows[0][3]["payment_method"] == "collection"
    dep = await env.client.post(API, json=_body(till, shift_id, direction="in", reason="deposit", amount="20000.00"),
                                headers=till.shop.h("cashier"))  # fmt: skip
    assert dep.status_code == 201, dep.text
    rows = await ledger(env.db, tenant, "cash_movements", UUID(dep.json()["id"]))
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("5010", "5110", "20000.00")]
    page = await env.client.get(API, params={"shift_id": str(shift_id), "direction": "in"},
                                headers=till.shop.h("cashier", key=None))  # fmt: skip
    assert page.status_code == 200
    assert [i["id"] for i in page.json()["items"]] == [dep.json()["id"]]
    closed = await push(env, till, "shift.closed", {"shift_id": str(shift_id), "counted_cash": "0.00",
                                                     "variance_note": "x"})  # fmt: skip
    assert closed.error is None
    late = await env.client.post(API, json=_body(till, shift_id), headers=till.shop.h("owner"))
    assert late.status_code == 409 and late.json()["error"]["code"] == "SHIFT_NOT_OPEN"


async def test_rest_over_limit_draft_then_approval_posts(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    tenant = till.shop.tenant_id
    res = await env.client.post(
        API, json=_body(till, shift_id, amount="70000.00"), headers=till.shop.h("cashier")
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "draft" and body["approval_request_id"]
    doc = UUID(body["id"])
    assert await _cash_moves(env, till, doc) == []
    approve = await env.client.post(
        f"/api/v1/approval-requests/{body['approval_request_id']}/approve", json={"pin": "4321"},
        headers=till.shop.h("manager"),
    )  # fmt: skip
    assert approve.status_code == 200, approve.text
    assert await one(env.db, tenant, "SELECT status FROM app.cash_movements WHERE id = :d", d=doc) == "posted"
    assert await _cash_moves(env, till, doc) == ["-70000.00:cash"]
    assert await one(env.db, tenant, "SELECT status FROM app.approval_requests WHERE id = :r",
                     r=UUID(body["approval_request_id"])) == "consumed"  # fmt: skip
    row = (
        await sql(env.db, tenant, "SELECT mode, approved_by FROM app.doc_approvals WHERE doc_id = :d", d=doc)
    )[0]
    assert row == ("remote_request", till.shop.user_ids["manager"])


async def test_cancel_reverses_registers(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    tenant = till.shop.tenant_id
    res = await env.client.post(API, json=_body(till, shift_id, reason="other", comment="x", amount="30000.00"),
                                headers=till.shop.h("owner"))  # fmt: skip
    doc = UUID(res.json()["id"])
    cancel = await env.client.post(
        f"{API}/{doc}/cancel", json={"reason": "xato"}, headers=till.shop.h("owner")
    )
    assert cancel.status_code == 200 and cancel.json() == {"id": str(doc), "status": "cancelled"}
    # one original + one reversal (reversal_of_id), compared order-free
    moves = await sql(env.db, tenant, "SELECT amount, reversal_of_id IS NOT NULL FROM app.cash_moves WHERE doc_id = :d",
                      d=doc)  # fmt: skip
    assert sorted((format(r[0], "f"), r[1]) for r in moves) == [("-30000.00", False), ("30000.00", True)]
    entries = await sql(env.db, tenant, "SELECT account_dt, account_kt, amount, reversal_of_id IS NOT NULL "
                        "FROM app.ledger_entries WHERE doc_type = 'cash_movements' AND doc_id = :d", d=doc)  # fmt: skip
    assert sorted((r[0], r[1], format(r[2], "f"), r[3]) for r in entries) == [
        ("5010", "9430", "30000.00", True),
        ("9430", "5010", "30000.00", False),
    ]
    again = await env.client.post(
        f"{API}/{doc}/cancel", json={"reason": "xato"}, headers=till.shop.h("owner")
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "DOC_ALREADY_CANCELLED"
    audit = await one(
        env.db, tenant, "SELECT count(*) FROM app.audit_log WHERE action = 'cash_movement_cancelled'"
    )
    assert audit == 1


async def test_qt_idemp_01_same_key_same_body_replays(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    headers = till.shop.h("owner", key="K1-" + str(uuid7()))
    first = await env.client.post(API, json=_body(till, shift_id), headers=headers)
    second = await env.client.post(API, json=_body(till, shift_id), headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert (
        await one(
            env.db,
            till.shop.tenant_id,
            "SELECT count(*) FROM app.cash_moves WHERE doc_type = 'cash_movements'",
        )
        == 1
    )


async def test_qt_idemp_02_parallel_same_key_in_progress(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    key = "K2-" + str(uuid7())
    lock = f"idem:{till.shop.tenant_id}:{key}"
    redis = env.app.state.redis
    await redis.set(
        lock, "other-request", ex=30
    )  # the first request still holds the lock (in its transaction)
    try:
        res = await env.client.post(API, json=_body(till, shift_id), headers=till.shop.h("owner", key=key))
    finally:
        await redis.delete(lock)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS" and res.headers["Retry-After"]
    # real concurrency: two requests with one key — one wins, the other is replayed or in progress
    key2 = "K2b-" + str(uuid7())
    a, b = await asyncio.gather(
        env.client.post(API, json=_body(till, shift_id), headers=till.shop.h("owner", key=key2)),
        env.client.post(API, json=_body(till, shift_id), headers=till.shop.h("owner", key=key2)),
    )
    assert sorted([a.status_code, b.status_code]) in ([201, 201], [201, 409])
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.cash_movements") == 1


async def test_qt_idemp_03_same_key_other_body_reused(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    headers = till.shop.h("owner", key="K3-" + str(uuid7()))
    first = await env.client.post(API, json=_body(till, shift_id, amount="50000.00"), headers=headers)
    assert first.status_code == 201
    second = await env.client.post(API, json=_body(till, shift_id, amount="70000.00"), headers=headers)
    assert second.status_code == 422 and second.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_permissions_and_scope(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    acct = await env.client.post(API, json=_body(till, shift_id), headers=till.shop.h("accountant"))
    assert acct.status_code == 403
    listing = await env.client.get(API, headers=till.shop.h("accountant", key=None))
    assert listing.status_code in (200, 403)
    missing = await env.client.post(
        f"{API}/{uuid7()}/cancel", json={"reason": "x"}, headers=till.shop.h("owner")
    )
    assert missing.status_code == 404
