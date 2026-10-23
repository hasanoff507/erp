"""Outgoing e-invoices (18 §14a; 21 §2 "Chiquvchi e-faktura oqimi"; 13 §2.22, §2.24; US-M01-06, QT-M01-09)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.core.db.session import tenant_transaction
from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter, einvoice_hooks
from tests.support.edocs import EI, Env, edocs_env_fixture, err, execute, poll, rows, run_docs, scalar, sign
from tests.support.sales import Pos, add_customer, make_pos, new_item, sale_line, sale_payload, sell

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["edocs_env_fixture"]

D = Decimal


async def _company(env: Env, pos: Pos, *, stir: str | None = "302345678") -> UUID:
    cid = await add_customer(env, pos, kind="company")
    await execute(
        env, pos.tenant_id, "UPDATE app.counterparties SET stir = :s WHERE id = :id", s=stir, id=cid
    )
    return cid


async def _counts(env: Env, pos: Pos) -> tuple[int, int]:
    ledger = await scalar(env, pos.tenant_id, "SELECT count(*) FROM app.ledger_entries")
    vat = await scalar(env, pos.tenant_id, "SELECT count(*) FROM app.vat_moves")
    return int(ledger), int(vat)


async def _cash_sale(env: Env, pos: Pos, product: UUID, qty: str = "2.000") -> dict[str, Any]:
    payload = sale_payload(pos, [sale_line(product, qty=qty, price="12000.0000")])
    await sell(env, pos, payload)
    return payload


async def test_qt_m01_09_einvoice_from_receipt_no_second_vat(env: Env) -> None:
    """QT-M01-09 / 13 §2.22: a B2C receipt, later an EHF for a company — ``related_doc_type='sales'``, lines and
    amounts from the receipt, no new ``ledger_entries``/``vat_moves``; one active EHF per receipt
    (``409 EINVOICE_ALREADY_LINKED``); sign → send (``202``) → operator ``sent`` → poll ``accepted``."""
    pos = await make_pos(env, "Chekdan EHF")
    product = await new_item(env, pos, "Shakar 1kg", price="12000.00")
    sale = await _cash_sale(env, pos, product)
    company = await _company(env, pos)
    before = await _counts(env, pos)
    created = await env.client.post(
        f"{EI}/from-receipt",
        json={"sale_id": sale["id"], "counterparty_id": str(company)},
        headers=pos.shop.h("owner"),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["direction"], body["status"], body["related_doc_type"], body["related_doc_id"]) == (
        "out", "draft", "sales", sale["id"],
    )  # fmt: skip
    assert (body["total_amount"], body["vat_amount"]) == ("24000.00", "2571.43")
    [line] = body["payload"]["lines"]
    assert (line["qty"], line["net_amount"], line["vat_amount"]) == ("2.000", "21428.57", "2571.43")
    assert await _counts(env, pos) == before  # 13 §2.22: no posting
    again = await env.client.post(
        f"{EI}/from-receipt",
        json={"sale_id": sale["id"], "counterparty_id": str(company)},
        headers=pos.shop.h("owner"),
    )
    assert (again.status_code, err(again)) == (409, "EINVOICE_ALREADY_LINKED")
    url = f"{EI}/{body['id']}"
    early = await env.client.post(f"{url}/send", headers=pos.shop.h("owner"))
    assert (early.status_code, err(early)) == (409, "EINVOICE_NOT_SIGNED")
    await sign(env, pos.shop, url, role="accountant", expect=200)
    queued = await env.client.post(f"{url}/send", headers=pos.shop.h("accountant"))
    assert queued.status_code == 202, queued.text
    port = FakeEInvoiceAdapter()
    [outcome] = await run_docs(env, pos.shop, port)
    assert (outcome.kind, outcome.doc_status) == ("einvoice_send", "sent")
    sent = (await env.client.get(url, headers=pos.shop.h("accountant"))).json()
    assert sent["status"] == "sent" and sent["operator_doc_id"]
    port.statuses[sent["operator_doc_id"]] = "accepted"
    result = await poll(env, pos.shop, port)
    assert result.updated_out == 1
    assert (await env.client.get(url, headers=pos.shop.h("accountant"))).json()["status"] == "accepted"
    assert await _counts(env, pos) == before


async def test_13_2_22_einvoice_amount_never_exceeds_receipt(env: Env) -> None:
    """13 §2.22: explicit lines above the receipt (less returns) → ``422 EINVOICE_AMOUNT_EXCEEDS_RECEIPT``; a
    counterparty without STIR → ``422 EINVOICE_COUNTERPARTY_INCOMPLETE``; a manual EHF without lines → 422."""
    pos = await make_pos(env, "EHF chegarasi")
    product = await new_item(env, pos, "Guruch 1kg", price="12000.00")
    sale = await _cash_sale(env, pos, product, qty="1.000")
    company = await _company(env, pos)
    too_much = await env.client.post(
        EI,
        json={"counterparty_id": str(company), "related_doc_type": "sales", "related_doc_id": sale["id"],
              "lines": [{"name": "Guruch", "qty": "2.000", "price": "10714.2900", "vat_rate": "12.00"}]},
        headers=pos.shop.h("owner"),
    )  # fmt: skip
    assert (too_much.status_code, err(too_much)) == (422, "EINVOICE_AMOUNT_EXCEEDS_RECEIPT")
    no_stir = await _company(env, pos, stir=None)
    incomplete = await env.client.post(
        f"{EI}/from-receipt",
        json={"sale_id": sale["id"], "counterparty_id": str(no_stir)},
        headers=pos.shop.h("owner"),
    )
    assert (incomplete.status_code, err(incomplete)) == (422, "EINVOICE_COUNTERPARTY_INCOMPLETE")
    manual = await env.client.post(EI, json={"counterparty_id": str(company)}, headers=pos.shop.h("owner"))
    assert manual.status_code == 422
    ok = await env.client.post(
        EI,
        json={"counterparty_id": str(company), "lines": [{"name": "Xizmat", "qty": "1.000", "price": "1000.0000",
                                                           "vat_rate": "12.00"}]},
        headers=pos.shop.h("owner"),
    )  # fmt: skip
    assert ok.status_code == 201, ok.text
    assert (ok.json()["total_amount"], ok.json()["related_doc_id"]) == ("1120.00", None)
    cancelled = await env.client.post(
        f"{EI}/{ok.json()['id']}/cancel", json={"reason": "xato"}, headers=pos.shop.h("owner")
    )
    assert cancelled.json() == {"id": ok.json()["id"], "status": "cancelled"}


async def test_us_m01_06_b2b_credit_sale_gets_a_draft(env: Env) -> None:
    """US-M01-06 / 13 §2.24 (contract 5a): a credit sale to a company → the hook makes one ``draft``
    (``related_doc_type='sales'``), idempotent, no postings; a sale to a person or a cash sale → nothing."""
    pos = await make_pos(env, "B2B nasiya")
    product = await new_item(env, pos, "Un 1kg", price="12000.00")
    company = await _company(env, pos)
    lines = [sale_line(product, qty="1.000", price="12000.0000")]
    debt_sale = sale_payload(
        pos, lines, [{"method": "debt", "amount": "12000.00"}], counterparty_id=str(company)
    )
    await sell(env, pos, debt_sale)
    person = await add_customer(env, pos)
    person_sale = sale_payload(
        pos, [sale_line(product, qty="1.000", price="12000.0000")], [{"method": "debt", "amount": "12000.00"}],
        counterparty_id=str(person),
    )  # fmt: skip
    await sell(env, pos, person_sale)
    before = await _counts(env, pos)
    hooks = einvoice_hooks()
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        first = await hooks.on_b2b_credit_sale_posted(s, pos.tenant_id, UUID(debt_sale["id"]))
        second = await hooks.on_b2b_credit_sale_posted(s, pos.tenant_id, UUID(debt_sale["id"]))
        none = await hooks.on_b2b_credit_sale_posted(s, pos.tenant_id, UUID(person_sale["id"]))
    assert first is not None and first == second and none is None
    [draft] = await rows(
        env, pos.tenant_id, "SELECT status, direction, related_doc_type, related_doc_id, counterparty_id, total_amount, "
        "payload->>'source' AS source FROM app.einvoices",
    )  # fmt: skip
    assert (draft["status"], draft["direction"], draft["related_doc_type"], str(draft["related_doc_id"])) == (
        "draft", "out", "sales", debt_sale["id"],
    )  # fmt: skip
    assert (draft["counterparty_id"], draft["total_amount"], draft["source"]) == (
        company,
        D("12000.00"),
        "b2b_credit_sale",
    )
    assert await _counts(env, pos) == before
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        alerts = await hooks.alerts(s)
    assert alerts["outgoing_drafts"] == 1
