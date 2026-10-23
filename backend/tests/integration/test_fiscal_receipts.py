"""Fiscal receipts: fake FM outbox, retry, 48 h rule, FM state, monitor (18 §4.10, §14; 16 §6; 21 §1)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.integrations.fiscal.wiring import (
    effective_created_at,
    fake_fiscal_adapter,
    fiscal_service,
    unacked_monitor,
)
from tests.support.sales import (
    API,
    Env,
    Pos,
    add_customer,
    deliver,
    execute,
    fiscalize,
    make_pos,
    new_item,
    one,
    rows,
    sale_line,
    sale_payload,
    sales_env_fixture,
    sell,
)

QR = re.compile(r"^https://ofd\.soliq\.uz/check\?t=\w{14}&r=\d+&c=\d{14}&s=\d{12}$")


pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def _sale_at(env: Env, pos: Pos, product: Any, at: datetime, actor: str = "cashier") -> Any:
    return await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)], is_offline=True),
                         created_at=at, received_at=at, actor=actor)  # fmt: skip


async def _events(env: Env, pos: Pos) -> list[dict[str, Any]]:
    return await rows(
        env.db, pos.tenant_id,
        "SELECT payload FROM app.outbox_jobs WHERE kind = 'telegram' AND payload->>'event' = 'offline_48h' "
        "ORDER BY (payload->>'stage') COLLATE \"C\"",
    )  # fmt: skip


# --- fake FM outbox (21 §1) ------------------------------------------------------------------------------
async def test_qt_m01_21_fake_fm_requisites(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(pos, [sale_line(product)])
    await sell(env, pos, payload)
    assert await fiscalize(env, pos) == 1
    r = (
        await rows(
            env.db, pos.tenant_id, "SELECT * FROM app.fiscal_receipts WHERE sale_id = :d", d=payload["id"]
        )
    )[0]
    assert (
        r["status"] == "fiscalized"
        and r["fm_terminal_id"].startswith("ZZ")
        and len(r["fm_terminal_id"]) == 14
    )
    assert r["fm_receipt_seq"] != r["receipt_seq"] and re.fullmatch(r"\d{12}", r["fiscal_sign"])
    assert QR.match(r["qr_url"]) and r["payment_form"] == "cash" and r["delivery"] == "printed"
    assert r["fiscal_at"] is not None and r["ofd_acked_at"] is not None
    assert (
        await one(env.db, pos.tenant_id, "SELECT status FROM app.outbox_jobs WHERE kind = 'ofd_send'")
        == "done"
    )


async def test_qt_m01_29_fiscal_failed_and_retry(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    payload = sale_payload(pos, [sale_line(product)])
    await sell(env, pos, payload)
    fake = fake_fiscal_adapter()
    fake.fail = "transient"
    await fiscalize(env, pos)
    status = await rows(env.db, pos.tenant_id, "SELECT f.status, f.attempts, j.status AS job FROM app.fiscal_receipts f "
                        "JOIN app.outbox_jobs j ON j.kind = 'ofd_send' WHERE f.sale_id = :d", d=payload["id"])  # fmt: skip
    assert status == [{"status": "pending", "attempts": 1, "job": "retry"}]
    backoff = await one(
        env.db, pos.tenant_id, "SELECT next_run_at - updated_at FROM app.outbox_jobs WHERE kind = 'ofd_send'"
    )
    assert backoff == timedelta(seconds=30)  # first retry: DB now() + 30 s (OFD_BASE_S)
    await execute(
        env.db,
        pos.tenant_id,
        "UPDATE app.outbox_jobs SET next_run_at = now() - interval '1 hour' WHERE kind = 'ofd_send'",
    )
    fake.fail = "validation"
    await fiscalize(env, pos)
    receipt_id = await one(
        env.db, pos.tenant_id, "SELECT id FROM app.fiscal_receipts WHERE sale_id = :d", d=payload["id"]
    )
    assert (
        await one(env.db, pos.tenant_id, "SELECT status FROM app.fiscal_receipts WHERE id = :i", i=receipt_id)
        == "failed"
    )
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'fiscal.send_failed'"
        )
        == 1
    )
    listed = await env.client.get(
        f"{API}/fiscal-receipts", params={"status": "failed"}, headers=pos.shop.h("accountant")
    )
    assert listed.status_code == 200 and [i["id"] for i in listed.json()["items"]] == [str(receipt_id)]
    denied = await env.client.post(f"{API}/fiscal-receipts/{receipt_id}/retry", headers=pos.shop.h("cashier"))
    assert denied.status_code == 403
    retried = await env.client.post(
        f"{API}/fiscal-receipts/{receipt_id}/retry", headers=pos.shop.h("accountant")
    )
    assert retried.status_code == 200 and retried.json() == {"status": "requeued"}
    fake.fail = None
    await fiscalize(env, pos)
    got = await env.client.get(f"{API}/fiscal-receipts/{receipt_id}", headers=pos.shop.h("cashier"))
    assert got.status_code == 200 and got.json()["status"] == "fiscalized"
    again = await env.client.post(
        f"{API}/fiscal-receipts/{receipt_id}/retry", headers=pos.shop.h("accountant")
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "DOC_INVALID_STATE"


async def test_qt_seq_03_one_z_report_per_shift(env: Env) -> None:
    pos = await make_pos(env)
    svc = fiscal_service(env.settings)
    from app.core.errors import AppError

    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await svc.record(s, kind="z_report", doc_id=pos.shift_id, cash_register_id=pos.register_id,
                         shift_id=pos.shift_id, receipt_seq=None, payment_form=None, payload={"z": 1},
                         fiscal_result=None, is_offline=False, offline_since=None)  # fmt: skip
    with pytest.raises(AppError) as caught:
        async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
            await svc.record(s, kind="z_report", doc_id=pos.shift_id, cash_register_id=pos.register_id,
                             shift_id=pos.shift_id, receipt_seq=None, payment_form=None, payload={"z": 2},
                             fiscal_result=None, is_offline=False, offline_since=None)  # fmt: skip
    assert caught.value.details[0].message_key == "validation.z_report_exists"


# --- 48 h rule (qaror #43, fake clock) ------------------------------------------------------------------
async def test_qt_offline48_01_warning_stages(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    t0 = datetime.now(UTC) - timedelta(hours=1)
    assert (await _sale_at(env, pos, product, t0)).error is None
    monitor = unacked_monitor(env.db.session_factory)
    report = await monitor.run(pos.tenant_id, t0 + timedelta(hours=23))
    assert report.events == 0
    for hours, stage in ((24, 24), (40, 40), (46, 46)):
        await monitor.run(pos.tenant_id, t0 + timedelta(hours=hours, minutes=1))
        assert stage in {e["payload"]["stage"] for e in await _events(env, pos)}
    await monitor.run(pos.tenant_id, t0 + timedelta(hours=46, minutes=30))  # same stage → no duplicate event
    assert len(await _events(env, pos)) == 3
    # sales are not stopped before 48 h (46 h is a warning only)
    late = await _sale_at(env, pos, product, t0 + timedelta(hours=47, minutes=59))
    assert late.error is None


async def test_qt_offline48_02_clamped_device_clock(env: Env) -> None:
    received = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    assert effective_created_at(received - timedelta(days=10), received) == received - timedelta(days=7)
    assert effective_created_at(received + timedelta(hours=3), received) == received + timedelta(seconds=300)
    assert effective_created_at(received - timedelta(hours=5), received) == received - timedelta(hours=5)


async def test_qt_offline48_03_block_at_48h(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    t0 = datetime.now(UTC) - timedelta(hours=60)
    sold = await _sale_at(env, pos, product, t0)
    assert sold.error is None
    at48 = t0 + timedelta(hours=48)
    assert (await _sale_at(env, pos, product, at48)).code == "FISCAL_OFFLINE_48H_BLOCKED"
    assert (await _sale_at(env, pos, product, at48, actor="owner")).code == "FISCAL_OFFLINE_48H_BLOCKED"
    line_id = await one(
        env.db, pos.tenant_id, "SELECT id FROM app.sale_lines WHERE sale_id = :d", d=sold.server["id"]
    )
    ret = {
        "id": str(uuid7()), "branch_id": str(pos.branch_id),
        "shift_id": str(pos.shift_id), "cash_register_id": str(pos.register_id), "receipt_seq": pos.next_seq(),
        "sale_id": sold.server["id"], "is_offline": True, "reason": "other", "refund_method": "cash",
        "lines": [{"sale_line_id": str(line_id),
                   "product_id": str(product), "qty": "1.000", "price": "12000.0000", "vat_rate": "12.00"}],
    }  # fmt: skip
    blocked_return = await deliver(env, pos, "return.created", ret, created_at=at48, received_at=at48)
    assert blocked_return.code == "FISCAL_OFFLINE_48H_BLOCKED"
    # non-fiscal operations keep working: a debt-only sale (no receipt), a draft void
    customer = await add_customer(env, pos)
    debt = await deliver(env, pos, "sale.created",
                         sale_payload(pos, [sale_line(product)], [{"method": "debt", "amount": "12000.00"}],
                                      counterparty_id=str(customer), is_offline=True),
                         created_at=at48, received_at=at48)  # fmt: skip
    assert debt.error is None
    assert (await deliver(env, pos, "sale.draft_voided", {"draft_ref": "x"}, created_at=at48)).error is None
    report = await unacked_monitor(env.db.session_factory).run(pos.tenant_id, at48 + timedelta(minutes=1))
    assert report.blocked == 1
    assert await one(env.db, pos.tenant_id,
                     "SELECT count(*) FROM app.audit_log WHERE action = 'fiscal.offline_48h_blocked'") == 1  # fmt: skip
    assert 48 in {e["payload"]["stage"] for e in await _events(env, pos)}


async def test_qt_offline48_04_auto_unblock_and_next_oldest(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    t0 = datetime.now(UTC) - timedelta(hours=70)
    t1 = t0 + timedelta(hours=10)
    first_sale = await _sale_at(env, pos, product, t0)
    assert first_sale.error is None
    assert (await _sale_at(env, pos, product, t1)).error is None
    monitor = unacked_monitor(env.db.session_factory)
    await monitor.run(pos.tenant_id, t0 + timedelta(hours=49))
    assert (await _sale_at(env, pos, product, t0 + timedelta(hours=49))).code == "FISCAL_OFFLINE_48H_BLOCKED"
    first = await one(
        env.db,
        pos.tenant_id,
        "SELECT id FROM app.fiscal_receipts WHERE sale_id = :d",
        d=first_sale.server["id"],
    )
    await execute(
        env.db, pos.tenant_id, "UPDATE app.fiscal_receipts SET ofd_acked_at = now() WHERE id = :i", i=first
    )
    # the timer now runs from t1 (the oldest unacked receipt)
    assert (await _sale_at(env, pos, product, t0 + timedelta(hours=50))).error is None
    report = await monitor.run(pos.tenant_id, t0 + timedelta(hours=50))
    assert report.unblocked == 1
    assert (await _sale_at(env, pos, product, t1 + timedelta(hours=48))).code == "FISCAL_OFFLINE_48H_BLOCKED"
    # internet back: the fake FM fiscalizes and acks everything → the block lifts by itself
    await fiscalize(env, pos)
    unacked = await one(
        env.db, pos.tenant_id, "SELECT count(*) FROM app.fiscal_receipts WHERE ofd_acked_at IS NULL"
    )
    assert unacked == 0
    assert (await _sale_at(env, pos, product, t1 + timedelta(hours=49))).error is None


async def test_qt_nfr_06_offline_receipts_within_48h(env: Env) -> None:
    """QT-NFR-06 = QT-OFFLINE48-01/03: a receipt made offline is sendable up to 48 h, then the register blocks."""
    pos = await make_pos(env)
    product = await new_item(env, pos)
    t0 = datetime.now(UTC) - timedelta(hours=50)
    assert (await _sale_at(env, pos, product, t0)).error is None
    assert (await _sale_at(env, pos, product, t0 + timedelta(hours=47))).error is None
    assert (await _sale_at(env, pos, product, t0 + timedelta(hours=48))).code == "FISCAL_OFFLINE_48H_BLOCKED"


async def test_qt_offline48_05_fm_state(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    await execute(
        env.db,
        pos.tenant_id,
        "UPDATE app.cash_registers SET fm_state = 'locked' WHERE id = :r",
        r=pos.register_id,
    )
    res = await deliver(env, pos, "sale.created", sale_payload(pos, [sale_line(product)]))
    assert (
        res.code == "FISCAL_DEVICE_LOCKED"
        and res.error is not None
        and res.error.params["fm_state"] == "locked"
    )
    await execute(
        env.db,
        pos.tenant_id,
        "UPDATE app.cash_registers SET fm_state = 'unknown' WHERE id = :r",
        r=pos.register_id,
    )
    await sell(env, pos, sale_payload(pos, [sale_line(product)]))  # fake FM answers 'ok' for a new register
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT fm_state FROM app.cash_registers WHERE id = :r", r=pos.register_id
        )
        == "ok"
    )


async def test_sync_15_ack_clears_last_unacked_at_once(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    t0 = datetime.now(UTC) - timedelta(hours=30)
    assert (await _sale_at(env, pos, product, t0)).error is None
    await unacked_monitor(env.db.session_factory).run(pos.tenant_id)
    query = "SELECT last_unacked_receipt_at FROM app.cash_registers WHERE id = :r"
    assert await one(env.db, pos.tenant_id, query, r=pos.register_id) is not None
    assert await fiscalize(env, pos) == 1  # the fake FM acks → no monitor run needed
    assert await one(env.db, pos.tenant_id, query, r=pos.register_id) is None
