"""Offline inventory events through ``/sync/push`` (19 §13–§14; QT-M06-04, QT-M05-05, B3-DoD-04).

Registers asserted with the 13 numbers: send ``Dt 2970 / Kt 2910`` at the sender's lot cost, receive
``Dt 2920 / Kt 2970`` (2970 nets to zero), counts recorded with the device time, posting stays online.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from tests.support.inventory import D, balance, new_product, set_method
from tests.support.inventory_docs import (
    COUNTS,
    account_balance,
    doc_ledger,
    entries,
    ok,
    stock_in,
    today,
    two_branches,
)
from tests.support.sync import (
    SyncEnv,
    event,
    pos_device,
    push_ok,
    rows,
    scalar,
    sent_payload,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]


async def test_qt_m06_04_offline_transfer_sent_and_received_through_sync(env: SyncEnv) -> None:
    shop = await env.shop("QT-M06-04")
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "10.000", "50000.00")
    sender = await pos_device(env, shop, SystemRole.STOREKEEPER)
    receiver = await pos_device(env, shop, SystemRole.STOREKEEPER, branch_id=to_branch)

    # internet was off: the transfer is in the device's append-only outbox, created an hour ago
    payload = sent_payload(src, dst, [(cola, "4.000")])
    sent_event = event(sender, "transfer.sent", payload, created_at=datetime.now(UTC) - timedelta(hours=1))
    [result] = await push_ok(env, sender, [sent_event])
    assert result["status"] == "accepted", result
    assert result["warnings"] == [] and result["retryable"] is False
    server = result["server"]
    assert (
        server["id"] == payload["id"] and server["status"] == "sent" and server["number"].startswith("P-01-")
    )
    doc = (
        await rows(env.db, shop.tenant_id, "SELECT * FROM app.transfers WHERE id = :i", i=UUID(payload["id"]))
    )[0]
    assert (doc["client_event_id"], doc["device_id"], doc["temp_number"]) == (
        UUID(sent_event["client_event_id"]), sender.device_id, payload["temp_number"],
    )  # fmt: skip
    assert entries(await doc_ledger(env, shop, payload["id"])) == [("2970", "2910", D("20000.00"))]
    assert await balance(env, shop, src, cola) == (D("6.000"), D("30000.00"))

    line_id = payload["lines"][0]["line_id"]
    received = event(receiver, "transfer.received", {"transfer_id": payload["id"], "lines": [
        {"transfer_line_id": line_id, "qty_received": "4.000"}]})  # fmt: skip
    [res] = await push_ok(env, receiver, [received])
    assert res["status"] == "accepted", res
    assert res["server"]["status"] == "received"
    assert res["server"]["lines"][0]["qty_received"] == "4.000"
    assert res["server"]["lines"][0]["unit_cost"] == "5000.0000"
    assert sorted(entries(await doc_ledger(env, shop, payload["id"]))) == [
        ("2920", "2970", D("20000.00")), ("2970", "2910", D("20000.00")),
    ]  # fmt: skip
    assert await account_balance(env, shop, "2970") == D("0.00")
    assert await balance(env, shop, dst, cola) == (D("4.000"), D("20000.00"))
    audit = await rows(
        env.db, shop.tenant_id,
        "SELECT action, device_id FROM app.audit_log WHERE entity = 'transfers' AND entity_id = :i ORDER BY action",
        i=UUID(payload["id"]),
    )  # fmt: skip
    assert [(a["action"], a["device_id"]) for a in audit] == [
        ("transfer.received", receiver.device_id), ("transfer.sent", sender.device_id),
    ]  # fmt: skip


async def test_qt_m06_04_vehicle_transfer_offline_waits_for_ettn(env: SyncEnv) -> None:
    """qaror #63: no e-TTN offline — the vehicle transfer is posted, e-TTN pending, ``ETTN_REQUIRED``."""
    shop = await env.shop("QT-M06-04 vehicle")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "10.000", "50000.00")
    pos = await pos_device(env, shop)
    payload = sent_payload(src, dst, [(cola, "2.000")], mode="vehicle")
    [result] = await push_ok(env, pos, [event(pos, "transfer.sent", payload)])
    assert result["status"] == "accepted", result
    assert result["warnings"] == ["ETTN_REQUIRED"] and result["server"]["status"] == "posted"
    ettn = await rows(
        env.db,
        shop.tenant_id,
        "SELECT status FROM app.ettn_documents WHERE transfer_id = :i",
        i=UUID(payload["id"]),
    )
    assert [e["status"] for e in ettn] == ["pending_signature"]
    assert await balance(env, shop, src, cola) == (D("10.000"), D("50000.00"))  # nothing moved yet
    jobs = await scalar(
        env.db, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'ettn_send' "
        "AND payload->>'transfer_id' = :i", i=payload["id"],
    )  # fmt: skip
    assert jobs == 1  # the fake operator registers it; the online "send" follows (19 §13)


