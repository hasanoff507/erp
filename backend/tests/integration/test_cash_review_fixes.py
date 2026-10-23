"""Review fixes of the cash slice: SYNC-06, ACC-01, ACC-06, SEC-02 (approver part), SEC-10."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.accounting.wiring import business_today
from app.modules.cash.wiring import shift_guard
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
from tests.support.catalog import Env, catalog_app

pytestmark = pytest.mark.asyncio
API = "/api/v1/cash-movements"


def _body(till: Till, shift_id: UUID, **over: Any) -> dict[str, Any]:
    return {
        "cash_register_id": str(till.register_id), "shift_id": str(shift_id), "direction": "out",
        "reason": "collection", "amount": "50000.00", "doc_date": business_today().isoformat(), **over,
    }  # fmt: skip


async def test_sync_06_unknown_shift_is_dependency_not_synced(env: Env) -> None:
    till = await make_till(env)
    async with env.db.session_factory() as s, tenant_transaction(s, till.shop.tenant_id):
        with pytest.raises(AppError) as exc:
            await shift_guard().require_open(
                s, shift_id=uuid7(), device_id=till.device_id, at=datetime.now(UTC)
            )
    assert exc.value.code.value == "DEPENDENCY_NOT_SYNCED" and exc.value.params["entity"] == "shifts"
    # the handler path too: retryable rejection, then accepted once the shift exists
    shift_id = uuid7()
    payload = movement(till, shift_id, direction="in", reason="deposit", comment=None, amount="1000.00")
    early = await push(env, till, "cash_movement.created", payload)
    assert early.code == "DEPENDENCY_NOT_SYNCED"
    opened = await push(
        env, till, "shift.opened",
        {"id": str(shift_id), "cash_register_id": str(till.register_id), "shift_no": 1, "opening_cash": "0.00"},
    )  # fmt: skip
    assert opened.error is None
    assert (await push(env, till, "cash_movement.created", payload)).error is None


async def test_acc_01_late_cash_document_in_closed_shift_is_corrected(env: Env) -> None:
    till = await make_till(env)
    tenant = till.shop.tenant_id
    shift_id = await open_shift(env, till, "500000.00")
    made = datetime.now(UTC)  # the withdrawal happened before the close …
    closed = await push(
        env, till, "shift.closed",
        {"shift_id": str(shift_id), "counted_cash": "480000.00", "variance_note": "Kamomad"},
        created_at=made + timedelta(minutes=1),
    )  # fmt: skip
    assert closed.error is None
    assert [(dt, kt, a) for dt, kt, a, _ in await ledger(env.db, tenant, "shifts", shift_id)] == [
        ("4730", "5010", "20000.00")
    ]
    late = movement(till, shift_id, amount="20000.00")  # … but reached the server after it
    res = await push(env, till, "cash_movement.created", late, created_at=made)
    assert res.error is None, res.error and (res.error.code, res.error.params)
    assert res.result is not None
    exc = [e for e in res.result.sync_exceptions if e.kind == "late_in_closed_shift"]
    assert len(exc) == 1
    assert exc[0].details["variance_before"] == "-20000.00"
    assert exc[0].details["variance_after"] == "0.00"
    assert exc[0].details["cash_delta"] == "-20000.00"
    row = (
        await sql(env.db, tenant, "SELECT expected_cash, variance FROM app.shifts WHERE id = :s", s=shift_id)
    )[0]
    assert (format(row[0], "f"), format(row[1], "f")) == ("480000.00", "0.00")
    lines = sorted((dt, kt, a) for dt, kt, a, _ in await ledger(env.db, tenant, "shifts", shift_id))
    assert lines == [("4730", "5010", "20000.00"), ("5010", "4730", "20000.00")]
    # 5010 is credited once for the 20 000 that really left the drawer, not twice
    net = await one(
        env.db, tenant,
        "SELECT COALESCE(sum(CASE WHEN account_dt = '5010' THEN amount ELSE -amount END), 0) "
        "FROM app.ledger_entries WHERE '5010' IN (account_dt, account_kt) AND (doc_id = :s OR doc_id = :m)",
        s=shift_id, m=UUID(late["id"]),
    )  # fmt: skip
    assert format(net, "f") == "-20000.00"
    after = await push(
        env, till, "cash_movement.created", movement(till, shift_id), created_at=made + timedelta(minutes=5)
    )
    assert after.code == "SHIFT_NOT_OPEN"


async def test_acc_06_withdrawal_request_ttl_comes_from_settings(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    settings = env.settings.model_copy(update={"approval_ttl_minutes": 30})
    async with catalog_app(settings) as (_, client):
        res = await client.post(
            API, json=_body(till, shift_id, amount="70000.00"), headers=till.shop.h("cashier")
        )
    assert res.status_code == 202, res.text
    ttl = await one(
        env.db, till.shop.tenant_id,
        "SELECT expires_at - requested_at FROM app.approval_requests WHERE id = :r",
        r=UUID(res.json()["approval_request_id"]),
    )  # fmt: skip
    assert ttl.total_seconds() == 1800


async def test_sec_02_online_unbound_pin_approver_is_flagged(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    manager = till.shop.user_ids["manager"]
    approval = {"mode": "local_pin", "approved_by": str(manager), "pin_verified_locally": True}

    async def unbound(_: UUID) -> bool:
        return False

    async def bound(user: UUID) -> bool:
        return user == manager

    def body() -> dict[str, Any]:
        return {**movement(till, shift_id, amount="60000.00"), "approval": approval}

    flagged = await push(env, till, "cash_movement.created", body(), actor_bound=unbound)
    assert flagged.error is None and flagged.result is not None
    rows = [e for e in flagged.result.sync_exceptions if e.kind == "actor_unverified"]
    assert len(rows) == 1
    assert rows[0].details["approved_by"] == str(manager) and rows[0].details["role"] == "approver"
    ok = await push(env, till, "cash_movement.created", body(), actor_bound=bound)
    assert ok.result is not None and ok.result.sync_exceptions == ()
    offline = await push(
        env, till, "cash_movement.created", body(), actor_bound=unbound,
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )  # fmt: skip
    assert offline.result is not None and offline.result.sync_exceptions == ()


async def test_sec_10_cancelling_a_deposit_needs_withdraw_limit(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    dep = await env.client.post(
        API, json=_body(till, shift_id, direction="in", reason="deposit", amount="2000000.00"),
        headers=till.shop.h("cashier"),
    )  # fmt: skip
    assert dep.status_code == 201, dep.text
    doc = dep.json()["id"]
    refused = await env.client.post(
        f"{API}/{doc}/cancel", json={"reason": "x"}, headers=till.shop.h("cashier")
    )
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "CASH_WITHDRAW_LIMIT_EXCEEDED"
    assert (
        await one(
            env.db, till.shop.tenant_id, "SELECT status FROM app.cash_movements WHERE id = :d", d=UUID(doc)
        )
        == "posted"
    )
    owner = await env.client.post(f"{API}/{doc}/cancel", json={"reason": "x"}, headers=till.shop.h("owner"))
    assert owner.status_code == 200
    small = await env.client.post(
        API, json=_body(till, shift_id, direction="in", reason="deposit", amount="30000.00"),
        headers=till.shop.h("cashier"),
    )  # fmt: skip
    within = await env.client.post(
        f"{API}/{small.json()['id']}/cancel", json={"reason": "x"}, headers=till.shop.h("cashier")
    )
    assert within.status_code == 200
