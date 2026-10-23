"""Month closing — ``/period-closings`` + readiness (20 #14–#16; 13 §5.1, §5.5, §3.4; qaror #23, #69; US-M11-02;
QT-M11-02/-05/-06/-12/-14; B5-T13, B5-T16, ACC-09). Every test owns its tenant and its months."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.accounting.wiring import TASHKENT, business_today
from tests.support.accounting import (
    API,
    PC,
    D,
    Env,
    add_ledger,
    adjust,
    adjust_ok,
    close,
    close_sql,
    err,
    keys,
    label,
    month_end,
    months_ago,
    readiness,
    sales_env_fixture,
    set_go_live,
    shop,
)
from tests.support.inventory import new_product, receive, use_account
from tests.support.purchasing import create_supplier, gr_line, posted_receipt
from tests.support.sales import execute, make_pos, new_item, one, rows, sale_line, sale_payload, sell

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


# --- QT-M11-02 / QT-M11-06 / PERIOD_CLOSE_OUT_OF_ORDER ---------------------------------------------------
async def test_qt_m11_02_close_oldest_month_and_qt_m11_06_reclose_409(env: Env) -> None:
    s = await shop(env)
    m = months_ago(2)
    m1 = months_ago(1)
    await set_go_live(env, s, m + timedelta(days=1))  # first activity = m (openings on go_live − 1)
    await add_ledger(env, s, "5010", "9020", "100000.00", m + timedelta(days=5))
    await add_ledger(env, s, "5010", "6410", "12000.00", m + timedelta(days=5), tax_type="vat")
    await add_ledger(env, s, "9420", "5010", "30000.00", m + timedelta(days=7))

    early = await close(env, s, m1)
    assert early.status_code == 409 and err(early) == "PERIOD_CLOSE_OUT_OF_ORDER"
    assert early.json()["error"]["params"] == {"period": label(m1), "expected_period": label(m)}
    cashier = await close(env, s, m, role="cashier")
    assert cashier.status_code == 403
    ready = await readiness(env, s, m)
    assert ready["ready"] is True and ready["blockers"] == []

    closed = await close(env, s, m, role="accountant")
    assert closed.status_code == 201, closed.text
    assert closed.json()["period"] == label(m) and closed.json()["closed_by"] == str(s.user_ids["accountant"])
    again = await close(env, s, m)
    assert again.status_code == 409 and err(again) == "PERIOD_ALREADY_CLOSED"
    listed = await env.client.get(PC, headers=s.h("accountant", key=None))
    assert [i["period"] for i in listed.json()["items"]] == [label(m)]
    audit = await one(
        env.db, s.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'period_closing.posted'"
    )
    assert audit == 1

    # US-M11-02: the month's balance sheet and P&L are formed
    pl = await env.client.get(
        f"{API}/reports/profit-and-loss", params={"period": label(m)}, headers=s.h(key=None)
    )
    assert pl.status_code == 200 and pl.json()["net_profit"] == "70000.00"
    sheet = await env.client.get(f"{API}/reports/balance-sheet", params={"as_of": month_end(m).isoformat()},
                                 headers=s.h(key=None))  # fmt: skip
    assert sheet.status_code == 200, sheet.text
    body = sheet.json()
    assert body["assets"] == [
        {"account": "5010", "name": "Milliy valyutadagi pul mablag'lari", "amount": "82000.00"}
    ]
    assert {(x["account"], x["amount"]) for x in body["liabilities"]} == {("6410", "12000.00")}
    assert {(x["account"], x["amount"]) for x in body["equity"]} == {("9910", "70000.00")}
    assert body["total_assets"] == body["total_liabilities_and_equity"] == "82000.00"

    current = await close(env, s, months_ago(0))
    assert current.status_code == 409 and err(current) == "PERIOD_CLOSE_OUT_OF_ORDER"
    second = await close(env, s, m1)
    assert second.status_code == 201, second.text
    not_ended = await close(env, s, months_ago(0))
    assert not_ended.status_code == 422 and "validation.period_not_ended" in keys(not_ended)


# --- QT-M11-05 -----------------------------------------------------------------------------------------
async def test_qt_m11_05_recost_pending_blocks_close(env: Env) -> None:
    s = await shop(env)
    m = months_ago(1)
    await set_go_live(env, s, m + timedelta(days=1))
    product = await new_product(env, s)
    wh = await use_account(env, s, "2920")
    job = uuid7()
    await execute(
        env.db, s.tenant_id,
        "INSERT INTO app.recost_jobs (id, tenant_id, warehouse_id, product_id, from_date, status, reason_doc_type, "
        "reason_doc_id) VALUES (:id, :t, :w, :p, :d, 'queued', 'sales', :r)",
        id=job, t=s.tenant_id, w=wh, p=product, d=m + timedelta(days=10), r=uuid7(),
    )  # fmt: skip
    ready = await readiness(env, s, m)
    assert (
        ready["ready"] is False
        and ready["blockers"] == ["recost_pending"]
        and ready["pending_recost_jobs"] == 1
    )
    refused = await close(env, s, m)
    assert refused.status_code == 409 and err(refused) == "PERIOD_CLOSE_NOT_READY"
    assert refused.json()["error"]["params"]["blockers"] == ["recost_pending"]
    assert await one(env.db, s.tenant_id, "SELECT count(*) FROM app.period_closings") == 0
    await execute(env.db, s.tenant_id, "UPDATE app.recost_jobs SET status = 'done' WHERE id = :id", id=job)
    assert (await close(env, s, m)).status_code == 201


# --- QT-M11-14 (qaror #69, 16 §3.4) + devices_unsynced + fiscal_pending ----------------------------------
async def test_qt_m11_14_late_sale_into_closed_month(env: Env) -> None:
    pos = await make_pos(env)
    s = pos.shop
    m = months_ago(2)
    m1 = months_ago(1)
    product = await new_item(env, pos)
    await close_sql(env, s, m)
    created = datetime.combine(month_end(m), time(18, 0), tzinfo=TASHKENT)
    payload = sale_payload(pos, [sale_line(product)], is_offline=True, doc_date=month_end(m).isoformat())
    res = await sell(env, pos, payload, created_at=created, received_at=created + timedelta(days=3))
    sale_id = UUID(payload["id"])
    late = [e for e in res.result.sync_exceptions if e.kind == "late_in_closed_period"] if res.result else []
    assert late and dict(late[0].details)["period"] == label(m)
    assert dict(late[0].details)["doc_date"] == month_end(m).isoformat()
    assert await one(
        env.db, s.tenant_id, "SELECT doc_date FROM app.sales WHERE id = :d", d=sale_id
    ) == month_end(m)
    lines = await rows(env.db, s.tenant_id, "SELECT entry_date, account_dt, account_kt, analytics FROM "
                       "app.ledger_entries WHERE doc_id = :d", d=sale_id)  # fmt: skip
    assert lines and {x["entry_date"] for x in lines} == {m1}
    money_lines = [x for x in lines if x["account_dt"] == "5010"]
    assert money_lines and all(x["analytics"].get("correction_of_period") == label(m) for x in money_lines)
    vat = await rows(env.db, s.tenant_id, "SELECT period FROM app.vat_moves WHERE doc_id = :d", d=sale_id)
    assert vat == [{"period": m1}]
    moved = await one(
        env.db, s.tenant_id, "SELECT min(moved_at) FROM app.stock_moves WHERE doc_id = :d", d=sale_id
    )
    assert moved == created.astimezone(UTC)

    # back-office REST document dated in the closed month → 409 PERIOD_CLOSED (QT-M11-03)
    rest = await adjust(env, s, "9430", "5010", "1.00", day=month_end(m))
    assert rest.status_code == 409 and err(rest) == "PERIOD_CLOSED"

    # an active device with pending outbox events older than the end of m1 blocks closing m1
    oldest = datetime.combine(month_end(m1), time(12, 0), tzinfo=TASHKENT)
    await execute(
        env.db, s.tenant_id,
        "UPDATE app.devices SET outbox_pending_count = 2, outbox_oldest_pending_at = :o, last_sync_at = :o "
        "WHERE id = :d", o=oldest, d=pos.device_id,
    )  # fmt: skip
    await execute(env.db, s.tenant_id, "UPDATE app.devices SET created_at = :c", c=m1)
    # the late receipt is still unsent to the OFD; b5-fiscal dates a receipt by its creation (contracts/fiscal.md)
    await execute(
        env.db, s.tenant_id, "UPDATE app.fiscal_receipts SET created_at = :c WHERE sale_id = :d",
        c=oldest, d=sale_id,
    )  # fmt: skip
    ready = await readiness(env, s, m1)
    assert "devices_unsynced" in ready["blockers"] and "fiscal_pending" in ready["blockers"]
    assert ready["pending_fiscal_receipts"] >= 1
    assert ready["unsynced_devices"] == [
        {"device_id": str(pos.device_id), "cash_register_name": "K1", "outbox_pending_count": 2,
         "outbox_oldest_pending_at": oldest.astimezone(UTC).isoformat().replace("+00:00", "Z")}
    ]  # fmt: skip
    assert "devices_not_synced_after_period_end" in ready["warnings"]
    refused = await close(env, s, m1)
    assert refused.status_code == 409 and err(refused) == "PERIOD_CLOSE_NOT_READY"
    assert "devices_unsynced" in refused.json()["error"]["params"]["blockers"]
    out_of_order = await close(env, s, months_ago(0))
    assert out_of_order.status_code == 409 and err(out_of_order) == "PERIOD_CLOSE_OUT_OF_ORDER"
    # resolution: the device is revoked → no longer a blocker
    await execute(
        env.db, s.tenant_id, "UPDATE app.devices SET revoked_at = now() WHERE id = :d", d=pos.device_id
    )
    assert "devices_unsynced" not in (await readiness(env, s, m1))["blockers"]


# --- QT-M11-12 / 13 §5.5 -------------------------------------------------------------------------------
async def test_13_5_5_qt_m11_12_opening_0000_warns_never_blocks(env: Env) -> None:
    s = await shop(env)
    m = months_ago(1)
    go_live = m + timedelta(days=1)
    opening_day = m  # go_live − 1
    await set_go_live(env, s, go_live)
    # stock (QT-M04-04) and debt (QT-M08-10) openings are in, cash and capital are not yet
    await add_ledger(env, s, "2920", "0000", "1000000.00", opening_day, doc_type="stock_openings")
    await add_ledger(env, s, "4010", "0000", "300000.00", opening_day, doc_type="debt_openings")
    as_of = {"as_of": month_end(m).isoformat()}
    sheet = (await env.client.get(f"{API}/reports/balance-sheet", params=as_of, headers=s.h(key=None))).json()
    assert sheet["warnings"] == ["opening_0000_nonzero"] and sheet["opening_balance_unresolved"] is True
    assert sheet["opening_0000_balance"] == "-1300000.00"
    assert sheet["total_assets"] == sheet["total_liabilities_and_equity"] == "1300000.00"
    ready = await readiness(env, s, m)
    assert "opening_0000_nonzero" in ready["warnings"] and ready["opening_balance_unresolved"] is True
    assert ready["ready"] is True  # never a blocker

    await adjust_ok(env, s, "5010", "0000", "200000.00", day=opening_day, comment="Kassa qoldig'i")
    await adjust_ok(env, s, "0000", "8330", "1500000.00", day=opening_day, comment="Ustav kapitali")
    sheet = (await env.client.get(f"{API}/reports/balance-sheet", params=as_of, headers=s.h(key=None))).json()
    assert sheet["warnings"] == [] and sheet["opening_0000_balance"] == "0.00"
    assert {(x["account"], x["amount"]) for x in sheet["assets"]} == {
        ("2920", "1000000.00"), ("4010", "300000.00"), ("5010", "200000.00"),
    }  # fmt: skip
    assert sheet["equity"] == [{"account": "8330", "name": "Ulushlar va paylar (ustav kapitali)",
                                "amount": "1500000.00"}]  # fmt: skip
    assert sheet["total_assets"] == sheet["total_liabilities_and_equity"] == "1500000.00"
    assert "opening_0000_nonzero" not in (await readiness(env, s, m))["warnings"]
    assert (await close(env, s, m)).status_code == 201


# --- B5-T16 tax_settlement_missing / tax_settlement_stale ---------------------------------------------
async def test_b5_t16_tax_settlement_stale_warning(env: Env) -> None:
    s = await shop(env)
    m = months_ago(1)
    await set_go_live(env, s, m + timedelta(days=1))

    async def input_vat(vat: str) -> None:
        await execute(
            env.db, s.tenant_id,
            "INSERT INTO app.vat_moves (tenant_id, period, kind, base_amount, vat_amount, doc_type, doc_id) "
            "VALUES (:t, :p, 'input', CAST(:v AS numeric) * 100 / 12, CAST(:v AS numeric), 'goods_receipts', :d)",
            t=s.tenant_id, p=m, v=vat, d=uuid7(),
        )  # fmt: skip

    await input_vat("84000.00")
    await add_ledger(env, s, "4410", "6010", "84000.00", m + timedelta(days=3), tax_type="vat")
    assert "tax_settlement_missing" in (await readiness(env, s, m))["warnings"]
    created = await env.client.post(f"{API}/tax-settlements", json={"tax_kind": "vat_offset", "period": label(m)},
                                    headers=s.h("accountant", branch=s.branch_id))  # fmt: skip
    assert created.status_code == 201, created.text
    posted = await env.client.post(f"{API}/tax-settlements/{created.json()['id']}/post",
                                   headers=s.h("accountant", branch=s.branch_id))  # fmt: skip
    assert posted.status_code == 200, posted.text
    ready = await readiness(env, s, m)
    assert (
        "tax_settlement_missing" not in ready["warnings"] and "tax_settlement_stale" not in ready["warnings"]
    )
    await input_vat("1200.00")  # a late input VAT of the same month after the settlement was posted
    ready = await readiness(env, s, m)
    assert "tax_settlement_stale" in ready["warnings"] and ready["ready"] is True
    assert ready["stale_tax_settlements"] == [
        {"id": created.json()["id"], "tax_kind": "vat_offset", "branch_id": None, "amount": "84000.00",
         "current_amount": "85200.00"}
    ]  # fmt: skip


# --- ACC-09: GL inventory ↔ stock register, doc_date stock report ------------------------------------
async def test_acc09_ledger_stock_mismatch_warning(env: Env) -> None:
    s = await shop(env)
    m = months_ago(1)
    await set_go_live(env, s, m + timedelta(days=1))
    product = await new_product(env, s)
    wh = await use_account(env, s, "2920")
    assert "ledger_stock_mismatch" not in (await readiness(env, s, m))["warnings"]
    await receive(env, s, wh, product, "5.000", "40000.00")  # stock register only — no ledger line
    ready = await readiness(env, s, m)
    assert "ledger_stock_mismatch" in ready["warnings"]
    assert ready["ledger_stock_mismatches"] == [
        {"account": "2920", "ledger_balance": "0.00", "stock_value": "40000.00", "difference": "-40000.00"}
    ]


async def test_acc09_stock_as_of_by_doc_date(env: Env) -> None:
    s = await shop(env)
    m = months_ago(1)
    await set_go_live(env, s, m + timedelta(days=1))
    product = await new_product(env, s)
    wh = await use_account(env, s, "2910")
    supplier = await create_supplier(env.client, s)
    doc_date = m + timedelta(days=10)  # back-dated receipt: ledger on doc_date, stock moved today
    await posted_receipt(env.client, s, supplier["id"], wh, [gr_line(product, "10.000", "1120.0000", "12.00")],
                         doc_date=doc_date)  # fmt: skip
    url = f"{API}/reports/stock-as-of"
    at_end = await env.client.get(url, params={"as_of": month_end(m).isoformat()}, headers=s.h(key=None))
    assert at_end.status_code == 200, at_end.text
    body = at_end.json()
    assert [(i["product_id"], i["qty"]) for i in body["items"]] == [(str(product), "10.000")]
    account = body["accounts"][0]
    assert account["account"] == "2910" and account["stock_value"] == account["ledger_value"]
    assert account["difference"] == "0.00" and D(account["stock_value"]) > 0
    before = await env.client.get(url, params={"as_of": (doc_date - timedelta(days=1)).isoformat()},
                                  headers=s.h(key=None))  # fmt: skip
    assert before.json()["items"] == []
    future = await env.client.get(url, params={"as_of": (business_today() + timedelta(days=1)).isoformat()},
                                  headers=s.h(key=None))  # fmt: skip
    assert future.status_code == 422
