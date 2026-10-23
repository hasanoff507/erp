"""Transfers (19 §13, 13 §2.9–§2.10, QT-M06-01…08): send ``Dt 2970 / Kt inv(from)``, receive ``Dt inv(to) /
Kt 2970`` at the sender's lot cost, shortage ``Dt 5910 / Kt 2970``; 2970 nets to zero to the tiyin."""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from app.modules.inventory.wiring import recost_service
from tests.support.catalog import Env
from tests.support.inventory import (
    D,
    add_user,
    avg,
    balance,
    close_period,
    err,
    execute,
    lots,
    moves,
    new_product,
    receive,
    rows,
    scalar,
    set_method,
    set_setting,
)
from tests.support.inventory_docs import (
    COUNTS,
    TRANSFERS,
    WRITE_OFFS,
    account_balance,
    act,
    create_transfer,
    doc_ledger,
    docs_env_fixture,
    entries,
    ok,
    receive_body,
    sent_transfer,
    stock_in,
    today,
    two_branches,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["docs_env_fixture"]

API_TENANT = "/api/v1/tenant"


def today_plus(days: int) -> date:
    return today() + timedelta(days=days)


async def test_qt_m06_01_send_books_dt_2970_kt_2910_and_takes_stock_from_the_sender(env: Env) -> None:
    shop = await env.shop("QT-M06-01")
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    lot = await stock_in(env, shop, src, cola, "15.000", "75000.00")
    doc = await create_transfer(env, shop, src, dst, [(cola, "10.000")], mode="on_foot_or_public", plate=None)
    assert (doc["status"], doc["number"], doc["ettn"], doc["from_branch_id"], doc["to_branch_id"]) == (
        "draft", None, None, str(shop.branch_id), str(to_branch),
    )  # fmt: skip
    posted = await ok(await act(env, shop, doc["id"], "post"))
    assert posted["status"] == "posted" and posted["number"].startswith("P-01-")
    assert await balance(env, shop, src, cola) == (D("15.000"), D("75000.00"))  # post moves no stock

    sent = await ok(await act(env, shop, doc["id"], "send"))
    assert sent["status"] == "sent" and sent["sent_at"] is not None
    [line] = sent["lines"]
    assert line["unit_cost"] == "5000.0000"
    assert line["lot_allocations"] == [
        {"lot_id": str(lot), "qty": "10.000", "unit_cost": "5000.0000", "pending": False}
    ]
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led) == [("2970", "2910", D("50000.00"))]
    assert led[0]["branch_id"] == shop.branch_id
    assert led[0]["analytics"]["stock_cost"] is True and led[0]["analytics"]["to_branch_id"] == str(to_branch)
    assert await balance(env, shop, src, cola) == (D("5.000"), D("25000.00"))  # sender −10
    assert [m["qty"] for m in await moves(env, shop, cola, UUID(doc["id"]))] == [D("-10.000")]
    assert await account_balance(env, shop, "2970") == D("50000.00")


async def test_qt_m06_02_receive_books_dt_inv_to_kt_2970_and_keeps_the_lot_cost(env: Env) -> None:
    shop = await env.shop("QT-M06-02")
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "15.000", "75000.00", expiry=today_plus(90))
    [origin] = await lots(env, shop, cola)
    doc = await sent_transfer(env, shop, src, dst, [(cola, "10.000")])

    received = await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc)))
    assert received["status"] == "received" and received["lines"][0]["qty_received"] == "10.000"
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led) == [("2970", "2910", D("50000.00")), ("2920", "2970", D("50000.00"))]
    assert led[1]["branch_id"] == to_branch and "stock_cost" not in led[1]["analytics"]
    assert await balance(env, shop, dst, cola) == (D("10.000"), D("50000.00"))  # receiver +10
    dest = [x for x in await lots(env, shop, cola) if x["source_doc_type"] == "transfers"]
    assert [(x["qty_in"], x["unit_cost"], x["expiry_date"], x["received_at"]) for x in dest] == [
        (D("10.000"), D("5000.0000"), origin["expiry_date"], origin["received_at"])  # partiya saqlanadi
    ]
    assert await account_balance(env, shop, "2970") == D("0.00")
    again = await act(env, shop, doc["id"], "receive", json=receive_body(doc))
    assert again.status_code == 409 and err(again) == "DOC_INVALID_STATE"


