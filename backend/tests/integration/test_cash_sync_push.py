"""Cash events through the real ``POST /api/v1/sync/push`` (16 §3.1): registry wiring, results, QT-SEQ-02."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from tests.support.sync import (
    SyncEnv,
    event,
    pos_device,
    push_ok,
    scalar,
    sync_env_fixture,  # noqa: F401 - fixture "env"
)

pytestmark = pytest.mark.asyncio


async def test_shift_cycle_through_sync_push(env: SyncEnv) -> None:
    shop = await env.shop("Sync kassa", SystemRole.OWNER)
    pos = await pos_device(env, shop, SystemRole.CASHIER)
    shift_id = uuid7()
    opened = {
        "id": str(shift_id),
        "cash_register_id": str(pos.register_id),
        "shift_no": 1,
        "opening_cash": "100000.00",
    }
    move = {
        "id": str(uuid7()), "cash_register_id": str(pos.register_id), "shift_id": str(shift_id), "direction": "in",
        "reason": "deposit", "amount": "20000.00",
    }  # fmt: skip
    closed = {"shift_id": str(shift_id), "counted_cash": "120000.00"}
    results = await push_ok(
        env, pos, [event(pos, "shift.opened", opened), event(pos, "cash_movement.created", move),
                   event(pos, "shift.closed", closed)],
    )  # fmt: skip
    assert [r["status"] for r in results] == ["accepted"] * 3, results
    assert results[0]["server"] == {
        "id": str(shift_id),
        "cash_register_id": str(pos.register_id),
        "shift_no": 1,
    }
    z = results[2]["server"]["z_report"]
    assert (z["expected_cash"], z["counted_cash"], z["variance"]) == ("120000.00", "120000.00", "0.00")
    assert (
        await scalar(env.db, shop.tenant_id, "SELECT status FROM app.shifts WHERE id = :s", s=shift_id)
        == "closed"
    )
    # replay of the same client_event_id is a duplicate, nothing posted twice
    again = await push_ok(
        env, pos, [{**event(pos, "shift.opened", opened), "client_event_id": results[0]["client_event_id"]}]
    )
    assert again[0]["status"] == "duplicate"


async def test_qt_seq_02_other_device_event_rejected_through_push(env: SyncEnv) -> None:
    shop = await env.shop("Sync ikki", SystemRole.OWNER)
    first = await pos_device(env, shop, SystemRole.CASHIER)
    second = await pos_device(env, shop, SystemRole.CASHIER, register_id=first.register_id)
    shift_id = uuid7()
    opened = {
        "id": str(shift_id),
        "cash_register_id": str(first.register_id),
        "shift_no": 1,
        "opening_cash": "0.00",
    }
    assert (await push_ok(env, first, [event(first, "shift.opened", opened)]))[0]["status"] == "accepted"
    move = {
        "id": str(uuid7()), "cash_register_id": str(first.register_id), "shift_id": str(shift_id), "direction": "in",
        "reason": "deposit", "amount": "1000.00",
    }  # fmt: skip
    other = await push_ok(env, second, [event(second, "cash_movement.created", move)])
    assert other[0]["status"] == "rejected" and other[0]["error_code"] == "SHIFT_DEVICE_MISMATCH"
    assert other[0]["retryable"] is False
    own = await push_ok(env, first, [event(first, "cash_movement.created", {**move, "id": str(uuid7())})])
    assert own[0]["status"] == "accepted"
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.cash_movements WHERE shift_id = :s",
                        s=UUID(str(shift_id))) == 1  # fmt: skip
