"""Tax settlement documents (20 #8a–#8d; 13 §2.26, §4.3, §5.2; US-M10-01, US-M10-04; QT-M10-07) — real app +
PostgreSQL/Redis; every posting asserted to the tiyin."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from tests.support.inventory import close_period, execute, scalar, set_setting
from tests.support.purchasing import API, Env, Shop, err, purchasing_env_fixture
from tests.support.supplier_tax import TS, D, account_balance, add_ledger, add_vat_move, ledger_of

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["purchasing_env_fixture"]

SEP = date(2026, 9, 1)
SEP_DAY = date(2026, 9, 15)


async def _shop(env: Env, name: str) -> Shop:
    return await env.shop(name, SystemRole.OWNER, SystemRole.ACCOUNTANT, SystemRole.CASHIER)


async def _vat_month(env: Env, shop: Shop) -> None:
    """13 §2.26 example: output VAT (Kt 6410) 120 000.00, input VAT (Dt 4410) 84 000.00 in September."""
    await add_ledger(env, shop, "5010", "6410", "120000.00", SEP_DAY, tax_type="vat")
    await add_ledger(env, shop, "4410", "6010", "84000.00", SEP_DAY, tax_type="vat")
    await add_vat_move(env, shop, "output", "1000000.00", "120000.00", SEP)
    await add_vat_move(env, shop, "input", "700000.00", "84000.00", SEP)


async def _create(env: Env, shop: Shop, role: str = "accountant", **body: Any) -> Any:
    payload = {"tax_kind": "vat_offset", "period": "2026-09", **body}
    return await env.client.post(TS, json=payload, headers=shop.h(role, branch=shop.branch_id))


async def _turnover_tenant(env: Env, shop: Shop) -> None:
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) "
        "VALUES (:t, '2026-01-01', 'turnover', :u)",
        t=shop.tenant_id, u=shop.user_ids["owner"],
    )  # fmt: skip


async def _turnover_month(env: Env, shop: Shop) -> None:
    """13 §4.3 example: 9020 = 50 000 000, 9040 = 1 000 000, 9050 = 500 000, 9390 = 200 000, 8530 = 300 000."""
    await add_ledger(env, shop, "5010", "9020", "50000000.00", SEP_DAY)
    await add_ledger(env, shop, "9040", "5010", "1000000.00", SEP_DAY)
    await add_ledger(env, shop, "9050", "5010", "500000.00", SEP_DAY)
    await add_ledger(env, shop, "5010", "9390", "200000.00", SEP_DAY)
    await add_ledger(env, shop, "2920", "8530", "300000.00", SEP_DAY)


async def _tax_payment(env: Env, shop: Shop, amount: str, tax_type: str) -> str:
    """The budget payment (M15, owned by expenses): ``expenses(tax_payment, source='bank')`` → Dt 6410 / Kt 5110."""
    cats = await env.client.get(f"{API}/expense-categories", headers=shop.h(key=None))
    assert cats.status_code == 200, cats.text
    found = [c for c in cats.json()["items"] if c["default_account"] == "6410"]
    if found:
        category_id = found[0]["id"]
    else:
        created = await env.client.post(
            f"{API}/expense-categories", json={"name": "Soliq to'lovi", "default_account": "6410"},
            headers=shop.h(),
        )  # fmt: skip
        assert created.status_code == 201, created.text
        category_id = created.json()["id"]
    draft = await env.client.post(
        f"{API}/expenses",
        json={"doc_date": str(business_today()), "category_id": category_id, "amount": amount, "source": "bank",
              "tax_type": tax_type},
        headers=shop.h(branch=shop.branch_id),
    )  # fmt: skip
    assert draft.status_code == 201, draft.text
    posted = await env.client.post(
        f"{API}/expenses/{draft.json()['id']}/post", headers=shop.h(branch=shop.branch_id)
    )
    assert posted.status_code == 200, posted.text
    expense_id: str = draft.json()["id"]
    return expense_id


# --- QT-M10-07 / 13 §2.26 example ------------------------------------------------------------------------
async def test_qt_m10_07_vat_offset_then_tax_payment(env: Env) -> None:
    shop = await _shop(env, "QT-M10-07")
    await _vat_month(env, shop)
    created = await _create(env, shop)
    assert created.status_code == 201, created.text
    draft = created.json()
    assert (draft["status"], draft["number"], draft["tax_kind"], draft["period"]) == (
        "draft", None, "vat_offset", "2026-09",
    )  # fmt: skip
    assert (draft["base_amount"], draft["amount"], draft["rate"], draft["expense_account"]) == (
        "700000.00", "84000.00", None, None,
    )  # fmt: skip
    assert draft["doc_date"] == "2026-09-30" and draft["branch_id"] == str(shop.branch_id)
    assert await ledger_of(env, shop, draft["id"]) == []  # a draft posts nothing

    key = "ts-post-qt-m10-07"
    posted = await env.client.post(f"{TS}/{draft['id']}/post", headers=shop.h("accountant", key=key))
    assert posted.status_code == 200, posted.text
    body = posted.json()
    assert (
        body["status"] == "posted" and body["number"] == "ST-01-2026-000001" and body["recalculated"] is False
    )
    replay = await env.client.post(f"{TS}/{draft['id']}/post", headers=shop.h("accountant", key=key))
    assert replay.status_code == 200 and replay.json() == body
    assert await ledger_of(env, shop, draft["id"]) == [("6410", "4410", D("84000.00"))]
    assert await account_balance(env, shop, "6410") == D("-36000.00")  # credit balance 36 000.00
    assert await account_balance(env, shop, "4410") == D("0.00")

    summary = await env.client.get(f"{API}/reports/vat-summary", params={"period": "2026-09"},
                                   headers=shop.h(key=None))  # fmt: skip
    assert summary.json()["tax_settlement_id"] == draft["id"]

    payment = await _tax_payment(env, shop, "36000.00", "vat")
    assert await ledger_of(env, shop, payment) == [("6410", "5110", D("36000.00"))]
    assert await account_balance(env, shop, "6410") == D("0.00")
    audit = await scalar(
        env, shop.tenant_id,
        "SELECT count(*) FROM app.audit_log WHERE entity = 'tax_settlements' AND entity_id = :id",
        id=UUID(draft["id"]),
    )  # fmt: skip
    assert audit == 2  # created + posted


async def test_13_2_26_deferred_red_vat_not_in_offset(env: Env) -> None:
    """A red/unknown invoice's deferred VAT (4410 ``vat_credit='deferred'``, no ``vat_moves``) stays on 4410."""
    shop = await _shop(env, "§2.26 deferred")
    await _vat_month(env, shop)
    await add_ledger(env, shop, "4410", "6010", "12000.00", SEP_DAY, tax_type="vat", vat_credit="deferred")
    body = (await _create(env, shop)).json()
    assert body["amount"] == "84000.00"
    await env.client.post(f"{TS}/{body['id']}/post", headers=shop.h("accountant"))
    assert await account_balance(env, shop, "4410") == D("12000.00")


