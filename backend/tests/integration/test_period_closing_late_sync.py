"""QT-M11-14 through ``/sync/push`` (16 §3.4, qaror #69): a ``late_in_closed_period`` sync exception is
recorded and announced to the Accountant (M18 event ``late_in_closed_period``, audience ``accounting.post``)."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.sync.application.handlers import SyncExceptionRow
from tests.support.sync import (
    SyncEnv,
    echo_handler,
    event,
    pos_device,
    push_ok,
    register,
    rows,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]

ECHO = "test.late_echo"


async def test_qt_m11_14_late_event_m18_to_accountant(env: SyncEnv) -> None:
    shop = await env.shop("late-m18")
    pos = await pos_device(env, shop)
    doc_id = uuid7()
    details = {"period": "2026-09", "doc_date": "2026-09-30", "entry_date": "2026-10-01"}
    register(
        env,
        ECHO,
        echo_handler(exceptions=(SyncExceptionRow("late_in_closed_period", details, "sales", doc_id),)),
    )
    [res] = await push_ok(env, pos, [event(pos, ECHO, {})])
    assert res["status"] == "accepted"
    found = await rows(env.db, shop.tenant_id, "SELECT kind, doc_id, details FROM app.sync_exceptions")
    assert found == [{"kind": "late_in_closed_period", "doc_id": doc_id, "details": details}]
    jobs = await rows(
        env.db, shop.tenant_id, "SELECT status, payload FROM app.outbox_jobs WHERE kind = 'telegram'"
    )
    assert [(j["status"], j["payload"]["event"], j["payload"]["kind"]) for j in jobs] == [
        ("queued", "late_in_closed_period", "late_in_closed_period")
    ]
    assert UUID(jobs[0]["payload"]["doc_id"]) == doc_id