async def test_transfer_received_before_the_send_is_synced_is_retryable(env: SyncEnv) -> None:
    """16 §3.3: dependency from another device → ``DEPENDENCY_NOT_SYNCED`` (retryable), others continue."""
    shop = await env.shop("dep-transfers")
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "10.000", "50000.00")
    sender = await pos_device(env, shop)
    receiver = await pos_device(env, shop, branch_id=to_branch)
    payload = sent_payload(src, dst, [(cola, "1.000")])
    early = event(receiver, "transfer.received", {"transfer_id": payload["id"], "lines": [
        {"transfer_line_id": payload["lines"][0]["line_id"], "qty_received": "1.000"}]})  # fmt: skip
    [rejected] = await push_ok(env, receiver, [early], pending=1)
    assert (rejected["status"], rejected["error_code"], rejected["retryable"]) == (
        "rejected", "DEPENDENCY_NOT_SYNCED", True,
    )  # fmt: skip
    assert rejected["params"] == {"entity": "transfers"}
    assert (await push_ok(env, sender, [event(sender, "transfer.sent", payload)]))[0]["status"] == "accepted"
    [retried] = await push_ok(env, receiver, [early])  # the same event, resent
    assert retried["status"] == "accepted" and retried["server"]["status"] == "received"


async def test_transfer_from_another_branch_is_refused(env: SyncEnv) -> None:
    shop = await env.shop("transfer-branch")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    foreign = await pos_device(env, shop, branch_id=to_branch)
    [res] = await push_ok(
        env, foreign, [event(foreign, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]))]
    )
    assert (res["status"], res["error_code"], res["retryable"]) == ("rejected", "BRANCH_SCOPE_DENIED", False)
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.transfers") == 0


async def test_transfer_sent_payload_errors_are_validation_errors(env: SyncEnv) -> None:
    shop = await env.shop("transfer-payload")
    pos = await pos_device(env, shop)
    [res] = await push_ok(env, pos, [event(pos, "transfer.sent", {"id": "x"})])
    assert (res["status"], res["error_code"], res["retryable"]) == ("rejected", "VALIDATION_ERROR", False)
    assert res["details"][0]["field"].startswith("payload.")


