"""Sync capacity / availability (31 QT-NFR-03, -04, -09, -10, -11, -12; 25 §3; 27 B3 DoD-01, DoD-03).

Load tests run over the real stack (ASGI app, Postgres, Redis) with modest N and the 25 thresholds:
reads p95 < 300 ms, posting p95 < 800 ms. Offline-capacity tests push the ≈300 events of 48 h offline
in ``seq`` order through the backpressure limits, losing and duplicating nothing.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.modules.sync.application.handlers import EventContext, HandlerResult
from tests.support.catalog import set_price
from tests.support.inventory import D, balance, new_product, set_method
from tests.support.inventory_docs import stock_in, two_branches
from tests.support.sync import (
    Pos,
    SyncEnv,
    echo_handler,
    event,
    execute,
    pos_device,
    pull_all,
    push,
    push_ok,
    register,
    rows,
    scalar,
    sent_payload,
    settle_clock,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]

ECHO = "test.echo"


def p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=20, method="inclusive")[18]


async def drain_outbox(
    env: SyncEnv, pos: Pos, outbox: list[dict[str, Any]], batch: int = 100
) -> list[dict[str, Any]]:
    """What the device does when the internet returns: oldest first, ≤ ``batch`` per push, honour 429
    ``Retry-After`` (backoff), keep everything not accepted/duplicate (16 §3.1, 24 sync engine)."""
    results: dict[str, dict[str, Any]] = {}
    pending = list(outbox)
    while pending:
        chunk = pending[:batch]
        response = await push(env, pos, chunk, pending=len(pending) - len(chunk),
                              oldest=None if len(pending) == len(chunk) else datetime.fromisoformat(
                                  pending[len(chunk)]["created_at"]))  # fmt: skip
        if response.status_code == 429:
            await asyncio.sleep(float(response.headers["Retry-After"]))
            continue
        assert response.status_code == 200, response.text
        for ev, res in zip(chunk, response.json()["results"], strict=True):
            results[ev["client_event_id"]] = res
        done = {
            r["client_event_id"]
            for r in response.json()["results"]
            if r["status"] in ("accepted", "duplicate")
        }
        pending = [e for e in pending if e["client_event_id"] not in done]
    return [results[e["client_event_id"]] for e in outbox]


async def timed_push(env: SyncEnv, pos: Pos, events: list[dict[str, Any]]) -> tuple[httpx.Response, float]:
    """One push timed in ms; a 429 (5 req/s per device) is honoured like the device does and not measured."""
    while True:
        t0 = time.perf_counter()
        response = await push(env, pos, events)
        elapsed = (time.perf_counter() - t0) * 1000
        if response.status_code != 429:
            return response, elapsed
        await asyncio.sleep(float(response.headers["Retry-After"]))


# --- QT-NFR-09 backpressure ---------------------------------------------------------------------------
async def test_qt_nfr_09_six_pushes_per_second_from_one_device_get_429(env: SyncEnv) -> None:
    shop = await env.shop("NFR-09 rate")
    pos = await pos_device(env, shop)
    statuses: list[httpx.Response] = []
    for _ in range(6):
        statuses.append(await push(env, pos, []))
    assert [r.status_code for r in statuses[:5]] == [200] * 5
    limited = statuses[5]
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1
    assert limited.json()["error"]["params"] == {"reason": "device_rate"}


async def test_qt_nfr_09_fifth_parallel_push_of_a_tenant_gets_429(env: SyncEnv) -> None:
    shop = await env.shop("NFR-09 tenant")
    devices = [await pos_device(env, shop) for _ in range(5)]
    release = asyncio.Event()
    started = 0

    async def slow(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
        nonlocal started
        started += 1
        await release.wait()
        return HandlerResult(server={"ok": True})

    register(env, "test.slow", slow)
    running = [asyncio.create_task(push(env, d, [event(d, "test.slow", {})])) for d in devices[:4]]
    for _ in range(200):
        if started == 4:
            break
        await asyncio.sleep(0.02)
    assert started == 4
    fifth = await push(env, devices[4], [])
    assert fifth.status_code == 429 and fifth.json()["error"]["params"] == {"reason": "tenant_concurrency"}
    assert "Retry-After" in fifth.headers
    busy = await push(env, devices[0], [])  # the same device while its push still runs (seq order)
    assert busy.status_code == 429 and busy.json()["error"]["params"] == {"reason": "device_busy"}
    release.set()
    done = await asyncio.gather(*running)
    assert [r.status_code for r in done] == [200] * 4
    assert (await push(env, devices[4], [])).status_code == 200  # slots are released


# --- QT-NFR-10 first snapshot paging --------------------------------------------------------------------
async def test_qt_nfr_10_first_snapshot_is_paged_by_page_size(env: SyncEnv) -> None:
    shop = await env.shop("NFR-10")
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.products (tenant_id, name, unit_code, vat_rate) "
        "SELECT :t, 'Tovar ' || g, 'box', 12 FROM generate_series(1, 1200) g",
        t=shop.tenant_id,
    )  # fmt: skip
    pos = await pos_device(env, shop)
    await settle_clock(env, shop.tenant_id)
    pages = await pull_all(env, pos, "all", None, page_size=500)
    assert len(pages) >= 3
    assert all(p["has_more"] for p in pages[:-1]) and pages[-1]["has_more"] is False
    rows_per_page = [sum(len(p[k]) for k in ("catalog", "barcodes", "prices", "customers", "stock",
                                              "marking_codes", "fiscal")) for p in pages]  # fmt: skip
    assert all(n == 500 for n in rows_per_page[:-1]) and rows_per_page[-1] <= 500
    product_ids = [r["id"] for p in pages for r in p["catalog"] if r["entity"] == "product"]
    assert len(product_ids) == 1200 and len(set(product_ids)) == 1200  # no loss, no duplicate
    barcode_rows = [r["id"] for p in pages for r in p["barcodes"]]
    assert len(set(barcode_rows)) == 1200
    # snapshot objects arrive once, then stay null while unchanged
    assert pages[0]["settings"] is not None and all(p["settings"] is None for p in pages[1:])
    after = await pull_all(env, pos, "all", pages[-1]["cursor"])
    assert len(after) == 1 and after[0]["catalog"] == []


# --- QT-NFR-11 / B3-DoD-01: 48 h offline, ≈300 events --------------------------------------------------
async def test_qt_nfr_11_three_hundred_events_after_48h_offline_ordered_no_loss_no_dup(env: SyncEnv) -> None:
    shop = await env.shop("NFR-11")
    pos = await pos_device(env, shop)
    inner = echo_handler()
    posted: list[int] = []  # handler call order — DB timestamps are not monotonic on the test VM clock

    async def recording(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
        result = await inner(s, ctx, payload)
        posted.append(ctx.seq)
        return result

    register(env, ECHO, recording)
    start = datetime.now(UTC) - timedelta(hours=48)
    outbox = [event(pos, ECHO, {"n": i}, created_at=start + timedelta(minutes=9.6 * i)) for i in range(300)]
    results = await drain_outbox(env, pos, outbox)
    assert [r["status"] for r in results] == ["accepted"] * 300
    # the response of the last batch was "lost": the device resends everything still in its buffer
    replay = await drain_outbox(env, pos, outbox)
    assert {r["status"] for r in replay} == {"duplicate"}
    assert [r["server"] for r in replay] == [r["server"] for r in results]
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.sync_receipts") == 300
    assert posted == [e["seq"] for e in outbox]  # posted strictly in seq order, once (replay posts nothing)
    handled = await rows(
        env.db, shop.tenant_id,
        "SELECT (after->>'seq')::int AS seq FROM app.audit_log WHERE action = 'test.echo'",
    )  # fmt: skip
    assert sorted(h["seq"] for h in handled) == [e["seq"] for e in outbox]  # committed once each
    device = (await rows(env.db, shop.tenant_id, "SELECT * FROM app.devices WHERE id = :d", d=pos.device_id))[
        0
    ]
    assert (device["outbox_pending_count"], device["outbox_oldest_pending_at"]) == (0, None)


async def test_b3_dod_01_two_hours_offline_documents_sync_without_loss_or_duplicates(env: SyncEnv) -> None:
    """DoD-01 (server half) with real documents: 2 h of offline transfers + count lines, synced, replayed."""
    shop = await env.shop("DoD-01")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "100.000", "100000.00")
    pos = await pos_device(env, shop)
    start = datetime.now(UTC) - timedelta(hours=2)
    outbox = [
        event(pos, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]), created_at=start + timedelta(minutes=3 * i))
        for i in range(40)
    ]  # fmt: skip
    results = await drain_outbox(env, pos, outbox, batch=15)
    assert [r["status"] for r in results] == ["accepted"] * 40
    replay = await drain_outbox(env, pos, outbox, batch=15)
    assert {r["status"] for r in replay} == {"duplicate"}
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.transfers") == 40
    numbers = [r["server"]["number"] for r in results]
    assert len(set(numbers)) == 40
    assert await balance(env, shop, src, cola) == (D("60.000"), D("60000.00"))


# --- QT-NFR-12: backend unavailable → events stay pending, nothing is lost ------------------------------
async def test_qt_nfr_12_maintenance_window_keeps_events_pending_and_loses_nothing(env: SyncEnv) -> None:
    shop = await env.shop("NFR-12")
    pos = await pos_device(env, shop)
    down = True
    inner = echo_handler()

    async def maybe_down(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
        if down:  # the database is in its maintenance window
            raise OperationalError("SELECT 1", {}, Exception("the database system is shutting down"))
        return await inner(s, ctx, payload)

    register(env, ECHO, maybe_down)
    outbox = [event(pos, ECHO, {"n": i}) for i in range(5)]
    during = await push_ok(env, pos, outbox, pending=0)
    assert {(r["status"], r["error_code"], r["retryable"]) for r in during} == {
        ("rejected", "INTERNAL_ERROR", True)
    }
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.sync_receipts") == 0
    device = (await rows(env.db, shop.tenant_id, "SELECT outbox_pending_count FROM app.devices WHERE id = :d",
                         d=pos.device_id))[0]  # fmt: skip
    assert device["outbox_pending_count"] == 5  # visible to the back office as unsynced
    down = False
    after = await drain_outbox(env, pos, outbox)
    assert [r["status"] for r in after] == ["accepted"] * 5
    assert (
        await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'test.echo'")
        == 5
    )


# --- B3-DoD-03: conflicts — overselling by two offline devices -----------------------------------------
async def test_b3_dod_03_two_devices_take_the_last_unit_offline_both_accepted(env: SyncEnv) -> None:
    """16 §5: delta registers — both offline documents are accepted, the balance goes negative."""
    shop = await env.shop("DoD-03")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "1.000", "1000.00")
    a, b = await pos_device(env, shop), await pos_device(env, shop)
    ra, rb = await asyncio.gather(
        push_ok(env, a, [event(a, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]))]),
        push_ok(env, b, [event(b, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]))]),
    )
    assert (ra[0]["status"], rb[0]["status"]) == ("accepted", "accepted")
    qty_left, _ = await balance(env, shop, src, cola)
    assert qty_left == D("-1.000")


# --- QT-NFR-03 / QT-NFR-04 load ---------------------------------------------------------------------------
async def test_qt_nfr_03_read_p95_below_300_ms(env: SyncEnv) -> None:
    shop = await env.shop("NFR-03")
    await set_method(env, shop, "fifo")
    src, _, _ = await two_branches(env, shop)
    for i in range(10):
        pid = await new_product(env, shop, f"Tovar {i}")
        await stock_in(env, shop, src, pid, "10.000", "1000.00")
        await set_price(env.client, shop, str(pid), "1500.0000")
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.products (tenant_id, name, unit_code, vat_rate) "
        "SELECT :t, 'Yuk ' || g, 'box', 12 FROM generate_series(1, 300) g",
        t=shop.tenant_id,
    )  # fmt: skip
    pos = await pos_device(env, shop)
    snapshot = await pull_all(env, pos)
    cursor = snapshot[-1]["cursor"]
    samples: list[float] = []
    for i in range(40):
        t0 = time.perf_counter()
        if i % 2:
            response = await env.client.get("/api/v1/sync/pull", params={"scope": "prices,stock", "cursor": cursor},
                                            headers=pos.h())  # fmt: skip
        else:
            response = await env.client.get("/api/v1/stock-balances", headers=shop.h(key=None))
        samples.append((time.perf_counter() - t0) * 1000)
        assert response.status_code == 200, response.text
    assert p95(samples) < 300, f"read p95 {p95(samples):.0f} ms"


async def test_transfer_posting_through_push_p95_below_800_ms(env: SyncEnv) -> None:
    """The same threshold for the inventory documents (on foot ``transfer.sent``: stock_moves + ledger 2970)."""
    shop = await env.shop("NFR-04")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "500.000", "500000.00")
    pos = await pos_device(env, shop)
    samples: list[float] = []
    for _ in range(30):
        ev = event(pos, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]))
        response, elapsed = await timed_push(env, pos, [ev])
        samples.append(elapsed)
        assert response.status_code == 200 and response.json()["results"][0]["status"] == "accepted", (
            response.text
        )
        await asyncio.sleep(0.21)  # stay under 5 req/s per device
    assert p95(samples) < 800, f"posting p95 {p95(samples):.0f} ms"


async def test_qt_nfr_04_sale_posting_p95_below_800_ms(env: SyncEnv) -> None:
    """QT-NFR-04: ``sale.created`` through ``/sync/push`` — sale + stock + cash + ledger + VAT in one transaction
    (OFD sending is after commit and not measured)."""
    from app.core.db.base import uuid7
    from tests.support.inventory_docs import use_account
    from tests.support.sales import cash_sale_payload, open_shift_sql

    shop = await env.shop("NFR-04 sale")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2920")
    pos = await pos_device(env, shop)
    await execute(
        env.db,
        shop.tenant_id,
        "UPDATE app.cash_registers SET fm_state = 'ok' WHERE id = :r",
        r=pos.register_id,
    )
    assert pos.register_id is not None
    shift = await open_shift_sql(env.db, shop, pos.register_id, pos.device_id, pos.user_id)
    cola = await new_product(env, shop)
    await set_price(env.client, shop, str(cola), "12000.0000")
    await stock_in(env, shop, wh, cola, "100.000", "800000.00")
    samples: list[float] = []
    for n in range(1, 31):
        payload = cash_sale_payload(
            sale_id=uuid7(), branch_id=pos.branch_id, cash_register_id=pos.register_id, shift_id=shift,
            product_id=cola, receipt_seq=n,
        )  # fmt: skip
        response, elapsed = await timed_push(env, pos, [event(pos, "sale.created", payload)])
        samples.append(elapsed)
        assert response.status_code == 200, response.text
        result = response.json()["results"][0]
        assert result["status"] == "accepted", result
        await asyncio.sleep(0.21)  # stay under 5 req/s per device
    assert p95(samples) < 800, f"sale posting p95 {p95(samples):.0f} ms"
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.sales") == 30