async def test_qt_m06_03_shortage_on_receive_books_dt_5910_kt_2970(env: Env) -> None:
    shop = await env.shop("QT-M06-03")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "10.000", "50000.00")
    doc = await sent_transfer(env, shop, src, dst, [(cola, "10.000")])
    received = await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc, ["8.000"])))
    assert received["status"] == "discrepancy" and received["lines"][0]["qty_received"] == "8.000"
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led) == [
        ("2970", "2910", D("50000.00")),
        ("2920", "2970", D("40000.00")),
        ("5910", "2970", D("10000.00")),  # 2 × 5000.0000
    ]
    assert led[2]["analytics"]["shortage_qty"] == "2.000"
    assert await balance(env, shop, dst, cola) == (D("8.000"), D("40000.00"))
    assert await account_balance(env, shop, "2970") == D("0.00")


async def test_fifo_multi_lot_receive_fills_in_order_and_takes_the_shortage_from_the_tail(env: Env) -> None:
    shop = await env.shop("Transfer FIFO lots")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    lot_a = await stock_in(env, shop, src, p, "6.000", "30000.00")  # 5000
    lot_b = await stock_in(env, shop, src, p, "10.000", "55000.00")  # 5500
    doc = await sent_transfer(env, shop, src, dst, [(p, "10.000")])
    assert doc["lines"][0]["lot_allocations"] == [
        {"lot_id": str(lot_a), "qty": "6.000", "unit_cost": "5000.0000", "pending": False},
        {"lot_id": str(lot_b), "qty": "4.000", "unit_cost": "5500.0000", "pending": False},
    ]
    assert doc["lines"][0]["unit_cost"] == "5200.0000"  # 52000 / 10
    await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc, ["8.000"])))
    assert entries(await doc_ledger(env, shop, doc["id"])) == [
        ("2970", "2910", D("52000.00")),
        ("2920", "2970", D("41000.00")),  # 6 × 5000 + 2 × 5500
        ("5910", "2970", D("11000.00")),  # the tail: 2 × 5500
    ]
    dest = [x for x in await lots(env, shop, p) if x["source_doc_type"] == "transfers"]
    assert [(x["qty_in"], x["unit_cost"]) for x in dest] == [
        (D("6.000"), D("5000.0000")),
        (D("2.000"), D("5500.0000")),
    ]
    assert await balance(env, shop, src, p) == (D("6.000"), D("33000.00"))
    assert await account_balance(env, shop, "2970") == D("0.00")


async def test_aveco_transfer_carries_the_average_cost_and_2970_closes_to_the_tiyin(env: Env) -> None:
    shop = await env.shop("Transfer AVECO")
    await set_method(env, shop, "aveco")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "100.000", "800000.00")
    await stock_in(env, shop, src, p, "50.000", "450000.00")  # avg 8333.3333 (13 §3.2)
    doc = await sent_transfer(env, shop, src, dst, [(p, "120.000")])
    assert [a["unit_cost"] for a in doc["lines"][0]["lot_allocations"]] == ["8333.3333", "8333.3333"]
    await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc, ["110.000"])))
    assert entries(await doc_ledger(env, shop, doc["id"])) == [
        ("2970", "2910", D("1000000.00")),  # ROUND(120 × 8333.3333) — 13 §3.2
        ("2920", "2970", D("916666.67")),  # 833333.33 + ROUND(166666.67 × 10/20)
        ("5910", "2970", D("83333.33")),  # send − received
    ]
    assert await balance(env, shop, src, p) == (D("30.000"), D("250000.00"))
    assert await balance(env, shop, dst, p) == (D("110.000"), D("916666.67"))
    dest_avg = await avg(env, shop, dst, p)
    assert dest_avg is not None and dest_avg["total_value"] == D("916666.67")
    assert dest_avg["avg_cost"] == D("8333.3334")  # 916666.67 / 110 (AVECO receipt at the sender's cost)
    assert await account_balance(env, shop, "2970") == D("0.00")


