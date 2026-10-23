"""M10 reads: ``GET /reports/vat-summary`` and ``GET /vat-moves`` (20 #1–#2; 13 §4.2, §4.3, §2.26)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from tests.support.cash import (
    cash_env_fixture,  # noqa: F401 - fixture "env"
    sql,
)
from tests.support.catalog import Env

pytestmark = pytest.mark.asyncio


async def _vat(
    env: Env, tenant: UUID, kind: str, base: str, vat: str, period: date, einvoice: UUID | None = None
) -> None:
    await sql(
        env.db, tenant,
        "INSERT INTO app.vat_moves (tenant_id, period, kind, base_amount, vat_amount, doc_type, doc_id, einvoice_id) "
        "VALUES (:t, :p, :k, :b, :v, :dt, :d, :e)",
        t=tenant, p=period, k=kind, b=base, v=vat, dt="sales" if kind == "output" else "goods_receipts", d=uuid7(),
        e=einvoice,
    )  # fmt: skip


async def _entry(
    env: Env, tenant: UUID, branch: UUID, dt: str, kt: str, amount: str, day: date, **an: str
) -> None:
    import json

    await sql(
        env.db, tenant,
        "INSERT INTO app.ledger_entries (tenant_id, entry_date, branch_id, account_dt, account_kt, amount, doc_type, "
        "doc_id, analytics) VALUES (:t, :d, :b, :dt, :kt, :a, 'test', :doc, CAST(:an AS jsonb))",
        t=tenant, d=day, b=branch, dt=dt, kt=kt, a=amount, doc=uuid7(), an=json.dumps(an),
    )  # fmt: skip


async def test_vat_summary_vat_regime_with_pending_red_invoice(env: Env) -> None:
    shop = await env.shop("QQS do'kon")
    tenant = shop.tenant_id
    await _vat(env, tenant, "output", "1000000.00", "120000.00", date(2026, 9, 1))
    await _vat(env, tenant, "input", "700000.00", "84000.00", date(2026, 9, 1))
    await _vat(env, tenant, "output", "50000.00", "6000.00", date(2026, 8, 1))  # another period
    supplier = uuid7()
    await sql(env.db, tenant, "INSERT INTO app.counterparties (id, tenant_id, kind, name, is_supplier) "
              "VALUES (:id, :t, 'company', 'Ta''minotchi', true)", id=supplier, t=tenant)  # fmt: skip
    for risk, vat in (("red", "12000.00"), ("green", "5000.00")):
        await sql(env.db, tenant, "INSERT INTO app.einvoices (tenant_id, direction, operator, counterparty_id, status, "
                  "doc_date, total_amount, vat_amount, risk_flag) VALUES (:t, 'in', 'didox', :c, 'received', "
                  "'2026-09-10', 112000, :v, :r)", t=tenant, c=supplier, v=vat, r=risk)  # fmt: skip
    res = await env.client.get(
        "/api/v1/reports/vat-summary", params={"period": "2026-09"}, headers=shop.h(key=None)
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["regime"], body["output_vat"], body["input_vat"], body["net_vat"]) == (
        "vat",
        "120000.00",
        "84000.00",
        "36000.00",
    )
    assert body["pending_credit_red_invoices"] == 1 and body["pending_credit_pct"] == "12.50"
    assert body["turnover_base"] is None and body["tax_settlement_id"] is None
    bad = await env.client.get(
        "/api/v1/reports/vat-summary", params={"period": "2026-9"}, headers=shop.h(key=None)
    )
    assert bad.status_code == 422
    month = await env.client.get(
        "/api/v1/reports/vat-summary", params={"period": "2026-13"}, headers=shop.h(key=None)
    )
    assert month.status_code == 422
    moves = await env.client.get("/api/v1/vat-moves", params={"period": "2026-09", "kind": "output"},
                                 headers=shop.h(key=None))  # fmt: skip
    assert moves.status_code == 200
    items = moves.json()["items"]
    assert [(i["kind"], i["vat_amount"], i["doc_type"], i["period"]) for i in items] == [
        ("output", "120000.00", "sales", "2026-09")
    ]
    page = await env.client.get("/api/v1/vat-moves", params={"limit": 1}, headers=shop.h(key=None))
    assert page.json()["next_cursor"]
    nxt = await env.client.get("/api/v1/vat-moves", params={"limit": 1, "cursor": page.json()["next_cursor"]},
                               headers=shop.h(key=None))  # fmt: skip
    assert nxt.json()["items"][0]["id"] != page.json()["items"][0]["id"]


async def test_vat_summary_turnover_regime_13_4_3_example(env: Env) -> None:
    shop = await env.shop("Aylanma do'kon")
    tenant, branch = shop.tenant_id, shop.branch_id
    await sql(env.db, tenant, "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) "
              "VALUES (:t, '2026-01-01', 'turnover', :u)", t=tenant, u=shop.user_ids["owner"])  # fmt: skip
    day = date(2026, 9, 15)
    await _entry(env, tenant, branch, "5010", "9020", "50000000.00", day)
    await _entry(env, tenant, branch, "9040", "5010", "1000000.00", day)
    await _entry(
        env, tenant, branch, "9050", "9020", "500000.00", day
    )  # gross_9050: Dt 9050 / Kt 9020 nets out
    await _entry(env, tenant, branch, "9020", "5010", "500000.00", day)
    await _entry(env, tenant, branch, "5010", "9390", "200000.00", day)
    await _entry(env, tenant, branch, "2920", "8530", "300000.00", day)
    await _entry(env, tenant, branch, "5010", "9020", "1.00", date(2026, 10, 1))  # other period
    res = await env.client.get(
        "/api/v1/reports/vat-summary", params={"period": "2026-09"}, headers=shop.h(key=None)
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["regime"] == "turnover" and body["output_vat"] is None
    # 9020 = 50 500 000 − 500 000, 9040 = 1 000 000, 9050 = 500 000, 9390 = 200 000, 8530 = 300 000
    # → base 49 000 000 × 4% (retail_city_100k_plus) = 1 960 000 (13 §4.3 example)
    assert (body["turnover_base"], body["turnover_rate_pct"], body["turnover_amount"]) == (
        "49000000.00",
        "4.00",
        "1960000.00",
    )
    no_tax = await env.client.get("/api/v1/reports/vat-summary", params={"period": "2026-09"},
                                  headers=shop.h("owner", key=None) | {"X-Branch-Id": str(branch)})  # fmt: skip
    assert no_tax.status_code == 200


async def test_vat_reads_need_tax_vat_view(env: Env) -> None:
    from app.modules.access.domain.permissions import SystemRole

    shop = await env.shop("Ruxsat", SystemRole.OWNER, SystemRole.CASHIER)
    denied = await env.client.get("/api/v1/vat-moves", headers=shop.h("cashier", key=None))
    assert denied.status_code == 403
    denied = await env.client.get("/api/v1/reports/vat-summary", params={"period": "2026-09"},
                                  headers=shop.h("cashier", key=None))  # fmt: skip
    assert denied.status_code == 403


async def test_sec_11_vat_summary_honours_branch_scope(env: Env) -> None:
    from app.modules.access.domain.permissions import SystemRole
    from tests.support.inventory import add_branch

    shop = await env.shop("Filial QQS", SystemRole.OWNER, SystemRole.ACCOUNTANT)
    tenant, b1 = shop.tenant_id, shop.branch_id
    b2, _ = await add_branch(env, shop, "02", "Ikkinchi")
    await sql(env.db, tenant, "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) "
              "VALUES (:t, '2026-01-01', 'turnover', :u)", t=tenant, u=shop.user_ids["owner"])  # fmt: skip
    await sql(env.db, tenant, "UPDATE app.memberships SET branch_ids = CAST(:b AS uuid[]) WHERE user_id = :u",
              b=[str(b1)], u=shop.user_ids["accountant"])  # fmt: skip
    day = date(2026, 9, 10)
    await _entry(env, tenant, b1, "5010", "9020", "1000000.00", day)
    await _entry(env, tenant, b2, "5010", "9020", "3000000.00", day)
    acct = shop.h("accountant", key=None)
    other = await env.client.get("/api/v1/reports/vat-summary", params={"period": "2026-09", "branch_id": str(b2)},
                                 headers=acct)  # fmt: skip
    assert other.status_code == 403
    mine = await env.client.get("/api/v1/reports/vat-summary", params={"period": "2026-09"}, headers=acct)
    assert mine.status_code == 200, mine.text
    assert mine.json()["turnover_base"] == "1000000.00"
    everything = await env.client.get("/api/v1/reports/vat-summary", params={"period": "2026-09"},
                                      headers=shop.h(key=None))  # fmt: skip
    assert everything.json()["turnover_base"] == "4000000.00"
    moves = await env.client.get("/api/v1/vat-moves", headers=acct)
    assert moves.status_code == 403  # tenant-wide register
    await sql(env.db, tenant, "UPDATE app.tenant_tax_regimes SET regime = 'vat'")
    vat = await env.client.get("/api/v1/reports/vat-summary", params={"period": "2026-09"}, headers=acct)
    assert vat.status_code == 403  # VAT is a tenant figure (qaror #31)
