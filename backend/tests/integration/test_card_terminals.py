"""Card terminal registry, manual-card policy and settlements (18 §16a.1/§16a.5/§16a.6, 21 §9.2;
QT-M01-31, QT-M16-08, QT-M02-08, B3-T05)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.core.errors import AppError
from app.modules.access.application.approval_gate import ApprovalRefIn
from app.modules.integrations.card_terminal.application.ports import (
    CardRefundRequest,
    CardVoidRequest,
    TerminalRef,
)
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.wiring import card_payments
from tests.conftest import MigratedDb
from tests.support.card import (
    API,
    CardShop,
    audit_actions,
    card_env_fixture,
    card_shop,
    create_sale,
    create_terminal,
    err,
    pos_purchase,
    post_tx,
    scalar,
    set_fallback,
    tx_body,
)
from tests.support.catalog import Env, catalog_app, catalog_settings, make_shop

__all__ = ["card_env_fixture"]

pytestmark = pytest.mark.asyncio


# --- registry (B3-EP-18#44/#45) --------------------------------------------------------------------


async def test_card_terminals_create_list_default_and_audit(env: Env) -> None:
    cs = await card_shop(env)
    assert cs.terminal["adapter"] == "fake" and cs.terminal["is_default"] is True
    assert cs.terminal["capabilities"]["void"] is True and cs.terminal["health_status"] == "unknown"
    second = await create_terminal(env.client, cs.shop, register=cs.register1, name="T2")
    r = await env.client.get(f"{API}/card-terminals", headers=cs.h("owner", key=None))
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 2 and page["page"] == 1
    defaults = {t["name"]: t["is_default"] for t in page["items"]}
    assert defaults == {"T1": False, "T2": True}  # the previous default of the register is cleared
    assert await audit_actions(env, cs, UUID(second["id"])) == ["card_terminal.created"]
    # cashier: only through a device bound to a register
    r = await env.client.get(f"{API}/card-terminals", headers=cs.h("cashier", key=None))
    assert r.status_code == 403 and err(r) == "PERMISSION_DENIED"
    # create needs cash_register.manage
    r = await env.client.post(f"{API}/card-terminals", json={
        "branch_id": str(cs.branch_id), "name": "X", "vendor": "fake", "adapter": "fake", "driver": "fake"},
        headers=cs.h("cashier"))  # fmt: skip
    assert r.status_code == 403


async def test_card_terminals_validation_rules(env: Env) -> None:
    cs = await card_shop(env)
    base: dict[str, Any] = {"branch_id": str(cs.branch_id), "name": "Humo P3", "vendor": "humo",
                            "adapter": "agent_ecr", "driver": "rahmat_lan", "agent_id": str(uuid7()),
                            "local_id": "term-1", "host": "192.168.1.50", "port": 8080, "tid": "TID00001"}  # fmt: skip

    async def post(body: dict[str, Any]) -> Any:
        return await env.client.post(f"{API}/card-terminals", json=body, headers=cs.h("owner"))

    r = await post({k: v for k, v in base.items() if k != "host"})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "host"
    r = await post(base | {"host": "8.8.8.8"})  # only RFC 1918
    assert (
        r.status_code == 422
        and r.json()["error"]["details"][0]["message_key"] == "validation.private_ipv4_required"
    )
    r = await post({k: v for k, v in base.items() if k != "tid"})  # active real terminal needs a TID
    assert r.status_code == 422
    r = await post(base | {"adapter": "cloud", "agent_id": None, "local_id": None, "host": None})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "vendor_terminal_ref"
    r = await post(base | {"is_default": True})
    assert r.status_code == 422  # is_default without a register
    assert (await post(base)).status_code == 201
    r = await post(base | {"local_id": "term-2"})  # TID unique in the tenant
    assert (
        r.status_code == 422
        and r.json()["error"]["details"][0]["message_key"] == "validation.card_terminal_tid_taken"
    )


async def test_card_terminals_patch_version_unknown_and_archive(env: Env) -> None:
    cs = await card_shop(env)
    url = f"{API}/card-terminals/{cs.terminal_id}"
    r = await env.client.patch(url, json={"name": "T1 kassa", "version": 99}, headers=cs.h("owner"))
    assert r.status_code == 409 and err(r) == "VERSION_CONFLICT"
    r = await env.client.patch(url, json={"name": "T1 kassa", "version": 1}, headers=cs.h("owner"))
    assert r.status_code == 200 and r.json()["name"] == "T1 kassa" and r.json()["version"] == 2
    # an unresolved unknown attempt blocks disabling
    attempt, result = await pos_purchase(cs, 1_200_300)
    await post_tx(env, cs, tx_body(cs, attempt, "12003.00", result))
    r = await env.client.patch(url, json={"status": "disabled", "version": 2}, headers=cs.h("owner"))
    assert r.status_code == 409 and err(r) == "CARD_OUTCOME_UNKNOWN"
    approval = {"mode": "local_pin", "approved_by": str(cs.uid("manager")), "pin_verified_locally": True}
    manager = {"attempt_id": str(attempt), "card_terminal_id": str(cs.terminal_id), "kind": "purchase",
               "status": "declined", "amount": "12003.00", "resolved_by": "manager"}  # fmt: skip
    assert (
        await post_tx(env, cs, tx_body(cs, attempt, "12003.00", manager, approval=approval))
    ).status_code == 200
    r = await env.client.patch(url, json={"status": "archived", "version": 2}, headers=cs.h("owner"))
    assert r.status_code == 200 and r.json()["status"] == "archived" and r.json()["is_default"] is False
    assert "card_terminal.archived" in await audit_actions(env, cs, cs.terminal_id)
    r = await env.client.patch(url, json={"name": "again", "version": 3}, headers=cs.h("owner"))
    assert r.status_code == 422  # archived terminal is read-only


async def test_card_fake_terminal_refused_without_setting(
    oauth_platform: None, app_db: Database, clean_redis: Redis, migrated_db: MigratedDb, redis_url: str,
    tmp_path: Path,
) -> None:  # fmt: skip
    settings = catalog_settings(migrated_db, redis_url, tmp_path / "files")
    async with catalog_app(settings) as (_, client):
        shop = await make_shop(app_db, client, "Prod-like")
        r = await client.post(f"{API}/card-terminals", json={
            "branch_id": str(shop.branch_id), "name": "F", "vendor": "fake", "adapter": "fake", "driver": "fake"},
            headers=shop.h())  # fmt: skip
        assert r.status_code == 422
        assert r.json()["error"]["details"][0]["message_key"] == "validation.card_terminal_fake_forbidden"
    with pytest.raises(ValidationError, match="ERP_CARD_FAKE_TERMINALS"):
        Settings(_env_file=None, environment="prod", card_fake_terminals=True)  # type: ignore[call-arg]


# --- manual card policy (QT-M01-31, B3-T05) --------------------------------------------------------


async def _authorize(
    env: Env, cs: CardShop, register: Any, reason: str, *, approval: ApprovalRefIn | None = None,
    offline: bool = False,
) -> Any:  # fmt: skip
    sale_id = await create_sale(env, cs)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        return await card_payments(env.settings).authorize_manual(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=register, manual_reason=reason,
            amount=Decimal("12000.00"), approval=approval, requested_by=cs.uid("cashier"), doc_type="sales",
            doc_id=sale_id, client_event_id=uuid7(), device_id=cs.device_id, offline=offline, line_id=None,
        )  # fmt: skip


async def test_qt_m01_31_manual_card_policy(env: Env) -> None:
    cs = await card_shop(env)
    cp = card_payments(env.settings)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        assert await cp.manual_policy(s, cash_register_id=cs.register1) == "manager_approval"  # key absent
        assert await cp.manual_policy(s, cash_register_id=cs.register2) == "standalone"
    with pytest.raises(AppError) as exc:
        await _authorize(env, cs, cs.register1, "terminal_offline")
    assert exc.value.code.value == "CARD_MANUAL_APPROVAL_REQUIRED"
    ok = await _authorize(env, cs, cs.register1, "terminal_offline",
                          approval=ApprovalRefIn("local_pin", cs.uid("manager"), True))  # fmt: skip
    assert ok.policy == "manager_approval" and ok.approval is not None and not ok.offline_violation
    assert (
        await scalar(env, cs, "SELECT count(*) FROM app.doc_approvals WHERE kind = 'card_manual_entry'") == 1
    )
    assert await scalar(env, cs, "SELECT count(*) FROM app.audit_log WHERE action = 'card.manual_entry'") == 1
    # offline: accepted, the caller records approval_limit_exceeded_offline
    off = await _authorize(env, cs, cs.register1, "terminal_error", offline=True)
    assert off.offline_violation
    await set_fallback(env, cs, "forbid")
    with pytest.raises(AppError) as exc:
        await _authorize(env, cs, cs.register1, "terminal_offline")
    assert exc.value.code.value == "CARD_MANUAL_NOT_ALLOWED"
    await set_fallback(env, cs, "allow")
    allowed = await _authorize(env, cs, cs.register1, "terminal_offline")
    assert allowed.policy == "allow" and allowed.approval is None
    # Kassa-2 — no bound terminal: always allowed, no approval, whatever the setting
    for value in ("manager_approval", "forbid"):
        await set_fallback(env, cs, value)
        res = await _authorize(env, cs, cs.register2, "standalone_terminal")
        assert res.policy == "standalone" and res.approval is None and not res.offline_violation
    assert await scalar(env, cs, "SELECT count(*) FROM app.approval_requests") == 0
    # the reason must match the register (online)
    with pytest.raises(AppError) as exc:
        await _authorize(env, cs, cs.register2, "terminal_offline")
    assert exc.value.code.value == "VALIDATION_ERROR"
    with pytest.raises(AppError):
        await _authorize(env, cs, cs.register1, "standalone_terminal")


# --- settlements (QT-M16-08, B3-EP-18#46) ----------------------------------------------------------


async def _approved(env: Env, cs: CardShop, tiyin: int) -> None:
    attempt, result = await pos_purchase(cs, tiyin)
    r = await post_tx(env, cs, tx_body(cs, attempt, result["amount"], result))
    assert r.status_code == 201, r.text


def _settlement(cs: CardShop, purchase_total: str, *, count: int = 2, **extra: Any) -> dict[str, Any]:
    return {
        "id": str(uuid7()), "card_terminal_id": str(cs.terminal_id), "shift_id": str(cs.shift_id),
        "batch_no": extra.pop("batch_no", "000001"), "business_date": "2026-10-17",
        "settled_at": datetime.now(UTC).isoformat(), "purchase_count": count, "purchase_total": purchase_total,
        "refund_count": 0, "refund_total": "0.00", **extra,
    }  # fmt: skip


async def test_qt_m16_08_settlement_mismatch_and_matched(env: Env) -> None:
    cs = await card_shop(env)
    await _approved(env, cs, 50_000_000)
    await _approved(env, cs, 20_000_000)  # expected_total 700000.00
    body = _settlement(cs, "650000.00")
    r = await env.client.post(f"{API}/card-terminal-settlements", json=body, headers=cs.h("cashier"))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out == {"id": body["id"], "card_terminal_id": str(cs.terminal_id), "status": "mismatch",
                   "net_total": "650000.00", "expected_total": "700000.00", "variance": "-50000.00"}  # fmt: skip
    assert await audit_actions(env, cs, UUID(body["id"])) == ["card.settlement.mismatch"]
    events = await scalar(
        env, cs, "SELECT count(*) FROM app.outbox_jobs WHERE payload ->> 'event' = 'card_settlement_mismatch'"
    )
    assert events == 1  # M18 to the Owner
    again = await env.client.post(f"{API}/card-terminal-settlements", json=body, headers=cs.h("cashier"))
    assert again.status_code == 201 and again.json() == out  # idempotent by id
    # the batch is closed: the next settlement only sees new purchases
    await _approved(env, cs, 10_000_000)
    body2 = _settlement(cs, "100000.00", count=1, batch_no="000002")
    r = await env.client.post(f"{API}/card-terminal-settlements", json=body2, headers=cs.h("cashier"))
    assert r.json()["status"] == "matched" and r.json()["variance"] == "0.00"
    assert await audit_actions(env, cs, UUID(body2["id"])) == []
    # shift.closed path (raw items) + failed terminal settlement
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        recs = await card_payments(env.settings).record_shift_settlements(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, shift_id=cs.shift_id, device_id=cs.device_id,
            actor_user_id=cs.uid("cashier"), client_event_id=uuid7(),
            items=[_settlement(cs, "0.00", count=0, batch_no=None, status="failed")],
        )  # fmt: skip
    assert recs[0].status == "failed"
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        with pytest.raises(AppError) as exc:
            await card_payments(env.settings).record_shift_settlements(
                s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, shift_id=cs.shift_id, device_id=None,
                actor_user_id=cs.uid("cashier"), client_event_id=None, items=[{"id": "x"}],
            )  # fmt: skip
    assert exc.value.code.value == "VALIDATION_ERROR"


# --- returns: void same day, refund after settlement (QT-M02-08) ------------------------------------


async def test_qt_m02_08_card_return_void_and_refund(env: Env) -> None:
    cs = await card_shop(env)
    attempt, result = await pos_purchase(cs, 1_200_000)
    sale_id = await create_sale(env, cs)
    cp = card_payments(env.settings)
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await cp.link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=result, expected_amount=Decimal("12000.00"), kind="purchase", doc_type="sales",
            doc_id=sale_id, client_event_id=None, actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    ref = TerminalRef(card_terminal_id=cs.terminal_id)
    return_id = uuid7()  # the return document id (return posting itself is the sales slice's)
    # same day, before settlement → void of the original purchase
    void_id = uuid7()
    void = await cs.fake.void(CardVoidRequest(attempt_id=void_id, terminal=ref, amount_tiyin=1_200_000,
                                              original_attempt_id=attempt))  # fmt: skip
    vres = card_result_from_port(void, card_terminal_id=cs.terminal_id, requested_amount_tiyin=1_200_000,
                                 resolved_by="auto", original_attempt_id=attempt)  # fmt: skip
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await cp.link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=vres, expected_amount=Decimal("12000.00"), kind="void", doc_type="returns",
            doc_id=return_id, client_event_id=None, actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    assert rec.id == void_id and rec.mismatch is None and rec.rrn is not None
    assert (
        await scalar(env, cs, "SELECT status FROM app.card_terminal_transactions WHERE id = :i", i=attempt)
        == "voided"
    )
    assert await audit_actions(env, cs, void_id) == ["card.refund"]
    # after settlement → refund with the original RRN
    second, res2 = await pos_purchase(cs, 800_000)
    refund_id = uuid7()
    refund = await cs.fake.refund(CardRefundRequest(attempt_id=refund_id, terminal=ref, amount_tiyin=800_000,
                                                    original_rrn=res2["rrn"], original_attempt_id=second))  # fmt: skip
    rres = card_result_from_port(refund, card_terminal_id=cs.terminal_id, requested_amount_tiyin=800_000,
                                 resolved_by="auto", original_attempt_id=second)  # fmt: skip
    r = await post_tx(env, cs, tx_body(cs, second, "8000.00", res2))
    assert r.status_code == 201
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rec = await cp.link_result(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1, shift_id=cs.shift_id,
            card_result=rres, expected_amount=Decimal("8000.00"), kind="refund", doc_type="returns",
            doc_id=uuid7(), client_event_id=None, actor_user_id=cs.uid("cashier"), device_id=cs.device_id,
        )  # fmt: skip
    assert rec.id == refund_id and rec.card_mask is not None
    assert await audit_actions(env, cs, refund_id) == ["card.refund"]
    kind = await scalar(env, cs, "SELECT kind FROM app.card_terminal_transactions WHERE id = :i", i=refund_id)
    assert kind == "refund"


async def test_sec02_manual_card_local_pin_approver_not_bound_is_flagged(env: Env) -> None:
    """SEC-02: online local_pin approver not PIN-bound to the session → accepted, `actor_unverified` details."""
    cs = await card_shop(env)
    sale_id = await create_sale(env, cs)

    async def not_bound(_user: UUID) -> bool:
        return False

    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        auth = await card_payments(env.settings).authorize_manual(
            s, tenant_id=cs.tenant_id, branch_id=cs.branch_id, cash_register_id=cs.register1,
            manual_reason="terminal_offline", amount=Decimal("12000.00"),
            approval=ApprovalRefIn("local_pin", cs.uid("manager"), True), requested_by=cs.uid("cashier"),
            doc_type="sales", doc_id=sale_id, client_event_id=uuid7(), device_id=cs.device_id, offline=False,
            approver_bound=not_bound, session_user_id=cs.uid("cashier"),
        )  # fmt: skip
    assert auth.approver_unverified
    assert auth.unverified_details["session_user_id"] == str(cs.uid("cashier"))
