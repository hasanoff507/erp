"""``sale.created`` posting (18 §4, 13 §2.1–§2.4, §3, §4.1; 16 §5) — M01/M03/M10 acceptance (03, 31)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from tests.support.catalog import create_product
from tests.support.sales import (
    D,
    Env,
    Pos,
    add_customer,
    bind_terminal,
    card_result,
    deliver,
    execute,
    ledger_rows,
    make_pos,
    new_item,
    one,
    rows,
    sale_line,
    sale_payload,
    sales_env_fixture,
    sell,
    sums,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def _receipt(env: Env, pos: Pos, sale_id: str) -> dict[str, Any]:
    found = await rows(
        env.db, pos.tenant_id,
        "SELECT kind, status, payment_form, payload, offline_since, receipt_seq FROM app.fiscal_receipts "
        "WHERE sale_id = :d ORDER BY receipt_seq",
        d=sale_id,
    )  # fmt: skip
    return found[0]


def _local_pin(user_id: object) -> dict[str, Any]:
    return {"mode": "local_pin", "approved_by": str(user_id), "pin_verified_locally": True}


# --- M01: posting --------------------------------------------------------------------------------------
async def test_qt_m01_01_cash_sale_posting(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    product = await new_item(env, pos, price="12000.00", stock="5.000", cost="8000.00")
    payload = sale_payload(pos, [sale_line(product)])
    res = await sell(env, pos, payload)
    sale_id = payload["id"]
    assert res.server["fiscal"]["status"] == "pending"
    assert res.server["number"].startswith("K-")
    moves = await rows(
        env.db, pos.tenant_id, "SELECT qty, cost_amount FROM app.stock_moves WHERE doc_id = :d", d=sale_id
    )
    assert [(m["qty"], m["cost_amount"]) for m in moves] == [(D("-1.000"), D("-8000.00"))]
    totals = sums(await ledger_rows(env, pos, sale_id))
    assert totals == {
        ("5010", "9020"): D("10714.29"),
        ("5010", "6410"): D("1285.71"),
        ("9120", "2910"): D("8000.00"),
    }
    receipt = await _receipt(env, pos, sale_id)
    assert (receipt["kind"], receipt["status"], receipt["payment_form"]) == ("sale", "pending", "cash")
    cash = await rows(
        env.db, pos.tenant_id, "SELECT method, amount FROM app.cash_moves WHERE doc_id = :d", d=sale_id
    )
    assert cash == [{"method": "cash", "amount": D("12000.00")}]


async def test_qt_m01_02_no_open_shift(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.shifts SET status = 'closed', closed_at = now() - interval '1 day', expected_cash = 0, counted_cash = 0 WHERE id = :s",
        s=pos.shift_id,
    )  # fmt: skip
    payload = sale_payload(pos, [sale_line(product)])
    res = await deliver(env, pos, "sale.created", payload)
    assert res.code == "SHIFT_NOT_OPEN"
    assert (
        await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.sales WHERE id = :d", d=payload["id"]) == 0
    )


async def test_qt_seq_02_other_device(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    res = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product)]), device_id=pos.other_device_id
    )
    assert res.code == "SHIFT_DEVICE_MISMATCH"


async def test_qt_m01_03_offline_sale_offline_since(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(pos, [sale_line(product)], is_offline=True)
    await sell(env, pos, payload)
    receipt = await _receipt(env, pos, payload["id"])
    assert receipt["offline_since"] is not None and receipt["status"] == "pending"
    from tests.support.sales import fiscalize

    assert await fiscalize(env, pos) == 1
    after = await rows(env.db, pos.tenant_id, "SELECT status, sent_at, ofd_acked_at FROM app.fiscal_receipts WHERE sale_id = :d",
                       d=payload["id"])  # fmt: skip
    assert (
        after[0]["status"] == "fiscalized"
        and after[0]["sent_at"] is not None
        and after[0]["ofd_acked_at"] is not None
    )


async def test_qt_m01_08_uzqr_static_posting(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(
        pos, [sale_line(product)],
        [{"method": "uzqr", "amount": "12000.00", "qr_type": "static", "terminal_ref": "P-7781"}],
    )  # fmt: skip
    await sell(env, pos, payload)
    cash = await rows(
        env.db, pos.tenant_id, "SELECT method, amount FROM app.cash_moves WHERE doc_id = :d", d=payload["id"]
    )
    assert cash == [{"method": "uzqr", "amount": D("12000.00")}]
    entries = await ledger_rows(env, pos, payload["id"])
    revenue = [e for e in entries if e[1] in ("9020", "6410")]
    assert {(e[0], e[1]) for e in revenue} == {("5710", "9020"), ("5710", "6410")}
    assert all(e[3]["payment_method"] == "uzqr" for e in revenue)
    assert (await _receipt(env, pos, payload["id"]))["payment_form"] == "qr"


async def test_qt_m01_16_static_uzqr_checkout_free_online_only(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(
        pos, [sale_line(product)], [{"method": "uzqr", "amount": "12000.00", "qr_type": "static"}]
    )
    await sell(env, pos, payload)
    pay = await rows(env.db, pos.tenant_id, "SELECT qr_type, provider_tx_id, checkout_ref FROM app.sale_payments WHERE sale_id = :d",
                     d=payload["id"])  # fmt: skip
    assert pay == [{"qr_type": "static", "provider_tx_id": None, "checkout_ref": None}]
    offline = sale_payload(
        pos,
        [sale_line(product)],
        [{"method": "uzqr", "amount": "12000.00", "qr_type": "static"}],
        is_offline=True,
    )
    res = await deliver(env, pos, "sale.created", offline)
    assert res.code == "VALIDATION_ERROR" and res.keys == ["validation.uzqr_online_only"]


async def test_qt_m01_17_uzqr_and_provider_fields(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    cases = [
        ({"method": "uzqr", "amount": "12000.00"}, "payments[0].qr_type"),
        ({"method": "uzqr", "amount": "12000.00", "qr_type": "dynamic", "checkout_ref": str(uuid7())},
         "payments[0].provider_tx_id"),
        ({"method": "click", "amount": "12000.00", "checkout_ref": str(uuid7())}, "payments[0].provider_tx_id"),
        ({"method": "payme", "amount": "12000.00", "provider_tx_id": "x1"}, "payments[0].checkout_ref"),
    ]  # fmt: skip
    for pay, field in cases:
        res = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
        assert res.code == "VALIDATION_ERROR" and res.fields == [field], (pay, res.fields)


async def test_qt_m01_13_dynamic_uzqr_needs_confirmed_checkout(env: Env) -> None:
    """Dynamic UzQR checkouts are Bosqich 5 (D4); the posting side already consumes a confirmed checkout once."""
    pos = await make_pos(env)
    product = await new_item(env, pos)
    ref = uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.payment_checkouts (checkout_ref, tenant_id, branch_id, cash_register_id, provider, qr_type, "
        "amount, provider_tx_id, status, confirmed_at, expires_at, created_by) VALUES (:r, :t, :b, :c, 'uzqr', "
        "'dynamic', 12000, :x, 'pending', NULL, now() + interval '1 day', :u)",
        x=f"tx-{ref.hex}", r=ref, t=pos.tenant_id, b=pos.branch_id, c=pos.register_id, u=pos.shop.user_ids["cashier"],
    )  # fmt: skip
    pay = {
        "method": "uzqr",
        "amount": "12000.00",
        "qr_type": "dynamic",
        "checkout_ref": str(ref),
        "provider_tx_id": f"tx-{ref.hex}",
    }
    pending = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert pending.code == "PAYMENT_NOT_CONFIRMED"
    await execute(
        env.db, pos.tenant_id, "UPDATE app.payment_checkouts SET status = 'confirmed', confirmed_at = now()"
    )
    await sell(env, pos, sale_payload(pos, [sale_line(product)], [pay]))
    assert await one(env.db, pos.tenant_id, "SELECT status FROM app.payment_checkouts") == "consumed"
    again = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert again.code == "PAYMENT_NOT_CONFIRMED"  # a checkout backs one sale only (no double counting)


async def test_qt_m01_10_mixed_cash_card_debt(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="100000.00", stock="2.000", cost="60000.00")
    customer = await add_customer(env, pos)
    payload = sale_payload(
        pos, [sale_line(product, price="100000.0000")],
        [
            {"method": "cash", "amount": "40000.00"},
            {"method": "card", "amount": "30000.00", "card_entry_mode": "manual", "manual_reason": "standalone_terminal"},
            {"method": "debt", "amount": "30000.00", "due_date": "2026-11-30"},
        ],
        counterparty_id=str(customer),
    )  # fmt: skip
    await sell(env, pos, payload)
    sale_id = payload["id"]
    pays = await rows(env.db, pos.tenant_id, "SELECT method, amount FROM app.sale_payments WHERE sale_id = :d ORDER BY method",
                      d=sale_id)  # fmt: skip
    assert sorted((p["method"], p["amount"]) for p in pays) == [
        ("card", D("30000.00")), ("cash", D("40000.00")), ("debt", D("30000.00"))
    ]  # fmt: skip
    totals = sums(await ledger_rows(env, pos, sale_id))
    assert totals[("5010", "9020")] == D("35714.28") and totals[("5010", "6410")] == D("4285.72")
    assert totals[("5710", "9020")] == D("26785.71") and totals[("5710", "6410")] == D("3214.29")
    assert totals[("4010", "9020")] == D("26785.72") and totals[("4010", "6410")] == D("3214.28")
    entries = await ledger_rows(env, pos, sale_id)
    assert sum(e[2] for e in entries if e[1] == "9020") == D("89285.71")
    assert sum(e[2] for e in entries if e[1] == "6410") == D("10714.29")
    assert all(e[3]["payment_method"] == "card" for e in entries if e[0] == "5710")
    debt = await rows(
        env.db, pos.tenant_id, "SELECT amount, due_date FROM app.debt_moves WHERE doc_id = :d", d=sale_id
    )
    assert debt[0]["amount"] == D("30000.00") and debt[0]["due_date"].isoformat() == "2026-11-30"
    receipt = await _receipt(env, pos, sale_id)
    assert receipt["payload"]["total"] == "70000.00" and receipt["payment_form"] == "mixed"
    assert await one(
        env.db, pos.tenant_id, "SELECT settled_amount FROM app.sale_lines WHERE sale_id = :d", d=sale_id
    ) == D("70000.00")


async def test_qt_m01_debt_only_sale_deferred(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    customer = await add_customer(env, pos)
    payload = sale_payload(pos, [sale_line(product)], [{"method": "debt", "amount": "12000.00"}],
                           counterparty_id=str(customer))  # fmt: skip
    res = await sell(env, pos, payload)
    assert res.server["fiscal"]["status"] == "deferred" and res.server["fiscal_receipt_seq"] is None
    assert (
        await one(
            env.db,
            pos.tenant_id,
            "SELECT count(*) FROM app.fiscal_receipts WHERE sale_id = :d",
            d=payload["id"],
        )
        == 0
    )
    assert sums(await ledger_rows(env, pos, payload["id"]))[("4010", "9020")] == D("10714.29")


# --- M01: card rows ------------------------------------------------------------------------------------
async def test_qt_m01_14_manual_card_without_details(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(
        pos, [sale_line(product)],
        [{"method": "card", "amount": "12000.00", "card_entry_mode": "manual", "manual_reason": "standalone_terminal"}],
    )  # fmt: skip
    await sell(env, pos, payload)
    pay = (
        await rows(
            env.db, pos.tenant_id,
            "SELECT card_entry_mode, manual_reason, card_type, card_type_source, card_mask, rrn, approval_code, "
            "card_scheme, card_terminal_transaction_id, terminal_ref FROM app.sale_payments WHERE sale_id = :d",
            d=payload["id"],
        )
    )[0]  # fmt: skip
    assert pay.pop("card_entry_mode") == "manual" and pay.pop("manual_reason") == "standalone_terminal"
    assert set(pay.values()) == {None}
    receipt = await _receipt(env, pos, payload["id"])
    assert receipt["payment_form"] == "card"
    assert receipt["payload"]["payments"] == [
        {"method": "card", "amount": "12000.00", "card_entry_mode": "manual"}
    ]
    entries = await ledger_rows(env, pos, payload["id"])
    assert any(e[0] == "5710" and e[3]["payment_method"] == "card" and "rrn" not in e[3] for e in entries)


async def test_qt_m01_15_manual_card_with_details_rejected(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    base = {
        "method": "card",
        "amount": "12000.00",
        "card_entry_mode": "manual",
        "manual_reason": "standalone_terminal",
    }
    for field, value in (("card_mask", "8600****1234"), ("rrn", "612345678901"), ("card_type", "social"),
                         ("approval_code", "A1B2C3"), ("card_scheme", "uzcard"), ("terminal_ref", "T-9"),
                         ("card_terminal_transaction_id", str(uuid7()))):  # fmt: skip
        res = await deliver(
            env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [{**base, field: value}])
        )
        assert res.code == "VALIDATION_ERROR" and res.fields == [f"payments[0].{field}"], field
        assert res.keys == ["validation.card_manual_details_forbidden"]
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.sales") == 0


async def test_qt_m01_32_payment_row_checks(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    cases = [
        ({"method": "card", "amount": "12000.00"}, "validation.card_entry_mode_required"),
        ({"method": "card", "amount": "12000.00", "card_entry_mode": "integrated"}, "validation.card_result_required"),
        ({"method": "card", "amount": "12000.00", "card_entry_mode": "manual"}, "validation.card_manual_reason_required"),
        ({"method": "cash", "amount": "12000.00", "approval_code": "A1"}, "validation.card_fields_forbidden"),
        ({"method": "cash", "amount": "12000.00", "card_scheme": "humo"}, "validation.card_fields_forbidden"),
    ]  # fmt: skip
    for pay, key in cases:
        res = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
        assert res.code == "VALIDATION_ERROR" and res.keys == [key], pay


async def test_qt_m01_33_card_type_source_never_from_device(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    pay = {"method": "card", "amount": "12000.00", "card_entry_mode": "manual", "manual_reason": "standalone_terminal",
           "card_type_source": "cashier"}  # fmt: skip
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert res.code == "VALIDATION_ERROR" and res.fields == ["payments[0].card_type_source"]


async def test_qt_m01_24_integrated_card_server_side(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    terminal = await bind_terminal(env, pos)
    result = await card_result(pos, terminal, "12000.00")
    payload = sale_payload(
        pos, [sale_line(product)],
        [{"method": "card", "amount": "12000.00", "card_entry_mode": "integrated", "card_result": result}],
    )  # fmt: skip
    res = await sell(env, pos, payload)
    assert "CARD_TRANSACTION_MISMATCH" not in res.server["warnings"]
    pay = (
        await rows(
            env.db, pos.tenant_id, "SELECT * FROM app.sale_payments WHERE sale_id = :d", d=payload["id"]
        )
    )[0]
    assert str(pay["card_terminal_transaction_id"]) == result["attempt_id"]
    assert (
        pay["rrn"] == result["rrn"]
        and pay["card_mask"] == result["card_mask"]
        and pay["card_type"] is not None
    )
    receipt = await _receipt(env, pos, payload["id"])
    assert receipt["payment_form"] == "card"
    assert receipt["payload"]["payments"][0]["rrn"] == result["rrn"]
    assert receipt["payload"]["payments"][0]["card_mask"] == result["card_mask"]
    linked = await one(env.db, pos.tenant_id, "SELECT doc_id FROM app.card_terminal_transactions WHERE id = :i",
                       i=result["attempt_id"])  # fmt: skip
    assert str(linked) == payload["id"]


async def test_qt_m01_31_manual_card_policy_on_terminal_register(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await bind_terminal(env, pos)
    pay = {
        "method": "card",
        "amount": "12000.00",
        "card_entry_mode": "manual",
        "manual_reason": "terminal_offline",
    }
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]))
    assert res.code == "CARD_MANUAL_APPROVAL_REQUIRED"
    approved = {**pay, "card_manual_approval": _local_pin(pos.shop.user_ids["manager"])}
    await sell(env, pos, sale_payload(pos, [sale_line(product)], [approved]))
    offline = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay], is_offline=True)
    )
    assert offline.error is None and "approval_limit_exceeded_offline" in offline.exception_kinds


# --- B3-DoD-03: accepted-with-flag rules (16 §5) ---------------------------------------------------------
async def test_qt_m01_overselling_stock_negative_warning(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, stock="1.000")
    res = await sell(env, pos, sale_payload(pos, [sale_line(product, qty="3.000")], is_offline=True))
    assert res.server["warnings"] == ["STOCK_NEGATIVE"] and res.result is not None
    assert "STOCK_NEGATIVE" in res.result.warnings and "stock_negative" in res.exception_kinds
    qty = await one(
        env.db, pos.tenant_id, "SELECT qty FROM app.stock_balances WHERE product_id = :p", p=product
    )
    assert qty == D("-2.000")


async def test_qt_m09_09_price_frozen_price_mismatch(env: Env) -> None:
    """CORR-06: the server re-checks the price in force at posting; the receipt price stays frozen."""
    pos = await make_pos(env)
    product = await new_item(env, pos, price="12000.00")
    payload = sale_payload(pos, [sale_line(product, price="11000.0000")], is_offline=True)
    res = await sell(env, pos, payload)
    assert "price_mismatch" in res.exception_kinds
    exc = next(e for e in res.result.sync_exceptions if e.kind == "price_mismatch")  # type: ignore[union-attr]
    assert exc.details["device_price"] == "11000.0000" and exc.details["server_price"] == "12000.0000"
    assert await one(
        env.db, pos.tenant_id, "SELECT price FROM app.sale_lines WHERE sale_id = :d", d=payload["id"]
    ) == D("11000.0000")
    clean = await sell(env, pos, sale_payload(pos, [sale_line(product)]))
    assert "price_mismatch" not in clean.exception_kinds


async def test_qt_m01_archived_product_flag(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await execute(
        env.db, pos.tenant_id, "UPDATE app.products SET archived_at = now() WHERE id = :p", p=product
    )
    res = await sell(env, pos, sale_payload(pos, [sale_line(product)], is_offline=True))
    assert "archived_product" in res.exception_kinds


async def test_qt_m01_debt_limit_online_and_offline(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    customer = await add_customer(env, pos, credit_limit="10000.00")
    debt = [{"method": "debt", "amount": "12000.00"}]
    online = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product)], debt, counterparty_id=str(customer))
    )
    assert online.code == "DEBT_LIMIT_EXCEEDED"
    offline = await sell(env, pos, sale_payload(pos, [sale_line(product)], debt, counterparty_id=str(customer),
                                                is_offline=True))  # fmt: skip
    assert offline.server["warnings"] == ["DEBT_LIMIT_EXCEEDED"]
    assert "debt_limit_exceeded_offline" in offline.exception_kinds
    assert await one(env.db, pos.tenant_id, "SELECT debt_limit_exceeded FROM app.sales") is True


# --- M01-03 marking (server side) ----------------------------------------------------------------------
CODE = "0104600000000001215abcdefgh\x1d93AbCd"


async def test_qt_m01_19_marking_duplicate_and_sold(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(
        env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages"
    )
    twice = await deliver(env, pos, "sale.created", sale_payload(
        pos, [sale_line(product, marking_code=CODE), sale_line(product, marking_code=CODE)]
    ))  # fmt: skip
    assert twice.code == "VALIDATION_ERROR" and twice.keys == ["validation.marking_code_duplicate"]
    first = sale_payload(pos, [sale_line(product, marking_code=CODE)])
    await sell(env, pos, first)
    assert await one(
        env.db, pos.tenant_id, "SELECT status FROM app.marking_codes WHERE code = :c", c=CODE
    ) == ("pending_verification")
    again = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product, marking_code=CODE)])
    )
    assert again.code == "MARKING_CODE_ALREADY_SOLD"
    receipt = await _receipt(env, pos, first["id"])
    assert receipt["payload"]["items"][0]["marking_codes"] == [CODE]  # GS kept exactly (qaror #62)
    from tests.support.sales import fiscalize

    await fiscalize(env, pos)
    assert (
        await one(env.db, pos.tenant_id, "SELECT status FROM app.marking_codes WHERE code = :c", c=CODE)
        == "sold"
    )


async def test_qt_m01_marking_line_rules(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(
        env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages"
    )
    missing = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)]))
    assert missing.keys == ["validation.marking_code_required"]
    bad = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product, marking_code="short")])
    )
    assert bad.code == "MARKING_CODE_INVALID"
    two = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product, qty="2.000", marking_code=CODE)])
    )
    assert two.keys == ["validation.marking_qty_single"]


async def test_qt_m01_05_marked_offline_price_unknown(env: Env) -> None:
    pos = await make_pos(env)
    created = await create_product(
        env.client, pos.shop, "Yangi suv", is_marked=True, marking_group_code="water_beverages"
    )
    product = UUID(created["id"])
    res = await deliver(env, pos, "sale.created",
                        sale_payload(pos, [sale_line(product, marking_code=CODE)], is_offline=True))  # fmt: skip
    assert res.code == "MARKING_PRICE_UNKNOWN_OFFLINE"


# --- line math, receipt numbering ----------------------------------------------------------------------
async def test_qt_m01_line_math_rechecked(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    line = sale_line(product)
    line["vat_amount"] = "1285.70"
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [line]))
    assert res.keys == ["validation.vat_amount_mismatch"]
    line = sale_line(product)
    line["line_total"] = "12001.00"
    res = await deliver(
        env, pos, "sale.created", sale_payload(pos, [line], [{"method": "cash", "amount": "12001.00"}])
    )
    assert res.keys == ["validation.line_total_mismatch"]
    short = await deliver(
        env,
        pos,
        "sale.created",
        sale_payload(pos, [sale_line(product)], [{"method": "cash", "amount": "11000.00"}]),
    )
    assert short.keys == ["validation.payments_total_mismatch"]


async def test_qt_seq_01_receipt_seq_conflict(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await sell(env, pos, sale_payload(pos, [sale_line(product)], receipt_seq=5))
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], receipt_seq=5))
    assert res.code == "RECEIPT_SEQ_CONFLICT" and res.error is not None
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.sales") == 1


async def test_qt_m01_23_local_bridge_result_renumbered(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await sell(env, pos, sale_payload(pos, [sale_line(product)], receipt_seq=1))
    fiscal_result = {"fm_terminal_id": "ZZ000000000001", "fm_receipt_seq": 77, "fiscal_sign": "123456789012",
                     "qr_url": "https://ofd.soliq.uz/check?t=ZZ000000000001&r=77&c=20261017120000&s=123456789012",
                     "fiscal_at": "2026-10-17T07:00:00Z"}  # fmt: skip
    payload = sale_payload(pos, [sale_line(product)], receipt_seq=1, fiscal_result=fiscal_result)
    res = await sell(env, pos, payload)
    assert res.server["fiscal"]["status"] == "fiscalized" and res.server["fiscal_receipt_seq"] == 2
    assert "receipt_seq_conflict" in res.exception_kinds
    receipt = await _receipt(env, pos, payload["id"])
    assert receipt["receipt_seq"] == 2 and receipt["payload"]["device_receipt_seq"] == 1


# --- M03 discounts / QT-PERM ---------------------------------------------------------------------------
async def test_qt_perm_02_cashier_discount_within_limit(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="10000.00")
    await sell(env, pos, sale_payload(pos, [sale_line(product, price="10000.0000", discount="500.00",
                                                     discount_pct="5.00")]))  # fmt: skip
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.doc_approvals") == 0


async def test_qt_m03_01_vat_after_discount(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="10000.00")
    payload = sale_payload(
        pos, [sale_line(product, price="10000.0000", discount="500.00", discount_pct="5.00")]
    )
    await sell(env, pos, payload)
    line = (await rows(env.db, pos.tenant_id, "SELECT line_total, vat_amount, discount_pct FROM app.sale_lines WHERE sale_id = :d",
                       d=payload["id"]))[0]  # fmt: skip
    assert line == {"line_total": D("9500.00"), "vat_amount": D("1017.86"), "discount_pct": D("5.00")}


async def test_qt_perm_03_discount_over_limit_needs_approval(env: Env) -> None:
    """Also QT-M03-02."""
    pos = await make_pos(env)
    product = await new_item(env, pos, price="10000.00")
    over = sale_line(product, price="10000.0000", discount="600.00", discount_pct="6.00")
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [over]))
    assert res.code == "DISCOUNT_LIMIT_EXCEEDED"
    approved = sale_line(product, price="10000.0000", discount="600.00", discount_pct="6.00",
                         discount_approval=_local_pin(pos.shop.user_ids["manager"]))  # fmt: skip
    payload = sale_payload(pos, [approved])
    await sell(env, pos, payload)
    approval = await rows(env.db, pos.tenant_id, "SELECT kind, doc_type, approved_by FROM app.doc_approvals WHERE doc_id = :d",
                          d=payload["id"])  # fmt: skip
    assert approval == [
        {"kind": "discount_over_limit", "doc_type": "sales", "approved_by": pos.shop.user_ids["manager"]}
    ]


async def test_qt_m03_04_one_most_favourable_rule(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="10000.00")
    customer = await add_customer(env, pos, standing="10.00")
    standing = sale_line(product, price="10000.0000", discount="1000.00", source="standing_customer")
    await sell(env, pos, sale_payload(pos, [standing], counterparty_id=str(customer)))
    stacked = sale_line(
        product, price="10000.0000", discount="1500.00", source="standing_customer"
    )  # 10 % + 5 %
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [stacked], counterparty_id=str(customer)))
    assert res.code == "VALIDATION_ERROR" and res.keys == ["validation.discount_exceeds_standing"]


async def test_qt_m03_05_negative_price_rejected(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="3000.00")
    line = {"id": str(uuid7()), "product_id": str(product), "unit_code": "box", "qty": "1.000", "price": "3000.0000",
            "vat_rate": "12.00", "discount_amount": "3600.00", "discount_source": "manual", "discount_pct": "120.00",
            "line_total": "0.00", "vat_amount": "0.00"}  # fmt: skip
    res = await deliver(
        env, pos, "sale.created", sale_payload(pos, [line], [{"method": "cash", "amount": "0.00"}])
    )
    assert res.code == "VALIDATION_ERROR"


async def test_dod_05_discount_gross_9050_example(env: Env) -> None:
    """13 §2.1a example: list 112 000, 10 % discount, paid 100 800 (owner — no approval, QT-PERM-01)."""
    pos = await make_pos(env)
    product = await new_item(env, pos, price="112000.00", stock="1.000", cost="50000.00")
    payload = sale_payload(
        pos, [sale_line(product, price="112000.0000", discount="11200.00", discount_pct="10.00")]
    )
    await sell(env, pos, payload, actor="owner")
    totals = sums(await ledger_rows(env, pos, payload["id"]))
    assert totals[("5010", "9020")] == D("100000.00")
    assert totals[("9050", "5010")] == D("10000.00")
    assert totals[("5010", "6410")] == D("10800.00")
    vat = await rows(env.db, pos.tenant_id, "SELECT kind, base_amount, vat_amount FROM app.vat_moves WHERE doc_id = :d",
                     d=payload["id"])  # fmt: skip
    assert vat == [{"kind": "output", "base_amount": D("90000.00"), "vat_amount": D("10800.00")}]


# --- M10 -----------------------------------------------------------------------------------------------
async def test_qt_m10_01_vat_to_ledger_and_register(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    zero = await new_item(env, pos, "Non", price="5000.00", vat_rate="0.00")
    payload = sale_payload(pos, [sale_line(product), sale_line(zero, price="5000.0000", vat_rate="0.00")])
    await sell(env, pos, payload)
    totals = sums(await ledger_rows(env, pos, payload["id"]))
    assert totals[("5010", "6410")] == D("1285.71") and totals[("5010", "9020")] == D("15714.29")
    vat = await rows(env.db, pos.tenant_id, "SELECT base_amount, vat_amount FROM app.vat_moves WHERE doc_id = :d ORDER BY vat_amount",
                     d=payload["id"])  # fmt: skip
    assert vat == [{"base_amount": D("5000.00"), "vat_amount": D("0.00")},
                   {"base_amount": D("10714.29"), "vat_amount": D("1285.71")}]  # fmt: skip


async def test_qt_m01_late_sale_into_closed_period(env: Env) -> None:
    from tests.support.inventory import close_period

    pos = await make_pos(env)
    product = await new_item(env, pos)
    when = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    await close_period(env, pos.shop, when.date())
    payload = sale_payload(pos, [sale_line(product)], is_offline=True)
    res = await sell(env, pos, payload, created_at=when)
    assert "late_in_closed_period" in res.exception_kinds
    dates = {r["entry_date"] for r in await rows(env.db, pos.tenant_id, "SELECT entry_date FROM app.ledger_entries WHERE doc_id = :d",
                                                  d=payload["id"])}  # fmt: skip
    assert dates == {when.date().replace(month=10, day=1)}
    assert (
        await one(env.db, pos.tenant_id, "SELECT doc_date FROM app.sales WHERE id = :d", d=payload["id"])
        == when.date()
    )


async def test_qt_m01_11_draft_voided_audit_only(env: Env) -> None:
    pos = await make_pos(env)
    res = await deliver(
        env, pos, "sale.draft_voided", {"draft_ref": "local-42", "voided_lines": None, "reason": "mijoz"}
    )
    assert res.server == {"status": "accepted"}
    audit = await rows(
        env.db, pos.tenant_id, "SELECT action, after FROM app.audit_log WHERE action = 'sale.draft_voided'"
    )
    assert len(audit) == 1 and audit[0]["after"]["whole_receipt"] is True
    assert audit[0]["after"]["shift_id"] == str(pos.shift_id)
    for table in ("sales", "stock_moves", "ledger_entries", "fiscal_receipts"):
        assert await one(env.db, pos.tenant_id, f"SELECT count(*) FROM app.{table}") == 0, table


async def test_qt_m01_12_receipt_reprinted_unlimited(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(pos, [sale_line(product)])
    await sell(env, pos, payload)
    receipt_id = await one(
        env.db, pos.tenant_id, "SELECT id FROM app.fiscal_receipts WHERE sale_id = :d", d=payload["id"]
    )
    for _ in range(3):
        res = await deliver(
            env, pos, "receipt.reprinted", {"fiscal_receipt_id": str(receipt_id), "sale_id": payload["id"]}
        )
        assert res.server == {"status": "accepted", "copy_label": "NUSXA"}
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'receipt.reprinted'"
        )
        == 3
    )
    missing = await deliver(env, pos, "receipt.reprinted", {"fiscal_receipt_id": str(uuid7())})
    assert missing.code == "DEPENDENCY_NOT_SYNCED"


async def test_sync_14_signed_receipt_with_duplicate_code_accepted(env: Env) -> None:
    """F-5: without fiscal_result a duplicate code is rejected (QT-M01-19); a receipt the FM already signed is
    accepted with a warning and a ``marking.verify_failed`` audit (16 §7, 18 §4.2)."""
    pos = await make_pos(env)
    product = await new_item(
        env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages"
    )
    await sell(env, pos, sale_payload(pos, [sale_line(product, marking_code=CODE)]))
    fiscal_result = {"fm_terminal_id": "ZZ000000000002", "fm_receipt_seq": 9, "fiscal_sign": "123456789012",
                     "qr_url": "https://ofd.soliq.uz/check?t=ZZ000000000002&r=9&c=20261017120000&s=123456789012",
                     "fiscal_at": "2026-10-17T07:00:00Z"}  # fmt: skip
    payload = sale_payload(
        pos, [sale_line(product, marking_code=CODE)], fiscal_result=fiscal_result, is_offline=True
    )
    res = await sell(env, pos, payload)
    assert "MARKING_CODE_ALREADY_SOLD" in res.server["warnings"]
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'marking.verify_failed'"
        )
        == 1
    )
    first_owner = await one(
        env.db, pos.tenant_id, "SELECT last_doc_id FROM app.marking_codes WHERE code = :c", c=CODE
    )
    assert str(first_owner) != payload["id"]  # the first sale keeps the code


async def test_acc_01_late_sale_into_closed_shift(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.shifts SET status = 'closed', closed_at = now() - interval '1 hour', expected_cash = 0, "
        "counted_cash = 0 WHERE id = :s",
        s=pos.shift_id,
    )  # fmt: skip
    created = datetime.now(UTC) - timedelta(hours=2)
    res = await sell(env, pos, sale_payload(pos, [sale_line(product)], is_offline=True), created_at=created)
    assert "late_in_closed_shift" in res.exception_kinds
    assert await one(
        env.db, pos.tenant_id, "SELECT expected_cash FROM app.shifts WHERE id = :s", s=pos.shift_id
    ) == D("12000.00")


async def test_sec_02_unbound_online_approver_flagged(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, price="10000.00")

    async def not_bound(_: object) -> bool:
        return False

    line = sale_line(product, price="10000.0000", discount="600.00", discount_pct="6.00",
                     discount_approval=_local_pin(pos.shop.user_ids["manager"]))  # fmt: skip
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [line]), actor_bound=not_bound)
    assert res.error is None, (res.code, res.keys)
    assert "actor_unverified" in res.exception_kinds


async def test_sec_02_unbound_manual_card_approver_flagged(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await bind_terminal(env, pos)

    async def not_bound(_: object) -> bool:
        return False

    pay = {"method": "card", "amount": "12000.00", "card_entry_mode": "manual", "manual_reason": "terminal_offline",
           "card_manual_approval": _local_pin(pos.shop.user_ids["manager"])}  # fmt: skip
    res = await deliver(
        env, pos, "sale.created", sale_payload(pos, [sale_line(product)], [pay]), actor_bound=not_bound
    )
    assert res.error is None, (res.code, res.keys)
    assert "actor_unverified" in res.exception_kinds


async def test_sync_04_card_attempt_of_another_sale_flagged(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    terminal = await bind_terminal(env, pos)
    result = await card_result(pos, terminal, "12000.00")
    pay = {"method": "card", "amount": "12000.00", "card_entry_mode": "integrated", "card_result": result}
    await sell(env, pos, sale_payload(pos, [sale_line(product)], [pay]))
    again = await sell(env, pos, sale_payload(pos, [sale_line(product)], [pay]))
    assert "CARD_TRANSACTION_MISMATCH" in again.server["warnings"]
    exc = next(e for e in again.result.sync_exceptions if e.kind == "card_result_mismatch")  # type: ignore[union-attr]
    assert exc.details["reason"] == "linked_to_other_document"
