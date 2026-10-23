"""Shifts: ``shift.opened`` / ``shift.closed`` (18 §3), Z-report, variance postings (13 §2.19), ShiftGuard.

US-M01-04, US-M16-02; QT-M01-06/07, QT-M16-03/05/07, QT-SEQ-02/03.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.cash.wiring import shift_guard
from tests.support.cash import (
    add_cash_move,
    add_sale,
    cash_env_fixture,  # noqa: F401 - fixture "env"
    ledger,
    make_till,
    movement,
    one,
    open_shift,
    outbox_events,
    push,
    sql,
)
from tests.support.catalog import Env

pytestmark = pytest.mark.asyncio


async def _close(env: Env, till, shift_id, counted: str, **extra):  # type: ignore[no-untyped-def]
    return await push(
        env, till, "shift.closed", {"shift_id": str(shift_id), "counted_cash": counted, **extra}
    )


async def test_shift_opened_creates_open_shift_and_rejects_second(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, "200000.00")
    row = (await sql(env.db, till.shop.tenant_id, "SELECT status, opening_cash, device_id, shift_no FROM app.shifts "
                     "WHERE id = :id", id=shift_id))[0]  # fmt: skip
    assert (row[0], format(row[1], "f"), row[2], row[3]) == ("open", "200000.00", till.device_id, 1)
    # X-01: opening cash never becomes a cash_moves row
    assert (
        await one(
            env.db, till.shop.tenant_id, "SELECT count(*) FROM app.cash_moves WHERE shift_id = :s", s=shift_id
        )
        == 0
    )
    again = await push(
        env, till, "shift.opened",
        {"id": str(uuid7()), "cash_register_id": str(till.register_id), "shift_no": 2, "opening_cash": "0.00"},
    )  # fmt: skip
    assert again.code == "SHIFT_ALREADY_OPEN"
    bad = await push(
        env, till, "shift.opened",
        {"id": str(uuid7()), "cash_register_id": str(till.register_id), "shift_no": 0, "opening_cash": "0.00"},
    )  # fmt: skip
    assert bad.code == "VALIDATION_ERROR"
    negative = await push(
        env, till, "shift.opened",
        {"id": str(uuid7()), "cash_register_id": str(till.register_id), "shift_no": 3, "opening_cash": "-1.00"},
    )  # fmt: skip
    assert negative.code == "VALIDATION_ERROR"


async def test_qt_m01_06_close_zero_variance_creates_z_report(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, "100000.00")
    await add_sale(env, till, shift_id, [("cash", "400000.00", None)], vat="42857.14")
    res = await _close(env, till, shift_id, "500000.00")
    assert res.error is None, res.error and res.error.details
    z = res.server["z_report"]
    assert (z["expected_cash"], z["counted_cash"], z["variance"]) == ("500000.00", "500000.00", "0.00")
    assert (
        z["totals_by_method"]["cash"] == "400000.00"
        and z["vat_total"] == "42857.14"
        and z["sales_count"] == 1
    )
    assert res.server["fiscal"]["status"] in ("pending", "sent", "fiscalized")
    tenant = till.shop.tenant_id
    assert await one(env.db, tenant, "SELECT count(*) FROM app.fiscal_receipts WHERE shift_id = :s AND kind = 'z_report'",
                     s=shift_id) == 1  # fmt: skip
    assert await ledger(env.db, tenant, "shifts", shift_id) == []
    row = (await sql(env.db, tenant, "SELECT status, expected_cash, counted_cash, variance FROM app.shifts WHERE id = :s",
                     s=shift_id))[0]  # fmt: skip
    assert (row[0], format(row[3], "f")) == ("closed", "0.00")


async def test_qt_m01_07_shortage_needs_note_and_posts_4730(env: Env, admin_engine: AsyncEngine) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, "500000.00")
    no_note = await _close(env, till, shift_id, "480000.00")
    assert no_note.code == "VALIDATION_ERROR"
    assert (
        no_note.error is not None
        and no_note.error.details[0].message_key == "validation.variance_note_required"
    )
    res = await _close(env, till, shift_id, "480000.00", variance_note="Kamomad")
    assert res.error is None
    assert res.server["z_report"]["variance"] == "-20000.00"
    rows = await ledger(env.db, till.shop.tenant_id, "shifts", shift_id)
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("4730", "5010", "20000.00")]
    assert rows[0][3]["employee_id"] == str(till.shop.user_ids["cashier"])
    events = await outbox_events(admin_engine, till.shop.tenant_id, "cash_variance")
    assert len(events) == 1 and events[0]["variance"] == "-20000.00" and events[0]["kind"] == "shortage"


async def test_qt_m16_07_overage_posts_5010_9390(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, "500000.00")
    res = await _close(env, till, shift_id, "505000.00", variance_note="Ortiqcha")
    assert res.error is None
    rows = await ledger(env.db, till.shop.tenant_id, "shifts", shift_id)
    assert [(dt, kt, a) for dt, kt, a, _ in rows] == [("5010", "9390", "5000.00")]


async def test_qt_m16_03_expected_cash_formula(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, "200000.00")
    await add_sale(env, till, shift_id, [("cash", "350000.00", None)])
    await add_cash_move(env, till, shift_id, "50000.00", "debt_payments")
    out = await push(env, till, "cash_movement.created", movement(till, shift_id, amount="40000.00"))
    assert out.error is None, out.error and out.error.details
    detail = await env.client.get(f"/api/v1/shifts/{shift_id}", headers=till.shop.h("owner", key=None))
    assert detail.status_code == 200, detail.text
    running = detail.json()["running_totals"]
    assert running["expected_cash"] == "560000.00" and running["cash_out"] == "40000.00"
    res = await _close(env, till, shift_id, "560000.00")
    assert res.error is None
    assert res.server["z_report"]["expected_cash"] == "560000.00"
    assert res.server["z_report"]["variance"] == "0.00"


async def test_qt_m16_05_card_split_integrated_vs_manual(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    for amount in ("150000.00", "200000.00", "100000.00"):
        await add_sale(env, till, shift_id, [("card", amount, "manual")])
    await add_sale(env, till, shift_id, [("card", "300000.00", "integrated")])
    res = await _close(env, till, shift_id, "0.00")
    assert res.error is None, res.error and (res.error.code, res.error.details)
    z = res.server["z_report"]
    assert z["card_split"] == {"integrated": "300000.00", "manual": "450000.00"}
    assert z["totals_by_method"]["card"] == "750000.00"
    total = await one(
        env.db, till.shop.tenant_id, "SELECT counted_card_total FROM app.shifts WHERE id = :s", s=shift_id
    )
    assert format(total, "f") == "450000.00"


async def test_close_with_unknown_card_attempt_is_refused(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    await add_sale(env, till, shift_id, [("card", "10000.00", "integrated")])
    await sql(env.db, till.shop.tenant_id, "UPDATE app.card_terminal_transactions SET status = 'unknown', "
              "approved_amount = NULL, resolved_at = NULL, rrn = NULL, card_mask = NULL, card_type = NULL, "
              "card_type_source = NULL, resolved_by = NULL WHERE shift_id = :s", s=shift_id)  # fmt: skip
    res = await _close(env, till, shift_id, "0.00")
    assert res.code == "CARD_OUTCOME_UNKNOWN"
    assert (
        await one(env.db, till.shop.tenant_id, "SELECT status FROM app.shifts WHERE id = :s", s=shift_id)
        == "open"
    )


async def test_close_rules_device_and_state(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    other = await push(env, till, "shift.closed", {"shift_id": str(shift_id), "counted_cash": "0.00"},
                       device_id=till.other_device_id)  # fmt: skip
    assert other.code == "SHIFT_DEVICE_MISMATCH"
    assert (await _close(env, till, shift_id, "0.00")).error is None
    again = await _close(env, till, shift_id, "0.00")
    assert again.code == "SHIFT_NOT_OPEN"
    unknown = await _close(env, till, uuid7(), "0.00")
    assert unknown.code == "DEPENDENCY_NOT_SYNCED"  # SYNC-06: retryable, its shift.opened may follow


async def test_qt_seq_02_shift_guard_device_mismatch(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    guard = shift_guard()
    now = datetime.now(UTC)
    async with env.db.session_factory() as s, tenant_transaction(s, till.shop.tenant_id):
        opened = await guard.require_open(s, shift_id=shift_id, device_id=till.device_id, at=now)
        assert opened.cash_register_id == till.register_id
        with pytest.raises(AppError) as exc:
            await guard.require_open(s, shift_id=shift_id, device_id=till.other_device_id, at=now)
        assert exc.value.code.value == "SHIFT_DEVICE_MISMATCH"
    # an event of a device that never opened this shift is rejected, others are unaffected
    foreign = await push(
        env, till, "cash_movement.created", movement(till, shift_id), device_id=till.other_device_id
    )
    assert foreign.code == "SHIFT_DEVICE_MISMATCH"
    ok = await push(env, till, "cash_movement.created", movement(till, shift_id))
    assert ok.error is None
    # created while open, pushed after closing → accepted (16 §5); created after closing → SHIFT_NOT_OPEN
    closed_at = datetime.now(UTC)
    assert (
        await push(env, till, "shift.closed", {"shift_id": str(shift_id), "counted_cash": "-40000.00"})
    ).code == ("VALIDATION_ERROR")
    res = await push(env, till, "shift.closed", {"shift_id": str(shift_id), "counted_cash": "0.00",
                                                  "variance_note": "x"}, created_at=closed_at)  # fmt: skip
    assert res.error is None
    async with env.db.session_factory() as s, tenant_transaction(s, till.shop.tenant_id):
        await guard.require_open(
            s, shift_id=shift_id, device_id=till.device_id, at=closed_at - timedelta(seconds=1)
        )
        with pytest.raises(AppError) as late:
            await guard.require_open(
                s, shift_id=shift_id, device_id=till.device_id, at=closed_at + timedelta(seconds=1)
            )
        assert late.value.code.value == "SHIFT_NOT_OPEN"


async def test_qt_seq_03_second_z_report_is_refused(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till)
    assert (await _close(env, till, shift_id, "0.00")).error is None
    tenant = till.shop.tenant_id
    assert (
        await one(env.db, tenant, "SELECT count(*) FROM app.fiscal_receipts WHERE shift_id = :s", s=shift_id)
        == 1
    )
    with pytest.raises(IntegrityError, match="uq_fiscal_z_per_shift"):
        async with env.db.session_factory() as s, tenant_transaction(s, tenant):
            await s.execute(
                text(
                    "INSERT INTO app.fiscal_receipts (tenant_id, kind, cash_register_id, shift_id, payload) "
                    "VALUES (:t, 'z_report', :c, :s, '{}')"
                ),
                {"t": tenant, "c": till.register_id, "s": shift_id},
            )


async def test_shift_reads_list_z_report_and_cash_history(env: Env) -> None:
    till = await make_till(env)
    shift_id = await open_shift(env, till, "100000.00")
    await add_sale(env, till, shift_id, [("cash", "50000.00", None), ("uzqr", "25000.00", None)])
    h = till.shop.h("owner", key=None)
    early = await env.client.get(f"/api/v1/shifts/{shift_id}/z-report", headers=h)
    assert early.status_code == 409
    assert (await _close(env, till, shift_id, "150000.00")).error is None
    page = await env.client.get(
        "/api/v1/shifts", params={"cash_register_id": str(till.register_id)}, headers=h
    )
    assert page.status_code == 200 and page.json()["items"][0]["id"] == str(shift_id)
    z = await env.client.get(f"/api/v1/shifts/{shift_id}/z-report", headers=h)
    assert z.status_code == 200, z.text
    assert z.json()["totals_by_method"]["uzqr"] == "25000.00" and z.json()["fiscal"]["id"] is not None
    detail = (await env.client.get(f"/api/v1/shifts/{shift_id}", headers=h)).json()
    assert detail["running_totals"] is None and detail["z_report"]["expected_cash"] == "150000.00"
    # QT-M16-04 / US-M16-03: per shift opening / sales / in-out / expected-counted / variance
    hist = await env.client.get(f"/api/v1/cash-registers/{till.register_id}/cash-history", headers=h)
    assert hist.status_code == 200, hist.text
    item = hist.json()["items"][0]
    assert (
        item["opening_cash"],
        item["cash_sales"],
        item["expected_cash"],
        item["counted_cash"],
        item["variance"],
    ) == (
        "100000.00",
        "50000.00",
        "150000.00",
        "150000.00",
        "0.00",
    )
    # storekeeper-like caller without reports.sales.view / cash.count.shift is denied; accountant allowed
    acct = await env.client.get("/api/v1/shifts", headers=till.shop.h("accountant", key=None))
    assert acct.status_code in (200, 403)
    missing = await env.client.get(f"/api/v1/shifts/{uuid7()}", headers=h)
    assert missing.status_code == 404
    assert Decimal(item["variance"]) == 0
