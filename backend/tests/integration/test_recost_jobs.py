"""Negative stock, settlement and recost jobs (13 §3.1, §3.3–§3.4, 16 §5, 19 §18; QT-M04-11).

Scenario for both methods: receipt 10 × 8000 → issue 10 → issue 2 more with 0 in stock (pending at the
last known cost 8000.0000 → 16000.00) → receipt 5 × 9000 settles the 2 pending units from the new lot at
once (stock register exact: 3 × 9000 = 27000.00) and queues a recost job → the job re-posts the pending
issue's cost line: storno 16000.00 + new 18000.00 (``analytics.recost_job_id``).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.accounting.wiring import business_today
from app.modules.inventory.wiring import stock_service
from tests.support.catalog import Env, catalog_env_fixture
from tests.support.inventory import (
    API,
    D,
    avg,
    balance,
    close_period,
    err,
    execute,
    issue,
    ledger,
    lots,
    moves,
    new_product,
    receive,
    rows,
    scalar,
    set_method,
    set_setting,
    stock_txn,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]


async def _job(env: Env, tenant_id: UUID, job_id: UUID) -> dict[str, Any]:
    [job] = await rows(env, tenant_id, "SELECT * FROM app.recost_jobs WHERE id = :id", id=job_id)
    return job


async def _negative_scenario(env: Env, method: str) -> tuple[Any, UUID, UUID, UUID, UUID]:
    shop = await env.shop(f"Manfiy {method}")
    await set_method(env, shop, method)
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "10.000", "80000.00")
    await issue(env, shop, wh, p, "10.000", account_dt="9430")
    res, doc, line = await issue(env, shop, wh, p, "2.000", account_dt="9430")
    assert res.pending_qty == D("2.000") and res.cost == D("16000.00")
    assert [a.as_json() for a in res.allocations] == [
        {"lot_id": None, "qty": "2.000", "unit_cost": "8000.0000", "pending": True}
    ]
    assert await balance(env, shop, wh, p) == (D("-2.000"), D("-16000.00"))
    [line_entry] = await ledger(env, shop, doc)
    assert (line_entry["account_dt"], line_entry["account_kt"], line_entry["amount"]) == (
        "9430",
        "2910",
        D("16000.00"),
    )
    return shop, wh, p, doc, line


@pytest.mark.parametrize("method", ["fifo", "aveco"])
async def test_qt_m04_11_negative_stock_pending_then_recost(env: Env, method: str) -> None:
    shop, wh, p, doc, line = await _negative_scenario(env, method)
    receipt = uuid7()
    res, jobs = await receive(env, shop, wh, p, "5.000", "45000.00", doc_id=receipt)
    assert res.settled_qty == D("2.000") and len(jobs) == 1
    # the stock register is exact at once: 3 × 9000 = 27000.00; the new lot gave 2 to the pending issue
    assert await balance(env, shop, wh, p) == (D("3.000"), D("27000.00"))
    new_lot = (await lots(env, shop, p))[-1]
    assert (new_lot["qty_in"], new_lot["qty_left"], new_lot["unit_cost"]) == (
        D("5.000"),
        D("3.000"),
        D("9000.0000"),
    )
    if method == "aveco":
        assert await avg(env, shop, wh, p) == {
            "qty": D("3.000"),
            "avg_cost": D("9000.0000"),
            "total_value": D("27000.00"),
        }
    issued = await moves(env, shop, p, doc)
    pending_move, storno, settled = issued
    assert (pending_move["lot_id"], pending_move["qty"], pending_move["cost_amount"]) == (
        None,
        D("-2.000"),
        D("-16000.00"),
    )
    assert (storno["reversal_of_id"], storno["qty"], storno["cost_amount"]) == (
        pending_move["id"],
        D("2.000"),
        D("16000.00"),
    )
    assert (settled["lot_id"], settled["qty"], settled["cost_amount"]) == (
        new_lot["id"],
        D("-2.000"),
        D("-18000.00"),
    )
    assert storno["moved_at"] == settled["moved_at"] == pending_move["moved_at"]  # history position kept
    job = await _job(env, shop.tenant_id, jobs[0])
    assert (job["status"], job["from_date"], job["reason_doc_type"], job["reason_doc_id"]) == (
        "queued", business_today(), "goods_receipts", receipt,
    )  # fmt: skip
    # ledger still at the estimate until the job runs
    assert [e["amount"] for e in await ledger(env, shop, doc)] == [D("16000.00")]

    await stock_service(env.settings).enqueue_recost(shop.tenant_id, jobs)
    assert await env.drain() >= 1
    job = await _job(env, shop.tenant_id, jobs[0])
    assert (job["status"], job["attempts"], job["last_error"]) == ("done", 1, None)
    estimate, storno_e, new_e = await ledger(env, shop, doc)
    assert (storno_e["account_dt"], storno_e["account_kt"], storno_e["amount"], storno_e["reversal_of_id"]) == (
        "2910", "9430", D("16000.00"), estimate["id"],
    )  # fmt: skip
    assert (new_e["account_dt"], new_e["account_kt"], new_e["amount"], new_e["reversal_of_id"]) == (
        "9430", "2910", D("18000.00"), None,
    )  # fmt: skip
    assert new_e["analytics"]["recost_job_id"] == str(jobs[0]) == storno_e["analytics"]["recost_job_id"]
    assert new_e["analytics"]["line_id"] == str(line) and new_e["analytics"]["lot_ids"] == [
        str(new_lot["id"])
    ]
    assert new_e["entry_date"] == estimate["entry_date"]  # period open → the original date
    assert "correction_of_period" not in new_e["analytics"]
    # the cost ledger (net Kt 2910 of the issues) equals the stock register of the issues: 80000 + 18000
    gl = await scalar(
        env, shop.tenant_id,
        "SELECT sum(CASE WHEN account_kt = '2910' THEN amount ELSE -amount END) FROM app.ledger_entries "
        "WHERE doc_type = 'write_offs'",
    )  # fmt: skip
    stock = await scalar(
        env, shop.tenant_id, "SELECT -sum(cost_amount) FROM app.stock_moves WHERE doc_type = 'write_offs'"
    )
    assert gl == stock == D("98000.00")
    # GET /recost-jobs/{id} shows the corrected rows; a second run changes nothing
    detail = (await env.client.get(f"{API}/recost-jobs/{jobs[0]}", headers=shop.h(key=None))).json()
    assert detail["status"] == "done" and len(detail["ledger_entries"]) == 2
    assert {m["qty"] for m in detail["stock_moves"]} == {"2.000", "-2.000"}
    await execute(
        env, shop.tenant_id, "UPDATE app.recost_jobs SET status = 'queued' WHERE id = :id", id=jobs[0]
    )
    await stock_service(env.settings).enqueue_recost(shop.tenant_id, jobs)
    await env.drain()
    assert len(await ledger(env, shop, doc)) == 3  # idempotent: stock cost = ledger cost already


async def test_recost_writes_the_cost_line_when_the_estimate_was_zero(env: Env) -> None:
    """No cost known at all → pending at 0, no ledger line (zero lines are skipped), ``sync_exceptions
    (cost_unknown)`` keeps the line template; the recost job then writes Dt 9430 / Kt 2910 = 40000.00."""
    shop = await env.shop("Cost unknown")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    res, doc, line = await issue(env, shop, wh, p, "4.000", account_dt="9430")
    assert (res.cost, res.allocations[0].unit_cost) == (D("0.00"), D("0.0000"))
    assert await ledger(env, shop, doc) == []
    [exc] = await rows(env, shop.tenant_id, "SELECT kind, doc_type, doc_id, details FROM app.sync_exceptions")
    assert (exc["kind"], exc["doc_type"], exc["doc_id"]) == ("cost_unknown", "write_offs", doc)
    assert exc["details"]["cost_line"]["account_dt"] == "9430" and exc["details"]["line_id"] == str(line)
    _, jobs = await receive(env, shop, wh, p, "10.000", "100000.00")
    await stock_service(env.settings).enqueue_recost(shop.tenant_id, jobs)
    await env.drain()
    [entry] = await ledger(env, shop, doc)
    assert (entry["account_dt"], entry["account_kt"], entry["amount"]) == ("9430", "2910", D("40000.00"))
    assert entry["analytics"]["recost_job_id"] == str(jobs[0])


async def test_recost_correction_lands_in_the_open_period_when_the_original_is_closed(env: Env) -> None:
    """13 §3.4: the pending issue was posted last month, which is now closed — storno + new line are dated
    the first open date with ``analytics.correction_of_period``; the closed month is untouched."""
    shop = await env.shop("Closed recost")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    last_month = (business_today().replace(day=1) - timedelta(days=1)).replace(day=1)
    await receive(env, shop, wh, p, "1.000", "5000.00")
    await issue(env, shop, wh, p, "1.000", account_dt="9430", entry_date=last_month)
    _, doc, _ = await issue(env, shop, wh, p, "1.000", account_dt="9430", entry_date=last_month)
    await close_period(env, shop, last_month)
    _, jobs = await receive(env, shop, wh, p, "1.000", "7000.00")
    await stock_service(env.settings).enqueue_recost(shop.tenant_id, jobs)
    await env.drain()
    estimate, storno, new = await ledger(env, shop, doc)
    assert estimate["entry_date"] == last_month and estimate["amount"] == D("5000.00")
    label = f"{last_month.year:04d}-{last_month.month:02d}"
    for row in (storno, new):
        assert row["entry_date"] == business_today()
        assert row["analytics"]["correction_of_period"] == label
    assert (storno["amount"], new["amount"]) == (D("5000.00"), D("7000.00"))


async def test_partial_settlement_keeps_the_rest_pending(env: Env) -> None:
    shop = await env.shop("Partial")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "1.000", "1000.00")
    await issue(env, shop, wh, p, "1.000")
    res, doc, _ = await issue(env, shop, wh, p, "5.000")
    assert res.cost == D("5000.00")
    first, jobs = await receive(env, shop, wh, p, "3.000", "3600.00")  # 1200.0000 each
    assert first.settled_qty == D("3.000")
    assert await balance(env, shop, wh, p) == (D("-2.000"), D("-2000.00"))
    doc_moves = await moves(env, shop, p, doc)
    reversed_ids = {m["reversal_of_id"] for m in doc_moves if m["reversal_of_id"]}
    live = [m for m in doc_moves if m["reversal_of_id"] is None and m["id"] not in reversed_ids]
    assert sorted((m["lot_id"] is None, m["qty"], m["cost_amount"]) for m in live) == [
        (False, D("-3.000"), D("-3600.00")),
        (True, D("-2.000"), D("-2000.00")),
    ]
    second, jobs2 = await receive(env, shop, wh, p, "2.000", "3000.00")  # 1500.0000 each
    assert second.settled_qty == D("2.000") and jobs2 == jobs  # merged into the still-queued job
    assert await balance(env, shop, wh, p) == (D("0.000"), D("0.00"))
    await stock_service(env.settings).enqueue_recost(shop.tenant_id, [*jobs, *jobs2])
    await env.drain()
    entries = await ledger(env, shop, doc)
    net = sum(e["amount"] if e["reversal_of_id"] is None else -e["amount"] for e in entries)
    assert net == D("3600.00") + D("3000.00")  # 3 × 1200 + 2 × 1500


async def test_negative_stock_policy_block(env: Env) -> None:
    shop = await env.shop("Block")
    await set_setting(env, shop, "negative_stock_policy", "block")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "1.000", "1000.00")
    with pytest.raises(AppError) as exc:
        await issue(env, shop, wh, p, "3.000")
    assert exc.value.code is ErrorCode.NEGATIVE_STOCK_NOT_ALLOWED
    assert exc.value.params == {
        "warehouse_id": str(wh), "product_id": str(p), "requested": "3.000", "available": "1.000",
    }  # fmt: skip
    assert await balance(env, shop, wh, p) == (D("1.000"), D("1000.00"))


async def test_cancel_issue_after_settlement_restores_the_new_lot(env: Env) -> None:
    shop, wh, p, doc, _ = await _negative_scenario(env, "fifo")
    await receive(env, shop, wh, p, "5.000", "45000.00")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_issue("write_offs", doc)
    assert (await lots(env, shop, p))[-1]["qty_left"] == D("5.000")
    assert await balance(env, shop, wh, p) == (D("5.000"), D("45000.00"))


async def test_recost_retry_rules(env: Env) -> None:
    shop = await env.shop("Retry")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    ids = {status: uuid7() for status in ("failed", "done", "rejected_period_closed")}
    for status, job_id in ids.items():
        await execute(
            env, shop.tenant_id,
            "INSERT INTO app.recost_jobs (id, tenant_id, warehouse_id, product_id, from_date, status, reason_doc_type, "
            "reason_doc_id, attempts, last_error) VALUES (:id, :t, :w, :p, :f, :s, 'goods_receipts', :r, 1, 'x')",
            id=job_id, t=shop.tenant_id, w=wh, p=p, f=date(2026, 10, 1), s=status, r=uuid7(),
        )  # fmt: skip
    queued = uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.recost_jobs (id, tenant_id, warehouse_id, product_id, from_date, status, reason_doc_type, "
        "reason_doc_id) VALUES (:id, :t, :w, :p, :f, 'queued', 'goods_receipts', :r)",
        id=queued, t=shop.tenant_id, w=wh, p=p, f=date(2026, 9, 1), r=uuid7(),
    )  # fmt: skip
    url = f"{API}/recost-jobs"
    done = await env.client.post(f"{url}/{ids['done']}/retry", headers=shop.h())
    assert done.status_code == 409 and err(done) == "DOC_INVALID_STATE"
    rejected = await env.client.post(f"{url}/{ids['rejected_period_closed']}/retry", headers=shop.h())
    assert rejected.status_code == 409 and err(rejected) == "RECOST_REJECTED_PERIOD_CLOSED"
    missing = await env.client.post(f"{url}/{uuid7()}/retry", headers=shop.h())
    assert missing.status_code == 404 and missing.json()["error"]["params"] == {"resource": "recost_job"}
    key = str(uuid7())
    ok = await env.client.post(f"{url}/{ids['failed']}/retry", headers=shop.h(key=key))
    assert ok.status_code == 200, ok.text
    body = ok.json()
    # one queued job per key: the failed one absorbs the queued one (from_date → the earliest)
    assert (body["status"], body["from_date"]) == ("queued", "2026-09-01")
    assert (await _job(env, shop.tenant_id, queued))["status"] == "done"
    replay = await env.client.post(f"{url}/{ids['failed']}/retry", headers=shop.h(key=key))
    assert (
        replay.status_code == 200
        and replay.json() == body
        and replay.headers["Idempotent-Replayed"] == "true"
    )
    listed = (await env.client.get(url, params={"status": "queued"}, headers=shop.h(key=None))).json()
    assert [j["id"] for j in listed["items"]] == [str(ids["failed"])]
    page = (await env.client.get(url, params={"limit": 2}, headers=shop.h(key=None))).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = (
        await env.client.get(
            url, params={"limit": 2, "cursor": page["next_cursor"]}, headers=shop.h(key=None)
        )
    ).json()
    assert len(rest["items"]) == 2 and rest["next_cursor"] is None
    audit = await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'recost_job.retried'"
    )
    assert audit == 1


async def test_recost_retry_needs_accounting_post(env: Env) -> None:
    from app.modules.access.domain.permissions import SystemRole

    shop = await env.shop("Retry perm", SystemRole.OWNER, SystemRole.STOREKEEPER)
    resp = await env.client.post(f"{API}/recost-jobs/{uuid7()}/retry", headers=shop.h("storekeeper"))
    assert resp.status_code == 403 and err(resp) == "PERMISSION_DENIED"


async def _queued_job(env: Env, label: str) -> tuple[Any, UUID]:
    shop, wh, p, _, _ = await _negative_scenario(env, "fifo")
    _, jobs = await receive(env, shop, wh, p, "5.000", "45000.00")
    [job_id] = jobs
    return shop, job_id


async def test_recost_run_failure_is_recorded_in_a_new_transaction(env: Env, monkeypatch: Any) -> None:
    """SEC-04: claim + process + done in ONE transaction; an error rolls it back and a new transaction
    marks the job ``failed`` with ``attempts = 1``."""
    from app.modules.inventory.application.recost import RecostService
    from app.modules.inventory.wiring import recost_service

    shop, job_id = await _queued_job(env, "fail")

    async def boom(*_: Any, **__: Any) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(RecostService, "process", boom)
    result = await recost_service(env.db.session_factory, env.settings).run(shop.tenant_id, job_id)
    assert result == {"status": "failed"}
    job = await _job(env, shop.tenant_id, job_id)
    assert (job["status"], job["attempts"], job["last_error"]) == ("failed", 1, "RuntimeError: boom")
    assert job["finished_at"] is not None


async def test_recost_dead_worker_leaves_the_job_queued(env: Env, monkeypatch: Any) -> None:
    """SEC-04: ``running`` is only visible inside the run's transaction — a worker that dies mid-run
    (the transaction rolls back) leaves the job ``queued`` (attempts 0) for the sweeper to re-run."""
    import asyncio

    from app.modules.inventory.application.recost import RecostService
    from app.modules.inventory.wiring import recost_service

    shop, job_id = await _queued_job(env, "dead")
    real = RecostService.process

    async def killed(*_: Any, **__: Any) -> int:
        raise asyncio.CancelledError

    monkeypatch.setattr(RecostService, "process", killed)
    service = recost_service(env.db.session_factory, env.settings)
    with pytest.raises(asyncio.CancelledError):
        await service.run(shop.tenant_id, job_id)
    job = await _job(env, shop.tenant_id, job_id)
    assert (job["status"], job["attempts"], job["finished_at"]) == ("queued", 0, None)
    monkeypatch.setattr(RecostService, "process", real)
    result = await service.run(shop.tenant_id, job_id)
    assert result == {"status": "done", "corrected_lines": 1}
    job = await _job(env, shop.tenant_id, job_id)
    assert (job["status"], job["attempts"]) == ("done", 1)
    assert await service.run(shop.tenant_id, job_id) == {"skipped": True}


async def test_recost_retry_merges_the_queued_job_of_the_key(env: Env) -> None:
    """SEC-09: retry takes the stock lock of the key, then the job rows (the posters' order) — a failed
    job retried while a queued one exists for the same key absorbs it, no unique-index error."""
    shop, job_id = await _queued_job(env, "merge")
    failed = await _job(env, shop.tenant_id, job_id)
    await execute(
        env,
        shop.tenant_id,
        "UPDATE app.recost_jobs SET status = 'failed', attempts = 1 WHERE id = :id",
        id=job_id,
    )
    queued = uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.recost_jobs (id, tenant_id, warehouse_id, product_id, from_date, status, reason_doc_type, "
        "reason_doc_id) VALUES (:id, :t, :w, :p, :f, 'queued', 'goods_receipts', :r)",
        id=queued, t=shop.tenant_id, w=failed["warehouse_id"], p=failed["product_id"],
        f=failed["from_date"] - timedelta(days=1), r=uuid7(),
    )  # fmt: skip
    ok = await env.client.post(f"{API}/recost-jobs/{job_id}/retry", headers=shop.h())
    assert ok.status_code == 200, ok.text
    assert (ok.json()["status"], ok.json()["from_date"]) == (
        "queued", (failed["from_date"] - timedelta(days=1)).isoformat(),
    )  # fmt: skip
    merged = await _job(env, shop.tenant_id, queued)
    assert (merged["status"], merged["last_error"]) == ("done", f"merged into recost job {job_id}")
    await env.drain()
    job = await _job(env, shop.tenant_id, job_id)
    assert (job["status"], job["attempts"]) == ("done", 2)
