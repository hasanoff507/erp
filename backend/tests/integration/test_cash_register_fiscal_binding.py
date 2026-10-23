"""BO-12 «Fiskal agent» binding — ``PATCH /cash-registers/{id}`` ``fiscal_agent_id`` + ``fiscal_local_device_id``
(20 #40, 21 §16, 34 §14.2, qaror #66): both or neither; the agent belongs to the tenant, is active, has
``capabilities.fiscal.enabled`` with that ``local_id``; one FM serves one register; the binding queues ``fiscal.status``."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.db.base import uuid7
from tests.support.fiscal import InMemoryAgentTasks, add_agent, local_env_fixture
from tests.support.sales import API, Env, Pos, execute, make_pos, one

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["local_env_fixture"]


async def _patch(env: Env, pos: Pos, body: dict[str, Any], role: str = "owner") -> Any:
    version = await one(
        env.db, pos.tenant_id, "SELECT version FROM app.cash_registers WHERE id = :r", r=pos.register_id
    )
    return await env.client.patch(
        f"{API}/cash-registers/{pos.register_id}", json={**body, "version": version}, headers=pos.shop.h(role)
    )


async def test_cash_register_fiscal_agent_binding_rules(
    local_env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = local_env
    tasks = InMemoryAgentTasks()
    import app.modules.integrations.fiscal.wiring as fiscal_wiring

    monkeypatch.setattr(fiscal_wiring, "agent_task_port", lambda: tasks)
    pos = await make_pos(env)
    other = await make_pos(env, "Boshqa do'kon")
    foreign = await add_agent(env, other)
    revoked = await add_agent(env, pos, status="revoked")
    disabled = await add_agent(env, pos, fiscal_enabled=False)
    agent = await add_agent(env, pos, ("fm-1", "fm-2"))

    def detail(r: Any) -> tuple[str, str]:
        d = r.json()["error"]["details"][0]
        return d["field"], d["message_key"]

    half = await _patch(env, pos, {"fiscal_agent_id": str(agent)})
    assert half.status_code == 422 and detail(half)[1] == "validation.fiscal_agent_pair"
    cases = [
        (foreign, "fm-1", ("fiscal_agent_id", "validation.not_found")),  # another tenant's agent (RLS)
        (revoked, "fm-1", ("fiscal_agent_id", "validation.fiscal_agent_inactive")),
        (disabled, "fm-1", ("fiscal_agent_id", "validation.fiscal_capability_disabled")),
        (agent, "fm-9", ("fiscal_local_device_id", "validation.fiscal_local_device_unknown")),
    ]
    for agent_id, local_id, expected in cases:
        r = await _patch(env, pos, {"fiscal_agent_id": str(agent_id), "fiscal_local_device_id": local_id})
        assert r.status_code == 422 and detail(r) == expected, r.text
    ok = await _patch(env, pos, {"fiscal_agent_id": str(agent), "fiscal_local_device_id": "fm-1"})
    assert ok.status_code == 200 and ok.json()["fiscal_agent_id"] == str(agent)
    (status,) = tasks.of("fiscal.status")  # the new binding learns the FM state at once
    assert status.payload == {"cash_register_id": str(pos.register_id), "local_id": "fm-1"}

    # one FM serves one register
    second_id = uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) VALUES (:id, :t, :b, 'K2', 'web')",
        id=second_id, t=pos.tenant_id, b=pos.branch_id,
    )  # fmt: skip
    taken = await env.client.patch(
        f"{API}/cash-registers/{second_id}",
        json={"fiscal_agent_id": str(agent), "fiscal_local_device_id": "fm-1", "version": 1},
        headers=pos.shop.h("owner"),
    )
    assert taken.status_code == 422 and detail(taken) == (
        "fiscal_local_device_id",
        "validation.fiscal_local_device_taken",
    )
    free = await env.client.patch(
        f"{API}/cash-registers/{second_id}",
        json={"fiscal_agent_id": str(agent), "fiscal_local_device_id": "fm-2", "version": 1},
        headers=pos.shop.h("owner"),
    )
    assert free.status_code == 200
    cleared = await _patch(env, pos, {"fiscal_agent_id": None, "fiscal_local_device_id": None})
    assert cleared.status_code == 200 and cleared.json()["fiscal_agent_id"] is None
    assert len(tasks.of("fiscal.status")) == 2  # clearing queues nothing
