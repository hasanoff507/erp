"""``card.settlement`` through the Do'kon agent + cron ``card_settlement_sweep`` (B5-T05, DoD-02 server part;
qaror #71; 21 §16, 23 §4.2, 18 §16a.6, QT-M16-08)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.integrations.card_terminal.application.ports import CardPurchaseRequest, TerminalRef
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.wiring import card_agent_service
from tests.support.card import CardShop, card_env_fixture, card_shop, post_tx, tx_body
from tests.support.catalog import Env
from tests.support.devices import (
    AGENT_DEVICE,
    FakeAgentTasks,
    ResultStub,
    TaskStub,
    agent_terminal,
    card_capabilities,
    insert_agent,
)

__all__ = ["card_env_fixture"]

pytestmark = pytest.mark.asyncio


async def _rows(env: Env, cs: CardShop, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        return [dict(r) for r in (await s.execute(text(sql), params)).mappings()]


async def _setup(env: Env, name: str = "Settlement") -> tuple[CardShop, UUID, dict[str, Any]]:
    cs = await card_shop(env, name)
    agent_id = await insert_agent(env, cs, capabilities=card_capabilities(AGENT_DEVICE))
    return cs, agent_id, await agent_terminal(env, cs, agent_id)


async def _sell(env: Env, cs: CardShop, terminal_id: UUID, amount_tiyin: int) -> UUID:
    attempt = uuid7()
    result = await cs.fake.purchase(
        CardPurchaseRequest(
            attempt_id=attempt, terminal=TerminalRef(card_terminal_id=terminal_id, local_id="ecr-1"),
            amount_tiyin=amount_tiyin, cash_register_id=cs.register1, client_event_id=uuid7(),
        )
    )  # fmt: skip
    body = tx_body(cs, attempt, f"{amount_tiyin // 100}.00", card_result_from_port(
        result, card_terminal_id=terminal_id, requested_amount_tiyin=amount_tiyin, resolved_by="auto",
    )) | {"card_terminal_id": str(terminal_id)}  # fmt: skip
    r = await post_tx(env, cs, body)
    assert r.status_code == 201, r.text
    return attempt


async def _handle(env: Env, cs: CardShop, agent_id: UUID, task: TaskStub, result: ResultStub) -> None:
    service = card_agent_service(env.settings, env.db.session_factory, FakeAgentTasks())
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_settlement(s, cs.tenant_id, agent_id, task, result)


async def test_qt_m16_08_agent_settlement_matched_and_mismatch(env: Env) -> None:
    cs, agent_id, terminal = await _setup(env)
    tid = UUID(terminal["id"])
    await _sell(env, cs, tid, 50_000_000)  # 500 000.00
    await _sell(env, cs, tid, 20_000_000)  # 200 000.00 → expected 700 000.00
    settlement = await cs.fake.settlement(TerminalRef(card_terminal_id=tid, local_id="ecr-1"))
    data = settlement.model_dump(mode="json") | {"card_terminal_id": str(tid), "local_id": "ecr-1"}
    task = TaskStub(uuid7(), "card.settlement", {"card_terminal_id": str(tid), "local_id": "ecr-1"})
    await _handle(env, cs, agent_id, task, ResultStub("done", data))
    rows = await _rows(env, cs, "SELECT id, status, purchase_total, expected_total, variance, created_by, "
                                "device_id, batch_no FROM app.card_terminal_settlements WHERE card_terminal_id = :t",
                       t=tid)  # fmt: skip
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == task.id and row["status"] == "matched" and row["created_by"] is None
    assert row["expected_total"] == Decimal("700000.00") and row["variance"] == Decimal("0.00")
    agent_device = (
        await _rows(env, cs, "SELECT device_id FROM app.onec_agents WHERE id = :id", id=agent_id)
    )[0]
    assert row["device_id"] == agent_device["device_id"]
    stamped = await _rows(env, cs, "SELECT count(*) AS n FROM app.card_terminal_transactions "
                                   "WHERE settlement_id = :s", s=task.id)  # fmt: skip
    assert stamped[0]["n"] == 2
    # replay of the same task result → idempotent by id
    await _handle(env, cs, agent_id, task, ResultStub("done", data))
    assert len(await _rows(env, cs, "SELECT id FROM app.card_terminal_settlements WHERE card_terminal_id = :t",
                           t=tid)) == 1  # fmt: skip
    # next batch: the terminal reports 50 000.00 less → mismatch, audit, M18 event
    await _sell(env, cs, tid, 70_000_000)
    cs.fake.settlement_skew_tiyin = -5_000_000
    second = await cs.fake.settlement(TerminalRef(card_terminal_id=tid, local_id="ecr-1"))
    task2 = TaskStub(uuid7(), "card.settlement", {"card_terminal_id": str(tid), "local_id": "ecr-1",
                                                  "shift_id": str(cs.shift_id)})  # fmt: skip
    await _handle(env, cs, agent_id, task2, ResultStub("done", second.model_dump(mode="json")))
    row2 = (await _rows(env, cs, "SELECT status, variance, shift_id FROM app.card_terminal_settlements "
                                 "WHERE id = :id", id=task2.id))[0]  # fmt: skip
    assert row2 == {"status": "mismatch", "variance": Decimal("-50000.00"), "shift_id": cs.shift_id}
    audit = await _rows(
        env, cs, "SELECT action, user_id FROM app.audit_log WHERE entity_id = :id", id=task2.id
    )
    assert audit == [{"action": "card.settlement.mismatch", "user_id": None}]
    events = await _rows(env, cs, "SELECT kind FROM app.outbox_jobs WHERE idempotency_key = :k",
                         k=f"card_settlement_mismatch:{task2.id}")  # fmt: skip
    assert len(events) == 1
    # the same batch_no reported again under another id → recorded for review, no exception
    task3 = TaskStub(uuid7(), "card.settlement", {"card_terminal_id": str(tid), "local_id": "ecr-1"})
    await _handle(env, cs, agent_id, task3, ResultStub("done", second.model_dump(mode="json")))
    exc = await _rows(env, cs, "SELECT details FROM app.sync_exceptions WHERE doc_id = :t "
                               "AND kind = 'card_result_mismatch'", t=tid)  # fmt: skip
    assert exc and exc[0]["details"]["reason"] == "settlement_rejected"


async def test_b5_t05_agent_settlement_failed_and_malformed(env: Env) -> None:
    cs, agent_id, terminal = await _setup(env, "Settlement fail")
    tid = UUID(terminal["id"])
    task = TaskStub(uuid7(), "card.settlement", {"card_terminal_id": str(tid), "local_id": "ecr-1"})
    await _handle(env, cs, agent_id, task, ResultStub("failed", error={"code": "CARD_TERMINAL_UNREACHABLE"}))
    row = (await _rows(env, cs, "SELECT status, terminal_response FROM app.card_terminal_settlements "
                                "WHERE id = :id", id=task.id))[0]  # fmt: skip
    assert (
        row["status"] == "failed" and row["terminal_response"]["error"]["code"] == "CARD_TERMINAL_UNREACHABLE"
    )
    bad = TaskStub(uuid7(), "card.settlement", {"card_terminal_id": str(tid), "local_id": "ecr-1"})
    await _handle(env, cs, agent_id, bad, ResultStub("done", {"count": "two", "pan": "8600123412341234"}))
    exc = await _rows(env, cs, "SELECT details FROM app.sync_exceptions WHERE doc_id = :t", t=tid)
    assert (
        exc[0]["details"]["reason"] == "malformed_result"
        and "pan" not in exc[0]["details"]["terminal_response"]
    )
    # a task naming another agent's terminal is ignored
    other = await insert_agent(env, cs, capabilities=card_capabilities(AGENT_DEVICE))
    await _handle(env, cs, other, TaskStub(uuid7(), "card.settlement", {"card_terminal_id": str(tid)}),
                  ResultStub("failed"))  # fmt: skip
    assert len(await _rows(env, cs, "SELECT id FROM app.card_terminal_settlements WHERE card_terminal_id = :t",
                           t=tid)) == 1  # fmt: skip


async def test_b5_t05_card_settlement_sweep_per_business_day(env: Env) -> None:
    cs, _, terminal = await _setup(env, "Sweep")
    tid = UUID(terminal["id"])
    tasks = FakeAgentTasks()
    service = card_agent_service(env.settings, env.db.session_factory, tasks)
    day = date(2026, 9, 14)  # this test's own business day
    report = await service.settlement_sweep(cs.tenant_id, business_date=day)
    assert report.enqueued == 1
    assert tasks.calls[0]["kind"] == "card.settlement" and tasks.calls[0]["payload"] == {
        "card_terminal_id": str(tid), "local_id": "ecr-1"}  # fmt: skip
    assert tasks.calls[0]["dedupe_key"] == f"card.settlement:{tid}:2026-09-14"
    # the terminal settled that day (e.g. at shift close by the POS) → no task
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.card_terminal_settlements (id, tenant_id, branch_id, card_terminal_id, business_date, "
                "settled_at, purchase_count, purchase_total, refund_count, refund_total, expected_count, "
                "expected_total, status) VALUES (:id, :t, :b, :c, :d, now(), 0, 0, 0, 0, 0, 0, 'matched')"
            ),
            {"id": uuid7(), "t": cs.tenant_id, "b": cs.branch_id, "c": tid, "d": day},
        )
    tasks2 = FakeAgentTasks()
    service2 = card_agent_service(env.settings, env.db.session_factory, tasks2)
    assert (await service2.settlement_sweep(cs.tenant_id, business_date=day)).enqueued == 0
    assert (await service2.settlement_sweep(cs.tenant_id, business_date=date(2026, 9, 15))).enqueued == 1
