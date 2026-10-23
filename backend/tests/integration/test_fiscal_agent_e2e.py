"""End to end through the real store-agent channel (contract 1; 21 §16; DoD-05): pairing → hello (fiscal
capability) → BO-12 binding → ``fiscal.status`` / ``fiscal.resend_unsent`` / ``fiscal.zreport`` leased by A-03 and
answered by A-05 → the fiscal result handlers (``fm_state``, ``ofd_acked_at``, Z-report)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import tenant_transaction
from app.modules.integrations.fiscal.wiring import fiscal_service, unacked_monitor
from tests.support.agent import (
    FULL_CAPABILITIES,
    AgentFixture,
    agent_platform,
    hello,
    pair_agent,
    poll,
    result,
)
from tests.support.branches import Member
from tests.support.branches import Shop as BranchShop
from tests.support.fiscal import StoreAgentEmulator, local_env_fixture
from tests.support.sales import API, Env, Pos, deliver, make_pos, new_item, rows, sale_line, sale_payload

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["local_env_fixture"]


@pytest.fixture(name="agent_env")
async def agent_env_fixture(local_env: Env, migrator_engine: AsyncEngine) -> Env:
    await agent_platform(migrator_engine)
    return local_env


async def _paired(env: Env, pos: Pos, admin_engine: AsyncEngine) -> AgentFixture:
    owner = Member(pos.shop.user_ids["owner"], "", pos.shop.tokens["owner"])
    shop = BranchShop(pos.tenant_id, pos.branch_id, pos.warehouse_id, owner)
    fx = await pair_agent(env.client, shop, admin_engine)
    r = await hello(env.client, fx, FULL_CAPABILITIES)
    assert r.status_code == 200, r.text
    return fx


async def _take(env: Env, fx: AgentFixture, kind: str) -> dict[str, Any]:
    r = await poll(env.client, fx)
    assert r.status_code == 200, r.text
    (task,) = r.json()["tasks"]
    assert task["kind"] == kind, task
    return task  # type: ignore[no-any-return]


async def test_b5_dod_05_fiscal_tasks_through_the_real_agent_channel(
    agent_env: Env, admin_engine: AsyncEngine
) -> None:
    env = agent_env
    pos = await make_pos(env)
    fx = await _paired(env, pos, admin_engine)
    fm = StoreAgentEmulator()

    # BO-12 binding (20 #40) queues fiscal.status at once
    version = (await rows(env.db, pos.tenant_id, "SELECT version FROM app.cash_registers WHERE id = :r",
                          r=pos.register_id))[0]["version"]  # fmt: skip
    bound = await env.client.patch(
        f"{API}/cash-registers/{pos.register_id}",
        json={"fiscal_agent_id": str(fx.agent_id), "fiscal_local_device_id": "fm-1", "version": version},
        headers=pos.shop.h("owner"),
    )
    assert bound.status_code == 200, bound.text
    status = await _take(env, fx, "fiscal.status")
    assert status["payload"] == {"cash_register_id": str(pos.register_id), "local_id": "fm-1"}

    # the POS sells offline: the FM signs, the OFD has not acked (48 h timer runs)
    product = await new_item(env, pos)
    fm.fm().online = False
    t0 = datetime.now(UTC) - timedelta(hours=41)
    sold = await deliver(env, pos, "sale.created",
                         sale_payload(pos, [sale_line(product)], is_offline=True, fiscal_result=fm.sign(1_200_000)),
                         created_at=t0, received_at=t0)  # fmt: skip
    assert sold.error is None and sold.server["fiscal"]["status"] == "fiscalized"

    # A-05 fiscal.status: still offline → fm_receipts_pending, nothing acked
    r = await result(env.client, fx, status, data=fm.answer("fiscal.status", status["payload"]))
    assert r.status_code == 200 and r.json()["accepted"] is True, r.text
    reg = (await rows(env.db, pos.tenant_id, "SELECT fm_state, fm_receipts_pending, last_unacked_receipt_at "
                      "FROM app.cash_registers WHERE id = :r", r=pos.register_id))[0]  # fmt: skip
    assert (
        reg["fm_state"] == "ok"
        and reg["fm_receipts_pending"] == 1
        and reg["last_unacked_receipt_at"] is not None
    )

    # 40 h stage → fiscal.resend_unsent; the network is back → acked[] → ofd_acked_at
    await unacked_monitor(env.db.session_factory).run(pos.tenant_id, t0 + timedelta(hours=40, minutes=1))
    resend = await _take(env, fx, "fiscal.resend_unsent")
    fm.fm().online = True
    r = await result(env.client, fx, resend, data=fm.answer("fiscal.resend_unsent", resend["payload"]))
    assert r.status_code == 200, r.text
    receipt = (await rows(env.db, pos.tenant_id, "SELECT ofd_acked_at FROM app.fiscal_receipts WHERE sale_id = :d",
                          d=sold.server["id"]))[0]  # fmt: skip
    assert receipt["ofd_acked_at"] is not None

    # a failed task outcome is audited, never fatal for the A-05
    await env.client.post(
        f"{API}/cash-registers/{pos.register_id}/fiscal-resend", headers=pos.shop.h("owner")
    )
    manual = await _take(env, fx, "fiscal.resend_unsent")
    r = await result(env.client, fx, manual, outcome="failed",
                     error={"code": "FISCAL_PROVIDER_ERROR", "message": "FM javob bermadi", "retryable": True})  # fmt: skip
    assert r.status_code == 200, r.text
    failed = await rows(
        env.db, pos.tenant_id, "SELECT after FROM app.audit_log WHERE action = 'fiscal.agent_task_failed'"
    )
    assert failed[0]["after"]["outcome"] == "failed"

    # the shift closes (local bridge: no FM requisites) → fiscal.zreport → the Z row is filled
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await fiscal_service(env.settings).record(
            s, kind="z_report", doc_id=pos.shift_id, cash_register_id=pos.register_id, shift_id=pos.shift_id,
            receipt_seq=None, payment_form=None, payload={"shift_no": 1}, fiscal_result=None, is_offline=False,
            offline_since=None,
        )  # fmt: skip
    z = await _take(env, fx, "fiscal.zreport")
    r = await result(env.client, fx, z, data=fm.answer("fiscal.zreport", z["payload"]))
    assert r.status_code == 200, r.text
    zrow = (await rows(env.db, pos.tenant_id, "SELECT status, payload FROM app.fiscal_receipts WHERE kind = 'z_report' "
                       "AND shift_id = :s", s=pos.shift_id))[0]  # fmt: skip
    assert zrow["status"] == "fiscalized" and zrow["payload"]["fm_z"]["z_number"] == 1