async def test_qt_m05_05_offline_count_lines_sync_and_post_stays_online(env: SyncEnv) -> None:
    shop = await env.shop("QT-M05-05")
    await set_method(env, shop, "fifo")
    src, _, _ = await two_branches(env, shop)
    cola = await new_product(env, shop, "Cola")
    sugar = await new_product(env, shop, "Shakar")
    await stock_in(env, shop, src, cola, "10.000", "50000.00")
    await stock_in(env, shop, src, sugar, "5.000", "10000.00")
    count = await ok(
        await env.client.post(
            COUNTS, json={"warehouse_id": str(src), "doc_date": str(today())}, headers=shop.h()
        ),
        201,
    )
    scanner = await pos_device(env, shop, SystemRole.STOREKEEPER)
    base = datetime.now(UTC) - timedelta(minutes=30)
    events = [
        event(scanner, "stock_count.line_recorded",
              {"count_id": count["id"], "product_id": str(cola), "counted": "6.000", "recorded_at": base.isoformat()},
              created_at=base),
        event(scanner, "stock_count.line_recorded",
              {"count_id": count["id"], "product_id": str(cola), "counted": "7.000",
               "recorded_at": (base + timedelta(minutes=5)).isoformat()}, created_at=base + timedelta(minutes=5)),
        # an older scan arriving later never overwrites the newer one (19 §14: the latest recorded_at wins)
        event(scanner, "stock_count.line_recorded",
              {"count_id": count["id"], "product_id": str(cola), "counted": "1.000",
               "recorded_at": (base + timedelta(minutes=1)).isoformat()}, created_at=base + timedelta(minutes=6)),
        event(scanner, "stock_count.line_recorded",
              {"count_id": count["id"], "barcode": "0000000000000", "counted": "1.000",
               "recorded_at": base.isoformat()}, created_at=base + timedelta(minutes=7)),
        event(scanner, "stock_count.line_recorded",
              {"count_id": count["id"], "product_id": str(sugar), "counted": "5.000",
               "recorded_at": base.isoformat()}, created_at=base + timedelta(minutes=8)),
    ]  # fmt: skip
    results = await push_ok(env, scanner, events)
    assert [r["status"] for r in results] == ["accepted"] * 5
    assert [r["server"]["applied"] for r in results] == [True, True, False, False, True]
    assert results[3]["warnings"] == ["BARCODE_NOT_IN_CATALOG"]
    lines = {
        r["product_id"]: r
        for r in await rows(
            env.db, shop.tenant_id, "SELECT product_id, counted, counted_at FROM app.count_lines WHERE count_id = :c",
            c=UUID(count["id"]),
        )
    }  # fmt: skip
    assert lines[cola]["counted"] == D("7.000")
    assert abs(lines[cola]["counted_at"] - (base + timedelta(minutes=5))) < timedelta(seconds=1)
    assert lines[sugar]["counted"] == D("5.000")
    assert await scalar(env.db, shop.tenant_id, "SELECT device_id FROM app.stock_counts WHERE id = :c",
                        c=UUID(count["id"])) == scanner.device_id  # fmt: skip
    # MVP: one count — one device
    other = await pos_device(env, shop, SystemRole.STOREKEEPER)
    [refused] = await push_ok(env, other, [event(other, "stock_count.line_recorded", {
        "count_id": count["id"], "product_id": str(cola), "counted": "9.000", "recorded_at": base.isoformat()})])  # fmt: skip
    assert (refused["error_code"], refused["params"]) == (
        "DOC_INVALID_STATE",
        {"reason": "count_device_mismatch"},
    )
    # no sync event posts a count: the final confirmation is the online back-office action
    assert (await ok(await env.client.post(f"{COUNTS}/{count['id']}/submit-for-review", headers=shop.h())))[
        "status"
    ] == "review"
    posted = await ok(await env.client.post(f"{COUNTS}/{count['id']}/post", headers=shop.h()))
    assert posted["status"] == "posted"
    assert await balance(env, shop, src, cola) == (D("7.000"), D("35000.00"))


def widen_clamp(env: SyncEnv, days: int = 90) -> None:
    """The 7-day clamp (16 §8) would pull a weeks-old event into the current month — widen it for the test."""
    from dataclasses import replace

    env.module.push._cfg = replace(env.module.push._cfg, clamp_window_s=days * 86400)