async def test_settled_pending_piece_is_received_at_its_real_cost(env: Env) -> None:
    """Sent on negative stock (allow), settled before arrival: receive uses the live allocations; the
    recost job moves the 2970 debit to the settled cost, so 2970 closes at 0."""
    shop = await env.shop("Transfer settled")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "4.000", "20000.00")
    doc = await sent_transfer(env, shop, src, dst, [(p, "10.000")])
    allocations = doc["lines"][0]["lot_allocations"]
    assert [(a["qty"], a["pending"]) for a in allocations] == [("4.000", False), ("6.000", True)]
    assert entries(await doc_ledger(env, shop, doc["id"])) == [
        ("2970", "2910", D("50000.00"))
    ]  # 6 × 5000 est.
    _, jobs = await receive(env, shop, src, p, "10.000", "60000.00")  # settles 6 @ 6000
    assert len(jobs) == 1
    received = await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc)))
    assert [(a["qty"], a["unit_cost"], a["pending"]) for a in received["lines"][0]["lot_allocations"]] == [
        ("4.000", "5000.0000", False),
        ("6.000", "6000.0000", False),
    ]
    assert entries(await doc_ledger(env, shop, doc["id"]))[-1] == ("2920", "2970", D("56000.00"))
    assert await account_balance(env, shop, "2970") == D("-6000.00")  # until recost re-posts the send
    await recost_service(env.db.session_factory).run(shop.tenant_id, jobs[0])
    assert await account_balance(env, shop, "2970") == D("0.00")
    assert await balance(env, shop, dst, p) == (D("10.000"), D("56000.00"))


async def test_unsettled_pending_piece_refuses_the_receive_until_the_sender_is_settled(env: Env) -> None:
    """ACC-08: a still-pending piece has no real cost → ``409 TRANSFER_COST_PENDING``; once a sender
    receipt settles it the receive books the real cost and, after recost, 2970 closes at 0."""
    shop = await env.shop("Transfer pending")
    await set_method(env, shop, "fifo")
    await set_setting(env, shop, "negative_stock_policy", "allow")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    doc = await sent_transfer(env, shop, src, dst, [(p, "5.000")])  # sender stock 0
    assert [a["pending"] for a in doc["lines"][0]["lot_allocations"]] == [True]
    line_id = doc["lines"][0]["id"]

    refused = await act(env, shop, doc["id"], "receive", json=receive_body(doc))
    assert refused.status_code == 409 and err(refused) == "TRANSFER_COST_PENDING", refused.text
    assert refused.json()["error"]["params"] == {"line_id": line_id, "product_id": str(p), "qty": "5.000"}
    assert [x for x in await lots(env, shop, p) if x["source_doc_type"] == "transfers"] == []
    flagged = "SELECT count(*) FROM app.sync_exceptions WHERE details ->> 'reason' = 'transfer_received_at_pending_cost'"
    assert await scalar(env, shop.tenant_id, flagged) == 0  # no receive-at-estimate any more

    _, jobs = await receive(env, shop, src, p, "5.000", "5000.00")  # 5 × 1000 settles the pending piece
    received = await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc)))
    assert received["status"] == "received"
    assert entries(await doc_ledger(env, shop, doc["id"]))[-1] == ("2920", "2970", D("5000.00"))
    assert await balance(env, shop, dst, p) == (D("5.000"), D("5000.00"))
    for job in jobs:
        await recost_service(env.db.session_factory).run(shop.tenant_id, job)
    assert await account_balance(env, shop, "2970") == D("0.00")


