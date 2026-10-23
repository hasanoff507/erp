"""DoD-02 (server part) through the REAL store-agent channel (b5-agent A-API): pairing → hello with
``capabilities.card_terminal`` → BO-12 binding → ``card.status`` / ``card.settlement`` enqueued by the card slice,
leased by A-03 and answered by A-05 with the driver emulator's results → the card handlers
(``health_status``, ``resolved_by='status_query'``, ``card_terminal_settlements``)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.integrations.card_terminal.application.ports import CardPurchaseRequest, TerminalRef
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.domain.model import tashkent_date
from app.modules.integrations.card_terminal.wiring import card_agent_service
from tests.support.agent import FULL_CAPABILITIES, agent_platform, hello, pair_agent, poll, result
from tests.support.branches import Member
from tests.support.branches import Shop as BranchShop
from tests.support.card import API, CardShop, card_env_fixture, card_shop, post_tx, tx_body
from tests.support.catalog import Env

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["card_env_fixture"]


@pytest.fixture(name="agent_env")
async def agent_env_fixture(env: Env, migrator_engine: AsyncEngine) -> Env:
    await agent_platform(migrator_engine)
    return env


async def _rows(env: Env, cs: CardShop, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        return [dict(r) for r in (await s.execute(text(sql), params)).mappings()]


async def _take(env: Env, fx: Any, kind: str) -> dict[str, Any]:
    r = await poll(env.client, fx)
    assert r.status_code == 200, r.text
    (task,) = r.json()["tasks"]
    assert task["kind"] == kind, task
    return task  # type: ignore[no-any-return]


async def test_b5_dod_02_card_tasks_through_the_real_agent_channel(
    agent_env: Env, admin_engine: AsyncEngine
) -> None:
    env = agent_env
    cs = await card_shop(env, "Agent karta")
    warehouse = (await _rows(env, cs, "SELECT id FROM app.warehouses ORDER BY id LIMIT 1"))[0]["id"]
    owner = Member(cs.uid("owner"), "", cs.shop.tokens["owner"])
    fx = await pair_agent(env.client, BranchShop(cs.tenant_id, cs.branch_id, warehouse, owner), admin_engine)
    assert (await hello(env.client, fx, FULL_CAPABILITIES)).status_code == 200
    # BO-12: bind an agent_ecr terminal of Kassa-1 to the agent's ct-1 (host from the capability allow-list)
    r = await env.client.post(f"{API}/card-terminals", json={
        "branch_id": str(cs.branch_id), "cash_register_id": str(cs.register1), "name": "Humo P3", "vendor": "humo",
        "adapter": "agent_ecr", "driver": "humo_lan", "agent_id": str(fx.agent_id), "local_id": "ct-1",
        "host": "192.168.1.60", "tid": "T0000001", "is_default": True}, headers=cs.h("owner"))  # fmt: skip
    assert r.status_code == 201, r.text
    tid = UUID(r.json()["id"])
    # the POS buys through the agent; one purchase times out (unknown on the server)
    approved, unknown = uuid7(), uuid7()
    for attempt, amount in ((approved, 1_000_000), (unknown, 1_100_200)):
        res = await cs.fake.purchase(CardPurchaseRequest(
            attempt_id=attempt, terminal=TerminalRef(card_terminal_id=tid, local_id="ct-1"), amount_tiyin=amount,
            cash_register_id=cs.register1, client_event_id=uuid7()))  # fmt: skip
        body = tx_body(cs, attempt, f"{amount // 100}.00", card_result_from_port(
            res, card_terminal_id=tid, requested_amount_tiyin=amount, resolved_by="auto")) | {
            "card_terminal_id": str(tid)}  # fmt: skip
        assert (await post_tx(env, cs, body)).status_code == 201
    # cron card_status_sweep → real AgentTaskPort → A-03 lease → A-05 result
    service = card_agent_service(env.settings, env.db.session_factory)
    assert (await service.status_sweep(cs.tenant_id)).enqueued == 1
    status = await _take(env, fx, "card.status")
    assert status["payload"] == {"terminals": [{"card_terminal_id": str(tid), "local_id": "ct-1"}]}
    late = await cs.fake.get_status(unknown)
    data = {
        "terminals": [{"card_terminal_id": str(tid), "local_id": "ct-1", "status": "online", "tid": "T0000001",
                       "last_tx_at": None}],
        "unresolved": [late.model_dump(mode="json") | {"resolved_by": "status_query", "local_id": "ct-1"}],
    }  # fmt: skip
    r = await result(env.client, fx, status, data=data)
    assert r.status_code == 200 and r.json()["accepted"] is True, r.text
    tx = (await _rows(env, cs, "SELECT status, resolved_by FROM app.card_terminal_transactions WHERE id = :id",
                      id=unknown))[0]  # fmt: skip
    assert tx == {"status": "approved", "resolved_by": "status_query"}
    health = (await _rows(env, cs, "SELECT health_status FROM app.card_terminals WHERE id = :id", id=tid))[0]
    assert health["health_status"] == "online"
    # end of day without the POS: card_settlement_sweep → card.settlement → matched batch
    day = tashkent_date(late.tx_at) if late.tx_at else None
    assert day is not None
    assert (await service.settlement_sweep(cs.tenant_id, business_date=day)).enqueued == 1
    settle = await _take(env, fx, "card.settlement")
    batch = await cs.fake.settlement(TerminalRef(card_terminal_id=tid, local_id="ct-1"))
    r = await result(env.client, fx, settle, data=batch.model_dump(mode="json") | {"card_terminal_id": str(tid),
                                                                                    "local_id": "ct-1"})  # fmt: skip
    assert r.status_code == 200, r.text
    row = (await _rows(env, cs, "SELECT status, expected_total, variance, created_by FROM "
                       "app.card_terminal_settlements WHERE id = :id", id=UUID(settle["task_id"])))[0]  # fmt: skip
    assert row == {"status": "matched", "expected_total": Decimal("21002.00"), "variance": Decimal("0.00"),
                   "created_by": None}  # fmt: skip
