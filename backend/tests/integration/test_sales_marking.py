"""Marked goods in ``sale.created`` (16 §7, 18 §4.2, qaror #17/#62): QT-M01-04 offline sale with a cached
price (code inside the fiscal receipt, no CRPT call; verified with CRPT once online) and B3 F-5 (a duplicate
code on a receipt the FM already signed → accepted + sync exception + M18)."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.db.base import uuid7
from tests.support.marking import (
    code,
    events,
    fake_crpt_fixture,
    jobs,
    marking_env_fixture,
    run_outbox,
    set_precheck,
)
from tests.support.sales import (
    Env,
    Pos,
    deliver,
    execute,
    fiscalize,
    make_pos,
    new_item,
    one,
    rows,
    sale_line,
    sale_payload,
    sell,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["fake_crpt_fixture", "marking_env_fixture"]

SIGNED = {
    "fm_terminal_id": "ZZ000000000002", "fm_receipt_seq": 9, "fiscal_sign": "123456789012",
    "qr_url": "https://ofd.soliq.uz/check?t=ZZ000000000002&r=9&c=20261017120000&s=123456789012",
    "fiscal_at": "2026-10-17T07:00:00Z",
}  # fmt: skip


async def _water(env: Env, pos: Pos) -> Any:
    return await new_item(env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages",
                          price="8000.00", cost="5000.00")  # fmt: skip


def _offline(pos: Pos, product: Any, raw: str, **extra: Any) -> dict[str, Any]:
    line = sale_line(product, price="8000.0000", marking_code=raw, marking_offline=True)
    return sale_payload(pos, [line], is_offline=True, **extra)


async def test_qt_m01_04_offline_marked_sale_price_cached(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    product = await _water(env, pos)  # the device has the product and its price (Dexie cache)
    raw = code("5a8pLsr>qeHnD")
    payload = _offline(pos, product, raw)
    res = await sell(env, pos, payload)
    assert res.server["warnings"] == []
    receipt = await one(env.db, pos.tenant_id, "SELECT payload FROM app.fiscal_receipts WHERE sale_id = :s",
                        s=payload["id"])  # fmt: skip
    assert receipt["items"][0]["marking_codes"] == [raw] and receipt["is_offline"] is True  # GS kept exactly
    assert crpt.calls == []  # no CRPT call for a sale (qaror #62)
    mc = await rows(env.db, pos.tenant_id, "SELECT status, verified_at FROM app.marking_codes WHERE code = :c",
                    c=raw)  # fmt: skip
    assert mc == [{"status": "pending_verification", "verified_at": None}]
    audit = await rows(env.db, pos.tenant_id, "SELECT after, device_id FROM app.audit_log "
                       "WHERE action = 'marking.offline_sold'")  # fmt: skip
    assert audit[0]["after"]["codes"] == [raw] and audit[0]["after"]["price_source"] == "cache"
    assert audit[0]["device_id"] == pos.device_id
    queued = await jobs(env, pos.tenant_id, "marking_verify")
    assert [j["idempotency_key"] for j in queued] == [f"marking_verify:{payload['id']}"]
    assert queued[0]["payload"]["codes"] == [raw]
    # internet is back: the FM receipt reaches the OFD (→ sold), the worker verifies the code with CRPT
    await fiscalize(env, pos)
    done = await run_outbox(env, pos.tenant_id)
    assert [o.status for o in done] == ["done"] and crpt.calls == [("verify_code", raw)]
    mc = await rows(env.db, pos.tenant_id, "SELECT status, verified_at FROM app.marking_codes WHERE code = :c",
                    c=raw)  # fmt: skip
    assert mc[0]["status"] == "sold" and mc[0]["verified_at"] is not None
    assert await events(env, pos.tenant_id, "marking_alert") == []


async def test_qt_m01_04_offline_code_invalid_later_alerts_owner(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    product = await _water(env, pos)
    raw = code()
    crpt.statuses[raw] = "not_found"
    payload = _offline(pos, product, raw)
    await sell(env, pos, payload)  # accepted offline — the goods are gone
    await run_outbox(env, pos.tenant_id)
    alerts = await events(env, pos.tenant_id, "marking_alert")
    assert len(alerts) == 1 and alerts[0]["reason"] == "verify_failed"
    assert alerts[0]["codes"] == [raw] and alerts[0]["reasons"] == {raw: "not_found"}
    assert alerts[0]["doc_id"] == payload["id"] and alerts[0]["branch_id"] == str(pos.branch_id)
    audit = await one(
        env.db, pos.tenant_id, "SELECT after FROM app.audit_log WHERE action = 'marking.verify_failed'"
    )
    assert audit["reason"] == "crpt_invalid" and audit["codes"] == [raw]
    assert await one(
        env.db, pos.tenant_id, "SELECT status FROM app.sales WHERE id = :s", s=payload["id"]
    ) == ("posted")


async def test_qt_m01_04_precheck_off_no_later_verify_and_transient_retry(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    product = await _water(env, pos)
    await set_precheck(env, pos, "off")
    await sell(env, pos, _offline(pos, product, code()))
    assert await jobs(env, pos.tenant_id, "marking_verify") == []
    await set_precheck(env, pos, "warn")
    payload = _offline(pos, product, code())
    await sell(env, pos, payload)
    crpt.fail = "transient"  # CRPT down → retry with backoff (21 §4), nothing alerted
    out = await run_outbox(env, pos.tenant_id)
    assert [o.status for o in out] == ["retry"]
    queued = await jobs(env, pos.tenant_id, "marking_verify")
    assert queued[0]["status"] == "retry" and queued[0]["attempts"] == 1
    crpt.fail = None
    assert [o.status for o in await run_outbox(env, pos.tenant_id)] == ["done"]


async def test_b3_f5_signed_duplicate_accepted_m18_exception(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    product = await _water(env, pos)
    raw = code()
    first = sale_payload(pos, [sale_line(product, price="8000.0000", marking_code=raw)])
    await sell(env, pos, first)
    unsigned = await deliver(env, pos, "sale.created", _offline(pos, product, raw))
    assert unsigned.code == "MARKING_CODE_ALREADY_SOLD"  # no fiscal_result → never fiscalized (18 §4.2)
    signed = _offline(pos, product, raw, fiscal_result=SIGNED)
    res = await sell(env, pos, signed)
    assert "MARKING_CODE_ALREADY_SOLD" in res.server["warnings"]
    assert "marking_code_duplicate" in res.exception_kinds
    flag = next(e for e in res.result.sync_exceptions if e.kind == "marking_code_duplicate")  # type: ignore[union-attr]
    assert flag.doc_id is not None and str(flag.doc_id) == signed["id"] and flag.details["codes"] == [raw]
    alerts = await events(env, pos.tenant_id, "marking_alert")
    assert [(a["reason"], a["sale_id"], a["codes"]) for a in alerts] == [
        ("duplicate_code", signed["id"], [raw])
    ]
    owner = await one(
        env.db, pos.tenant_id, "SELECT last_doc_id FROM app.marking_codes WHERE code = :c", c=raw
    )
    assert str(owner) == first["id"]  # the first sale keeps the code
    verify = await jobs(env, pos.tenant_id, "marking_verify")
    assert all(raw not in j["payload"]["codes"] for j in verify)  # the duplicate is not re-verified
    # the sync_exceptions CHECK accepts the kind (0028a)
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.sync_exceptions (id, tenant_id, kind, doc_type, doc_id, details) "
        "VALUES (:id, :t, 'marking_code_duplicate', 'sales', :d, '{}')",
        id=uuid7(), t=pos.tenant_id, d=signed["id"],
    )  # fmt: skip


async def test_us_m01_06_b2b_credit_sale_calls_einvoice_hook(env: Env, crpt: Any) -> None:
    """The single ``einvoice_hooks().on_b2b_credit_sale_posted`` call in the sale posting (contract 5a)."""
    from tests.support.sales import add_customer

    pos = await make_pos(env)
    product = await new_item(env, pos)
    company = await add_customer(env, pos, kind="company")
    line = sale_line(product)
    credit = sale_payload(
        pos, [line], [{"method": "debt", "amount": line["line_total"]}], counterparty_id=str(company)
    )
    await sell(env, pos, credit)
    person = await add_customer(env, pos)
    retail = sale_payload(pos, [sale_line(product)], [{"method": "debt", "amount": line["line_total"]}],
                          counterparty_id=str(person))  # fmt: skip
    await sell(env, pos, retail)
    drafts = await rows(
        env.db, pos.tenant_id,
        "SELECT related_doc_id, direction, status FROM app.einvoices WHERE related_doc_type = 'sales'",
    )  # fmt: skip
    assert [(str(d["related_doc_id"]), d["direction"], d["status"]) for d in drafts] == [
        (credit["id"], "out", "draft")
    ]


async def test_qt_m01_13_checkout_provider_tx_strict(env: Env, crpt: Any) -> None:
    """18 §16.4: a confirmed checkout backs a sale only with the provider transaction it was paid by — a
    checkout without ``provider_tx_id`` or with another one is not a payment (same rule as debt payments)."""
    pos = await make_pos(env)
    product = await new_item(env, pos)
    ref = uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.payment_checkouts (checkout_ref, tenant_id, branch_id, cash_register_id, provider, qr_type, "
        "amount, provider_tx_id, status, confirmed_at, expires_at, created_by) VALUES (:r, :t, :b, :c, 'uzqr', "
        "'dynamic', 12000, NULL, 'confirmed', now(), now() + interval '1 day', :u)",
        r=ref, t=pos.tenant_id, b=pos.branch_id, c=pos.register_id, u=pos.shop.user_ids["cashier"],
    )  # fmt: skip
    tx = f"tx-{ref.hex}"  # (provider, provider_tx_id) is unique platform-wide
    pay = {"method": "uzqr", "amount": "12000.00", "qr_type": "dynamic", "checkout_ref": str(ref),
           "provider_tx_id": f"{tx}-other"}  # fmt: skip
    no_tx = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert no_tx.code == "PAYMENT_NOT_CONFIRMED"
    await execute(env.db, pos.tenant_id, "UPDATE app.payment_checkouts SET provider_tx_id = :x", x=tx)
    other = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert other.code == "PAYMENT_NOT_CONFIRMED"
    await sell(env, pos, sale_payload(pos, [sale_line(product)], [{**pay, "provider_tx_id": tx}]))
    assert await one(env.db, pos.tenant_id, "SELECT status FROM app.payment_checkouts") == "consumed"
