"""M10 internal VAT register — red/``unknown`` incoming e-invoices shown separately with a not-yet-confirmed
credit (US-M10-03, QT-M10-04, 13 §2.8, 20 #1 ``pending_credit_invoices``, BO-07/BO-10 data)."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from tests.support.accounting import API, Env, Shop, customer, label, months_ago, sales_env_fixture, shop
from tests.support.sales import execute

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def _einvoice(env: Env, s: Shop, supplier: UUID, risk: str, vat: str, day: date) -> UUID:
    eid = uuid7()
    await execute(
        env.db, s.tenant_id,
        "INSERT INTO app.einvoices (id, tenant_id, direction, operator, counterparty_id, status, risk_flag, number, "
        "doc_date, total_amount, vat_amount) VALUES (:id, :t, 'in', 'faktura', :c, 'accepted', :r, :n, :d, "
        "CAST(:v AS numeric) * 112 / 12, CAST(:v AS numeric))",
        id=eid, t=s.tenant_id, c=supplier, r=risk, n=f"EF-{eid.hex[-6:]}", d=day, v=vat,
    )  # fmt: skip
    return eid


async def test_qt_m10_04_red_invoice_shown_separately_credit_unconfirmed(env: Env) -> None:
    s = await shop(env)
    supplier = await customer(env, s, '"Qizil" MChJ')
    m = months_ago(1)
    day = m + timedelta(days=5)
    red = await _einvoice(env, s, supplier, "red", "12000.00", day)
    unknown = await _einvoice(env, s, supplier, "unknown", "6000.00", day)
    await _einvoice(env, s, supplier, "green", "24000.00", day)  # green: credit on receipt, not listed
    # partly paid unknown invoice: 13 §2.16 opened 2 000.00 of its credit
    await execute(
        env.db, s.tenant_id,
        "INSERT INTO app.vat_moves (tenant_id, period, kind, base_amount, vat_amount, doc_type, doc_id, einvoice_id) "
        "VALUES (:t, :p, 'input', 16666.67, 2000.00, 'supplier_payments', :d, :e)",
        t=s.tenant_id, p=m, d=uuid7(), e=unknown,
    )  # fmt: skip
    response = await env.client.get(f"{API}/reports/vat-summary", params={"period": label(m)},
                                    headers=s.h("accountant", key=None))  # fmt: skip
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_credit_red_invoices"] == 2
    assert body["input_vat"] == "2000.00"
    assert body["pending_credit_pct"] == "88.89"  # 16 000 ÷ (2 000 + 16 000) × 100
    items = {i["einvoice_id"]: i for i in body["pending_credit_invoices"]}
    assert set(items) == {str(red), str(unknown)}
    assert (items[str(red)]["risk_flag"], items[str(red)]["pending_vat"], items[str(red)]["credit_status"]) == (
        "red", "12000.00", "pending",
    )  # fmt: skip
    partial = items[str(unknown)]
    assert (partial["credited_vat"], partial["pending_vat"], partial["credit_status"]) == (
        "2000.00", "4000.00", "partial",
    )  # fmt: skip
    assert partial["counterparty_name"] == '"Qizil" MChJ' and partial["doc_date"] == day.isoformat()
