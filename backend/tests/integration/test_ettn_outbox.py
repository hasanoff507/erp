"""e-TTN outbox (21 §0, §3; 19 §20; 27 B2): ``outbox_jobs(kind='ettn_send')`` claimed with SKIP LOCKED,
the operator called outside the business transaction, transient errors retried with backoff (1 min ×2,
cap 1 h, 24 tries), permanent ones dead-lettered; the telegram outbox is never touched."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.integrations.einvoice.application.ettn_outbox import EttnOutboxService
from app.modules.integrations.einvoice.infrastructure.ettn_sql import SqlEttnOutboxRepository
from app.modules.integrations.einvoice.tasks import einvoice_ettn_sweep
from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter
from tests.support.catalog import Env, Shop
from tests.support.inventory import err, execute, new_product, rows, scalar, set_method
from tests.support.inventory_docs import (
    act,
    create_transfer,
    docs_env_fixture,
    ok,
    principal_of,
    stock_in,
    two_branches,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["docs_env_fixture"]


def _service(env: Env, port: FakeEInvoiceAdapter) -> EttnOutboxService:
    return EttnOutboxService(env.db.session_factory, SqlEttnOutboxRepository(), port, rand=lambda: 0.0)


async def _posted_vehicle_transfer(env: Env, name: str) -> tuple[Shop, dict[str, Any]]:
    shop = await env.shop(name)
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    await stock_in(env, shop, src, p, "5.000", "25000.00")
    doc = await create_transfer(env, shop, src, dst, [(p, "1.000")])
    posted = await ok(await act(env, shop, doc["id"], "post"))
    await _due_now(env, shop)  # enqueued at the post's DB now(); the test VM clock may step back since
    return shop, posted


async def _job(env: Env, shop: Shop) -> dict[str, Any]:
    [job] = await rows(
        env, shop.tenant_id,
        "SELECT id, status, attempts, next_run_at, last_error, updated_at FROM app.outbox_jobs WHERE kind = 'ettn_send'",
    )  # fmt: skip
    return job


async def _ettn(env: Env, shop: Shop) -> dict[str, Any]:
    [row] = await rows(
        env, shop.tenant_id, "SELECT id, status, last_error, operator_doc_id FROM app.ettn_documents"
    )
    return row


async def _due_now(env: Env, shop: Shop, **values: Any) -> None:
    """Make the job due: an hour back, so a DB clock that steps backwards (~1 s) still sees it as due."""
    sets = ", ".join(f"{k} = :{k}" for k in values)
    extra = f", {sets}" if sets else ""
    await execute(
        env, shop.tenant_id,
        f"UPDATE app.outbox_jobs SET next_run_at = now() - interval '1 hour'{extra} WHERE kind = 'ettn_send'",
        **values,
    )  # fmt: skip


async def test_transient_errors_retry_with_backoff_then_dead_letter(env: Env) -> None:
    shop, doc = await _posted_vehicle_transfer(env, "e-TTN retry")
    down = FakeEInvoiceAdapter(fail=True)
    service = _service(env, down)
    first = await service.run(shop.tenant_id)
    assert first is not None and (first.status, first.ettn_status) == ("retry", "sending")
    job = await _job(env, shop)
    assert (job["status"], job["attempts"]) == ("retry", 1) and "down" in job["last_error"]
    # next_run_at = the database now() + backoff (jitter 0) — the same clock as updated_at and the claim
    assert job["next_run_at"] - job["updated_at"] == timedelta(minutes=1)
    ettn = await _ettn(env, shop)
    assert ettn["status"] == "sending" and "down" in ettn["last_error"]
    assert await service.run(shop.tenant_id) is None  # not due yet

    await _due_now(env, shop)
    await service.run(shop.tenant_id)
    job = await _job(env, shop)
    assert job["attempts"] == 2
    assert job["next_run_at"] - job["updated_at"] == timedelta(minutes=2)

    await _due_now(env, shop, attempts=10)
    await service.run(shop.tenant_id)
    job = await _job(env, shop)
    assert job["attempts"] == 11
    assert job["next_run_at"] - job["updated_at"] == timedelta(hours=1)  # cap 1 h

    await _due_now(env, shop, attempts=23)
    last = await service.run(shop.tenant_id)
    assert last is not None and (last.status, last.ettn_status) == ("failed", "failed")
    job = await _job(env, shop)
    assert (job["status"], job["attempts"]) == ("failed", 24) and "24 attempts" in job["last_error"]
    assert (await _ettn(env, shop))["status"] == "failed"
    assert await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'ettn.send_failed'"
    ) == 1  # fmt: skip
    refused = await act(env, shop, doc["id"], "send")
    assert refused.status_code == 409 and err(refused) == "ETTN_REQUIRED"
    assert refused.json()["error"]["params"]["ettn_status"] == "failed"


async def test_permanent_rejection_fails_at_once_and_recovery_registers(env: Env) -> None:
    shop, doc = await _posted_vehicle_transfer(env, "e-TTN reject")
    outcome = await _service(env, FakeEInvoiceAdapter(reject_ettn=True)).run(shop.tenant_id)
    assert outcome is not None and outcome.status == "failed"
    job = await _job(env, shop)
    assert (job["status"], job["attempts"]) == ("failed", 1) and job["last_error"].startswith("validation")
    assert (await _ettn(env, shop))["status"] == "failed"

    shop2, doc2 = await _posted_vehicle_transfer(env, "e-TTN recover")
    await _service(env, FakeEInvoiceAdapter(fail=True)).run(shop2.tenant_id)
    await _due_now(env, shop2)
    ok_port = FakeEInvoiceAdapter()
    done = await _service(env, ok_port).run(shop2.tenant_id)
    assert done is not None and (done.status, done.ettn_status) == ("done", "registered")
    ettn = await _ettn(env, shop2)
    assert (
        ettn["status"] == "registered"
        and ettn["last_error"] is None
        and ettn["operator_doc_id"] == done.operator_doc_id
    )
    assert list(ok_port.sent_ettn) == [ettn["id"]]
    ref = await scalar(
        env, shop2.tenant_id, "SELECT ettn_ref FROM app.transfers WHERE id = :id", id=UUID(doc2["id"])
    )
    assert ref == done.operator_doc_id
    assert (await ok(await act(env, shop2, doc2["id"], "send")))["status"] == "sent"
    assert doc["ettn"]["status"] == "pending_signature"


async def test_claim_is_exclusive_and_telegram_jobs_are_never_touched(env: Env) -> None:
    shop, _ = await _posted_vehicle_transfer(env, "e-TTN claim")
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.outbox_jobs (tenant_id, kind, payload, idempotency_key) "
        "VALUES (:t, 'telegram', '{\"event\": \"low_stock\"}', 'tg-probe')",
        t=shop.tenant_id,
    )  # fmt: skip
    port = FakeEInvoiceAdapter()
    service = _service(env, port)
    results = await asyncio.gather(service.run(shop.tenant_id), service.run(shop.tenant_id))
    assert sorted(r is None for r in results) == [False, True]
    assert len(port.sent_ettn) == 1
    [tg] = await rows(
        env, shop.tenant_id, "SELECT status, attempts FROM app.outbox_jobs WHERE kind = 'telegram'"
    )
    assert (tg["status"], tg["attempts"]) == ("queued", 0)
    assert await service.process_due(shop.tenant_id) == []


async def test_sweeper_runs_through_saq_and_reclaims_a_dead_worker(env: Env) -> None:
    shop, doc = await _posted_vehicle_transfer(env, "e-TTN sweep")
    result = await einvoice_ettn_sweep(
        {"db": env.db, "settings": env.settings}, tenant_id=str(shop.tenant_id)
    )
    assert result == {"processed": 1, "statuses": ["done"]}
    job = await _job(env, shop)
    assert (job["status"], job["attempts"]) == ("done", 1)
    got = await ok(await env.client.get(f"/api/v1/transfers/{doc['id']}", headers=shop.h(key=None)))
    assert got["ettn"]["status"] == "registered" and got["ettn_ref"] == got["ettn"]["operator_doc_id"]

    shop2, _ = await _posted_vehicle_transfer(env, "e-TTN dead worker")
    await execute(env, shop2.tenant_id, "UPDATE app.outbox_jobs SET status = 'running', attempts = 1")
    await execute(env, shop2.tenant_id, "UPDATE app.ettn_documents SET status = 'sending'")
    fresh = EttnOutboxService(env.db.session_factory, SqlEttnOutboxRepository(), FakeEInvoiceAdapter())
    assert await fresh.process_due(shop2.tenant_id) == []  # a live worker holds it (< 10 min)
    # stale threshold −60 s (not 0): updated_at comes from the DB now() (trigger), and the test VM clock can
    # step back ~1 s between the two transactions — this still treats the running job as a dead worker's
    stale = EttnOutboxService(
        env.db.session_factory, SqlEttnOutboxRepository(stale_running_s=-60), FakeEInvoiceAdapter()
    )
    [outcome] = await stale.process_due(shop2.tenant_id)
    assert (outcome.status, outcome.ettn_status) == ("done", "registered")
    assert ((await _job(env, shop2))["attempts"]) == 2


async def test_real_operator_keeps_the_ettn_waiting_for_the_sign_flow(env: Env) -> None:
    """``einvoice_provider='faktura_uz'``: post creates the e-TTN but no outbox job (Bosqich 5 E-IMZO)."""
    from app.modules.inventory.wiring import transfer_service

    shop = await env.shop("e-TTN real operator")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    p = await new_product(env, shop)
    doc = await create_transfer(env, shop, src, dst, [(p, "1.000")])
    real = env.settings.model_copy(update={"einvoice_provider": "faktura_uz"})
    service = transfer_service(env.db.session_factory, real)
    actor, scope = await principal_of(env, shop)
    body = await service.post(actor, scope, UUID(doc["id"]), None)
    assert body["ettn"]["status"] == "pending_signature"
    assert (
        await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE kind = 'ettn_send'")
        == 0
    )
