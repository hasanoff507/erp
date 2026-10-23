"""Do'kon agent ``card_terminal`` capability — server side (B5-T05; qaror #71; 21 §16, 18 §16a.5, 23 §4.2).

BO-12 binding of an ``agent_ecr`` terminal to the agent's ``local_id``/``host``, ``card.status`` enqueue and result
handling (``health_status``, ``unresolved`` → ``resolved_by='status_query'``), SYNC-05 lenient event parsing and
DoD-02 (server part): purchase / void / status query through the agent with the Python driver emulator
(:class:`FakeCardTerminalAdapter`, same table as the agent's ``FakeCardTerminalDriver``)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.integrations.card_terminal.application.ports import (
    CardPurchaseRequest,
    CardVoidRequest,
    TerminalRef,
)
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.wiring import card_agent_service, card_payments
from tests.support.card import API, CardShop, card_env_fixture, card_shop, create_sale, err, post_tx, tx_body
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


async def _row(env: Env, cs: CardShop, sql: str, **params: Any) -> dict[str, Any]:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        return dict((await s.execute(text(sql), params)).mappings().one())


async def _bound(env: Env) -> tuple[CardShop, UUID, dict[str, Any]]:
    cs = await card_shop(env)
    agent_id = await insert_agent(env, cs, capabilities=card_capabilities(AGENT_DEVICE))
    terminal = await agent_terminal(env, cs, agent_id)
    return cs, agent_id, terminal


async def _pos(cs: CardShop, terminal_id: UUID, amount_tiyin: int) -> tuple[UUID, dict[str, Any]]:
    """What ``AgentEcrAdapter`` does through ``/v1/card/purchase`` (the agent runs the driver emulator)."""
    attempt = uuid7()
    result = await cs.fake.purchase(
        CardPurchaseRequest(
            attempt_id=attempt, terminal=TerminalRef(card_terminal_id=terminal_id, local_id="ecr-1"),
            amount_tiyin=amount_tiyin, cash_register_id=cs.register1, client_event_id=uuid7(),
        )
    )  # fmt: skip
    return attempt, card_result_from_port(
        result, card_terminal_id=terminal_id, requested_amount_tiyin=amount_tiyin, resolved_by="auto"
    )


def _body(cs: CardShop, terminal_id: UUID, attempt: UUID, amount: str, result: dict[str, Any] | None,
          **kw: Any) -> dict[str, Any]:  # fmt: skip
    return tx_body(cs, attempt, amount, result, **kw) | {"card_terminal_id": str(terminal_id)}


# --- BO-12 binding (B5-US-M01-08) --------------------------------------------------------------------


async def test_b5_us_m01_08_bo12_terminal_agent_binding(env: Env) -> None:
    cs = await card_shop(env)
    caps = card_capabilities(AGENT_DEVICE)
    agent_id = await insert_agent(env, cs, capabilities=caps)
    base: dict[str, Any] = {
        "branch_id": str(cs.branch_id), "cash_register_id": str(cs.register1), "name": "ECR", "vendor": "rahmat",
        "adapter": "agent_ecr", "driver": "rahmat_lan", "agent_id": str(agent_id), "local_id": "ecr-1",
        "host": "192.168.1.60", "tid": "T0000001",
    }  # fmt: skip

    async def post(body: dict[str, Any]) -> Any:
        return await env.client.post(f"{API}/card-terminals", json=body, headers=cs.h("owner"))

    def key(r: Any) -> str:
        detail: str = r.json()["error"]["details"][0]["message_key"]
        return detail

    r = await post(base | {"agent_id": str(uuid7())})
    assert r.status_code == 422 and key(r) == "validation.card_terminal_agent_not_found"
    r = await post(base | {"local_id": "ecr-9"})  # not among capabilities.card_terminal.devices[]
    assert r.status_code == 422 and key(r) == "validation.card_terminal_local_unknown"
    r = await post(base | {"host": "192.168.1.61"})  # only the host the agent reported (allow-list)
    assert r.status_code == 422 and key(r) == "validation.card_terminal_host_mismatch"
    r = await post(base | {"host": "8.8.8.8"})
    assert r.status_code == 422 and key(r) == "validation.private_ipv4_required"
    disabled = await insert_agent(env, cs, capabilities=card_capabilities(AGENT_DEVICE, enabled=False))
    r = await post(base | {"agent_id": str(disabled)})
    assert r.status_code == 409 and err(r) == "AGENT_CAPABILITY_DISABLED"
    revoked = await insert_agent(env, cs, capabilities=caps, status="revoked")
    r = await post(base | {"agent_id": str(revoked)})
    assert r.status_code == 422 and key(r) == "validation.card_terminal_agent_revoked"
    r = await post(base)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["agent_id"] == str(agent_id) and created["host"] == "192.168.1.60"
    # the same local_id of the agent cannot be bound twice
    r = await post(base | {"tid": "T0000002", "is_default": False})
    assert r.status_code == 422 and key(r) == "validation.card_terminal_local_taken"
    # a terminal can always be disabled, even when its agent no longer qualifies
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await s.execute(
            text("UPDATE app.onec_agents SET capabilities = '{}' WHERE id = :id"), {"id": agent_id}
        )
    r = await env.client.patch(
        f"{API}/card-terminals/{created['id']}", json={"status": "disabled", "version": created["version"]},
        headers=cs.h("owner"),
    )  # fmt: skip
    assert r.status_code == 200 and r.json()["status"] == "disabled"


# --- card.status --------------------------------------------------------------------------------------


async def test_b5_t05_card_status_enqueue_sweep_and_health(env: Env) -> None:
    cs, agent_id, terminal = await _bound(env)
    tasks = FakeAgentTasks()
    service = card_agent_service(env.settings, env.db.session_factory, tasks)
    first = await service.status_sweep(cs.tenant_id)
    again = await service.status_sweep(cs.tenant_id)  # dedupe while queued
    assert (first.enqueued, again.enqueued) == (1, 1) and len(tasks.calls) == 1
    call = tasks.calls[0]
    assert call["kind"] == "card.status" and call["agent_id"] == agent_id
    assert call["payload"] == {"terminals": [{"card_terminal_id": terminal["id"], "local_id": "ecr-1"}]}
    task = TaskStub(call["id"], "card.status", call["payload"])
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_status(s, cs.tenant_id, agent_id, task, ResultStub("done", {
            "terminals": [{"card_terminal_id": terminal["id"], "local_id": "ecr-1", "status": "online",
                           "tid": "T0000001", "last_tx_at": None}], "unresolved": []}))  # fmt: skip
    row = await _row(env, cs, "SELECT health_status, health_checked_at, version FROM app.card_terminals "
                              "WHERE id = :id", id=terminal["id"])  # fmt: skip
    assert row["health_status"] == "online" and row["health_checked_at"] is not None
    assert row["version"] == terminal["version"]  # live state, not a managed edit
    # a failed task: busy → busy, anything else → offline
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_status(
            s, cs.tenant_id, agent_id, task, ResultStub("failed", error={"code": "CARD_TERMINAL_BUSY"})
        )
    assert (await _row(env, cs, "SELECT health_status FROM app.card_terminals WHERE id = :id",
                       id=terminal["id"]))["health_status"] == "busy"  # fmt: skip
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_status(
            s, cs.tenant_id, agent_id, task, ResultStub("failed", error={"code": "CARD_TERMINAL_UNREACHABLE"})
        )
    assert (await _row(env, cs, "SELECT health_status FROM app.card_terminals WHERE id = :id",
                       id=terminal["id"]))["health_status"] == "offline"  # fmt: skip
    # an agent without the capability gets no task
    other = await card_shop(env, "Agentsiz")
    disabled = await insert_agent(env, other, capabilities=card_capabilities(AGENT_DEVICE, enabled=False))
    assert disabled is not None
    assert (await service.status_sweep(other.tenant_id)).enqueued == 0


async def test_b5_dod_02_agent_purchase_unknown_status_query_void(env: Env) -> None:
    """DoD-02 (server part): online purchase through the agent, a timeout resolved by ``card.status``
    (``resolved_by='status_query'``, audit without a user, with the agent device), a void, and a terminal
    answer that the server cannot use (SYNC-05) → ``card_result_mismatch{malformed_result}``, no exception."""
    cs, agent_id, terminal = await _bound(env)
    tid = UUID(terminal["id"])
    # approved purchase recorded online (POST /card-terminal-transactions with the agent's result)
    approved, result = await _pos(cs, tid, 1_200_000)
    r = await post_tx(env, cs, _body(cs, tid, approved, "12000.00", result))
    assert r.status_code == 201 and r.json()["status"] == "approved"
    # timeout → unknown on the server; the agent's journal later learns the answer
    unknown, timeout = await _pos(cs, tid, 1_500_200)
    r = await post_tx(env, cs, _body(cs, tid, unknown, "15002.00", timeout))
    assert r.status_code == 201 and r.json()["status"] == "unknown"
    late = await cs.fake.get_status(unknown)
    assert late.status == "approved"
    tasks = FakeAgentTasks()
    service = card_agent_service(env.settings, env.db.session_factory, tasks)
    item = late.model_dump(mode="json") | {"resolved_by": "status_query", "local_id": "ecr-1"}
    garbage = {"attempt_id": str(approved), "kind": "purchase", "status": "approved", "amount_tiyin": "x"}
    data = {"terminals": [], "unresolved": [item, garbage]}
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_status(s, cs.tenant_id, agent_id, TaskStub(uuid7(), "card.status", {}),
                                    ResultStub("done", data))  # fmt: skip
    row = await _row(env, cs, "SELECT status, resolved_by, rrn, card_mask, card_type, approved_amount "
                              "FROM app.card_terminal_transactions WHERE id = :id", id=unknown)  # fmt: skip
    assert row == {"status": "approved", "resolved_by": "status_query", "rrn": late.rrn,
                   "card_mask": "8600********1234", "card_type": "unknown", "approved_amount": Decimal("15002.00")}  # fmt: skip
    audit = await _row(env, cs, "SELECT action, user_id, device_id FROM app.audit_log WHERE entity_id = :id "
                                "AND action = 'card.purchase.approved'", id=unknown)  # fmt: skip
    agent_device = await _row(env, cs, "SELECT device_id FROM app.onec_agents WHERE id = :id", id=agent_id)
    assert audit["user_id"] is None and audit["device_id"] == agent_device["device_id"]
    # the garbage item targets an already final attempt → ignored, nothing raised
    # replay of the same result → no change, no second audit row
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_status(s, cs.tenant_id, agent_id, TaskStub(uuid7(), "card.status", {}),
                                    ResultStub("done", data))  # fmt: skip
    count = await _row(env, cs, "SELECT count(*) AS n FROM app.audit_log WHERE entity_id = :id", id=unknown)
    assert count["n"] == 2  # card.purchase.unknown + card.purchase.approved
    # a malformed unresolved answer for a still-unknown attempt → sync exception, no exception raised
    stuck, stuck_result = await _pos(cs, tid, 1_600_300)
    await post_tx(env, cs, _body(cs, tid, stuck, "16003.00", stuck_result))
    bad = {"attempt_id": str(stuck), "kind": "purchase", "status": "approved", "amount_tiyin": 1_600_300,
           "card_scheme": "amex-ish"}  # fmt: skip
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await service.handle_status(s, cs.tenant_id, agent_id, TaskStub(uuid7(), "card.status", {}),
                                    ResultStub("done", {"unresolved": [bad]}))  # fmt: skip
    exc = await _row(env, cs, "SELECT kind, details FROM app.sync_exceptions WHERE doc_id = :id", id=stuck)
    assert exc["kind"] == "card_result_mismatch" and exc["details"]["reason"] == "malformed_result"
    assert (await _row(env, cs, "SELECT status FROM app.card_terminal_transactions WHERE id = :id",
                       id=stuck))["status"] == "unknown"  # fmt: skip
    # void of the first purchase through the agent → the purchase becomes voided
    void_id = uuid7()
    void = await cs.fake.void(CardVoidRequest(
        attempt_id=void_id, terminal=TerminalRef(card_terminal_id=tid, local_id="ecr-1"), amount_tiyin=1_200_000,
        original_attempt_id=approved))  # fmt: skip
    void_result = card_result_from_port(void, card_terminal_id=tid, requested_amount_tiyin=1_200_000,
                                        resolved_by="auto", original_attempt_id=approved)  # fmt: skip
    r = await post_tx(
        env, cs, _body(cs, tid, void_id, "12000.00", void_result, kind="void", original=approved)
    )
    assert r.status_code == 201 and r.json()["status"] == "approved"
    assert (await _row(env, cs, "SELECT status FROM app.card_terminal_transactions WHERE id = :id",
                       id=approved))["status"] == "voided"  # fmt: skip


async def test_b5_dod_02_offline_integrated_card_event_via_agent_terminal(env: Env) -> None:
    """Offline (no internet, agent + terminal work): the sale event carries the agent's card result and the
    server upserts the attempt for the ``agent_ecr`` terminal (QT-M01-34 path)."""
    cs, _, terminal = await _bound(env)
    tid = UUID(terminal["id"])
    attempt, result = await _pos(cs, tid, 2_000_000)
    sale_id = await create_sale(env, cs, total="20000.00")
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await card_payments(env.settings).link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=result, expected_amount=Decimal("20000.00"), kind="purchase", doc_type="sales",
            doc_id=sale_id, client_event_id=uuid7(), actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    assert rec.id == attempt and rec.mismatch is None and rec.card_terminal_id == tid
    row = await _row(env, cs, "SELECT status, doc_id, resolved_by FROM app.card_terminal_transactions "
                              "WHERE id = :id", id=attempt)  # fmt: skip
    assert row == {"status": "approved", "doc_id": sale_id, "resolved_by": "auto"}


# --- SYNC-05 -----------------------------------------------------------------------------------------


async def test_sync_05_lenient_card_result_in_event_mode(env: Env) -> None:
    cs, _, terminal = await _bound(env)
    tid = UUID(terminal["id"])
    attempt, result = await _pos(cs, tid, 2_100_000)
    odd = dict(result, rrn=f"{result['rrn'][:6]}-{result['rrn'][6:]}", card_mask="8600 31** **** 1234",
               tid="TERMINAL-ID-0000000001", card_scheme="UZCARD", slip_text="x" * 5000, vendor_extra={"a": 1})  # fmt: skip
    sale_id = await create_sale(env, cs, total="21000.00")
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await card_payments(env.settings).link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=odd, expected_amount=Decimal("21000.00"), kind="purchase", doc_type="sales",
            doc_id=sale_id, client_event_id=uuid7(), actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    assert rec.mismatch is not None and rec.mismatch["reason"] == "malformed_result"
    assert set(rec.mismatch["fields"]) >= {
        "rrn",
        "card_mask",
        "tid",
        "card_scheme",
        "slip_text",
        "vendor_extra",
    }
    assert rec.rrn == result["rrn"] and rec.card_mask == "8600********1234" and rec.tid is None
    assert rec.card_scheme == "uzcard"
    row = await _row(env, cs, "SELECT status, rrn, tid, terminal_response FROM app.card_terminal_transactions "
                              "WHERE id = :id", id=attempt)  # fmt: skip
    assert row["status"] == "approved" and row["rrn"] == result["rrn"] and row["tid"] is None
    raw = row["terminal_response"]["raw_card_result"]
    assert raw["card_mask"] == "8600 31** **** 1234" and raw["tid"] == "TERMINAL-ID-0000000001"
    # an approved purchase whose mask cannot be recovered still fails (the payment row needs it, 12 CHECK)
    attempt2, result2 = await _pos(cs, tid, 2_200_000)
    sale2 = await create_sale(env, cs, total="22000.00")
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        with pytest.raises(AppError) as exc:
            await card_payments(env.settings).link_result(
                s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1,
                shift_id=cs.shift_id, card_result=dict(result2, card_mask="************1234"),
                expected_amount=Decimal("22000.00"), kind="purchase", doc_type="sales", doc_id=sale2,
                client_event_id=uuid7(), actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
            )  # fmt: skip
    assert exc.value.code.value == "VALIDATION_ERROR" and attempt2 is not None
    # REST stays strict
    nid = uuid7()
    r = await post_tx(env, cs, _body(cs, tid, nid, "21000.00", dict(odd, attempt_id=str(nid))))
    assert r.status_code == 422 and err(r) == "VALIDATION_ERROR"