async def test_qt_m06_07_vehicle_transfer_needs_a_registered_ettn(env: Env) -> None:
    shop = await env.shop("QT-M06-07")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "10.000", "50000.00")
    telegram_before = await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'telegram'"
    )
    doc = await create_transfer(env, shop, src, dst, [(p, "10.000")], driver_name="Ali Valiyev")
    posted = await ok(await act(env, shop, doc["id"], "post"))
    assert posted["ettn"]["status"] == "pending_signature" and posted["ettn_ref"] is None
    [ettn] = await rows(
        env, shop.tenant_id,
        "SELECT id, transfer_id, direction, transport_type, status, doc_date, payload FROM app.ettn_documents",
    )  # fmt: skip
    assert (str(ettn["transfer_id"]), ettn["direction"], ettn["transport_type"], ettn["status"]) == (
        doc["id"], "out", "warehouse_to_warehouse", "pending_signature",
    )  # fmt: skip
    assert ettn["payload"]["number"] == posted["number"] and ettn["payload"]["vehicle_plate"] == "01A123BC"
    assert ettn["payload"]["driver_name"] == "Ali Valiyev" and ettn["payload"]["lines"][0]["qty"] == "10.000"
    [job] = await rows(
        env,
        shop.tenant_id,
        "SELECT kind, status, payload, idempotency_key FROM app.outbox_jobs WHERE kind = 'ettn_send'",
    )
    assert (job["status"], job["payload"]["ettn_id"], job["idempotency_key"]) == (
        "queued", str(ettn["id"]), f"ettn_send:{ettn['id']}",
    )  # fmt: skip

    refused = await act(env, shop, doc["id"], "send")
    assert refused.status_code == 409 and err(refused) == "ETTN_REQUIRED"
    assert refused.json()["error"]["params"]["ettn_status"] == "pending_signature"
    assert await doc_ledger(env, shop, doc["id"]) == []

    assert await env.drain() >= 1  # the SAQ job enqueued after the post commit
    got = await ok(await env.client.get(f"{TRANSFERS}/{doc['id']}", headers=shop.h(key=None)))
    op_id = f"FAKE-TTN-{ettn['id'].hex[:12].upper()}"
    assert got["ettn"] == {"id": str(ettn["id"]), "status": "registered", "operator_doc_id": op_id}
    assert got["ettn_ref"] == op_id
    assert (
        await scalar(env, shop.tenant_id, "SELECT status FROM app.outbox_jobs WHERE kind = 'ettn_send'")
        == "done"
    )
    sent = await ok(await act(env, shop, doc["id"], "send"))
    assert sent["status"] == "sent"
    assert entries(await doc_ledger(env, shop, doc["id"])) == [("2970", "2910", D("50000.00"))]
    listed = await ok(
        await env.client.get(TRANSFERS, params={"ettn_status": "registered"}, headers=shop.h(key=None))
    )
    assert [x["id"] for x in listed["items"]] == [doc["id"]]
    telegram_after = await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'telegram'"
    )
    assert telegram_after == telegram_before


async def test_qt_m06_08_on_foot_needs_no_ettn_and_vehicle_needs_a_plate(env: Env) -> None:
    shop = await env.shop("QT-M06-08")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "10.000", "50000.00")
    on_foot = await create_transfer(env, shop, src, dst, [(p, "1.000")], mode="on_foot_or_public", plate=None)
    posted = await ok(await act(env, shop, on_foot["id"], "post"))
    assert posted["ettn"] is None
    assert (await ok(await act(env, shop, on_foot["id"], "send")))["status"] == "sent"
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.ettn_documents") == 0
    assert (
        await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'ettn_send'")
        == 0
    )

    no_plate = await create_transfer(env, shop, src, dst, [(p, "1.000")], plate=None)
    refused = await act(env, shop, no_plate["id"], "post")
    assert refused.status_code == 422 and err(refused) == "VALIDATION_ERROR"
    assert refused.json()["error"]["params"]["field"] == "vehicle_plate"
    assert refused.json()["error"]["details"][0]["field"] == "vehicle_plate"