async def test_offline_transfer_into_a_closed_period_is_posted_in_the_first_open_period(env: SyncEnv) -> None:
    """16 §3.4, qaror #69 + ACC-03: no ``PERIOD_CLOSED`` for POS events — ``doc_date`` = the event's own
    business day, the ledger goes to the first open period, ``sync_exceptions(kind='late_in_closed_period')``."""
    from tests.support.inventory import close_period

    shop = await env.shop("late-period")
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "5.000", "5000.00")
    first_of_month = today().replace(day=1)
    last_month = (first_of_month - timedelta(days=1)).replace(day=15)
    made_at = datetime(last_month.year, last_month.month, 15, 7, 0, tzinfo=UTC)  # 12:00 Tashkent
    await close_period(env, shop, last_month)
    widen_clamp(env)
    pos = await pos_device(env, shop)
    payload = sent_payload(src, dst, [(cola, "2.000")])  # payload doc_date (today) is informational only
    [res] = await push_ok(env, pos, [event(pos, "transfer.sent", payload, created_at=made_at)])
    assert res["status"] == "accepted", res
    doc = (await rows(env.db, shop.tenant_id, "SELECT doc_date, status, sent_at FROM app.transfers WHERE id = :i",
                      i=UUID(payload["id"])))[0]  # fmt: skip
    assert (doc["doc_date"], doc["status"], doc["sent_at"]) == (last_month, "sent", made_at)
    moved = await rows(env.db, shop.tenant_id, "SELECT moved_at FROM app.stock_moves WHERE doc_id = :i",
                       i=UUID(payload["id"]))  # fmt: skip
    assert {m["moved_at"] for m in moved} == {made_at}
    [line] = await doc_ledger(env, shop, payload["id"])
    assert (line["account_dt"], line["account_kt"]) == ("2970", "2910")
    assert line["entry_date"] == first_of_month
    assert (
        line["analytics"]["stock_cost"] is True
    )  # cost-line contract kept (recost owns correction_of_period)
    [exc] = await rows(
        env.db, shop.tenant_id, "SELECT kind, doc_type, doc_id, details FROM app.sync_exceptions"
    )
    assert (exc["kind"], exc["doc_type"], exc["doc_id"]) == (
        "late_in_closed_period",
        "transfers",
        UUID(payload["id"]),
    )
    assert exc["details"]["period"] == last_month.strftime("%Y-%m")

    # the receive made offline the same afternoon, pushed today: dated by the event, first open day + correction
    receiver = await pos_device(env, shop, branch_id=to_branch)
    received_at = made_at + timedelta(hours=3)
    got = event(receiver, "transfer.received", {"transfer_id": payload["id"], "lines": [
        {"transfer_line_id": payload["lines"][0]["line_id"], "qty_received": "2.000"}]}, created_at=received_at)  # fmt: skip
    [r2] = await push_ok(env, receiver, [got])
    assert r2["status"] == "accepted", r2
    lines = [x for x in await doc_ledger(env, shop, payload["id"]) if x["account_kt"] == "2970"]
    assert [(x["entry_date"], x["analytics"]["correction_of_period"]) for x in lines] == [
        (first_of_month, last_month.strftime("%Y-%m"))
    ]
    moves_in = await rows(env.db, shop.tenant_id, "SELECT moved_at FROM app.stock_moves WHERE doc_id = :i "
                          "AND warehouse_id = :w", i=UUID(payload["id"]), w=dst)  # fmt: skip
    assert {m["moved_at"] for m in moves_in} == {received_at}
    kinds = await rows(env.db, shop.tenant_id, "SELECT kind FROM app.sync_exceptions")
    assert [k["kind"] for k in kinds] == ["late_in_closed_period", "late_in_closed_period"]


async def test_acc_03_offline_transfer_is_dated_by_the_event_not_the_push(env: SyncEnv) -> None:
    """ACC-03 (13 §5.1, 16 §8): created two days ago, pushed now → moves, doc_date and ledger of that day."""
    from app.modules.accounting.domain.calendar import business_date

    shop = await env.shop("acc-03")
    await set_method(env, shop, "fifo")
    src, to_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "5.000", "5000.00")
    sender = await pos_device(env, shop)
    receiver = await pos_device(env, shop, branch_id=to_branch)
    made_at = datetime.now(UTC) - timedelta(days=2)
    payload = sent_payload(src, dst, [(cola, "1.000")])
    [res] = await push_ok(env, sender, [event(sender, "transfer.sent", payload, created_at=made_at)])
    assert res["status"] == "accepted", res
    day = business_date(made_at)
    doc = (await rows(env.db, shop.tenant_id, "SELECT doc_date, sent_at FROM app.transfers WHERE id = :i",
                      i=UUID(payload["id"])))[0]  # fmt: skip
    assert (doc["doc_date"], doc["sent_at"]) == (day, made_at)
    later = made_at + timedelta(days=1)
    [r2] = await push_ok(env, receiver, [event(receiver, "transfer.received", {"transfer_id": payload["id"], "lines": [
        {"transfer_line_id": payload["lines"][0]["line_id"], "qty_received": "1.000"}]}, created_at=later)])  # fmt: skip
    assert r2["status"] == "accepted", r2
    ledger = await doc_ledger(env, shop, payload["id"])
    # sorted by account: ledger created_at is the DB clock, which steps back on the test VM
    assert sorted((x["account_dt"], x["account_kt"], x["entry_date"]) for x in ledger) == [
        ("2920", "2970", business_date(later)), ("2970", "2910", day),
    ]  # fmt: skip
    moves = await rows(env.db, shop.tenant_id, "SELECT qty, moved_at FROM app.stock_moves WHERE doc_id = :i "
                       "ORDER BY qty", i=UUID(payload["id"]))  # fmt: skip
    assert [(m["qty"], m["moved_at"]) for m in moves] == [(D("-1.000"), made_at), (D("1.000"), later)]
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.sync_exceptions") == 0
