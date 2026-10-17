"""Card terminal transactions (18 §16a.3/§16a.4, 21 §9.4, 16 §2.1; QT-M01-24…34, B3-DoD-02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.access.application.approval_gate import ApprovalRefIn
from app.modules.integrations.card_terminal.application.ports import CardVoidRequest, TerminalRef
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.wiring import card_payments, orphan_sweep
from tests.support.card import (
    API,
    CardShop,
    audit_actions,
    card_env_fixture,
    card_shop,
    create_sale,
    err,
    pos_purchase,
    post_tx,
    scalar,
    tx_body,
)
from tests.support.catalog import Env

__all__ = ["card_env_fixture"]

pytestmark = pytest.mark.asyncio


async def _row(env: Env, cs: CardShop, tx_id: UUID) -> dict[str, Any]:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        row = (
            (
                await s.execute(
                    text("SELECT * FROM app.card_terminal_transactions WHERE id = :id"), {"id": tx_id}
                )
            )
            .mappings()
            .one()
        )
        return dict(row)


async def test_qt_m01_24_integrated_card_approved(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_000)
    assert result["status"] == "approved" and result["card_mask"] == "8600********1234"
    assert result["card_type"] == "unknown" and result["card_type_source"] == "bin_table"
    r = await post_tx(env, cs, tx_body(cs, attempt, "12000.00", result))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == str(attempt) and body["status"] == "approved" and body["resolved_by"] == "auto"
    assert body["approved_amount"] == "12000.00" and body["rrn"] == result["rrn"]
    row = await _row(env, cs, attempt)
    assert row["kind"] == "purchase" and row["card_type"] == "unknown" and row["resolved_at"] is not None
    assert "860031" not in str(row["terminal_response"])  # BIN never stored (15 §9.3)
    assert await audit_actions(env, cs, attempt) == ["card.purchase.approved"]
    # sale.created links the same attempt (no second row) and the payment gets the card details
    sale_id = await create_sale(env, cs)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await card_payments(env.settings).link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1,
            shift_id=cs.shift_id, card_result=result, expected_amount=Decimal("12000.00"), kind="purchase",
            doc_type="sales", doc_id=sale_id, client_event_id=uuid7(), actor_user_id=cs.uid("cashier"),
            device_id=cs.device_id,
        )  # fmt: skip
    assert rec.id == attempt and rec.mismatch is None and rec.rrn == result["rrn"] and rec.tid == "T0000001"
    assert rec.card_type == "unknown" and rec.card_type_source == "bin_table"
    row = await _row(env, cs, attempt)
    assert (row["doc_type"], row["doc_id"]) == ("sales", sale_id)
    assert await scalar(env, cs, "SELECT count(*) FROM app.card_terminal_transactions") == 1


async def test_qt_m01_25_declined_and_retry_with_new_attempt(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_100)
    assert result["status"] == "declined" and result["decline_code"] == "51"
    r = await post_tx(env, cs, tx_body(cs, attempt, "12001.00", result))
    assert r.status_code == 201 and r.json()["status"] == "declined"
    assert r.json()["decline_message"] == "Mablag' yetarli emas"
    assert await audit_actions(env, cs, attempt) == ["card.purchase.declined"]
    # "Qayta yuborish" — a NEW attempt_id; the first one is unchanged
    second, result2 = await pos_purchase(cs, 1_200_000)
    assert second != attempt
    assert (await post_tx(env, cs, tx_body(cs, second, "12000.00", result2))).status_code == 201
    assert (await _row(env, cs, attempt))["status"] == "declined"
    # cancel on the terminal while waiting → declined with decline_code 'cancelled'
    third, result3 = await pos_purchase(cs, 1_200_700)
    r = await post_tx(env, cs, tx_body(cs, third, "12007.00", result3))
    assert r.json()["status"] == "declined" and r.json()["decline_code"] == "cancelled"


async def test_qt_m01_26_timeout_unknown_status_query_and_block(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_200)
    assert result["status"] == "unknown"
    r = await post_tx(env, cs, tx_body(cs, attempt, "12002.00", result))
    assert r.status_code == 201 and r.json()["status"] == "unknown"
    assert await audit_actions(env, cs, attempt) == ["card.purchase.unknown"]
    # a new purchase on the same terminal is blocked while unknown
    blocked, pending = uuid7(), None
    r = await post_tx(env, cs, tx_body(cs, blocked, "500.00", pending))
    assert r.status_code == 409 and err(r) == "CARD_OUTCOME_UNKNOWN"
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        with pytest.raises(AppError) as exc:
            await card_payments(env.settings).assert_shift_resolved(s, shift_id=cs.shift_id)
    assert exc.value.code.value == "CARD_OUTCOME_UNKNOWN"
    # get_status → approved; purchase was sent to the terminal exactly once
    status = await cs.fake.get_status(attempt)
    assert cs.fake.calls["purchase"] == 1
    resolved = card_result_from_port(
        status, card_terminal_id=cs.terminal_id, requested_amount_tiyin=1_200_200, resolved_by="status_query"
    )
    r = await post_tx(env, cs, tx_body(cs, attempt, "12002.00", resolved))
    assert (
        r.status_code == 200
        and r.json()["status"] == "approved"
        and r.json()["resolved_by"] == "status_query"
    )
    assert await audit_actions(env, cs, attempt) == ["card.purchase.unknown", "card.purchase.approved"]
    r = await post_tx(env, cs, tx_body(cs, uuid7(), "500.00", None))
    assert r.status_code == 201 and r.json()["status"] == "pending"
    r = await post_tx(env, cs, tx_body(cs, uuid7(), "600.00", None))
    assert r.status_code == 409 and err(r) == "CARD_TERMINAL_BUSY"


def _manager_result(cs: CardShop, attempt: UUID, status: str, amount: str) -> dict[str, Any]:
    return {
        "attempt_id": str(attempt), "card_terminal_id": str(cs.terminal_id), "kind": "purchase", "status": status,
        "amount": amount, "resolved_by": "manager",
    }  # fmt: skip


async def test_qt_m01_27_manager_resolves_unknown(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_300)
    await post_tx(env, cs, tx_body(cs, attempt, "12003.00", result))
    event_id = uuid7()
    body = tx_body(cs, attempt, "12003.00", _manager_result(cs, attempt, "approved", "12003.00"),
                   client_event_id=event_id)  # fmt: skip
    r = await post_tx(env, cs, body)  # cashier, no approval
    assert r.status_code == 403 and err(r) == "PERMISSION_DENIED"
    # card details with a manager resolution → 422
    bad = dict(body, result=dict(body["result"], rrn="612345678901"))
    assert (await post_tx(env, cs, bad)).status_code == 422
    approval = {"mode": "local_pin", "approved_by": str(cs.uid("manager")), "pin_verified_locally": True}
    r = await post_tx(env, cs, dict(body, card_manual_approval=approval))
    assert r.status_code == 200, r.text
    out = r.json()
    assert (
        out["status"] == "approved"
        and out["resolved_by"] == "manager"
        and out["approved_amount"] == "12003.00"
    )
    assert out["rrn"] is None and out["card_mask"] is None and out["approval_code"] is None
    assert out["card_type"] is None
    row = await _row(env, cs, attempt)
    assert row["resolved_by_user_id"] == cs.uid("manager")
    assert "card.outcome.resolved_manual" in await audit_actions(env, cs, attempt)
    # the sale arrives (manual / unknown_result) — the attempt gets linked through client_event_id
    sale_id = await create_sale(env, cs, client_event_id=event_id)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        auth = await card_payments(env.settings).authorize_manual(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1,
            manual_reason="unknown_result", amount=Decimal("12003.00"),
            approval=ApprovalRefIn("local_pin", cs.uid("manager"), True), requested_by=cs.uid("cashier"),
            doc_type="sales", doc_id=sale_id, client_event_id=event_id, device_id=cs.device_id, offline=False,
        )  # fmt: skip
    assert auth.linked_transaction_id == attempt and not auth.offline_violation
    assert (await _row(env, cs, attempt))["doc_id"] == sale_id
    # "not passed" → declined / not_found
    other, res2 = await pos_purchase(cs, 300_300)
    await post_tx(env, cs, tx_body(cs, other, "3003.00", res2))
    r = await post_tx(env, cs, tx_body(cs, other, "3003.00", _manager_result(cs, other, "declined", "3003.00"),
                                      approval=approval), role="cashier")  # fmt: skip
    assert (
        r.status_code == 200 and r.json()["status"] == "declined" and r.json()["decline_code"] == "not_found"
    )


async def test_qt_m01_28_attempt_id_idempotent_and_unique_rrn(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_000)
    body = tx_body(cs, attempt, "12000.00", result)
    assert (await post_tx(env, cs, body)).status_code == 201
    again = await post_tx(env, cs, body)
    assert again.status_code == 200 and again.json()["id"] == str(attempt)
    # the agent gets the same attempt again → journalled result, no second terminal hit
    _, replay = await pos_purchase(cs, 1_200_000, attempt_id=attempt)
    assert replay["rrn"] == result["rrn"] and cs.fake.calls["purchase"] == 1
    assert await scalar(env, cs, "SELECT count(*) FROM app.card_terminal_transactions") == 1
    # another id with the same (tid, rrn) → 409 + sync_exceptions(card_result_mismatch)
    dup_id = uuid7()
    dup = dict(result, attempt_id=str(dup_id))
    r = await post_tx(env, cs, tx_body(cs, dup_id, "12000.00", dup))
    assert r.status_code == 409 and err(r) == "CARD_TRANSACTION_MISMATCH"
    assert await scalar(env, cs, "SELECT count(*) FROM app.card_terminal_transactions") == 1
    kinds = await scalar(env, cs, "SELECT string_agg(kind, ',') FROM app.sync_exceptions")
    assert kinds == "card_result_mismatch"
    # a final state is never replaced by another one
    flipped = dict(result, status="declined", rrn=None, card_mask=None, card_type=None, card_type_source=None)
    r = await post_tx(env, cs, tx_body(cs, attempt, "12000.00", flipped))
    assert r.status_code == 409 and err(r) == "CARD_TRANSACTION_MISMATCH"


async def test_qt_m01_29_void_on_cancel_and_orphan_sweep(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_000)
    await post_tx(env, cs, tx_body(cs, attempt, "12000.00", result))
    # cashier cancels the sale (fiscal failed) → automatic void
    void_id = uuid7()
    void = await cs.fake.void(CardVoidRequest(attempt_id=void_id, terminal=TerminalRef(card_terminal_id=cs.terminal_id),
                                              amount_tiyin=1_200_000, original_attempt_id=attempt))  # fmt: skip
    vres = card_result_from_port(void, card_terminal_id=cs.terminal_id, requested_amount_tiyin=1_200_000,
                                 resolved_by="auto", original_attempt_id=attempt)  # fmt: skip
    r = await post_tx(env, cs, tx_body(cs, void_id, "12000.00", vres, kind="void", original=attempt))
    assert r.status_code == 201, r.text
    assert (await _row(env, cs, attempt))["status"] == "voided"
    assert await audit_actions(env, cs, void_id) == ["card.void.auto"]
    # a void the terminal refuses → card.void.failed, the purchase stays approved
    bad_attempt, bad = await pos_purchase(cs, 1_200_600)
    await post_tx(env, cs, tx_body(cs, bad_attempt, "12006.00", bad))
    fail_id = uuid7()
    failed = await cs.fake.void(CardVoidRequest(attempt_id=fail_id, terminal=TerminalRef(card_terminal_id=cs.terminal_id),
                                                amount_tiyin=1_200_600, original_attempt_id=bad_attempt))  # fmt: skip
    fres = card_result_from_port(failed, card_terminal_id=cs.terminal_id, requested_amount_tiyin=1_200_600,
                                 resolved_by="auto", original_attempt_id=bad_attempt)  # fmt: skip
    r = await post_tx(env, cs, tx_body(cs, fail_id, "12006.00", fres, kind="void", original=bad_attempt))
    assert r.json()["status"] == "declined"
    assert await audit_actions(env, cs, fail_id) == ["card.void.failed"]
    assert (await _row(env, cs, bad_attempt))["status"] == "approved"
    assert await scalar(env, cs, "SELECT count(*) FROM app.sync_exceptions") == 0
    # 24 h later nothing claimed it → card_orphan_transaction (once), never an automatic void
    sweep = orphan_sweep(env.db.session_factory)
    assert await sweep.run(cs.tenant_id) == 0
    later = datetime.now(UTC) + timedelta(hours=25)
    assert await sweep.run(cs.tenant_id, now=later) == 1
    assert await sweep.run(cs.tenant_id, now=later) == 0
    row = await scalar(
        env, cs, "SELECT doc_id FROM app.sync_exceptions WHERE kind = 'card_orphan_transaction'"
    )
    assert row == bad_attempt
    assert (await _row(env, cs, bad_attempt))["status"] == "approved"


async def test_qt_m01_30_amount_mismatch_auto_void(env: Env) -> None:
    cs = await card_shop(env)
    cs.fake.script("amount_mismatch")
    attempt, result = await pos_purchase(cs, 1_200_000)
    assert result["amount"] == "11000.00"  # POS sees ≠ 12000.00 → CARD_AMOUNT_MISMATCH, void at once
    await post_tx(env, cs, tx_body(cs, attempt, "12000.00", result))
    row = await _row(env, cs, attempt)
    assert row["amount"] == Decimal("12000.00") and row["approved_amount"] == Decimal("11000.00")
    void_id = uuid7()
    void = await cs.fake.void(CardVoidRequest(attempt_id=void_id, terminal=TerminalRef(card_terminal_id=cs.terminal_id),
                                              amount_tiyin=1_100_000, original_attempt_id=attempt))  # fmt: skip
    vres = card_result_from_port(void, card_terminal_id=cs.terminal_id, requested_amount_tiyin=1_100_000,
                                 resolved_by="auto", original_attempt_id=attempt)  # fmt: skip
    await post_tx(env, cs, tx_body(cs, void_id, "11000.00", vres, kind="void", original=attempt))
    assert (await _row(env, cs, attempt))["status"] == "voided"
    assert "card.void.auto" in await audit_actions(env, cs, void_id)
    # had a sale arrived with this result, the server reports the difference instead of rejecting
    _, res2 = await pos_purchase(cs, 1_100_000)
    sale_id = await create_sale(env, cs)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await card_payments(env.settings).link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=res2, expected_amount=Decimal("12000.00"), kind="purchase", doc_type="sales",
            doc_id=sale_id, client_event_id=None, actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    assert rec.mismatch is not None and rec.mismatch["reason"] == "amount"


async def test_qt_m01_33_card_type_source(env: Env, migrator_engine: Any) -> None:
    cs = await card_shop(env)
    async with migrator_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO platform.card_bin_rules (bin_prefix, card_type, card_scheme, source, "
                "valid_from) "
                "VALUES ('860031', 'corporate', 'uzcard', 'test', '2026-01-01') ON CONFLICT DO NOTHING"
            )
        )
    from app.modules.integrations.card_terminal.domain.model import normalize_mask
    from app.modules.integrations.card_terminal.infrastructure.sql import SqlCardRepository

    norm = normalize_mask("860031******1234")
    assert norm is not None and norm.bin == "860031" and norm.mask == "8600********1234"
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        repo = SqlCardRepository()
        found = await repo.bin_rule_type(s, "86003155", datetime.now(UTC).date())
        missing = await repo.bin_rule_type(s, "999999", datetime.now(UTC).date())
    assert found == "corporate" and missing is None
    attempt, result = await pos_purchase(cs, 1_200_000, bin_rule_type=found)
    assert (result["card_type"], result["card_type_source"]) == ("corporate", "bin_table")
    assert (await post_tx(env, cs, tx_body(cs, attempt, "12000.00", result))).json()[
        "card_type"
    ] == "corporate"
    _, res_social = await pos_purchase(cs, 1_200_900)
    assert (res_social["card_type"], res_social["card_type_source"]) == ("social", "terminal")
    # no card_type at all from an old client → server fills unknown / bin_table
    plain, res_plain = await pos_purchase(cs, 1_300_000)
    res_plain = dict(res_plain, card_type=None, card_type_source=None)
    out = (await post_tx(env, cs, tx_body(cs, plain, "13000.00", res_plain))).json()
    assert (out["card_type"], out["card_type_source"]) == ("unknown", "bin_table")
    # the cashier never picks the type: any other source value is rejected
    bad_id, bad = await pos_purchase(cs, 1_400_000)
    r = await post_tx(env, cs, tx_body(cs, bad_id, "14000.00", dict(bad, card_type_source="cashier")))
    assert r.status_code == 422 and err(r) == "VALIDATION_ERROR"
    async with migrator_engine.begin() as conn:
        await conn.execute(text("DELETE FROM platform.card_bin_rules WHERE source = 'test'"))


async def test_qt_m01_34_offline_event_upsert_and_mismatch(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_000)
    sale_id = await create_sale(env, cs)
    cp = card_payments(env.settings)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await cp.link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=result, expected_amount=Decimal("12000.00"), kind="purchase", doc_type="sales",
            doc_id=sale_id, client_event_id=uuid7(), actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    assert rec.id == attempt and rec.mismatch is None
    row = await _row(env, cs, attempt)
    assert row["status"] == "approved" and row["doc_id"] == sale_id and row["tid"] == "T0000001"
    # the same attempt reported with another RRN by a second sale event of the same document → mismatch only
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec2 = await cp.link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=dict(result, rrn="999999999999"), expected_amount=Decimal("12000.00"), kind="purchase",
            doc_type="sales", doc_id=sale_id, client_event_id=None, actor_user_id=cs.uid("cashier"),
            device_id=cs.device_id,
        )  # fmt: skip
    assert rec2.mismatch is not None and "rrn" in rec2.mismatch["fields"]
    # linked to ANOTHER document → accepted with a mismatch (SYNC-04, 16 §2.1): the original link stays and
    # the second document gets a duplicate row of its own
    other_sale = await create_sale(env, cs)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec3 = await cp.link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1,
            shift_id=cs.shift_id, card_result=result, expected_amount=Decimal("12000.00"), kind="purchase",
            doc_type="sales", doc_id=other_sale, client_event_id=None, actor_user_id=cs.uid("cashier"),
            device_id=cs.device_id,
        )  # fmt: skip
    assert rec3.mismatch is not None and rec3.mismatch["reason"] == "linked_to_other_document"
    assert rec3.id != attempt and rec3.mismatch["existing_doc_id"] == str(sale_id)
    assert (await _row(env, cs, attempt))["doc_id"] == sale_id
    dup = await _row(env, cs, rec3.id)
    assert (
        dup["doc_id"] == other_sale
        and dup["tid"] is None
        and dup["terminal_response"]["duplicate_of"] == str(attempt)
    )
    # a non-approved result cannot back a payment row
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        with pytest.raises(AppError) as exc:
            await cp.link_result(
                s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1,
                shift_id=cs.shift_id, card_result=dict(result, status="unknown"), expected_amount=Decimal("1"),
                kind="purchase", doc_type="sales", doc_id=other_sale, client_event_id=None,
                actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
            )  # fmt: skip
    assert exc.value.code.value == "VALIDATION_ERROR"


async def test_get_card_transaction(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_000)
    await post_tx(env, cs, tx_body(cs, attempt, "12000.00", result))
    r = await env.client.get(f"{API}/card-terminal-transactions/{attempt}", headers=cs.h("cashier", key=None))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r = await env.client.get(f"{API}/card-terminal-transactions/{uuid7()}", headers=cs.h("cashier", key=None))
    assert r.status_code == 404