async def test_qt_m06_05_sent_transfer_is_overdue_after_the_tenant_setting(env: Env) -> None:
    shop = await env.shop("QT-M06-05")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "10.000", "50000.00")
    doc = await sent_transfer(env, shop, src, dst, [(p, "1.000")])
    assert doc["is_overdue"] is False
    await execute(
        env, shop.tenant_id, "UPDATE app.transfers SET sent_at = now() - interval '3 hours' WHERE id = :id",
        id=UUID(doc["id"]),
    )  # fmt: skip

    async def flag() -> bool:
        items = (await ok(await env.client.get(TRANSFERS, headers=shop.h(key=None))))["items"]
        return bool(items[0]["is_overdue"])

    assert await flag() is False  # default 48 h
    settings = await ok(await env.client.get(f"{API_TENANT}/settings", headers=shop.h(key=None)))
    assert settings["settings"]["transfer_overdue_hours"] == 48
    patched = await env.client.patch(
        f"{API_TENANT}/settings",
        json={"version": settings["version"], "settings": {"transfer_overdue_hours": 2}},
        headers=shop.h(),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["settings"]["transfer_overdue_hours"] == 2
    assert await flag() is True
    for bad in (0, 721, "24"):
        refused = await env.client.patch(
            f"{API_TENANT}/settings",
            json={"version": patched.json()["version"], "settings": {"transfer_overdue_hours": bad}},
            headers=shop.h(),
        )
        assert refused.status_code == 422, bad


async def test_qt_m06_06_marked_product_transfer_is_allowed_without_crpt(env: Env) -> None:
    shop = await env.shop("QT-M06-06")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    water = await new_product(env, shop, "Hayot suvi 1.5L")
    await execute(
        env, shop.tenant_id,
        "UPDATE app.products SET is_marked = true, "
        "marking_group_code = (SELECT code FROM platform.marking_product_groups ORDER BY code LIMIT 1) WHERE id = :p",
        p=water,
    )  # fmt: skip
    await stock_in(env, shop, src, water, "5.000", "25000.00")
    doc = await sent_transfer(env, shop, src, dst, [(water, "5.000")])
    received = await ok(await act(env, shop, doc["id"], "receive", json=receive_body(doc)))
    assert received["status"] == "received"
    assert (
        await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind LIKE 'marking%'")
        == 0
    )
    assert await balance(env, shop, dst, water) == (D("5.000"), D("25000.00"))


async def test_cancel_draft_posted_sent_and_received(env: Env) -> None:
    shop = await env.shop("Transfer cancel")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "20.000", "100000.00")
    reason = {"reason": "xato"}

    draft = await create_transfer(env, shop, src, dst, [(p, "1.000")])
    cancelled = await ok(await act(env, shop, draft["id"], "cancel", json=reason))
    assert (cancelled["status"], cancelled["cancel_reason"], cancelled["warnings"]) == (
        "cancelled",
        "xato",
        [],
    )
    again = await act(env, shop, draft["id"], "cancel", json=reason)
    assert again.status_code == 409 and err(again) == "DOC_ALREADY_CANCELLED"

    pending = await create_transfer(env, shop, src, dst, [(p, "1.000")])
    await ok(await act(env, shop, pending["id"], "post"))
    body = await ok(await act(env, shop, pending["id"], "cancel", json=reason))
    assert body["ettn"]["status"] == "cancelled" and body["warnings"] == []
    assert await scalar(
        env, shop.tenant_id, "SELECT status FROM app.outbox_jobs WHERE payload ->> 'transfer_id' = :t",
        t=pending["id"],
    ) == "done"  # fmt: skip
    assert await env.drain() >= 1  # the queued SAQ job finds nothing to send
    assert (await ok(await env.client.get(f"{TRANSFERS}/{pending['id']}", headers=shop.h(key=None))))["ettn"][
        "status"
    ] == "cancelled"

    registered = await create_transfer(env, shop, src, dst, [(p, "2.000")])
    await ok(await act(env, shop, registered["id"], "post"))
    await env.drain()
    await ok(await act(env, shop, registered["id"], "send"))
    assert await balance(env, shop, src, p) == (D("18.000"), D("90000.00"))
    body = await ok(await act(env, shop, registered["id"], "cancel", json=reason))
    assert body["status"] == "cancelled" and body["warnings"] == ["ETTN_CANCEL_IN_OPERATOR"]
    assert body["ettn"]["status"] == "registered"
    led = await doc_ledger(env, shop, registered["id"])
    assert entries(led) == [("2970", "2910", D("10000.00")), ("2910", "2970", D("10000.00"))]
    assert led[1]["reversal_of_id"] == led[0]["id"]
    assert await balance(env, shop, src, p) == (D("20.000"), D("100000.00"))
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("20.000")]
    assert await account_balance(env, shop, "2970") == D("0.00")

    done = await sent_transfer(env, shop, src, dst, [(p, "1.000")])
    await ok(await act(env, shop, done["id"], "receive", json=receive_body(done)))
    refused = await act(env, shop, done["id"], "cancel", json=reason)
    assert refused.status_code == 409 and err(refused) == "DOC_INVALID_STATE"


