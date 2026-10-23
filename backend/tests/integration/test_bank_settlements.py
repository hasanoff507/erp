"""Bank settlements — BO-24 backend (20 #55a–#55h, 13 §2.18a, qaror #42/#71, US-M11-04).

QT-M11-07/08/09/10/11/13/15; B4 DoD: a synthetic anonymised 1CClientBankExchange sample
(``tests/fixtures/bank/``) is imported and the 5710 transit balance closes to zero.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.session import tenant_transaction
from app.modules.accounting.wiring import business_today
from tests.support.bank import (
    API,
    D15,
    D16,
    D17,
    FIXTURES,
    balance,
    bank_till,
    body,
    card_purchase,
    statement,
    transit_in,
    transit_out,
    upload,
)
from tests.support.cash import (
    Till,
    cash_env_fixture,  # noqa: F401 - fixture "env"
    ledger,
    one,
    open_shift,
    sql,
)
from tests.support.catalog import Env

pytestmark = pytest.mark.asyncio


def _rows(entries: list[tuple[str, str, str, dict[str, Any]]]) -> list[tuple[str, str, str]]:
    return [(dt, kt, a) for dt, kt, a, _ in entries]


async def _card_day(env: Env, till: Till) -> None:
    """Yesterday: card sale 1 000 000, refund to the card 50 000 → 5710 (card) = 950 000."""
    await transit_in(env, till, "card", "1000000.00", D16)
    await transit_out(env, till, "card", "50000.00", D16)


async def _create(env: Env, till: Till, role: str = "accountant", **over: Any) -> Any:
    return await env.client.post(API, json=body(till, **over), headers=till.shop.h(role))


async def test_qt_m11_07_card_settlement_posts_5110_and_9430(env: Env) -> None:
    till = await bank_till(env)
    await _card_day(env, till)
    assert await balance(env, till, "card") == "950000.00"
    over = await _create(env, till, gross_amount="950000.01")
    assert over.status_code == 422, over.text
    err = over.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and err["params"]["available"] == "950000.00"
    assert err["details"][0]["field"] == "gross_amount"
    assert err["details"][0]["message_key"] == "validation.bank_settlement_exceeds_in_transit"

    res = await _create(env, till, bank_ref="5521")
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["status"] == "draft" and doc["source"] == "manual" and doc["net_amount"] == "940500.00"
    assert doc["variance_amount"] == "0.00" and doc["version"] == 1
    assert await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(doc["id"])) == []

    posted = await env.client.post(f"{API}/{doc['id']}/post", json={}, headers=till.shop.h("accountant"))
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "posted" and posted.json()["posted_at"]
    rows = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(doc["id"]))
    assert _rows(rows) == [("5110", "5710", "940500.00"), ("9430", "5710", "9500.00")]
    assert all(an["payment_method"] == "card" and an["bank_ref"] == "5521" for *_, an in rows)
    assert await balance(env, till, "card") == "0.00"
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.cash_moves WHERE doc_id = :d",
                     d=UUID(doc["id"])) == 0  # fmt: skip
    again = await env.client.post(f"{API}/{doc['id']}/post", json={}, headers=till.shop.h("accountant"))
    assert again.json()["error"]["code"] == "DOC_NOT_DRAFT"

    detail = await env.client.get(f"{API}/{doc['id']}", headers=till.shop.h("accountant", key=None))
    assert detail.status_code == 200
    assert [(e["account_dt"], e["account_kt"], e["amount"]) for e in detail.json()["ledger_entries"]] == [
        ("5110", "5710", "940500.00"),
        ("9430", "5710", "9500.00"),
    ]

    cancel = await env.client.post(
        f"{API}/{doc['id']}/cancel", json={"reason": "xato ko'chirma"}, headers=till.shop.h("accountant")
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled" and cancel.json()["cancel_reason"] == "xato ko'chirma"
    rows = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(doc["id"]))
    assert _rows(rows)[2:] == [("5710", "5110", "940500.00"), ("5710", "9430", "9500.00")]
    assert await balance(env, till, "card") == "950000.00"
    twice = await env.client.post(
        f"{API}/{doc['id']}/cancel", json={"reason": "x"}, headers=till.shop.h("accountant")
    )
    assert twice.json()["error"]["code"] == "DOC_ALREADY_CANCELLED"


async def test_qt_m11_08_permissions_validation_number_and_audit(env: Env) -> None:
    till = await bank_till(env)
    await _card_day(env, till)
    cashier = await _create(env, till, role="cashier")
    assert cashier.status_code == 403 and cashier.json()["error"]["code"] == "PERMISSION_DENIED"
    eq = await _create(env, till, commission_amount="950000.00")
    assert eq.status_code == 422
    assert {(d["field"], d["message_key"]) for d in eq.json()["error"]["details"]} == {
        ("commission_amount", "validation.bank_commission_ge_gross")
    }
    order = await _create(env, till, settled_from=D17.isoformat(), settled_to=D16.isoformat())
    assert order.status_code == 422
    assert "settled_from" in {d["field"] for d in order.json()["error"]["details"]}
    variance = await _create(env, till, variance_amount="-100.00")
    assert variance.status_code == 422
    assert variance.json()["error"]["details"][0]["message_key"] == "validation.not_allowed"
    future = await _create(env, till, doc_date=date.fromordinal(business_today().toordinal() + 1).isoformat())
    assert future.status_code == 422
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.bank_settlements") == 0

    res = await _create(env, till, role="owner")
    assert res.status_code == 201, res.text
    number = res.json()["number"]
    assert number.startswith("BT-") and number.endswith("-000001")
    posted = await env.client.post(f"{API}/{res.json()['id']}/post", json={}, headers=till.shop.h("owner"))
    assert posted.json()["number"] == number
    actions = [r[0] for r in await sql(
        env.db, till.shop.tenant_id,
        "SELECT action FROM app.audit_log WHERE entity = 'bank_settlements' AND entity_id = :d ORDER BY id",
        d=UUID(res.json()["id"]),
    )]  # fmt: skip
    assert actions == ["bank_settlement_created", "bank_settlement_posted"]
    after = (await sql(env.db, till.shop.tenant_id, "SELECT after FROM app.audit_log WHERE entity_id = :d "
                       "AND action = 'bank_settlement_posted'", d=UUID(res.json()["id"])))[0][0]  # fmt: skip
    assert (
        after["method"] == "card"
        and after["gross_amount"] == "950000.00"
        and after["commission_amount"] == "9500.00"
    )


async def test_qt_m11_09_transit_balances(env: Env) -> None:
    till = await bank_till(env)
    await _card_day(env, till)
    await transit_in(env, till, "uzqr", "120000.00", D15)
    await transit_in(env, till, "card", "70000.00", D16, rrn="000000000777")
    res = await env.client.get(f"{API}/transit-balances", headers=till.shop.h("accountant", key=None))
    assert res.status_code == 200, res.text
    items = {i["method"]: i for i in res.json()["items"]}
    assert res.json()["as_of"] == business_today().isoformat()
    assert items["card"] == {
        "branch_id": str(till.shop.branch_id), "method": "card", "balance": "1020000.00",
        "oldest_unsettled_date": D16.isoformat(), "card_breakdown": {"integrated": "70000.00", "manual": "950000.00"},
    }  # fmt: skip
    assert items["uzqr"]["balance"] == "120000.00" and items["uzqr"]["card_breakdown"] is None
    assert items["uzqr"]["oldest_unsettled_date"] == D15.isoformat()
    # as_of before the card day — only uzqr
    early = await env.client.get(
        f"{API}/transit-balances",
        params={"as_of": D15.isoformat()},
        headers=till.shop.h("accountant", key=None),
    )
    assert [i["method"] for i in early.json()["items"]] == ["uzqr"]
    doc = (await _create(env, till, gross_amount="1020000.00", commission_amount="10200.00")).json()
    await env.client.post(f"{API}/{doc['id']}/post", json={}, headers=till.shop.h("accountant"))
    res = await env.client.get(f"{API}/transit-balances", headers=till.shop.h("accountant", key=None))
    assert [i["method"] for i in res.json()["items"]] == ["uzqr"]
    cashier = await env.client.get(f"{API}/transit-balances", headers=till.shop.h("cashier", key=None))
    assert cashier.status_code == 403


async def test_qt_m11_10_statement_import_creates_draft_only(env: Env) -> None:
    till = await bank_till(env)
    await _card_day(env, till)
    content = statement(
        {"number": "5521", "amount": "940500.00", "purpose": "Возмещение по эквайрингу за день"}
    )
    res = await env.client.post(f"{API}/imports", **upload(content), headers=till.shop.h("accountant"))
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["drafts_created"] == 1 and out["duplicates"] == 0 and out["unmatched_lines"] == []
    assert out["account"] == "20208000900100000001" and len(out["file_sha256"]) == 64
    draft = (
        await env.client.get(f"{API}/{out['draft_ids'][0]}", headers=till.shop.h("accountant", key=None))
    ).json()
    assert (draft["source"], draft["status"], draft["method"]) == ("statement_import", "draft", "card")
    assert (draft["gross_amount"], draft["commission_amount"], draft["net_amount"]) == (
        "950000.00", "9500.00", "940500.00",
    )  # fmt: skip
    assert draft["statement_import_id"] == out["import_id"] and draft["bank_ref"] == "5521"
    assert (draft["settled_from"], draft["settled_to"], draft["doc_date"]) == (
        D16.isoformat(), D16.isoformat(), D17.isoformat(),
    )  # fmt: skip
    assert draft["ledger_entries"] == [] and await balance(env, till, "card") == "950000.00"
    imp = (await sql(env.db, till.shop.tenant_id, "SELECT status, drafts_created, rows_total, attachment_id "
                     "FROM app.bank_statement_imports WHERE id = :i", i=UUID(out["import_id"])))[0]  # fmt: skip
    assert (imp[0], imp[1], imp[2]) == ("parsed", 1, 1)
    assert (
        await one(env.db, till.shop.tenant_id, "SELECT kind FROM app.attachments WHERE id = :a", a=imp[3])
        == "import"
    )
    dup = await env.client.post(f"{API}/imports", **upload(content), headers=till.shop.h("accountant"))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "BANK_IMPORT_DUPLICATE"
    assert dup.json()["error"]["params"]["import_id"] == out["import_id"]
    # the same statement line in another file is a duplicate line, not a second draft
    other = statement(
        {"number": "5521", "amount": "940500.00", "purpose": "Возмещение по эквайрингу за день"},
        {"number": "1", "amount": "10.00", "purpose": "Оплата за товар", "to": "20208000900100000099"},
    )
    res2 = await env.client.post(f"{API}/imports", **upload(other), headers=till.shop.h("accountant"))
    assert res2.json()["duplicates"] == 1 and res2.json()["ignored_outgoing"] == 1
    assert res2.json()["drafts_created"] == 0
    posted = await env.client.post(f"{API}/{draft['id']}/post", json={}, headers=till.shop.h("accountant"))
    assert posted.status_code == 200
    rows = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(draft["id"]))
    assert _rows(rows) == [("5110", "5710", "940500.00"), ("9430", "5710", "9500.00")]


async def test_qt_m11_11_statement_file_errors_and_unmatched_lines(env: Env) -> None:
    till = await bank_till(env)
    h = till.shop.h
    bad = await env.client.post(
        f"{API}/imports", **upload("Выписка\r\nНомер=1\r\n".encode()), headers=h("accountant")
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "BANK_IMPORT_FILE_INVALID"
    assert bad.json()["error"]["params"]["line_no"] == 1
    foreign = statement(
        {"number": "1", "amount": "1.00", "purpose": "эквайринг"}, account="20208000900199999999"
    )
    mism = await env.client.post(f"{API}/imports", **upload(foreign), headers=h("accountant"))
    assert mism.status_code == 422 and mism.json()["error"]["code"] == "BANK_IMPORT_ACCOUNT_MISMATCH"
    assert mism.json()["error"]["params"]["file_account"] == "20208000900199999999"
    csv = await env.client.post(
        f"{API}/imports", files={"file": ("v.csv", b"a,b", "text/csv")}, headers=h("accountant")
    )
    assert csv.status_code == 415
    cashier = await env.client.post(f"{API}/imports", **upload(statement()), headers=h("cashier"))
    assert cashier.status_code == 403

    await transit_in(env, till, "click", "100000.00", D16)
    lines = statement(
        {"number": "1", "amount": "500000.00", "purpose": "Оплата по QR-код UzQR"},  # no uzqr transit
        {"number": "2", "amount": "1000.00", "purpose": "Возврат займа", "payer_inn": "300000009"},
        {"number": "3", "amount": "120000.00", "purpose": "CLICK merchant payout"},  # > Σ → no match
        {"number": "4", "amount": "99000.00", "purpose": "CLICK merchant payout"},
    )
    res = await env.client.post(f"{API}/imports", **upload(lines), headers=h("accountant"))
    assert res.status_code == 201, res.text
    reasons = [(u["number"], u["reason"]) for u in res.json()["unmatched_lines"]]
    assert reasons == [("1", "no_transit_match"), ("2", "unknown_method"), ("3", "no_transit_match")]
    assert res.json()["drafts_created"] == 1
    draft = (
        await env.client.get(f"{API}/{res.json()['draft_ids'][0]}", headers=h("accountant", key=None))
    ).json()
    assert (draft["method"], draft["gross_amount"], draft["commission_amount"]) == (
        "click",
        "100000.00",
        "1000.00",
    )


async def test_qt_m11_13_collection_shortage_posts_9410_and_5910(env: Env) -> None:
    till = await bank_till(env)
    shift_id = await open_shift(env, till)
    move = await env.client.post(
        "/api/v1/cash-movements",
        json={"cash_register_id": str(till.register_id), "shift_id": str(shift_id), "direction": "out",
              "reason": "collection", "amount": "2000000.00", "doc_date": D17.isoformat()},
        headers=till.shop.h("owner"),
    )  # fmt: skip
    assert move.status_code == 201, move.text
    assert await balance(env, till, "collection") == "2000000.00"
    res = await _create(
        env, till, method="collection", settled_from=D17.isoformat(), settled_to=D17.isoformat(),
        gross_amount="2000000.00", commission_amount="5000.00", variance_amount="-5000.00",
    )  # fmt: skip
    assert res.status_code == 201, res.text
    assert res.json()["net_amount"] == "1990000.00"
    posted = await env.client.post(
        f"{API}/{res.json()['id']}/post", json={}, headers=till.shop.h("accountant")
    )
    assert posted.status_code == 200, posted.text
    rows = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(res.json()["id"]))
    assert _rows(rows) == [
        ("5110", "5710", "1990000.00"),
        ("9410", "5710", "5000.00"),
        ("5910", "5710", "5000.00"),
    ]
    assert await balance(env, till, "collection") == "0.00"
    assert (
        await one(
            env.db,
            till.shop.tenant_id,
            "SELECT count(*) FROM app.cash_moves WHERE doc_type = 'bank_settlements'",
        )
        == 0
    )


async def test_qt_m11_15_rrn_matching_and_terminal_less_by_amount(env: Env) -> None:
    till = await bank_till(env)
    await card_purchase(env, till, "000000000001", "500000.00", D16)
    await card_purchase(env, till, "000000000002", "300000.00", D16)
    r3 = await card_purchase(env, till, "000000000003", "150000.00", D16)
    await transit_in(env, till, "card", "200000.00", D15)  # terminal-less card receipt (no rrn)
    content = statement(
        {"number": "801", "amount": "792000.00",
         "purpose": "Эквайринг TID T1 RRN: 000000000001, 000000000002 комиссия 8000.00"},
        {"number": "802", "amount": "198000.00", "purpose": "Возмещение по картам (эквайринг)"},
    )  # fmt: skip
    res = await env.client.post(f"{API}/imports", **upload(content), headers=till.shop.h("accountant"))
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["drafts_created"] == 2 and out["unmatched_lines"] == []
    assert [t["card_terminal_transaction_id"] for t in out["unmatched_card_transactions"]] == [str(r3)]
    assert out["unmatched_card_transactions"][0]["rrn"] == "000000000003"
    rrn_draft, plain = [
        (await env.client.get(f"{API}/{i}", headers=till.shop.h("accountant", key=None))).json()
        for i in out["draft_ids"]
    ]
    assert (rrn_draft["gross_amount"], rrn_draft["commission_amount"]) == ("800000.00", "8000.00")
    assert (rrn_draft["settled_from"], rrn_draft["settled_to"]) == (D16.isoformat(), D16.isoformat())
    linked = await sql(env.db, till.shop.tenant_id, "SELECT rrn FROM app.card_terminal_transactions "
                       "WHERE bank_settlement_id = :b ORDER BY rrn", b=UUID(rrn_draft["id"]))  # fmt: skip
    assert [r[0] for r in linked] == ["000000000001", "000000000002"]
    # terminal-less receipt: by amount and date only (never by RRN)
    assert (plain["gross_amount"], plain["commission_amount"]) == ("200000.00", "2000.00")
    assert (plain["settled_from"], plain["settled_to"]) == (D15.isoformat(), D15.isoformat())
    for doc in (rrn_draft, plain):
        ok = await env.client.post(f"{API}/{doc['id']}/post", json={}, headers=till.shop.h("accountant"))
        assert ok.status_code == 200, ok.text
    rows = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(rrn_draft["id"]))
    assert _rows(rows) == [("5110", "5710", "792000.00"), ("9430", "5710", "8000.00")]
    assert await balance(env, till, "card") == "150000.00"  # R3 still in transit
    tb = (await env.client.get(f"{API}/transit-balances", headers=till.shop.h("accountant", key=None))).json()
    card = next(i for i in tb["items"] if i["method"] == "card")
    assert card["card_breakdown"] == {"integrated": "150000.00", "manual": "0.00"}
    # cancelling the RRN settlement releases its transactions
    await env.client.post(
        f"{API}/{rrn_draft['id']}/cancel", json={"reason": "x"}, headers=till.shop.h("accountant")
    )
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.card_terminal_transactions "
                     "WHERE bank_settlement_id IS NOT NULL") == 0  # fmt: skip


async def test_patch_draft_version_and_list(env: Env) -> None:
    till = await bank_till(env)
    await transit_in(env, till, "collection", "2000000.00", D16)
    doc = (
        await _create(env, till, method="collection", gross_amount="2000000.00", commission_amount="0.00")
    ).json()
    h = till.shop.h
    patched = await env.client.patch(
        f"{API}/{doc['id']}",
        json={
            "commission_amount": "5000.00",
            "variance_amount": "3000.00",
            "comment": "inkassa ortiqchasi",
            "version": 1,
        },
        headers=h("accountant"),
    )
    assert patched.status_code == 200, patched.text
    assert (patched.json()["net_amount"], patched.json()["version"]) == ("1998000.00", 2)
    stale = await env.client.patch(
        f"{API}/{doc['id']}", json={"comment": "x", "version": 1}, headers=h("accountant")
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "VERSION_CONFLICT"
    too_much = await env.client.patch(
        f"{API}/{doc['id']}", json={"gross_amount": "2000000.01", "version": 2}, headers=h("accountant")
    )
    assert too_much.status_code == 422
    posted = await env.client.post(f"{API}/{doc['id']}/post", json={}, headers=h("accountant"))
    rows = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(doc["id"]))
    assert _rows(rows) == [
        ("5110", "5710", "1998000.00"),
        ("9410", "5710", "5000.00"),
        ("5710", "9390", "3000.00"),
    ]
    assert posted.json()["version"] == 3
    late = await env.client.patch(
        f"{API}/{doc['id']}", json={"comment": "x", "version": 3}, headers=h("accountant")
    )
    assert late.json()["error"]["code"] == "DOC_NOT_DRAFT"
    # list: filters + cursor by doc_date
    await transit_in(env, till, "card", "10.00", D16)
    second = (
        await _create(env, till, gross_amount="10.00", commission_amount="0.00", doc_date=D16.isoformat())
    ).json()
    page = (await env.client.get(API, params={"limit": 1}, headers=h("accountant", key=None))).json()
    assert [i["id"] for i in page["items"]] == [doc["id"]] and page["next_cursor"]
    nxt = (await env.client.get(API, params={"limit": 1, "cursor": page["next_cursor"]},
                                headers=h("accountant", key=None))).json()  # fmt: skip
    assert [i["id"] for i in nxt["items"]] == [second["id"]] and nxt["next_cursor"] is None
    only = (
        await env.client.get(
            API, params={"status": "draft", "method": "card"}, headers=h("accountant", key=None)
        )
    ).json()
    assert [i["id"] for i in only["items"]] == [second["id"]]
    ranged = await env.client.get(
        API, params={"doc_date__gte": D17.isoformat()}, headers=h("accountant", key=None)
    )
    assert [i["id"] for i in ranged.json()["items"]] == [doc["id"]]


async def test_b4_dod_03_fixture_statement_closes_transit_to_zero(env: Env) -> None:
    """B4 DoD: the synthetic anonymised windows-1251 sample is imported and 5710 closes to 0 (13 §2.18a)."""
    till = await bank_till(env)
    sales_day, bank_day = date(2026, 10, 16), date(2026, 10, 17)
    await transit_in(env, till, "card", "1000000.00", sales_day)
    await transit_out(env, till, "card", "50000.00", sales_day)
    await transit_in(env, till, "collection", "2000000.00", sales_day)
    content = (FIXTURES / "statement_card_collection.cp1251.txt").read_bytes()
    res = await env.client.post(
        f"{API}/imports", **upload(content, "vypiska_20261017.txt"), headers=till.shop.h("accountant")
    )
    assert res.status_code == 201, res.text
    out = res.json()
    assert (out["drafts_created"], out["ignored_outgoing"], out["unmatched_lines"]) == (2, 1, [])
    assert (out["period_from"], out["period_to"]) == ("2026-10-17", "2026-10-17")
    docs = [
        (await env.client.get(f"{API}/{i}", headers=till.shop.h("accountant", key=None))).json()
        for i in out["draft_ids"]
    ]
    assert [(d["method"], d["gross_amount"], d["commission_amount"], d["doc_date"]) for d in docs] == [
        ("card", "950000.00", "9500.00", bank_day.isoformat()),
        ("collection", "2000000.00", "10000.00", bank_day.isoformat()),
    ]
    for d in docs:
        posted = await env.client.post(f"{API}/{d['id']}/post", json={}, headers=till.shop.h("accountant"))
        assert posted.status_code == 200, posted.text
    assert await balance(env, till, "card") == "0.00"
    assert await balance(env, till, "collection") == "0.00"
    collection = await ledger(env.db, till.shop.tenant_id, "bank_settlements", UUID(docs[1]["id"]))
    assert _rows(collection) == [("5110", "5710", "1990000.00"), ("9410", "5710", "10000.00")]
    tb = (await env.client.get(f"{API}/transit-balances", headers=till.shop.h("accountant", key=None))).json()
    assert tb["items"] == []


async def test_idempotent_create_and_branch_scope(env: Env) -> None:
    till = await bank_till(env)
    await _card_day(env, till)
    key = "BT-" + str(UUID(int=till.shop.tenant_id.int))
    first = await env.client.post(API, json=body(till), headers=till.shop.h("accountant", key=key))
    second = await env.client.post(API, json=body(till), headers=till.shop.h("accountant", key=key))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.bank_settlements") == 1
    foreign = await env.client.post(
        API,
        json=body(till, branch_id="00000000-0000-7000-8000-000000000001"),
        headers=till.shop.h("accountant"),
    )
    assert foreign.status_code == 404
    other_branch = await env.client.get(
        API, headers=till.shop.h("accountant", key=None, branch=UUID("00000000-0000-7000-8000-000000000002"))
    )
    assert other_branch.status_code == 200 and other_branch.json()["items"] == []  # X-Branch-Id narrows
    missing = await env.client.post(
        API,
        json=body(till, attachment_id="00000000-0000-7000-8000-000000000003"),
        headers=till.shop.h("accountant"),
    )
    assert missing.status_code == 404 and missing.json()["error"]["params"]["resource"] == "attachment"


async def test_sec02_bank_statement_not_readable_by_catalog_role(env: Env) -> None:
    """SEC-02 (17 §12): an ``import`` file referenced by ``bank_statement_imports`` is read only with
    ``bank_settlements.manage`` — a catalog/stock-opening role (Manager) gets 403; other import files stay
    readable with the import rights."""
    till = await bank_till(env)
    await _card_day(env, till)
    content = statement({"number": "5522", "amount": "940500.00", "purpose": "Возмещение по эквайрингу"})
    res = await env.client.post(f"{API}/imports", **upload(content), headers=till.shop.h("accountant"))
    assert res.status_code == 201, res.text
    attachment_id = await one(env.db, till.shop.tenant_id, "SELECT attachment_id FROM app.bank_statement_imports "
                              "WHERE id = :i", i=UUID(res.json()["import_id"]))  # fmt: skip
    att = f"/api/v1/attachments/{attachment_id}"
    denied = await env.client.get(att, headers=till.shop.h("manager", key=None))
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["params"]["permission"] == "bank_settlements.manage"
    assert (await env.client.get(att, headers=till.shop.h("accountant", key=None))).status_code == 200
    assert (await env.client.get(att, headers=till.shop.h("owner", key=None))).status_code == 200
    catalog_file = await env.client.post(
        "/api/v1/attachments", data={"kind": "import"}, files={"file": ("p.csv", b"name\nNon\n", "text/csv")},
        headers=till.shop.h("manager"),
    )  # fmt: skip
    assert catalog_file.status_code == 201, catalog_file.text
    mine = await env.client.get(
        f"/api/v1/attachments/{catalog_file.json()['id']}", headers=till.shop.h("manager", key=None)
    )
    assert mine.status_code == 200, mine.text


async def test_sync04_concurrent_imports_serialize(env: Env) -> None:
    """SYNC-04 (23 §2.1): the import write transaction first takes the tenant's
    ``bank_statement_import:<tenant>`` advisory lock — a held lock makes a second import wait, and two
    parallel imports both succeed (no transit / doc_sequences lock cycle)."""
    till = await bank_till(env)
    await _card_day(env, till)
    tenant = till.shop.tenant_id
    first = statement({"number": "6601", "amount": "400000.00", "purpose": "Возмещение по эквайрингу"})
    async with env.db.session_factory() as s, tenant_transaction(s, tenant):
        await s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"bank_statement_import:{tenant}"},
        )
        task = asyncio.create_task(
            env.client.post(f"{API}/imports", **upload(first), headers=till.shop.h("accountant"))
        )
        waiting = 0
        for _ in range(200):
            if task.done():
                break
            waiting = int(
                await one(
                    env.db,
                    tenant,
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock' AND wait_event = 'advisory'",
                )
            )
            if waiting:
                break
            await asyncio.sleep(0.05)
        assert not task.done() and waiting > 0
    res = await asyncio.wait_for(task, timeout=30)
    assert res.status_code == 201, res.text
    a = statement({"number": "6602", "amount": "200000.00", "purpose": "Возмещение по эквайрингу"})
    b = statement({"number": "6603", "amount": "100000.00", "purpose": "Возмещение по эквайрингу"})
    both = await asyncio.gather(
        env.client.post(f"{API}/imports", **upload(a), headers=till.shop.h("accountant")),
        env.client.post(f"{API}/imports", **upload(b), headers=till.shop.h("accountant")),
    )
    assert [r.status_code for r in both] == [201, 201], [r.text for r in both]
    assert await one(env.db, tenant, "SELECT count(*) FROM app.bank_statement_imports") == 3
