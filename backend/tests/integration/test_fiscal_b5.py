"""Bosqich 5 fiscal (B5-T02, DoD-05; 21 §1, §16; 16 §6; 13 §2.5/§2.14; 26 #189): local bridge through the store
agent, partner-cloud/fake OFD acks, FM state, Z-report task, readiness/alerts, RefundInfo, BO-14 endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.db.session import tenant_transaction
from app.modules.integrations.fiscal.infrastructure.fiscal_sql import SqlFiscalRepository
from app.modules.integrations.fiscal.wiring import (
    agent_status_sweep,
    agent_task_handlers,
    fake_fiscal_adapter,
    fiscal_alerts,
    fiscal_readiness,
    fiscal_service,
    provider_ack_poller,
    unacked_monitor,
)
from tests.support.debts import customer, debt_payment, debt_sale, deliver_debt, item, open_docs
from tests.support.fiscal import (
    InMemoryAgentTasks,
    StoreAgentEmulator,
    add_agent,
    bind_agent,
    local_env_fixture,
)
from tests.support.sales import (
    API,
    Env,
    Pos,
    deliver,
    execute,
    fiscalize,
    make_pos,
    new_item,
    one,
    return_line,
    return_payload,
    rows,
    sale_line,
    sale_payload,
    sales_env_fixture,
    sell,
    sold_lines,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["local_env_fixture", "sales_env_fixture"]

TOTAL_TIYIN = 1_200_000  # one "12000.00" line


async def _handle(env: Env, pos: Pos, agent_id: Any, task: Any, result: dict[str, Any]) -> None:
    """Run the registered result handler the way the A-05 result transaction does."""
    handler = agent_task_handlers(env.settings, env.db)[task.kind]
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await handler(s, pos.tenant_id, agent_id, {"payload": task.payload}, result)


async def _receipt(env: Env, pos: Pos, sale_id: str) -> dict[str, Any]:
    return (
        await rows(env.db, pos.tenant_id, "SELECT * FROM app.fiscal_receipts WHERE sale_id = :d", d=sale_id)
    )[0]


async def _offline_signed_sale(env: Env, pos: Pos, agent: StoreAgentEmulator, at: datetime) -> dict[str, Any]:
    product = await new_item(env, pos)
    agent.fm().online = False  # network down: the FM still signs (21 §1 Offline)
    signed = agent.sign(TOTAL_TIYIN)
    payload = sale_payload(pos, [sale_line(product)], is_offline=True, fiscal_result=signed)
    res = await deliver(env, pos, "sale.created", payload, created_at=at, received_at=at)
    assert res.error is None, (res.error.code, res.error.details) if res.error else None
    assert res.server["fiscal"]["status"] == "fiscalized"
    return payload


# --- DoD-05: local bridge — FM signs offline, resend, ofd_acked_at -----------------------------------------
async def test_b5_dod_05_local_bridge_offline_sign_resend_acks(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    agent_id = await add_agent(env, pos)
    await bind_agent(env, pos, agent_id)
    agent, tasks = StoreAgentEmulator(), InMemoryAgentTasks()
    t0 = datetime.now(UTC) - timedelta(hours=41)
    payload = await _offline_signed_sale(env, pos, agent, t0)
    r = await _receipt(env, pos, payload["id"])
    assert r["status"] == "fiscalized" and r["ofd_acked_at"] is None and r["fm_receipt_seq"] is not None
    assert (
        await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'ofd_send'") == 0
    )

    # the 40 h stage queues fiscal.resend_unsent for the register's agent (one per oldest receipt)
    monitor = unacked_monitor(env.db.session_factory, tasks=tasks)
    await monitor.run(pos.tenant_id, t0 + timedelta(hours=39))
    assert tasks.of("fiscal.resend_unsent") == []
    await monitor.run(pos.tenant_id, t0 + timedelta(hours=40, minutes=1))
    await monitor.run(pos.tenant_id, t0 + timedelta(hours=40, minutes=6))
    (resend,) = tasks.of("fiscal.resend_unsent")
    assert resend.payload == {"cash_register_id": str(pos.register_id), "local_id": "fm-1"}

    # still offline: nothing acked
    await _handle(env, pos, agent_id, resend, agent.answer(resend.kind, resend.payload))
    assert (await _receipt(env, pos, payload["id"]))["ofd_acked_at"] is None
    # network back → resend → acked[] → ofd_acked_at, the register's timer cleared at once
    agent.fm().online = True
    await _handle(env, pos, agent_id, resend, agent.answer(resend.kind, resend.payload))
    assert (await _receipt(env, pos, payload["id"]))["ofd_acked_at"] is not None
    reg = (
        await rows(env.db, pos.tenant_id, "SELECT last_unacked_receipt_at FROM app.cash_registers WHERE id = :r",
                   r=pos.register_id)
    )[0]  # fmt: skip
    assert reg["last_unacked_receipt_at"] is None
    assert await one(env.db, pos.tenant_id,
                     "SELECT after->>'sent' FROM app.audit_log WHERE action = 'fiscal.resend_unsent' "
                     "ORDER BY id DESC LIMIT 1") == "1"  # fmt: skip


async def test_b5_qt_m01_23_local_bridge_requires_and_validates_fiscal_result(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    product = await new_item(env, pos)
    missing = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)]))
    assert missing.code == "VALIDATION_ERROR" and missing.fields == ["fiscal_result"]
    agent = StoreAgentEmulator()
    bad_sign = {**agent.sign(TOTAL_TIYIN), "fiscal_sign": "12AB"}
    res = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product)], fiscal_result=bad_sign)
    )
    assert res.keys == ["validation.fiscal_sign_format"]
    good = agent.sign(TOTAL_TIYIN)
    mismatch = {**good, "fm_receipt_seq": good["fm_receipt_seq"] + 1}
    res = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product)], fiscal_result=mismatch)
    )
    assert res.keys == ["validation.fiscal_result_qr_mismatch"]
    ok = await sell(env, pos, sale_payload(pos, [sale_line(product)], fiscal_result=good))
    assert ok.server["fiscal"]["status"] == "fiscalized"


# --- fiscal.status: fm_state, pending, acks; foreign agent; sweep --------------------------------------------
async def test_b5_fiscal_status_sets_fm_state_alerts_and_unlocks(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    agent_id = await add_agent(env, pos)
    await bind_agent(env, pos, agent_id)
    agent, tasks = StoreAgentEmulator(), InMemoryAgentTasks()
    payload = await _offline_signed_sale(env, pos, agent, datetime.now(UTC) - timedelta(minutes=5))
    await agent_status_sweep(env.db.session_factory, tasks=tasks).run(pos.tenant_id)
    (status,) = tasks.of("fiscal.status")
    signed_before_lock = agent.sign(TOTAL_TIYIN)  # the POS event reaches the server after the FM locked
    agent.fm().state = "locked"
    await _handle(env, pos, agent_id, status, agent.answer(status.kind, status.payload))
    reg = (await rows(env.db, pos.tenant_id, "SELECT fm_state, fm_receipts_pending FROM app.cash_registers WHERE id = :r",
                      r=pos.register_id))[0]  # fmt: skip
    assert reg == {"fm_state": "locked", "fm_receipts_pending": 2}
    assert await one(env.db, pos.tenant_id,
                     "SELECT count(*) FROM app.audit_log WHERE action = 'fiscal.fm_state_changed'") == 1  # fmt: skip
    events = await rows(env.db, pos.tenant_id, "SELECT payload FROM app.outbox_jobs WHERE kind = 'telegram' "
                        "AND payload->>'event' = 'offline_48h'")  # fmt: skip
    assert [e["payload"]["stage"] for e in events] == ["fm_locked"]
    product = await new_item(env, pos, "Fanta")
    locked = await deliver(env, pos, "sale.created",
                           sale_payload(pos, [sale_line(product)], fiscal_result=signed_before_lock))  # fmt: skip
    assert locked.code == "FISCAL_DEVICE_LOCKED"
    # FM back to ok and the OFD acked the receipt → state ok, ofd_acked_at, sales again
    agent.fm().state, agent.fm().online = "ok", True
    agent.fm().resend()
    await _handle(env, pos, agent_id, status, agent.answer(status.kind, status.payload))
    assert (await _receipt(env, pos, payload["id"]))["ofd_acked_at"] is not None
    assert await one(env.db, pos.tenant_id, "SELECT fm_state FROM app.cash_registers WHERE id = :r",
                     r=pos.register_id) == "ok"  # fmt: skip
    again = await deliver(env, pos, "sale.created",
                          sale_payload(pos, [sale_line(product)], fiscal_result=agent.sign(TOTAL_TIYIN)))  # fmt: skip
    assert again.error is None


async def test_b5_fiscal_status_from_foreign_agent_changes_nothing(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    agent_id, other = await add_agent(env, pos), await add_agent(env, pos, ("fm-9",))
    await bind_agent(env, pos, agent_id)
    tasks = InMemoryAgentTasks()
    await agent_status_sweep(env.db.session_factory, tasks=tasks).run(pos.tenant_id)
    (status,) = tasks.of("fiscal.status")
    result = {"cash_register_id": str(pos.register_id), "fm_state": "locked", "pending_count": 3, "acked": []}
    await _handle(env, pos, other, status, result)
    assert await one(env.db, pos.tenant_id, "SELECT fm_state FROM app.cash_registers WHERE id = :r",
                     r=pos.register_id) == "ok"  # fmt: skip
    assert await one(env.db, pos.tenant_id,
                     "SELECT count(*) FROM app.audit_log WHERE action = 'fiscal.status_foreign_agent'") == 1  # fmt: skip
    # a malformed result is audited, never raised (contract 1: raising would loop the A-05 result forever)
    bad = {
        **result,
        "acked": [{"fm_terminal_id": "ZZ1", "fm_receipt_seq": 0, "acked_at": "2026-10-18T00:00:00Z"}],
    }
    await _handle(env, pos, agent_id, status, bad)
    invalid = await rows(
        env.db, pos.tenant_id, "SELECT after FROM app.audit_log WHERE action = 'fiscal.agent_result_invalid'"
    )
    assert invalid[0]["after"]["details"] == [
        {"field": "acked[0].fm_receipt_seq", "message_key": "validation.greater_than_equal"}
    ]
    assert await one(env.db, pos.tenant_id, "SELECT fm_state FROM app.cash_registers WHERE id = :r",
                     r=pos.register_id) == "ok"  # fmt: skip


async def test_b5_fiscal_status_sweep_dedupes_and_skips_disabled_agents(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    disabled = await add_agent(env, pos, fiscal_enabled=False)
    await bind_agent(env, pos, disabled)
    tasks = InMemoryAgentTasks()
    sweep = agent_status_sweep(env.db.session_factory, tasks=tasks)
    report = await sweep.run(pos.tenant_id)
    assert (
        report == {"registers": 1, "queued": 0} and tasks.tasks == []
    )  # AGENT_CAPABILITY_DISABLED — skipped
    agent_id = await add_agent(env, pos)
    await bind_agent(env, pos, agent_id)
    await sweep.run(pos.tenant_id)
    await sweep.run(pos.tenant_id)  # the first one is still open (agent offline) → no pile-up
    assert [t.payload["local_id"] for t in tasks.of("fiscal.status")] == ["fm-1"]
    tasks.tasks[0].done = True
    await sweep.run(pos.tenant_id)
    assert len(tasks.of("fiscal.status")) == 2


# --- fiscal.zreport -----------------------------------------------------------------------------------------
async def test_b5_fiscal_zreport_task_fills_the_z_report(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    agent_id = await add_agent(env, pos)
    await bind_agent(env, pos, agent_id)
    agent, tasks = StoreAgentEmulator(), InMemoryAgentTasks()
    svc = fiscal_service(env.settings, tasks=tasks)
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        ref = await svc.record(s, kind="z_report", doc_id=pos.shift_id, cash_register_id=pos.register_id,
                               shift_id=pos.shift_id, receipt_seq=None, payment_form=None, payload={"shift_no": 1},
                               fiscal_result=None, is_offline=False, offline_since=None)  # fmt: skip
    assert ref.status == "pending"
    (z,) = tasks.of("fiscal.zreport")
    assert z.payload == {
        "cash_register_id": str(pos.register_id),
        "local_id": "fm-1",
        "shift_id": str(pos.shift_id),
    }
    answer = agent.answer(z.kind, z.payload)
    await _handle(env, pos, agent_id, z, answer)
    await _handle(env, pos, agent_id, z, answer)  # repeated result — idempotent
    row = (await rows(env.db, pos.tenant_id, "SELECT status, fm_terminal_id, fm_receipt_seq, payload FROM "
                      "app.fiscal_receipts WHERE kind = 'z_report' AND shift_id = :s", s=pos.shift_id))[0]  # fmt: skip
    assert row["status"] == "fiscalized" and row["fm_terminal_id"] == answer["fm_terminal_id"]
    assert row["fm_receipt_seq"] is None and row["payload"]["fm_z"]["z_number"] == 1
    assert row["payload"]["fm_z"]["totals"]["sale"] == 1200000


# --- DoD-05 on the server-side path (fake FM / partner cloud) ---------------------------------------------
async def test_b5_dod_05_fake_fm_offline_then_ack_poll(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(pos, [sale_line(product)])
    await sell(env, pos, payload)
    fake = fake_fiscal_adapter()
    fake.ack = False  # FM signs, the OFD link is down
    assert await fiscalize(env, pos) == 1
    r = await _receipt(env, pos, payload["id"])
    assert r["status"] == "fiscalized" and r["ofd_acked_at"] is None
    poller = provider_ack_poller(env.db.session_factory, env.settings)
    assert (await poller.run(pos.tenant_id))["acked"] == 0
    fake.ack = True
    assert (await poller.run(pos.tenant_id)) == {"registers": 1, "acked": 1, "failed": 0}
    assert (await _receipt(env, pos, payload["id"]))["ofd_acked_at"] is not None
    assert ("resend_unsent", pos.register_id) in fake.calls


# --- 13 §2.14 debt_settlement, 26 #189, RefundInfo ------------------------------------------------------
async def test_b5_debt_settlement_receipt_fiscalized_by_fm(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos)
    a = await item(env, pos, "100000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "100000.0000")])
    pay = debt_payment(pos, cid, "100000.00", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", pay)).error is None
    await fiscalize(env, pos)
    r = (await rows(env.db, pos.tenant_id, "SELECT kind, status, payment_form, fm_terminal_id, fiscal_sign "
                    "FROM app.fiscal_receipts WHERE debt_payment_id = :p", p=pay["id"]))[0]  # fmt: skip
    assert (r["kind"], r["status"], r["payment_form"]) == ("debt_settlement", "fiscalized", "cash")
    assert r["fm_terminal_id"].startswith("ZZ") and len(r["fiscal_sign"]) == 12


async def test_26_189_return_of_fiscalised_debt_part_issues_no_receipt(env: Env) -> None:
    """13 §2.5 (26 #189, ⛔ partner answer): goods returned against the still-open debt get no refund receipt,
    even when part of the sale was already fiscalised by a debt_settlement receipt."""
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos)
    a, b = await item(env, pos, "60000.0000"), await item(env, pos, "40000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "60000.0000"), (b, "1.000", "40000.0000")])
    pay = debt_payment(pos, cid, "60000.00", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", pay)).error is None
    await fiscalize(env, pos)
    lines = await sold_lines(env, pos, sale["id"])
    ret = return_payload(pos, [return_line(b, sale_line_id=lines[1]["id"], price="40000.0000")],
                         sale_id=sale["id"], receipt_seq=None)  # fmt: skip
    res = await deliver(env, pos, "return.created", ret, actor="owner")
    assert res.error is None, (res.error.code, res.error.details) if res.error else None
    assert (res.server["debt_part"], res.server["money_part"]) == ("40000.00", "0.00")
    assert res.server["fiscal"]["status"] == "deferred"
    kinds = await rows(env.db, pos.tenant_id, "SELECT kind FROM app.fiscal_receipts ORDER BY id")
    assert [k["kind"] for k in kinds] == ["debt_settlement"]


async def test_b5_refund_info_of_a_paid_debt_sale_is_the_settlement_receipt(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    cid = await customer(env, pos)
    a = await item(env, pos, "50000.0000")
    sale = await debt_sale(env, pos, cid, [(a, "1.000", "50000.0000")])
    pay = debt_payment(pos, cid, "50000.00", await open_docs(env, pos, cid))
    assert (await deliver_debt(env, pos, "debt_payment.created", pay)).error is None
    await fiscalize(env, pos)
    lines = await sold_lines(env, pos, sale["id"])
    ret = return_payload(
        pos, [return_line(a, sale_line_id=lines[0]["id"], price="50000.0000")], sale_id=sale["id"]
    )
    res = await deliver(env, pos, "return.created", ret, actor="owner")
    assert res.error is None and res.server["money_part"] == "50000.00"
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        original = await SqlFiscalRepository().original_sale_receipt(s, ret["id"])
    assert original is not None and original.kind == "debt_settlement" and original.fiscal_sign is not None
    assert await fiscalize(env, pos) == 1
    assert await one(env.db, pos.tenant_id,
                     "SELECT status FROM app.fiscal_receipts WHERE return_id = :r", r=ret["id"]) == "fiscalized"  # fmt: skip


# --- PLAN contract 4: readiness, alerts ------------------------------------------------------------------
async def test_qt_m11_05_fiscal_readiness_counts_unsent_and_unacked(local_env: Env) -> None:
    env = local_env
    pos = await make_pos(env)
    agent = StoreAgentEmulator()
    at = datetime(2026, 9, 30, 18, 30, tzinfo=UTC)  # 23:30 Tashkent — inside 2026-09
    await execute(env.db, pos.tenant_id, "UPDATE app.shifts SET opened_at = :t WHERE id = :s",
                  t=at - timedelta(hours=1), s=pos.shift_id)  # fmt: skip
    await _offline_signed_sale(env, pos, agent, at)
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        sep = await fiscal_readiness(s, "2026-09")
        octo = await fiscal_readiness(s, "2026-10")
        alerts = await fiscal_alerts(s, at=at + timedelta(hours=25))
    assert (sep.pending_fiscal_receipts, sep.unacked, sep.not_fiscalized, sep.blocked) == (1, 1, 0, True)
    assert octo.blocked is False
    assert (alerts.fiscal_unacked, alerts.fiscal_blocked, alerts.fiscal_device_locked) == (1, 0, 0)


# --- BO-14 endpoints --------------------------------------------------------------------------------------
async def test_b5_bo14_fiscal_registers_and_manual_resend(
    local_env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = local_env
    pos = await make_pos(env)
    tasks = InMemoryAgentTasks()
    import app.modules.integrations.fiscal.wiring as fiscal_wiring

    monkeypatch.setattr(fiscal_wiring, "agent_task_port", lambda: tasks)
    env.app.state.fiscal_registers = fiscal_wiring.fiscal_register_queries(env.db.session_factory)
    url = f"{API}/cash-registers/{pos.register_id}/fiscal-resend"
    no_agent = await env.client.post(url, headers=pos.shop.h("accountant"))
    assert no_agent.status_code == 409 and no_agent.json()["error"]["code"] == "DOC_INVALID_STATE"
    agent_id = await add_agent(env, pos)
    await bind_agent(env, pos, agent_id)
    await _offline_signed_sale(env, pos, StoreAgentEmulator(), datetime.now(UTC) - timedelta(hours=2))
    assert (await env.client.post(url, headers=pos.shop.h("cashier"))).status_code == 403
    ok = await env.client.post(url, headers=pos.shop.h("accountant"))
    assert ok.status_code == 202 and ok.json()["status"] == "queued"
    assert [t.kind for t in tasks.tasks] == ["fiscal.resend_unsent"]
    listed = await env.client.get(f"{API}/fiscal-registers", headers=pos.shop.h("accountant"))
    assert listed.status_code == 200
    (reg,) = [i for i in listed.json()["items"] if i["cash_register_id"] == str(pos.register_id)]
    assert reg["fiscal_agent_id"] == str(agent_id) and reg["unacked_count"] == 1
    assert reg["oldest_unacked_age_s"] >= 7000 and reg["fm_state"] == "ok"