async def test_validation_and_state_errors(env: Env) -> None:
    shop = await env.shop("Transfer errors")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "5.000", "25000.00")
    same = await env.client.post(
        TRANSFERS,
        json={"from_warehouse_id": str(src), "to_warehouse_id": str(src), "doc_date": "2026-10-17",
              "lines": [{"product_id": str(p), "qty_sent": "1.000"}]},
        headers=shop.h(),
    )  # fmt: skip
    assert same.status_code == 422 and same.json()["error"]["details"][0]["field"] == "to_warehouse_id"
    zero = await env.client.post(
        TRANSFERS,
        json={"from_warehouse_id": str(src), "to_warehouse_id": str(dst), "doc_date": "2026-10-17",
              "lines": [{"product_id": str(p), "qty_sent": "0.000"}]},
        headers=shop.h(),
    )  # fmt: skip
    assert zero.status_code == 422
    doc = await create_transfer(env, shop, src, dst, [(p, "3.000")], mode="on_foot_or_public", plate=None)
    early = await act(env, shop, doc["id"], "send")
    assert early.status_code == 409 and err(early) == "DOC_INVALID_STATE"
    not_sent = await act(env, shop, doc["id"], "receive", json=receive_body(doc))
    assert not_sent.status_code == 409 and err(not_sent) == "DOC_INVALID_STATE"
    await ok(await act(env, shop, doc["id"], "post"))
    twice = await act(env, shop, doc["id"], "post")
    assert twice.status_code == 409 and err(twice) == "DOC_NOT_DRAFT"
    await ok(await act(env, shop, doc["id"], "send"))
    over = await act(env, shop, doc["id"], "receive", json=receive_body(doc, ["3.001"]))
    assert over.status_code == 422 and over.json()["error"]["details"][0]["field"] == "lines[0].qty_received"
    missing = await act(
        env,
        shop,
        doc["id"],
        "receive",
        json={"lines": [{"transfer_line_id": doc["id"], "qty_received": "1.000"}]},
    )
    assert missing.status_code == 422
    unknown = await env.client.get(f"{TRANSFERS}/{doc['lines'][0]['id']}", headers=shop.h(key=None))
    assert unknown.status_code == 404 and unknown.json()["error"]["params"]["resource"] == "transfer"


