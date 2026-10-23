"""Incoming e-invoices (19 §19, §8 from-einvoice; 21 §2, §2.1, §5; 13 §2.8, §2.20; US-M07-03, US-M10-03,
QT-M07-09, ACC-07, DoD-06 with the fake operator and the fake E-IMZO verifier)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter, fake_pkcs7
from tests.support.edocs import (
    API,
    EI,
    ROLES,
    Env,
    Shop,
    edocs_env_fixture,
    err,
    incoming,
    poll,
    rows,
    run_docs,
    scalar,
    sign,
)
from tests.support.purchasing import create_product, warehouse_of

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["edocs_env_fixture"]

D = Decimal
GR = f"{API}/goods-receipts"
SR = f"{API}/supplier-returns"


async def _shop(env: Env, name: str) -> tuple[Shop, str, UUID]:
    shop = await env.shop(name, *ROLES)
    product = (await create_product(env.client, shop, "Coca-Cola 1.5L", vat_rate="12.00"))["id"]
    return shop, product, await warehouse_of(env.db, shop)


async def _received(
    env: Env, shop: Shop, port: FakeEInvoiceAdapter, lines: list[dict[str, Any]], **kw: Any
) -> str:
    doc = incoming("301234567", lines, **kw)
    port.inbox.append(doc)
    await poll(env, shop, port)
    found = await scalar(
        env, shop.tenant_id, "SELECT id FROM app.einvoices WHERE operator_doc_id = :o", o=doc.operator_doc_id
    )
    assert found is not None
    return str(found)


async def _accepted(
    env: Env, shop: Shop, port: FakeEInvoiceAdapter, lines: list[dict[str, Any]], **kw: Any
) -> str:
    einvoice_id = await _received(env, shop, port, lines, **kw)
    await sign(env, shop, f"{EI}/{einvoice_id}", role="accountant", expect=200)
    queued = await env.client.post(f"{EI}/{einvoice_id}/accept", headers=shop.h("accountant"))
    assert queued.status_code == 202, queued.text
    [outcome] = await run_docs(env, shop, port)
    assert (outcome.kind, outcome.status, outcome.doc_status) == ("einvoice_accept", "done", "accepted")
    return einvoice_id


def _line(product: str, qty: str, net: str, vat: str, **extra: Any) -> dict[str, Any]:
    return {"product_id": product, "name": "Coca-Cola 1.5L", "qty": qty, "net_amount": net, "vat_rate": "12.00",
            "vat_amount": vat, **extra}  # fmt: skip


async def test_us_m07_03_poll_sign_accept_and_receipt_from_einvoice(env: Env) -> None:
    """DoD-06 (fake operator): the poll stores the EHF ``received`` with ``risk_flag='unknown'``; the Buxgalter
    signs with E-IMZO (challenge → PKCS#7 → ``signed``, audit), accepts (``einvoice_accept`` job → operator →
    ``accepted``, signature passed); a receipt is made from it (19 §8) and posted with the credit deferred."""
    shop, product, wh = await _shop(env, "EHF qabul")
    port = FakeEInvoiceAdapter()
    einvoice_id = await _received(env, shop, port, [_line(product, "10.000", "100000.00", "12000.00")])
    got = (await env.client.get(f"{EI}/{einvoice_id}", headers=shop.h("accountant"))).json()
    assert (got["direction"], got["status"], got["risk_flag"], got["total_amount"]) == (
        "in", "received", "unknown", "112000.00",
    )  # fmt: skip
    assert got["counterparty"]["stir"] == "301234567"
    signed = await sign(env, shop, f"{EI}/{einvoice_id}", role="accountant", expect=200)
    assert signed.json()["status"] == "signed"
    [audit] = await rows(
        env, shop.tenant_id, "SELECT action, after FROM app.audit_log WHERE entity_id = :e AND action = 'einvoice.sign'",
        e=UUID(einvoice_id),
    )  # fmt: skip
    assert audit["after"]["document_hash"]
    queued = await env.client.post(f"{EI}/{einvoice_id}/accept", headers=shop.h("accountant"))
    assert (queued.status_code, queued.json()["status"]) == (202, "queued")
    [outcome] = await run_docs(env, shop, port)
    assert outcome.doc_status == "accepted"
    assert port.signatures[UUID(einvoice_id)] is not None  # the PKCS#7 went to the operator
    draft = await env.client.post(
        f"{GR}/from-einvoice/{einvoice_id}", json={"warehouse_id": str(wh)}, headers=shop.h("storekeeper", branch=shop.branch_id)
    )  # fmt: skip
    assert draft.status_code == 201, draft.text
    body = draft.json()
    assert (body["source"], body["einvoice_id"], body["einvoice_risk_flag"]) == (
        "einvoice",
        einvoice_id,
        "unknown",
    )
    assert [(ln["qty"], ln["net_amount"], ln["vat_amount"]) for ln in body["lines"]] == [
        ("10.000", "100000.00", "12000.00")
    ]
    again = await env.client.post(
        f"{GR}/from-einvoice/{einvoice_id}", json={"warehouse_id": str(wh)}, headers=shop.h("storekeeper", branch=shop.branch_id)
    )  # fmt: skip
    assert (again.status_code, err(again)) == (409, "EINVOICE_ALREADY_LINKED")
    posted = await env.client.post(
        f"{GR}/{body['id']}/post", headers=shop.h("accountant", branch=shop.branch_id)
    )
    assert posted.status_code == 200, posted.text
    vat = await rows(
        env, shop.tenant_id, "SELECT vat_amount FROM app.vat_moves WHERE doc_id = :d", d=UUID(body["id"])
    )
    assert vat == []  # QT-M07-09: unknown risk → credit waits for the payment


async def test_qt_m07_09_green_flag_releases_the_deferred_credit(env: Env) -> None:
    """QT-M07-09 / 13 §2.8: ``PATCH …/risk-flag`` ``green`` writes only ``vat_moves(input)`` for the posted
    receipt (dated today, ``doc_type='goods_receipts'``), audit ``einvoice.risk_flag_set``; a second ``green`` is a
    no-op; ``red`` → ``green`` never credits twice."""
    shop, product, wh = await _shop(env, "Yashil belgi")
    port = FakeEInvoiceAdapter()
    einvoice_id = await _accepted(env, shop, port, [_line(product, "5.000", "50000.00", "6000.00")])
    draft = (
        await env.client.post(
            f"{GR}/from-einvoice/{einvoice_id}", json={"warehouse_id": str(wh)}, headers=shop.h("owner", branch=shop.branch_id)
        )
    ).json()  # fmt: skip
    assert (
        await env.client.post(f"{GR}/{draft['id']}/post", headers=shop.h("owner", branch=shop.branch_id))
    ).status_code == 200
    ledger_before = await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.ledger_entries")
    flagged = await env.client.patch(
        f"{EI}/{einvoice_id}/risk-flag", json={"risk_flag": "green", "note": "my.soliq: yashil"},
        headers=shop.h("accountant"),
    )  # fmt: skip
    assert flagged.status_code == 200, flagged.text
    assert flagged.json() == {"id": einvoice_id, "risk_flag": "green", "vat_released": "6000.00"}
    vat = await rows(
        env,
        shop.tenant_id,
        "SELECT doc_type, doc_id, kind, base_amount, vat_amount, einvoice_id FROM app.vat_moves",
    )
    assert [(v["doc_type"], str(v["doc_id"]), v["kind"], v["base_amount"], v["vat_amount"], str(v["einvoice_id"])) for v in vat] == [
        ("goods_receipts", draft["id"], "input", D("50000.00"), D("6000.00"), einvoice_id)
    ]  # fmt: skip
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.ledger_entries") == ledger_before
    assert (
        await scalar(
            env, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'einvoice.risk_flag_set'"
        )
        == 1
    )
    for flag in ("red", "green"):
        again = await env.client.patch(
            f"{EI}/{einvoice_id}/risk-flag",
            json={"risk_flag": flag, "note": "qayta"},
            headers=shop.h("accountant"),
        )
        assert again.status_code == 200
        assert again.json()["vat_released"] == "0.00"
    assert await scalar(env, shop.tenant_id, "SELECT sum(vat_amount) FROM app.vat_moves") == D("6000.00")


async def test_acc_07_einvoice_line_amounts_are_authoritative(env: Env) -> None:
    """ACC-07: 3 × 333.33 ≠ 1000.00 — the receipt keeps the invoice ``net_amount``/``vat_amount``; the lot, the
    ``Dt 2910`` and the payable use them; ``cost`` is the derived 4-dp price. A PATCH that keeps the line keeps
    the amounts; a changed quantity is recomputed."""
    shop, product, wh = await _shop(env, "ACC-07")
    port = FakeEInvoiceAdapter()
    einvoice_id = await _accepted(env, shop, port, [_line(product, "3.000", "1000.00", "120.00")])
    draft = (
        await env.client.post(
            f"{GR}/from-einvoice/{einvoice_id}", json={"warehouse_id": str(wh)}, headers=shop.h("owner", branch=shop.branch_id)
        )
    ).json()  # fmt: skip
    [line] = draft["lines"]
    assert (line["cost"], line["net_amount"], line["vat_amount"], draft["total"]) == (
        "333.3333", "1000.00", "120.00", "1120.00",
    )  # fmt: skip
    patch_body = {
        "supplier_id": draft["supplier_id"], "warehouse_id": str(wh), "doc_date": draft["doc_date"],
        "lines": [{"product_id": product, "qty": "3.000", "cost": "333.3333", "vat_rate": "12.00",
                   "expiry_date": "2027-01-01"}],
    }  # fmt: skip
    kept = await env.client.patch(
        f"{GR}/{draft['id']}", json=patch_body, headers=shop.h("owner", branch=shop.branch_id)
    )
    assert kept.status_code == 200, kept.text
    assert (kept.json()["source"], kept.json()["lines"][0]["net_amount"]) == ("einvoice", "1000.00")
    posted = await env.client.post(f"{GR}/{draft['id']}/post", headers=shop.h("owner", branch=shop.branch_id))
    assert posted.status_code == 200, posted.text
    ledger = await rows(
        env, shop.tenant_id,
        "SELECT account_dt, account_kt, amount FROM app.ledger_entries WHERE doc_id = :d ORDER BY account_dt",
        d=UUID(draft["id"]),
    )  # fmt: skip
    assert [(x["account_kt"], x["amount"]) for x in ledger] == [("6010", D("1000.00")), ("6010", D("120.00"))]
    assert [x["account_dt"] for x in ledger][1] == "4410"  # the first is the warehouse's inv_acct (29xx)
    payable = await scalar(
        env, shop.tenant_id, "SELECT sum(amount) FROM app.debt_moves WHERE doc_id = :d", d=UUID(draft["id"])
    )
    assert payable == D("1120.00")
    lot_value = await scalar(
        env,
        shop.tenant_id,
        "SELECT sum(cost_amount) FROM app.stock_moves WHERE doc_id = :d",
        d=UUID(draft["id"]),
    )
    assert lot_value == D("1000.00")


async def test_from_einvoice_refusals_and_line_matching(env: Env) -> None:
    """19 §8: only an accepted incoming EHF (``409 EINVOICE_NOT_ACCEPTED``); 404 for an unknown id; an
    unmatched line → ``422 validation.einvoice_line_unmatched`` until mapped by ``lines[].product_id``."""
    shop, product, wh = await _shop(env, "Moslash")
    port = FakeEInvoiceAdapter()
    received = await _received(env, shop, port, [_line(product, "1.000", "100.00", "12.00")])
    h = shop.h("owner", branch=shop.branch_id)
    not_yet = await env.client.post(
        f"{GR}/from-einvoice/{received}", json={"warehouse_id": str(wh)}, headers=h
    )
    assert (not_yet.status_code, err(not_yet)) == (409, "EINVOICE_NOT_ACCEPTED")
    missing = await env.client.post(
        f"{GR}/from-einvoice/{UUID(int=1)}",
        json={"warehouse_id": str(wh)},
        headers=shop.h("owner", branch=shop.branch_id),
    )
    assert (missing.status_code, err(missing)) == (404, "NOT_FOUND")
    unmatched = {
        "name": "Noma'lum",
        "qty": "2.000",
        "net_amount": "200.00",
        "vat_rate": "12.00",
        "vat_amount": "24.00",
    }
    accepted = await _accepted(env, shop, port, [unmatched])
    refused = await env.client.post(
        f"{GR}/from-einvoice/{accepted}",
        json={"warehouse_id": str(wh)},
        headers=shop.h("owner", branch=shop.branch_id),
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["details"][0]["message_key"] == "validation.einvoice_line_unmatched"
    mapped = await env.client.post(
        f"{GR}/from-einvoice/{accepted}",
        json={"warehouse_id": str(wh), "lines": [{"line_no": 1, "product_id": product}]},
        headers=shop.h("owner", branch=shop.branch_id),
    )
    assert mapped.status_code == 201, mapped.text


async def test_eimzo_challenge_is_single_use_bound_and_verified(env: Env) -> None:
    """21 §5: a challenge is bound to the user and consumed once; a signature over other content or a foreign
    challenge → ``422 EIMZO_SIGN_FAILED``; accept before signing → ``409 EINVOICE_NOT_SIGNED``; re-sign →
    ``409 EINVOICE_ALREADY_SIGNED``."""
    shop, product, _ = await _shop(env, "Imzo")
    port = FakeEInvoiceAdapter()
    einvoice_id = await _received(env, shop, port, [_line(product, "1.000", "100.00", "12.00")])
    url = f"{EI}/{einvoice_id}"
    early = await env.client.post(f"{url}/accept", headers=shop.h("accountant"))
    assert (early.status_code, err(early)) == (409, "EINVOICE_NOT_SIGNED")
    wrong = await sign(env, shop, url, role="accountant", content="boshqa hujjat")
    assert (wrong.status_code, err(wrong), wrong.json()["error"]["params"]["reason"]) == (
        422, "EIMZO_SIGN_FAILED", "content_mismatch",
    )  # fmt: skip
    challenge = (await env.client.post(f"{url}/sign-challenge", headers=shop.h("accountant"))).json()
    foreign = await env.client.post(
        f"{url}/submit-signed",
        json={
            "challenge_id": challenge["challenge_id"],
            "signature_pkcs7": fake_pkcs7(challenge["document_hash"]),
        },
        headers=shop.h("owner"),  # another user
    )
    assert (foreign.status_code, foreign.json()["error"]["params"]["reason"]) == (422, "challenge_invalid")
    replay = await env.client.post(
        f"{url}/submit-signed",
        json={
            "challenge_id": challenge["challenge_id"],
            "signature_pkcs7": fake_pkcs7(challenge["document_hash"]),
        },
        headers=shop.h("accountant"),
    )
    assert (replay.status_code, replay.json()["error"]["params"]["reason"]) == (422, "challenge_invalid")
    await sign(env, shop, url, role="accountant", expect=200)
    twice = await env.client.post(f"{url}/sign-challenge", headers=shop.h("accountant"))
    assert (twice.status_code, err(twice)) == (409, "EINVOICE_ALREADY_SIGNED")
    stored = await scalar(
        env,
        shop.tenant_id,
        "SELECT count(*) FROM app.edoc_signatures WHERE entity_id = :e",
        e=UUID(einvoice_id),
    )
    assert stored == 1


async def test_reject_incoming_with_combined_ettn(env: Env) -> None:
    """19 §19 reject (``202``) → ``rejected``; the combined EHF+TTN created by the poll is rejected with it
    (``ettn_documents(direction='in', transport_type='seller_to_buyer')``)."""
    shop, product, _ = await _shop(env, "Rad etish")
    port = FakeEInvoiceAdapter()
    einvoice_id = await _received(
        env,
        shop,
        port,
        [_line(product, "1.000", "100.00", "12.00")],
        ettn={"operator_doc_id": "TTN-1", "vehicle": "01A"},
    )
    [ettn] = await rows(
        env, shop.tenant_id, "SELECT direction, transport_type, status, operator_doc_id FROM app.ettn_documents "
        "WHERE einvoice_id = :e", e=UUID(einvoice_id),
    )  # fmt: skip
    assert (ettn["direction"], ettn["transport_type"], ettn["status"]) == (
        "in",
        "seller_to_buyer",
        "received",
    )
    rejected = await env.client.post(
        f"{EI}/{einvoice_id}/reject", json={"reason": "Narx mos emas"}, headers=shop.h("accountant")
    )
    assert rejected.status_code == 202, rejected.text
    [outcome] = await run_docs(env, shop, port)
    assert outcome.doc_status == "rejected"
    statuses = await rows(
        env, shop.tenant_id,
        "SELECT e.status AS e, x.status AS x FROM app.einvoices e JOIN app.ettn_documents x ON x.einvoice_id = e.id",
    )  # fmt: skip
    assert statuses == [{"e": "rejected", "x": "rejected"}]


async def test_13_2_20_additional_einvoice_adjusts_supplier_return_vat(env: Env) -> None:
    """13 §2.20 / 26 #115: a posted return waits (``awaiting_einvoice``); the supplier's additional EHF
    (``factura_type='additional'``, ``related`` = original) is linked by the poll to that return; once accepted:
    ``Dt 6010 / Kt 4410`` = return VAT, payable −VAT, negative ``vat_moves`` within what was credited (green
    original → full), ``vat_adjustment_status='adjusted'`` and the return can no longer be cancelled."""
    shop, product, wh = await _shop(env, "Qaytarish EHF")
    port = FakeEInvoiceAdapter()
    original = incoming("301234567", [_line(product, "10.000", "10000.00", "1200.00")], risk_flag="green")
    port.inbox.append(original)
    await poll(env, shop, port)
    einvoice_id = str(
        await scalar(
            env,
            shop.tenant_id,
            "SELECT id FROM app.einvoices WHERE operator_doc_id = :o",
            o=original.operator_doc_id,
        )
    )
    await sign(env, shop, f"{EI}/{einvoice_id}", role="accountant", expect=200)
    await env.client.post(f"{EI}/{einvoice_id}/accept", headers=shop.h("accountant"))
    await run_docs(env, shop, port)
    receipt = (
        await env.client.post(
            f"{GR}/from-einvoice/{einvoice_id}", json={"warehouse_id": str(wh)}, headers=shop.h("owner", branch=shop.branch_id)
        )
    ).json()  # fmt: skip
    posted = (
        await env.client.post(f"{GR}/{receipt['id']}/post", headers=shop.h("owner", branch=shop.branch_id))
    ).json()
    line = posted["lines"][0]
    sr = await env.client.post(
        SR,
        json={"receipt_id": receipt["id"], "doc_date": posted["doc_date"], "reason": "damaged",
              "lines": [{"receipt_line_id": line["id"], "lot_id": line["lot_id"], "qty": "2.000"}]},
        headers=shop.h("owner", branch=shop.branch_id),
    )  # fmt: skip
    assert sr.status_code == 201, sr.text
    sr_posted = await env.client.post(
        f"{SR}/{sr.json()['id']}/post", headers=shop.h("owner", branch=shop.branch_id)
    )
    assert sr_posted.json()["vat_adjustment_status"] == "awaiting_einvoice"
    extra = incoming(
        "301234567", [_line(product, "-2.000", "-2000.00", "-240.00")], factura_type="additional",
        related=original.operator_doc_id,
    )  # fmt: skip
    port.inbox.append(extra)
    await poll(env, shop, port)
    [linked] = await rows(
        env, shop.tenant_id,
        "SELECT id, factura_type, related_einvoice_id, related_doc_type, related_doc_id FROM app.einvoices "
        "WHERE operator_doc_id = :o", o=extra.operator_doc_id,
    )  # fmt: skip
    assert (linked["factura_type"], str(linked["related_einvoice_id"]), linked["related_doc_type"]) == (
        "additional", einvoice_id, "supplier_returns",
    )  # fmt: skip
    assert str(linked["related_doc_id"]) == sr.json()["id"]
    await sign(env, shop, f"{EI}/{linked['id']}", role="accountant", expect=200)
    await env.client.post(f"{EI}/{linked['id']}/accept", headers=shop.h("accountant"))
    await run_docs(env, shop, port)
    sr_id = UUID(sr.json()["id"])
    ledger = await rows(
        env, shop.tenant_id,
        "SELECT account_dt, account_kt, amount, analytics FROM app.ledger_entries WHERE doc_id = :d AND account_kt = '4410'",
        d=sr_id,
    )  # fmt: skip
    assert [(x["account_dt"], x["amount"]) for x in ledger] == [("6010", D("240.00"))]
    assert "vat_credit" not in ledger[0]["analytics"]  # green original: the credit was taken
    vat = await rows(
        env, shop.tenant_id, "SELECT base_amount, vat_amount FROM app.vat_moves WHERE doc_id = :d", d=sr_id
    )
    assert [(v["base_amount"], v["vat_amount"]) for v in vat] == [(D("-2000.00"), D("-240.00"))]
    debt = await rows(
        env, shop.tenant_id, "SELECT amount FROM app.debt_moves WHERE doc_id = :d ORDER BY id", d=sr_id
    )
    assert [d["amount"] for d in debt] == [D("-2000.00"), D("-240.00")]
    got = (await env.client.get(f"{SR}/{sr_id}", headers=shop.h("owner"))).json()
    assert got["vat_adjustment_status"] == "adjusted"
    cancel = await env.client.post(
        f"{SR}/{sr_id}/cancel", json={"reason": "x"}, headers=shop.h("owner", branch=shop.branch_id)
    )
    assert (cancel.status_code, cancel.json()["error"]["params"]["reason"]) == (409, "vat_adjusted")


async def test_permissions_and_risk_flag_on_outgoing(env: Env) -> None:
    """19 §19: incoming e-invoices — ``purchases.post`` (Omborchi 403); risk flag only on incoming (409)."""
    shop, product, _ = await _shop(env, "Ruxsat")
    port = FakeEInvoiceAdapter()
    await _received(env, shop, port, [_line(product, "1.000", "100.00", "12.00")])
    denied = await env.client.get(f"{EI}?direction=in", headers=shop.h("storekeeper"))
    assert (denied.status_code, err(denied)) == (403, "PERMISSION_DENIED")
    listed = await env.client.get(f"{EI}?direction=in&risk_flag=unknown", headers=shop.h("accountant"))
    assert [x["status"] for x in listed.json()["items"]] == ["received"]
    assert (
        await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.counterparties WHERE stir = '301234567'")
        == 1
    )
