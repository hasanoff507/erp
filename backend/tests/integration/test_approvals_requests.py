"""BO-16 approval queue (18 §9) and the ApprovalGate contract (18 §2.4, 15 §2.3).

QT-PERM-01/06/07; offline local PIN over limit (16 §5) is in test_cash_movements.py.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.access.wiring import ApprovalRefIn, approval_gate
from tests.support.cash import (
    PIN,
    Till,
    cash_env_fixture,  # noqa: F401 - fixture "env"
    make_till,
    movement,
    one,
    open_shift,
    outbox_events,
    push,
    sql,
)
from tests.support.catalog import Env
from tests.support.ordering import TXN_ORDER

pytestmark = pytest.mark.asyncio
API = "/api/v1/approval-requests"


async def _request(env: Env, till: Till, amount: str = "70000.00", **extra: Any) -> dict[str, Any]:
    res = await env.client.post(
        API, json={"kind": "cash_withdrawal_over_limit", "context": {"amount": amount}, **extra},
        headers=till.shop.h("cashier", branch=till.shop.branch_id),
    )  # fmt: skip
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


async def _approve(env: Env, till: Till, request_id: str, role: str = "manager", pin: str = PIN) -> Any:
    return await env.client.post(f"{API}/{request_id}/approve", json={"pin": pin}, headers=till.shop.h(role))


def _remote(request_id: str) -> dict[str, Any]:
    return {"mode": "remote_request", "approval_request_id": request_id}


async def test_create_list_get_and_notification(env: Env, admin_engine: AsyncEngine) -> None:
    till = await make_till(env)
    created = await _request(env, till)
    assert created["status"] == "pending" and created["kind"] == "cash_withdrawal_over_limit"
    row = (await sql(env.db, till.shop.tenant_id, "SELECT permission_code, requested_value, expires_at - requested_at "
                     "FROM app.approval_requests WHERE id = :r", r=UUID(created["id"])))[0]  # fmt: skip
    assert row[0] == "cash.withdraw" and row[1] == Decimal("70000.0000") and row[2].total_seconds() == 900
    events = await outbox_events(admin_engine, till.shop.tenant_id, "over_limit_action")
    assert [e["approval_request_id"] for e in events] == [created["id"]]
    queue = await env.client.get(API, params={"status": "pending"}, headers=till.shop.h("manager", key=None))
    assert queue.status_code == 200 and [i["id"] for i in queue.json()["items"]] == [created["id"]]
    own = await env.client.get(f"{API}/{created['id']}", headers=till.shop.h("cashier", key=None))
    assert own.status_code == 200 and own.json()["requested_value"] == "70000.0000"
    # the accountant holds no cash.withdraw → neither sees it nor may open it
    acct = await env.client.get(API, headers=till.shop.h("accountant", key=None))
    assert acct.status_code == 200 and acct.json()["items"] == []
    hidden = await env.client.get(f"{API}/{created['id']}", headers=till.shop.h("accountant", key=None))
    assert hidden.status_code == 404
    bad = await env.client.post(API, json={"kind": "price_change", "context": {"requested_pct": "20.00"}},
                                headers=till.shop.h("cashier", branch=till.shop.branch_id))  # fmt: skip
    assert bad.status_code == 422
    no_value = await env.client.post(API, json={"kind": "cash_withdrawal_over_limit", "context": {}},
                                     headers=till.shop.h("cashier", branch=till.shop.branch_id))  # fmt: skip
    assert no_value.status_code == 422


async def test_qt_perm_06_requester_cannot_approve_own_request(env: Env) -> None:
    till = await make_till(env)
    created = await _request(env, till)
    res = await _approve(env, till, created["id"], role="cashier")
    assert res.status_code == 403 and res.json()["error"]["code"] == "APPROVAL_INVALID"
    rej = await env.client.post(
        f"{API}/{created['id']}/reject", json={"reason": "x"}, headers=till.shop.h("cashier")
    )
    assert rej.status_code == 403
    assert await one(env.db, till.shop.tenant_id, "SELECT status FROM app.approval_requests WHERE id = :r",
                     r=UUID(created["id"])) == "pending"  # fmt: skip


async def test_approve_pin_step_up_and_qt_perm_07_single_use(env: Env, admin_engine: AsyncEngine) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    created = await _request(env, till, "70000.00")
    wrong = await _approve(env, till, created["id"], pin="0000")
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "PIN_INVALID"
    pending_use = await push(
        env,
        till,
        "cash_movement.created",
        {**movement(till, shift_id, amount="70000.00"), "approval": _remote(created["id"])},
    )
    assert pending_use.code == "APPROVAL_INVALID"  # not approved yet
    ok = await _approve(env, till, created["id"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "approved" and ok.json()["resolved_by"] == str(
        till.shop.user_ids["manager"]
    )
    too_big = await push(
        env,
        till,
        "cash_movement.created",
        {**movement(till, shift_id, amount="80000.00"), "approval": _remote(created["id"])},
    )
    assert too_big.code == "APPROVAL_INVALID"
    used = await push(
        env,
        till,
        "cash_movement.created",
        {**movement(till, shift_id, amount="65000.00"), "approval": _remote(created["id"])},
    )
    assert used.error is None
    assert await one(env.db, till.shop.tenant_id, "SELECT status FROM app.approval_requests WHERE id = :r",
                     r=UUID(created["id"])) == "consumed"  # fmt: skip
    again = await push(
        env,
        till,
        "cash_movement.created",
        {**movement(till, shift_id, amount="65000.00"), "approval": _remote(created["id"])},
    )
    assert again.code == "APPROVAL_REQUEST_ALREADY_RESOLVED"
    twice = await _approve(env, till, created["id"])
    assert twice.status_code == 409 and twice.json()["error"]["code"] == "APPROVAL_REQUEST_ALREADY_RESOLVED"
    async with admin_engine.connect() as conn:
        from sqlalchemy import text

        actions = [r[0] for r in await conn.execute(
            text(f"SELECT action FROM app.audit_log WHERE tenant_id = :t AND action LIKE 'approval%' ORDER BY {TXN_ORDER}"),
            {"t": till.shop.tenant_id},
        )]  # fmt: skip
    # the request is its own transaction; approve + apply share one (their relative order is not defined)
    assert actions[0] == "approval_requested"
    assert sorted(actions[1:]) == ["approval_applied", "approval_request_approved"]


async def test_reject_and_expiry(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    rejected = await _request(env, till)
    no_reason = await env.client.post(
        f"{API}/{rejected['id']}/reject", json={}, headers=till.shop.h("manager")
    )
    assert no_reason.status_code == 422
    rej = await env.client.post(
        f"{API}/{rejected['id']}/reject", json={"reason": "Yo'q"}, headers=till.shop.h("manager")
    )
    assert rej.status_code == 200 and rej.json()["status"] == "rejected"
    use = await push(
        env,
        till,
        "cash_movement.created",
        {**movement(till, shift_id, amount="60000.00"), "approval": _remote(rejected["id"])},
    )
    assert use.code == "APPROVAL_REQUEST_ALREADY_RESOLVED"
    late = await _request(env, till)
    await sql(env.db, till.shop.tenant_id, "UPDATE app.approval_requests SET requested_at = now() - interval '20 min', "
              "expires_at = now() - interval '5 min' WHERE id = :r", r=UUID(late["id"]))  # fmt: skip
    seen = await env.client.get(f"{API}/{late['id']}", headers=till.shop.h("manager", key=None))
    assert seen.json()["status"] == "expired"
    expired = await _approve(env, till, late["id"])
    assert expired.status_code == 409 and expired.json()["error"]["code"] == "APPROVAL_REQUEST_EXPIRED"
    assert await env.app.state.approvals.expire_due(till.shop.tenant_id) == 1
    assert await one(env.db, till.shop.tenant_id, "SELECT status FROM app.approval_requests WHERE id = :r",
                     r=UUID(late["id"])) == "expired"  # fmt: skip


async def test_gate_rules_by_kind(env: Env) -> None:
    till = await make_till(env)
    gate = approval_gate()
    users = till.shop.user_ids
    tenant, branch = till.shop.tenant_id, till.shop.branch_id

    async def require(**kw: Any) -> Any:
        base: dict[str, Any] = {
            "tenant_id": tenant, "branch_id": branch, "doc_type": "sales", "doc_id": uuid7(), "offline": False,
            "approval": None,
        }  # fmt: skip
        async with env.db.session_factory() as s, tenant_transaction(s, tenant):
            return await gate.require(s, **{**base, **kw})

    within = await require(kind="discount_over_limit", permission="discount.give", requested_by=users["cashier"],
                           value=Decimal("5.00"))  # fmt: skip
    assert within.required is False
    with pytest.raises(AppError) as exc:
        await require(kind="discount_over_limit", permission="discount.give", requested_by=users["cashier"],
                      value=Decimal("10.00"))  # fmt: skip
    assert exc.value.code.value == "DISCOUNT_LIMIT_EXCEEDED"
    # approver checked against discount.approve (manager holds it, limitless)
    approved = await require(
        kind="discount_over_limit", permission="discount.give", requested_by=users["cashier"], value=Decimal("25.00"),
        approval=ApprovalRefIn(mode="local_pin", approved_by=users["manager"], pin_verified_locally=True),
        line_id=uuid7(),
    )  # fmt: skip
    assert approved.required is True and approved.doc_approval_id is not None
    for kind, permission, code in (
        ("return_no_receipt", "returns.approve", "APPROVAL_INVALID"),
        ("card_manual_entry", "card.manual_entry.approve", "CARD_MANUAL_APPROVAL_REQUIRED"),
    ):
        with pytest.raises(AppError) as missing:
            await require(kind=kind, permission=permission, requested_by=users["cashier"], value=Decimal("1000.00"),
                          always_required=True)  # fmt: skip
        assert missing.value.code.value == code
    with pytest.raises(AppError) as expired_goods:
        await require(kind="return_over_limit", permission="returns.approve", requested_by=users["cashier"],
                      value=Decimal("10.00"), always_required=True, missing_code="APPROVAL_REQUIRED")  # fmt: skip
    assert expired_goods.value.code.value == "APPROVAL_REQUIRED" and expired_goods.value.status_code == 403
    # QT-PERM-01: the owner's own action never needs an approval, whatever the kind/amount
    for kind, permission in (("return_no_receipt", "returns.approve"), ("discount_over_limit", "discount.give"),
                             ("cash_withdrawal_over_limit", "cash.withdraw")):  # fmt: skip
        out = await require(kind=kind, permission=permission, requested_by=users["owner"], value=Decimal("99999999.00"),
                            always_required=True)  # fmt: skip
        assert out.required is False
    assert await one(env.db, tenant, "SELECT count(*) FROM app.approval_requests") == 0


async def test_price_change_approval_posts_or_rejects_linked_document(env: Env) -> None:
    """18 §10: approving the ``price_change`` request posts the price change; rejecting → ``rejected``."""
    from tests.support.catalog import create_product, set_price

    till = await make_till(env)
    shop = till.shop
    product = await create_product(env.client, shop)
    await set_price(env.client, shop, product["id"], "10000.0000")
    pending = await set_price(env.client, shop, product["id"], "13000.0000", role="manager")  # +30% > 10%
    assert pending["status"] == "pending_approval"
    tenant = shop.tenant_id
    approve = await _approve(env, till, pending["approval_request_id"], role="owner")
    assert approve.status_code == 200, approve.text
    row = (await sql(env.db, tenant, "SELECT status, number FROM app.price_changes WHERE id = :d",
                     d=UUID(pending["id"])))[0]  # fmt: skip
    assert row[0] == "posted" and row[1].startswith("C-")
    price = await one(env.db, tenant, "SELECT price FROM app.product_prices WHERE price_change_doc_id = :d",
                      d=UUID(pending["id"]))  # fmt: skip
    assert price == Decimal("13000.0000")
    assert await one(env.db, tenant, "SELECT status FROM app.approval_requests WHERE id = :r",
                     r=UUID(pending["approval_request_id"])) == "consumed"  # fmt: skip
    assert await one(env.db, tenant, "SELECT mode FROM app.doc_approvals WHERE doc_id = :d",
                     d=UUID(pending["id"])) == "remote_request"  # fmt: skip
    # the manager's own prices.approve limit (10%) is too small to approve it
    second = await set_price(env.client, shop, product["id"], "20000.0000", role="manager")
    assert second["status"] == "pending_approval"
    denied = await _approve(env, till, second["approval_request_id"], role="cashier")
    assert denied.status_code in (403, 404)
    rej = await env.client.post(f"{API}/{second['approval_request_id']}/reject", json={"reason": "Qimmat"},
                                headers=shop.h("owner"))  # fmt: skip
    assert rej.status_code == 200, rej.text
    assert await one(env.db, tenant, "SELECT status FROM app.price_changes WHERE id = :d",
                     d=UUID(second["id"])) == "rejected"  # fmt: skip
    assert await one(env.db, tenant, "SELECT count(*) FROM app.product_prices WHERE price_change_doc_id = :d",
                     d=UUID(second["id"])) == 0  # fmt: skip


async def test_expired_price_change_request_returns_document_to_draft(env: Env) -> None:
    """18 §10: an unanswered price_change request expires → the price change is a draft again (re-post)."""
    from app.modules.cash.tasks import expire_approvals
    from tests.support.catalog import create_product, set_price

    till = await make_till(env)
    shop = till.shop
    product = await create_product(env.client, shop)
    await set_price(env.client, shop, product["id"], "10000.0000")
    pending = await set_price(env.client, shop, product["id"], "13000.0000", role="manager")
    tenant = shop.tenant_id
    await sql(env.db, tenant, "UPDATE app.approval_requests SET expires_at = now() - interval '1 min', "
              "requested_at = now() - interval '16 min' WHERE id = :r", r=UUID(pending["approval_request_id"]))  # fmt: skip
    assert await expire_approvals(env.db, tenant) == 1
    assert await one(env.db, tenant, "SELECT status FROM app.price_changes WHERE id = :d",
                     d=UUID(pending["id"])) == "draft"  # fmt: skip
    assert (
        await one(
            env.db,
            tenant,
            "SELECT count(*) FROM app.audit_log WHERE action = 'price_change_approval_expired'",
        )
        == 1
    )
    assert await one(env.db, tenant, "SELECT count(*) FROM app.product_prices WHERE price_change_doc_id = :d",
                     d=UUID(pending["id"])) == 0  # fmt: skip
    again = await env.client.post(f"/api/v1/price-changes/{pending['id']}/post", headers=shop.h("manager"))
    assert again.status_code == 202 and again.json()["approval_request_id"] != pending["approval_request_id"]