async def test_block_policy_refuses_the_post_and_concurrent_sends_never_over_issue(env: Env) -> None:
    shop = await env.shop("Transfer block")
    await set_method(env, shop, "fifo")
    await set_setting(env, shop, "negative_stock_policy", "block")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "10.000", "50000.00")
    too_much = await create_transfer(
        env, shop, src, dst, [(p, "11.000")], mode="on_foot_or_public", plate=None
    )
    refused = await act(env, shop, too_much["id"], "post")
    assert refused.status_code == 422 and err(refused) == "NEGATIVE_STOCK_NOT_ALLOWED"
    assert refused.json()["error"]["params"]["available"] == "10.000"
    assert await balance(env, shop, src, p) == (D("10.000"), D("50000.00"))

    docs = [
        await create_transfer(env, shop, src, dst, [(p, "7.000")], mode="on_foot_or_public", plate=None)
        for _ in range(2)
    ]
    for d in docs:
        await ok(await act(env, shop, d["id"], "post"))
    results = await asyncio.gather(*(act(env, shop, d["id"], "send") for d in docs))
    assert sorted(r.status_code for r in results) == [200, 422]
    assert [err(r) for r in results if r.status_code == 422] == ["NEGATIVE_STOCK_NOT_ALLOWED"]
    assert await balance(env, shop, src, p) == (D("3.000"), D("15000.00"))
    assert await account_balance(env, shop, "2970") == D("35000.00")


async def test_concurrent_receives_of_one_transfer_post_once(env: Env) -> None:
    shop = await env.shop("Transfer double receive")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "10.000", "50000.00")
    doc = await sent_transfer(env, shop, src, dst, [(p, "10.000")])
    results = await asyncio.gather(
        *(act(env, shop, doc["id"], "receive", json=receive_body(doc)) for _ in range(2))
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert await balance(env, shop, dst, p) == (D("10.000"), D("50000.00"))
    assert len(await doc_ledger(env, shop, doc["id"])) == 2


async def test_idempotent_replay_and_scope_permissions_rls(env: Env) -> None:
    shop = await env.shop("Transfer scope", SystemRole.OWNER, SystemRole.CASHIER)
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    await add_user(env, shop, "keeper1", SystemRole.STOREKEEPER, (shop.branch_id,))
    await add_user(env, shop, "keeper2", SystemRole.STOREKEEPER, (to_branch,))
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "10.000", "50000.00")

    cashier = await env.client.post(TRANSFERS, json={}, headers=shop.h("cashier"))
    assert cashier.status_code in (403, 422)
    denied = await env.client.post(
        TRANSFERS,
        json={"from_warehouse_id": str(src), "to_warehouse_id": str(dst), "doc_date": "2026-10-17",
              "lines": [{"product_id": str(p), "qty_sent": "1.000"}]},
        headers=shop.h("cashier"),
    )  # fmt: skip
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    wrong_side = await env.client.post(
        TRANSFERS,
        json={"from_warehouse_id": str(src), "to_warehouse_id": str(dst), "doc_date": "2026-10-17",
              "lines": [{"product_id": str(p), "qty_sent": "1.000"}]},
        headers=shop.h("keeper2"),
    )  # fmt: skip
    assert wrong_side.status_code == 403 and err(wrong_side) == "BRANCH_SCOPE_DENIED"

    doc = await create_transfer(
        env, shop, src, dst, [(p, "4.000")], role="keeper1", mode="on_foot_or_public", plate=None
    )
    await ok(await act(env, shop, doc["id"], "post", role="keeper1"))
    key = "transfer-send-1"
    first = await env.client.post(f"{TRANSFERS}/{doc['id']}/send", headers=shop.h("keeper1", key=key))
    replay = await env.client.post(f"{TRANSFERS}/{doc['id']}/send", headers=shop.h("keeper1", key=key))
    assert first.status_code == replay.status_code == 200 and replay.json() == first.json()
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert await balance(env, shop, src, p) == (D("6.000"), D("30000.00"))

    sender_receives = await act(
        env, shop, doc["id"], "receive", role="keeper1", json=receive_body(first.json())
    )
    assert sender_receives.status_code == 403 and err(sender_receives) == "BRANCH_SCOPE_DENIED"
    seen = await ok(await env.client.get(f"{TRANSFERS}/{doc['id']}", headers=shop.h("keeper2", key=None)))
    assert seen["status"] == "sent"
    await ok(await act(env, shop, doc["id"], "receive", role="keeper2", json=receive_body(first.json())))
    keeper1_list = await ok(await env.client.get(TRANSFERS, headers=shop.h("keeper1", key=None)))
    assert [x["id"] for x in keeper1_list["items"]] == [doc["id"]]

    other = await env.shop("Transfer other tenant")
    hidden = await env.client.get(f"{TRANSFERS}/{doc['id']}", headers=other.h(key=None))
    assert hidden.status_code == 404
    assert (await ok(await env.client.get(TRANSFERS, headers=other.h(key=None))))["items"] == []


