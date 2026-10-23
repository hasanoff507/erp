"""Supplier payments (19 §11; 13 §2.16, §2.8, §5.2; qaror #47; US-M07-04, US-M08-11; QT-M07-05, QT-M08-14 —
payments half) — real app + PostgreSQL/Redis; every posting asserted to the tiyin."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from tests.support.inventory import execute, scalar, set_method, set_setting, use_account
from tests.support.purchasing import (
    API,
    Env,
    Shop,
    create_product,
    create_receipt,
    create_supplier,
    err,
    gr_line,
    post_gr,
    posted_receipt,
    purchasing_env_fixture,
)
from tests.support.sales import make_pos
from tests.support.supplier_tax import (
    SP,
    D,
    account_balance,
    cash_of,
    debt_of,
    ledger_of,
    link_einvoice,
    pay,
    payable,
    vat_of,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["purchasing_env_fixture"]


async def _setup(env: Env, name: str, *roles: SystemRole) -> tuple[Shop, str, UUID]:
    shop = await env.shop(name, *(roles or (SystemRole.OWNER, SystemRole.ACCOUNTANT, SystemRole.CASHIER)))
    supplier = await create_supplier(env.client, shop)
    wh = await use_account(env, shop, "2910")
    await set_method(env, shop, "fifo")
    return shop, supplier["id"], wh


async def _receipt(
    env: Env, shop: Shop, supplier: str, wh: UUID, cost: str, vat: str = "12.00"
) -> dict[str, Any]:
    product = await create_product(env.client, shop, f"Tovar {cost} {vat}")
    return await posted_receipt(env.client, shop, supplier, wh, [gr_line(product["id"], "1.000", cost, vat)])


# --- QT-M07-05 / US-M07-04 ---------------------------------------------------------------------------
async def test_qt_m07_05_bank_payment_closes_payable(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "QT-M07-05")
    receipt = await _receipt(env, shop, supplier, wh, "1000000.0000")
    assert receipt["total"] == "1120000.00" and await payable(env, shop, supplier) == D("1120000.00")

    key = "sp-qt-m07-05"
    response = await pay(env.client, shop, supplier, "1120000.00", role="accountant", key=key)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "posted" and body["number"] == f"SP-01-{business_today().year}-000001"
    assert body["advance_amount"] == "0.00" and body["warnings"] == [] and body["vat_credit_unlocked"] == []
    (alloc,) = body["allocations"]
    assert (alloc["target_doc_type"], alloc["target_doc_id"], alloc["amount"]) == (
        "goods_receipts", receipt["id"], "1120000.00",
    )  # fmt: skip
    assert alloc["target_number"] == receipt["number"]
    assert response.headers["Location"].endswith(body["id"])
    replay = await pay(env.client, shop, supplier, "1120000.00", role="accountant", key=key)
    assert replay.status_code == 201 and replay.json() == body

    assert await ledger_of(env, shop, body["id"]) == [("6010", "5110", D("1120000.00"))]
    assert await debt_of(env, shop, body["id"]) == [D("-1120000.00")]
    assert await payable(env, shop, supplier) == D("0.00")
    assert await cash_of(env, shop, body["id"]) == []  # bank: no till movement
    assert await vat_of(env, shop, body["id"]) == []
    audit = await scalar(
        env, shop.tenant_id,
        "SELECT count(*) FROM app.audit_log WHERE action = 'supplier_payment.created' AND entity_id = :id",
        id=UUID(body["id"]),
    )  # fmt: skip
    assert audit == 1

    got = await env.client.get(f"{SP}/{body['id']}", headers=shop.h("accountant", key=None))
    assert got.status_code == 200 and got.json() == {k: v for k, v in body.items() if k != "warnings"}


async def test_qt_m07_05_red_invoice_vat_credit_released_on_payment(env: Env) -> None:
    """13 §2.8 / §2.16: a red invoice defers only the VAT credit; each payment writes ``vat_moves(input)``
    proportional to its allocation, the closing payment takes the remainder; no 4410 line is rewritten."""
    shop, supplier, wh = await _setup(env, "QT-M07-05 red")
    product = await create_product(env.client, shop, "Qizil tovar")
    draft = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(product["id"], "3.000", "333333.3333")]
    )
    einvoice = await link_einvoice(
        env, shop, draft["id"], supplier, "red", total="1120000.00", vat="120000.00"
    )
    posted = await post_gr(env.client, shop, draft["id"])
    assert posted.status_code == 200, posted.text
    assert await vat_of(env, shop, draft["id"]) == []  # credit deferred
    total = D(posted.json()["total"])
    vat_total = D(posted.json()["vat_total"])

    docs = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    assert docs.status_code == 200, docs.text
    (doc,) = docs.json()["items"]
    assert (doc["outstanding"], doc["vat_pending"], doc["einvoice_risk_flag"]) == (
        str(total), str(vat_total), "red",
    )  # fmt: skip

    first = await pay(env.client, shop, supplier, "560000.00")
    assert first.status_code == 201, first.text
    expected_vat = (vat_total * D("560000.00") / total).quantize(D("0.01"))
    expected_base = (D(posted.json()["net_total"]) * D("560000.00") / total).quantize(D("0.01"))
    assert first.json()["vat_credit_unlocked"] == [
        {"einvoice_id": str(einvoice), "vat_amount": str(expected_vat)}
    ]
    assert first.json()["allocations"][0]["vat_credit_unlocked"] == str(expected_vat)
    assert await vat_of(env, shop, first.json()["id"]) == [("input", expected_base, expected_vat)]
    assert await ledger_of(env, shop, first.json()["id"]) == [("6010", "5110", D("560000.00"))]

    rest = total - D("560000.00")
    second = await pay(env.client, shop, supplier, str(rest))
    assert second.status_code == 201, second.text
    assert await vat_of(env, shop, second.json()["id"]) == [
        ("input", D(posted.json()["net_total"]) - expected_base, vat_total - expected_vat)
    ]
    released = await scalar(
        env, shop.tenant_id, "SELECT sum(vat_amount) FROM app.vat_moves WHERE einvoice_id = :e", e=einvoice
    )
    assert released == vat_total
    # the deferred 4410 line of the receipt stays the only 4410 debit (never rewritten)
    assert await account_balance(env, shop, "4410") == vat_total
    assert await payable(env, shop, supplier) == D("0.00")

    # cancelling the closing payment reverses its VAT credit too
    cancelled = await env.client.post(
        f"{SP}/{second.json()['id']}/cancel", json={"reason": "xato"}, headers=shop.h()
    )
    assert cancelled.status_code == 200, cancelled.text
    released = await scalar(
        env, shop.tenant_id, "SELECT sum(vat_amount) FROM app.vat_moves WHERE einvoice_id = :e", e=einvoice
    )
    assert released == expected_vat


# --- 13 §2.16 example / qaror #47 (B4-T08 supplier part) ----------------------------------------------
async def test_13_2_16_overpay_becomes_advance_and_offsets_next_receipt(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "13 §2.16")
    await _receipt(env, shop, supplier, wh, "800000.0000", "0.00")
    response = await pay(env.client, shop, supplier, "1000000.00")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["advance_amount"] == "200000.00"
    assert body["warnings"] == [
        {
            "code": "SUPPLIER_OVERPAY_ADVANCE",
            "params": {"debt": "800000.00", "amount": "1000000.00", "advance": "200000.00"},
        }
    ]
    assert await ledger_of(env, shop, body["id"]) == [
        ("6010", "5110", D("800000.00")),
        ("4310", "5110", D("200000.00")),
    ]
    assert await debt_of(env, shop, body["id"]) == [D("-1000000.00")]
    assert await payable(env, shop, supplier) == D("-200000.00")

    nxt = await _receipt(env, shop, supplier, wh, "500000.0000", "0.00")
    assert [(r[0], r[1], r[2]) for r in await ledger_of(env, shop, nxt["id"])] == [
        ("2910", "6010", D("500000.00")),
        ("6010", "4310", D("200000.00")),
    ]
    assert await payable(env, shop, supplier) == D("300000.00")
    assert await account_balance(env, shop, "4310", counterparty_id=supplier) == D("0.00")
    docs = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    (doc,) = docs.json()["items"]
    assert (doc["target_doc_id"], doc["outstanding"]) == (nxt["id"], "300000.00")


async def test_qaror_47_overpay_blocked_by_policy(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "qaror 47 block")
    await set_setting(env, shop, "supplier_overpay_policy", "block")
    await _receipt(env, shop, supplier, wh, "100000.0000", "0.00")
    response = await pay(env.client, shop, supplier, "100000.01")
    assert response.status_code == 422 and err(response) == "SUPPLIER_OVERPAY_BLOCKED"
    assert response.json()["error"]["params"] == {"debt": "100000.00", "amount": "100000.01"}
    count = await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.supplier_payments")
    assert count == 0 and await payable(env, shop, supplier) == D("100000.00")
    ok = await pay(env.client, shop, supplier, "100000.00")
    assert ok.status_code == 201 and ok.json()["warnings"] == []


# --- allocation (oldest first / explicit) ---------------------------------------------------------------
async def test_qt_m08_11_payment_allocated_oldest_first(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "US-M08-11 alloc")
    older = await _receipt(env, shop, supplier, wh, "300000.0000", "0.00")
    newer = await _receipt(env, shop, supplier, wh, "200000.0000", "0.00")
    response = await pay(env.client, shop, supplier, "400000.00")
    assert response.status_code == 201, response.text
    assert [(a["target_doc_id"], a["amount"]) for a in response.json()["allocations"]] == [
        (older["id"], "300000.00"),
        (newer["id"], "100000.00"),
    ]
    docs = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    assert [(d["target_doc_id"], d["outstanding"]) for d in docs.json()["items"]] == [
        (newer["id"], "100000.00")
    ]
    assert docs.json()["payable_balance"] == "100000.00"


async def test_explicit_allocations_validated(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "alloc explicit")
    older = await _receipt(env, shop, supplier, wh, "300000.0000", "0.00")
    newer = await _receipt(env, shop, supplier, wh, "200000.0000", "0.00")

    def alloc(doc: dict[str, Any], amount: str) -> dict[str, str]:
        return {"target_doc_type": "goods_receipts", "target_doc_id": doc["id"], "amount": amount}

    too_much = await pay(env.client, shop, supplier, "250000.00", allocations=[alloc(newer, "250000.00")])
    assert too_much.status_code == 422, too_much.text
    assert (
        too_much.json()["error"]["details"][0]["message_key"] == "validation.allocation_exceeds_outstanding"
    )
    mismatch = await pay(env.client, shop, supplier, "250000.00", allocations=[alloc(newer, "200000.00")])
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["details"][0]["message_key"] == "validation.allocation_sum_mismatch"
    foreign = await pay(
        env.client, shop, supplier, "1000.00",
        allocations=[{"target_doc_type": "goods_receipts", "target_doc_id": str(shop.branch_id), "amount": "1000.00"}],
    )  # fmt: skip
    assert foreign.status_code == 422
    assert foreign.json()["error"]["details"][0]["message_key"] == "validation.allocation_target_invalid"

    ok = await pay(
        env.client,
        shop,
        supplier,
        "250000.00",
        allocations=[alloc(newer, "200000.00"), alloc(older, "50000.00")],
    )
    assert ok.status_code == 201, ok.text
    assert sorted((a["target_doc_id"], a["amount"]) for a in ok.json()["allocations"]) == sorted(
        [(older["id"], "50000.00"), (newer["id"], "200000.00")]
    )
    assert await payable(env, shop, supplier) == D("250000.00")


# --- cash from the till (B2 → B4) ------------------------------------------------------------------------
async def test_cash_payment_from_till_writes_cash_moves(env: Env) -> None:
    pos = await make_pos(env, "Naqd to'lov")
    shop = pos.shop
    supplier = (await create_supplier(env.client, shop))["id"]
    await set_method(env, shop, "fifo")
    await _receipt(env, shop, supplier, pos.warehouse_id, "150000.0000", "0.00")

    wrong = await pay(
        env.client, shop, supplier, "150000.00", method="cash", cash_register_id=str(shop.branch_id),
        shift_id=str(pos.shift_id),
    )  # fmt: skip
    assert wrong.status_code == 422, wrong.text
    no_shift = await pay(env.client, shop, supplier, "150000.00", method="cash")
    assert no_shift.status_code == 422

    response = await pay(
        env.client, shop, supplier, "150000.00", method="cash", cash_register_id=str(pos.register_id),
        shift_id=str(pos.shift_id), role="accountant",
    )  # fmt: skip
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["method"], body["shift_id"], body["cash_register_id"]) == (
        "cash", str(pos.shift_id), str(pos.register_id),
    )  # fmt: skip
    assert await ledger_of(env, shop, body["id"]) == [("6010", "5010", D("150000.00"))]
    assert await cash_of(env, shop, body["id"]) == [(D("-150000.00"), "cash", pos.shift_id)]
    assert await payable(env, shop, supplier) == D("0.00")

    # close the shift → the cash cannot go back into it: cancel refused
    await execute(
        env, shop.tenant_id, "UPDATE app.shifts SET status = 'closed', closed_at = now(), counted_cash = 0, expected_cash = 0 "
        "WHERE id = :id",
        id=pos.shift_id,
    )  # fmt: skip
    refused = await env.client.post(f"{SP}/{body['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"
    closed = await pay(
        env.client, shop, supplier, "1000.00", method="cash", cash_register_id=str(pos.register_id),
        shift_id=str(pos.shift_id),
    )  # fmt: skip
    assert closed.status_code == 409 and err(closed) == "SHIFT_NOT_OPEN"


async def test_cash_payment_cancel_in_open_shift_storno(env: Env) -> None:
    pos = await make_pos(env, "Naqd bekor")
    shop = pos.shop
    supplier = (await create_supplier(env.client, shop))["id"]
    await set_method(env, shop, "fifo")
    await _receipt(env, shop, supplier, pos.warehouse_id, "90000.0000", "0.00")
    body = (
        await pay(
            env.client, shop, supplier, "100000.00", method="cash", cash_register_id=str(pos.register_id),
            shift_id=str(pos.shift_id),
        )
    ).json()  # fmt: skip
    assert body["advance_amount"] == "10000.00"
    cancelled = await env.client.post(f"{SP}/{body['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled" and cancelled.json()["cancel_reason"] == "xato"
    assert await ledger_of(env, shop, body["id"]) == [
        ("6010", "5010", D("90000.00")),
        ("4310", "5010", D("10000.00")),
        ("5010", "6010", D("90000.00")),
        ("5010", "4310", D("10000.00")),
    ]
    assert await cash_of(env, shop, body["id"]) == [
        (D("-100000.00"), "cash", pos.shift_id),
        (D("100000.00"), "cash", pos.shift_id),
    ]
    assert await debt_of(env, shop, body["id"]) == [D("-100000.00"), D("100000.00")]
    assert await payable(env, shop, supplier) == D("90000.00")
    again = await env.client.post(f"{SP}/{body['id']}/cancel", json={"reason": "yana"}, headers=shop.h())
    assert again.status_code == 409 and err(again) == "DOC_ALREADY_CANCELLED"
    # the cancelled payment no longer covers the receipt
    docs = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    assert docs.json()["items"][0]["outstanding"] == "90000.00"


# --- QT-M08-14 (payments half): the payable ledger rows ---------------------------------------------------
async def test_qt_m08_14_payable_debt_moves_of_payments(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "QT-M08-14")
    receipt = await _receipt(env, shop, supplier, wh, "400000.0000", "0.00")
    paid = (await pay(env.client, shop, supplier, "150000.00")).json()
    moves = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    (doc,) = moves.json()["items"]
    assert (doc["target_doc_id"], doc["total"], doc["outstanding"]) == (
        receipt["id"],
        "400000.00",
        "250000.00",
    )
    rows_ = await scalar(
        env, shop.tenant_id,
        "SELECT count(*) FROM app.debt_moves WHERE counterparty_id = :c AND direction = 'payable' "
        "AND doc_type = 'supplier_payments' AND doc_id = :d AND amount = -150000.00",
        c=UUID(supplier), d=UUID(paid["id"]),
    )  # fmt: skip
    assert rows_ == 1
    listed = await env.client.get(SP, params={"supplier_id": supplier}, headers=shop.h(key=None))
    assert listed.status_code == 200 and [p["id"] for p in listed.json()["items"]] == [paid["id"]]


# --- permissions / validation ---------------------------------------------------------------------------
async def test_supplier_payment_requires_purchases_pay(env: Env) -> None:
    shop, supplier, wh = await _setup(env, "perm")
    await _receipt(env, shop, supplier, wh, "1000.0000", "0.00")
    denied = await pay(env.client, shop, supplier, "1000.00", role="cashier")
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    future = await pay(env.client, shop, supplier, "1000.00", doc_date="2999-01-01")
    assert future.status_code == 422
    bank_with_shift = await pay(env.client, shop, supplier, "1000.00", shift_id=str(shop.branch_id))
    assert bank_with_shift.status_code == 422
    no_key = await pay(env.client, shop, supplier, "1000.00", key=None)
    assert no_key.status_code == 422 and err(no_key) == "VALIDATION_ERROR"  # Idempotency-Key required


async def test_payable_debt_opening_allocated_before_newer_receipt(env: Env) -> None:
    """``debt_openings`` (payable, 13 §2.13) are open documents too; the due date drives the order."""
    from datetime import timedelta

    from app.core.db.base import uuid7

    shop, supplier, wh = await _setup(env, "opening payable")
    receipt = await _receipt(env, shop, supplier, wh, "100000.0000", "0.00")
    opening = uuid7()
    day = business_today() - timedelta(days=30)
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.debt_openings (id, tenant_id, branch_id, number, doc_date, status, counterparty_id, amount, "
        "direction, due_date, created_by, posted_at) VALUES (:id, :t, :b, 'OD-01-2026-000001', :d, 'posted', :c, "
        "50000.00, 'payable', :d, :u, now())",
        id=opening, t=shop.tenant_id, b=shop.branch_id, d=day, c=UUID(supplier), u=shop.user_ids["owner"],
    )  # fmt: skip
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.debt_moves (tenant_id, counterparty_id, direction, amount, doc_type, doc_id) "
        "VALUES (:t, :c, 'payable', 50000.00, 'debt_openings', :id)",
        t=shop.tenant_id, c=UUID(supplier), id=opening,
    )  # fmt: skip
    await execute(
        env, shop.tenant_id,
        "UPDATE app.debt_balances SET balance = balance + 50000.00 WHERE counterparty_id = :c AND direction = 'payable'",
        c=UUID(supplier),
    )  # fmt: skip
    response = await pay(env.client, shop, supplier, "70000.00")
    assert response.status_code == 201, response.text
    assert [
        (a["target_doc_type"], a["target_doc_id"], a["amount"]) for a in response.json()["allocations"]
    ] == [
        ("debt_openings", str(opening), "50000.00"),
        ("goods_receipts", receipt["id"], "20000.00"),
    ]
    assert response.json()["allocations"][0]["target_number"] == "OD-01-2026-000001"
    assert await payable(env, shop, supplier) == D("80000.00")


async def test_receipt_cancel_refused_while_payment_allocated(env: Env) -> None:
    """19 §8 cancel guard: a posted receipt paid by a live supplier payment is not reversed until the payment is."""
    shop, supplier, wh = await _setup(env, "receipt cancel guard")
    receipt = await _receipt(env, shop, supplier, wh, "100000.0000", "0.00")
    paid = (await pay(env.client, shop, supplier, "40000.00")).json()
    gr_cancel = f"{API}/goods-receipts/{receipt['id']}/cancel"
    refused = await env.client.post(gr_cancel, json={"reason": "xato"}, headers=shop.h(branch=shop.branch_id))
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE", refused.text
    assert refused.json()["error"]["params"] == {
        "reason": "supplier_payment_allocated",
        "supplier_payment_ids": [paid["id"]],
    }
    assert await payable(env, shop, supplier) == D("60000.00")
    undone = await env.client.post(f"{SP}/{paid['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    assert undone.status_code == 200
    ok = await env.client.post(gr_cancel, json={"reason": "xato"}, headers=shop.h(branch=shop.branch_id))
    assert ok.status_code == 200, ok.text
    assert await payable(env, shop, supplier) == D("0.00")


# --- B4 fix round: ACC-03, ACC-05 (13 §2.6, §2.8, §2.16) ------------------------------------------------
async def _cancel(env: Env, shop: Shop, payment_id: str) -> Any:
    return await env.client.post(f"{SP}/{payment_id}/cancel", json={"reason": "xato"}, headers=shop.h())


async def test_acc03_cancel_refused_when_advance_consumed_by_receipt(env: Env) -> None:
    """13 §2.16 cancel: the advance part of a payment already offset by a later receipt (Dt 6010 / Kt 4310)
    cannot be reversed blindly — 4310 would go into credit with a payable and no document. Partly consumed
    is refused too; once the consuming receipts are cancelled the payment cancels normally."""
    shop, supplier, wh = await _setup(env, "ACC-03")
    await _receipt(env, shop, supplier, wh, "800000.0000", "0.00")
    paid = (await pay(env.client, shop, supplier, "1000000.00")).json()
    assert paid["advance_amount"] == "200000.00"
    assert await ledger_of(env, shop, paid["id"]) == [
        ("6010", "5110", D("800000.00")),
        ("4310", "5110", D("200000.00")),
    ]
    assert await debt_of(env, shop, paid["id"]) == [D("-1000000.00")]

    # partly consumed: a 100 000 receipt takes 100 000 of the 200 000 advance
    part = await _receipt(env, shop, supplier, wh, "100000.0000", "0.00")
    assert await ledger_of(env, shop, part["id"]) == [
        ("2910", "6010", D("100000.00")),
        ("6010", "4310", D("100000.00")),
    ]
    assert await debt_of(env, shop, part["id"]) == [D("100000.00")]
    refused = await _cancel(env, shop, paid["id"])
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"
    assert refused.json()["error"]["params"] == {
        "reason": "advance_consumed", "advance": "200000.00", "available": "100000.00",
    }  # fmt: skip

    # R1 repro: 800 000 / 1 000 000 / 500 000 — the rest of the advance is consumed
    nxt = await _receipt(env, shop, supplier, wh, "500000.0000", "0.00")
    assert await ledger_of(env, shop, nxt["id"]) == [
        ("2910", "6010", D("500000.00")),
        ("6010", "4310", D("100000.00")),
    ]
    assert await debt_of(env, shop, nxt["id"]) == [D("500000.00")]
    refused = await _cancel(env, shop, paid["id"])
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"
    assert refused.json()["error"]["params"] == {
        "reason": "advance_consumed", "advance": "200000.00", "available": "0.00",
    }  # fmt: skip
    # nothing was reversed: 4310 stays >= 0, the payment stays posted, its registers untouched
    assert await account_balance(env, shop, "4310", counterparty_id=supplier) == D("0.00")
    assert await ledger_of(env, shop, paid["id"]) == [
        ("6010", "5110", D("800000.00")),
        ("4310", "5110", D("200000.00")),
    ]
    assert await debt_of(env, shop, paid["id"]) == [D("-1000000.00")]
    assert await payable(env, shop, supplier) == D("400000.00")
    got = await env.client.get(f"{SP}/{paid['id']}", headers=shop.h(key=None))
    assert got.json()["status"] == "posted"

    # cancel the consuming receipts first -> the advance is back on 4310 -> the payment cancels
    for receipt in (nxt, part):
        undone = await env.client.post(
            f"{API}/goods-receipts/{receipt['id']}/cancel", json={"reason": "xato"},
            headers=shop.h(branch=shop.branch_id),
        )  # fmt: skip
        assert undone.status_code == 200, undone.text
    assert await account_balance(env, shop, "4310", counterparty_id=supplier) == D("200000.00")
    ok = await _cancel(env, shop, paid["id"])
    assert ok.status_code == 200, ok.text
    assert await ledger_of(env, shop, paid["id"]) == [
        ("6010", "5110", D("800000.00")),
        ("4310", "5110", D("200000.00")),
        ("5110", "6010", D("800000.00")),
        ("5110", "4310", D("200000.00")),
    ]
    assert await debt_of(env, shop, paid["id"]) == [D("-1000000.00"), D("1000000.00")]
    assert await account_balance(env, shop, "4310", counterparty_id=supplier) == D("0.00")
    assert await payable(env, shop, supplier) == D("800000.00")


async def _red_receipt(env: Env, shop: Shop, supplier: str, wh: UUID) -> tuple[str, UUID]:
    """A credit receipt 1 000 000 + 12 % VAT = 1 120 000 against a red e-invoice (13 §2.8: credit deferred)."""
    product = await create_product(env.client, shop, "Qizil avans tovar")
    draft = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(product["id"], "1.000", "1000000.0000")]
    )
    einvoice = await link_einvoice(
        env, shop, draft["id"], supplier, "red", total="1120000.00", vat="120000.00"
    )
    posted = await post_gr(env.client, shop, draft["id"])
    assert posted.status_code == 200, posted.text
    assert (posted.json()["net_total"], posted.json()["vat_total"]) == ("1000000.00", "120000.00")
    receipt_id: str = draft["id"]
    return receipt_id, einvoice


async def _released(env: Env, shop: Shop, einvoice: UUID) -> Any:
    return await scalar(
        env, shop.tenant_id, "SELECT sum(vat_amount) FROM app.vat_moves WHERE einvoice_id = :e", e=einvoice
    )


async def test_acc05_advance_covered_red_receipt_releases_vat(env: Env) -> None:
    """13 §2.6/§2.16: the advance offset is a payment — a red receipt fully covered by an advance takes its
    whole input-VAT credit at posting (no later payment would ever release it)."""
    shop, supplier, wh = await _setup(env, "ACC-05 full")
    advance = (await pay(env.client, shop, supplier, "1120000.00")).json()
    assert advance["advance_amount"] == "1120000.00" and advance["allocations"] == []
    assert await ledger_of(env, shop, advance["id"]) == [("4310", "5110", D("1120000.00"))]
    assert await debt_of(env, shop, advance["id"]) == [D("-1120000.00")]
    assert await vat_of(env, shop, advance["id"]) == []

    receipt_id, einvoice = await _red_receipt(env, shop, supplier, wh)
    assert await ledger_of(env, shop, receipt_id) == [
        ("2910", "6010", D("1000000.00")),
        ("4410", "6010", D("120000.00")),
        ("6010", "4310", D("1120000.00")),
    ]
    assert await vat_of(env, shop, receipt_id) == [("input", D("1000000.00"), D("120000.00"))]
    assert await debt_of(env, shop, receipt_id) == [D("1120000.00")]
    assert await _released(env, shop, einvoice) == D("120000.00")
    assert await payable(env, shop, supplier) == D("0.00")
    assert await account_balance(env, shop, "4310", counterparty_id=supplier) == D("0.00")
    assert await account_balance(env, shop, "4410") == D("120000.00")  # the one 4410 line, never rewritten
    docs = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    assert docs.json()["items"] == []

    # cancelling the receipt reverses the released credit with it
    undone = await env.client.post(
        f"{API}/goods-receipts/{receipt_id}/cancel", json={"reason": "xato"},
        headers=shop.h(branch=shop.branch_id),
    )  # fmt: skip
    assert undone.status_code == 200, undone.text
    assert await _released(env, shop, einvoice) == D("0.00")


async def test_acc05_partial_advance_then_payment_releases_remainder(env: Env) -> None:
    """Advance 400 000 against a 1 120 000 red receipt: the offset releases
    ROUND_HALF_UP(120 000 x 400 000 / 1 120 000) = 42 857.14 (base 357 142.86); the closing payment of
    720 000 takes the remainder 77 142.86 (base 642 857.14) — the sum is the invoice VAT exactly."""
    shop, supplier, wh = await _setup(env, "ACC-05 partial")
    advance = (await pay(env.client, shop, supplier, "400000.00")).json()
    assert await ledger_of(env, shop, advance["id"]) == [("4310", "5110", D("400000.00"))]
    assert await debt_of(env, shop, advance["id"]) == [D("-400000.00")]

    receipt_id, einvoice = await _red_receipt(env, shop, supplier, wh)
    assert await ledger_of(env, shop, receipt_id) == [
        ("2910", "6010", D("1000000.00")),
        ("4410", "6010", D("120000.00")),
        ("6010", "4310", D("400000.00")),
    ]
    assert await vat_of(env, shop, receipt_id) == [("input", D("357142.86"), D("42857.14"))]
    assert await debt_of(env, shop, receipt_id) == [D("1120000.00")]
    assert await payable(env, shop, supplier) == D("720000.00")
    docs = await env.client.get(
        f"{SP}/open-documents", params={"supplier_id": supplier}, headers=shop.h(key=None)
    )
    (doc,) = docs.json()["items"]
    assert (doc["outstanding"], doc["vat_pending"]) == ("720000.00", "77142.86")

    closing = await pay(env.client, shop, supplier, "720000.00")
    assert closing.status_code == 201, closing.text
    body = closing.json()
    assert body["advance_amount"] == "0.00"
    assert body["vat_credit_unlocked"] == [{"einvoice_id": str(einvoice), "vat_amount": "77142.86"}]
    assert await ledger_of(env, shop, body["id"]) == [("6010", "5110", D("720000.00"))]
    assert await vat_of(env, shop, body["id"]) == [("input", D("642857.14"), D("77142.86"))]
    assert await debt_of(env, shop, body["id"]) == [D("-720000.00")]
    assert await _released(env, shop, einvoice) == D("120000.00")
    assert await payable(env, shop, supplier) == D("0.00")
    assert await account_balance(env, shop, "4310", counterparty_id=supplier) == D("0.00")