async def test_vat_offset_post_recalculates(env: Env) -> None:
    shop = await _shop(env, "recalc")
    await _vat_month(env, shop)
    draft = (await _create(env, shop)).json()
    await add_vat_move(env, shop, "input", "100000.00", "12000.00", SEP)
    posted = await env.client.post(f"{TS}/{draft['id']}/post", headers=shop.h("accountant"))
    assert posted.status_code == 200, posted.text
    assert posted.json()["recalculated"] is True
    assert (posted.json()["base_amount"], posted.json()["amount"]) == ("800000.00", "96000.00")
    assert await ledger_of(env, shop, draft["id"]) == [("6410", "4410", D("96000.00"))]
    again = await env.client.post(f"{TS}/{draft['id']}/post", headers=shop.h("accountant"))
    assert again.status_code == 409 and err(again) == "DOC_NOT_DRAFT"


async def test_vat_offset_unique_per_period_and_cancel_storno(env: Env) -> None:
    shop = await _shop(env, "unique")
    await _vat_month(env, shop)
    first = (await _create(env, shop)).json()
    dup = await _create(env, shop)
    assert dup.status_code == 422, dup.text
    error = dup.json()["error"]
    assert error["details"][0]["message_key"] == "validation.tax_settlement_exists"
    assert error["params"]["existing_id"] == first["id"]

    await env.client.post(f"{TS}/{first['id']}/post", headers=shop.h("accountant"))
    cancelled = await env.client.post(
        f"{TS}/{first['id']}/cancel", json={"reason": "xato"}, headers=shop.h("accountant")
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled" and cancelled.json()["cancel_reason"] == "xato"
    assert [(r[0], r[1], r[2]) for r in await ledger_of(env, shop, first["id"])] == [
        ("6410", "4410", D("84000.00")),
        ("4410", "6410", D("84000.00")),
    ]
    again = await env.client.post(
        f"{TS}/{first['id']}/cancel", json={"reason": "x"}, headers=shop.h("accountant")
    )
    assert again.status_code == 409 and err(again) == "DOC_ALREADY_CANCELLED"
    second = await _create(env, shop)  # the cancelled one no longer blocks the period
    assert second.status_code == 201, second.text
    draft_cancel = await env.client.post(
        f"{TS}/{second.json()['id']}/cancel", json={"reason": "qoralama"}, headers=shop.h("accountant")
    )
    assert draft_cancel.status_code == 200 and await ledger_of(env, shop, second.json()["id"]) == []

    listed = await env.client.get(TS, params={"period": "2026-09"}, headers=shop.h(key=None))
    assert listed.status_code == 200
    assert [i["id"] for i in listed.json()["items"]] == [second.json()["id"], first["id"]]
    page = await env.client.get(TS, params={"limit": 1}, headers=shop.h(key=None))
    nxt = await env.client.get(
        TS, params={"limit": 1, "cursor": page.json()["next_cursor"]}, headers=shop.h(key=None)
    )
    assert nxt.json()["items"][0]["id"] == first["id"]
    got = await env.client.get(f"{TS}/{first['id']}", headers=shop.h(key=None))
    assert got.status_code == 200 and got.json()["status"] == "cancelled"


async def test_tax_settlement_validation(env: Env) -> None:
    shop = await _shop(env, "validation")
    wrong_kind = await _create(env, shop, tax_kind="turnover_tax", branch_id=str(shop.branch_id))
    assert wrong_kind.status_code == 422
    assert wrong_kind.json()["error"]["details"][0]["message_key"] == "validation.tax_kind_regime_mismatch"
    branch = await _create(env, shop, branch_id=str(shop.branch_id))
    assert branch.status_code == 422
    assert (
        branch.json()["error"]["details"][0]["message_key"] == "validation.branch_not_allowed_for_vat_offset"
    )
    outside = await _create(env, shop, doc_date="2026-10-01")
    assert outside.status_code == 422
    denied = await _create(env, shop, role="cashier")
    assert denied.status_code == 403
    await close_period(env, shop, SEP)
    closed = await _create(env, shop)
    assert closed.status_code == 409 and err(closed) == "PERIOD_CLOSED"


# --- 13 §4.3 example (turnover tax, US-M10-04) --------------------------------------------------------------
async def test_13_4_3_turnover_tax_settlement(env: Env) -> None:
    shop = await _shop(env, "§4.3 aylanma")
    await _turnover_tenant(env, shop)
    await _turnover_month(env, shop)
    vat_kind = await _create(env, shop)
    assert vat_kind.status_code == 422  # turnover tenant: vat_offset refused
    missing = await _create(env, shop, tax_kind="turnover_tax")
    assert missing.status_code == 422
    created = await _create(env, shop, tax_kind="turnover_tax", branch_id=str(shop.branch_id))
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["base_amount"], body["rate"], body["amount"], body["expense_account"]) == (
        "49000000.00", "4.00", "1960000.00", "9430",
    )  # fmt: skip
    posted = await env.client.post(f"{TS}/{body['id']}/post", headers=shop.h("accountant"))
    assert posted.status_code == 200, posted.text
    assert await ledger_of(env, shop, body["id"]) == [("9430", "6410", D("1960000.00"))]
    dup = await _create(env, shop, tax_kind="turnover_tax", branch_id=str(shop.branch_id))
    assert dup.status_code == 422