async def test_period_closed_refuses_post_and_send(env: Env) -> None:
    shop = await env.shop("Transfer period")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "5.000", "25000.00")
    last_month = today_plus(0).replace(day=1) - timedelta(days=1)
    doc = await create_transfer(
        env, shop, src, dst, [(p, "1.000")], mode="on_foot_or_public", plate=None, doc_date=str(last_month)
    )
    await close_period(env, shop, last_month)
    refused = await act(env, shop, doc["id"], "post")
    assert refused.status_code == 409 and err(refused) == "PERIOD_CLOSED"
    assert refused.json()["error"]["params"]["period"] == last_month.strftime("%Y-%m")


def _future_date_refused(response: Any) -> bool:
    detail = response.json()["error"]["details"][0] if response.status_code == 422 else {}
    return (
        err(response) == "VALIDATION_ERROR"
        and detail.get("field") == "doc_date"
        and detail.get("message_key") == "validation.doc_date_in_future"
    )


async def test_doc_date_after_the_business_day_is_refused_on_create_and_post(env: Env) -> None:
    """ACC-13 (13 §5.2, 19 §0): ``doc_date`` > business today → 422 ``validation.doc_date_in_future``."""
    shop = await env.shop("Transfer future date")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "5.000", "5000.00")
    body = {
        "from_warehouse_id": str(src), "to_warehouse_id": str(dst), "doc_date": str(today_plus(1)),
        "transport_mode": "on_foot_or_public", "lines": [{"product_id": str(p), "qty_sent": "1.000"}],
    }  # fmt: skip
    created = await env.client.post(TRANSFERS, json=body, headers=shop.h())
    assert created.status_code == 422 and _future_date_refused(created), created.text

    doc = await create_transfer(env, shop, src, dst, [(p, "1.000")], mode="on_foot_or_public", plate=None)
    await execute(
        env, shop.tenant_id, "UPDATE app.transfers SET doc_date = :d WHERE id = :id",
        d=today_plus(1), id=UUID(doc["id"]),
    )  # fmt: skip
    posted = await act(env, shop, doc["id"], "post")
    assert posted.status_code == 422 and _future_date_refused(posted), posted.text
    assert (await ok(await env.client.get(f"{TRANSFERS}/{doc['id']}", headers=shop.h(key=None))))[
        "status"
    ] == "draft"


async def test_out_of_range_cursor_is_a_422_on_every_stock_document_list(env: Env) -> None:
    """SEC-06: a cursor instant outside 2000..2100 UTC (here year 9999) → 422 ``validation.cursor_invalid``."""
    shop = await env.shop("Cursor range")
    raw = json.dumps(["9999-12-31T23:59:59+14:00", str(uuid7())]).encode()
    cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    naive = base64.urlsafe_b64encode(json.dumps(["2026-01-01T00:00:00", str(uuid7())]).encode()).decode()
    for url in (TRANSFERS, COUNTS, WRITE_OFFS):
        for bad in (cursor, naive):
            response = await env.client.get(url, params={"cursor": bad}, headers=shop.h(key=None))
            assert response.status_code == 422, (url, response.text)
            detail = response.json()["error"]["details"][0]
            assert (detail["field"], detail["message_key"]) == ("cursor", "validation.cursor_invalid")