async def test_13_4_3_turnover_tax_account_9820(env: Env) -> None:
    shop = await _shop(env, "§4.3 9820")
    await _turnover_tenant(env, shop)
    await _turnover_month(env, shop)
    await set_setting(env, shop, "turnover_tax_account", "9820")
    body = (await _create(env, shop, tax_kind="turnover_tax", branch_id=str(shop.branch_id))).json()
    assert body["expense_account"] == "9820"
    await env.client.post(f"{TS}/{body['id']}/post", headers=shop.h("accountant"))
    assert await ledger_of(env, shop, body["id"]) == [("9820", "6410", D("1960000.00"))]


# --- B4 fix round: ACC-06 (13 §4.3 transition month) --------------------------------------------------------
async def test_acc06_transition_month_turnover_tax_until_vat_valid_from(env: Env) -> None:
    """13 §4.3: a turnover tenant becomes a VAT payer from 15 September. The September turnover tax counts
    only the turnover days (sale on the 10th: 1 000 000 x 4 % = 40 000); the sale on the 20th is a VAT sale
    (output 240 000) and the same month's VAT offset (input 120 000) is accepted too."""
    shop = await _shop(env, "ACC-06")
    await _turnover_tenant(env, shop)
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) "
        "VALUES (:t, '2026-09-15', 'vat', :u)",
        t=shop.tenant_id, u=shop.user_ids["owner"],
    )  # fmt: skip
    await add_ledger(env, shop, "5010", "9020", "1000000.00", date(2026, 9, 10))
    await add_ledger(env, shop, "5010", "9020", "2000000.00", date(2026, 9, 20))
    await add_ledger(env, shop, "5010", "6410", "240000.00", date(2026, 9, 20), tax_type="vat")
    await add_ledger(env, shop, "4410", "6010", "120000.00", date(2026, 9, 20), tax_type="vat")
    await add_vat_move(env, shop, "output", "2000000.00", "240000.00", SEP)
    await add_vat_move(env, shop, "input", "1000000.00", "120000.00", SEP)

    turnover = await _create(env, shop, tax_kind="turnover_tax", branch_id=str(shop.branch_id))
    assert turnover.status_code == 201, turnover.text
    body = turnover.json()
    assert (body["base_amount"], body["rate"], body["amount"], body["expense_account"]) == (
        "1000000.00", "4.00", "40000.00", "9430",
    )  # fmt: skip
    posted = await env.client.post(f"{TS}/{body['id']}/post", headers=shop.h("accountant"))
    assert posted.status_code == 200, posted.text
    assert posted.json()["recalculated"] is False
    assert await ledger_of(env, shop, body["id"]) == [("9430", "6410", D("40000.00"))]

    offset = await _create(env, shop)
    assert offset.status_code == 201, offset.text
    vat = offset.json()
    assert (vat["base_amount"], vat["amount"], vat["rate"]) == ("1000000.00", "120000.00", None)
    posted = await env.client.post(f"{TS}/{vat['id']}/post", headers=shop.h("accountant"))
    assert posted.status_code == 200, posted.text
    assert await ledger_of(env, shop, vat["id"]) == [("6410", "4410", D("120000.00"))]
    # 6410: + 240 000 output VAT + 40 000 turnover tax − 120 000 offset = 160 000 credit
    assert await account_balance(env, shop, "6410") == D("-160000.00")
    assert await account_balance(env, shop, "4410") == D("0.00")

    summary = await env.client.get(
        f"{API}/reports/vat-summary", params={"period": "2026-09"}, headers=shop.h(key=None)
    )
    assert summary.status_code == 200, summary.text
    got = summary.json()
    assert (got["regime"], got["output_vat"], got["input_vat"], got["net_vat"]) == (
        "vat", "240000.00", "120000.00", "120000.00",
    )  # fmt: skip
    assert (got["turnover_base"], got["turnover_amount"], got["turnover_rate_pct"]) == (
        "1000000.00", "40000.00", "4.00",
    )  # fmt: skip
    assert got["tax_settlement_id"] == vat["id"]

    # August is turnover only: a VAT offset there is still refused
    wrong = await _create(env, shop, period="2026-08")
    assert wrong.status_code == 422, wrong.text
    assert wrong.json()["error"]["details"][0]["message_key"] == "validation.tax_kind_regime_mismatch"
