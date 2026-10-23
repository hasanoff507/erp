"""E-TTN sign / send / manual registration / receiver answer (19 §20, §13; 21 §3, §5; qaror #63; QT-M06-07;
DoD-07 with the fake operator)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter
from tests.support.edocs import (
    ETTN,
    ROLES,
    Env,
    Shop,
    edocs_env_fixture,
    err,
    execute,
    rows,
    run_docs,
    run_ettn,
    sign,
)
from tests.support.inventory import new_product, set_method
from tests.support.inventory_docs import act, create_transfer, ok, receive_body, stock_in, two_branches

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["edocs_env_fixture"]


async def _posted(env: Env, name: str) -> tuple[Shop, dict[str, Any], str, UUID]:
    shop = await env.shop(name, *ROLES)
    await set_method(env, shop, "fifo")
    src, branch, dst = await two_branches(env, shop)
    product = await new_product(env, shop)
    await stock_in(env, shop, src, product, "5.000", "25000.00")
    doc = await create_transfer(env, shop, src, dst, [(product, "2.000")])
    posted = await ok(await act(env, shop, doc["id"], "post"))
    # the fake operator's unsigned auto-send (27 B2) is not what is tested here: drop it
    await execute(env, shop.tenant_id, "DELETE FROM app.outbox_jobs WHERE kind = 'ettn_send'")
    return shop, posted, posted["ettn"]["id"], branch


async def test_qt_m06_07_ettn_signed_sent_and_registered(env: Env) -> None:
    """QT-M06-07 / DoD-07: ``pending_signature`` → E-IMZO ``submit-signed`` (``202 sending``, ``ettn_send`` job)
    → the operator gets the payload WITH the sender's PKCS#7 → ``registered``, ``transfers.ettn_ref``; the
    transfer can be sent; the receiving branch accepts after ``receive`` (signed, ``ettn_accept``)."""
    shop, transfer, ettn_id, _ = await _posted(env, "E-TTN imzo")
    url = f"{ETTN}/{ettn_id}"
    blocked = await act(env, shop, transfer["id"], "send")
    assert (blocked.status_code, err(blocked)) == (409, "ETTN_REQUIRED")
    sending = await sign(env, shop, url)
    assert (sending.status_code, sending.json()["status"]) == (202, "sending")
    port = FakeEInvoiceAdapter()
    [outcome] = await run_ettn(env, shop, port)
    assert outcome.ettn_status == "registered"
    assert port.signatures[UUID(ettn_id)] is not None
    assert port.sent_ettn[UUID(ettn_id)]["transport_type"] == "warehouse_to_warehouse"
    got = (await env.client.get(url, headers=shop.h("owner"))).json()
    assert got["status"] == "registered" and got["operator_doc_id"].startswith("FAKE-TTN-")
    early = await env.client.post(f"{url}/sign-challenge?action=accept", headers=shop.h("owner"))
    assert (early.status_code, early.json()["error"]["params"]["reason"]) == (409, "transfer_not_received")
    sent = await ok(await act(env, shop, transfer["id"], "send"))
    assert sent["ettn_ref"] == got["operator_doc_id"]
    await ok(await act(env, shop, transfer["id"], "receive", json=receive_body(sent)))
    accepted = await sign(env, shop, url, submit="accept", action="accept")
    assert accepted.status_code == 202, accepted.text
    [answer] = await run_docs(env, shop, port)
    assert (answer.kind, answer.doc_status) == ("ettn_accept", "accepted")
    assert ("respond_ettn:accept", ettn_id) in port.calls


async def test_ettn_register_manual_and_resign_after_failure(env: Env) -> None:
    """19 §20 ``register-manual`` (operator cabinet): ``registered`` + ``transfers.ettn_ref`` + audit; a second
    registration → ``409``. A permanently rejected send → ``failed`` → signed again → ``sending``."""
    shop, transfer, ettn_id, _ = await _posted(env, "E-TTN qo'lda")
    url = f"{ETTN}/{ettn_id}"
    await sign(env, shop, url, expect=202)
    [outcome] = await run_ettn(env, shop, FakeEInvoiceAdapter(reject_ettn=True))
    assert outcome.ettn_status == "failed"
    resent = await sign(env, shop, url)
    assert (resent.status_code, resent.json()["status"]) == (202, "sending")
    manual = await env.client.post(
        f"{url}/register-manual", json={"operator_doc_id": "TTN-CAB-77", "doc_date": transfer["doc_date"]},
        headers=shop.h("storekeeper"),
    )  # fmt: skip
    assert manual.status_code == 200, manual.text
    assert (manual.json()["status"], manual.json()["operator_doc_id"]) == ("registered", "TTN-CAB-77")
    [row] = await rows(
        env, shop.tenant_id, "SELECT ettn_ref FROM app.transfers WHERE id = :id", id=UUID(transfer["id"])
    )
    assert row["ettn_ref"] == "TTN-CAB-77"
    [skipped] = await run_ettn(env, shop, FakeEInvoiceAdapter())  # the queued send finds it registered
    assert skipped.status == "skipped"
    again = await env.client.post(
        f"{url}/register-manual", json={"operator_doc_id": "X", "doc_date": transfer["doc_date"]},
        headers=shop.h("storekeeper"),
    )  # fmt: skip
    assert (again.status_code, err(again)) == (409, "DOC_INVALID_STATE")
    audit = await rows(
        env, shop.tenant_id, "SELECT 1 FROM app.audit_log WHERE action = 'ettn.registered_manually'"
    )
    assert len(audit) == 1


async def test_ettn_list_filters_and_permissions(env: Env) -> None:
    """19 §20 list (``stock.view``) with ``transfer_id``/``status`` filters; signing needs ``einvoice.sign``."""
    shop, transfer, ettn_id, _ = await _posted(env, "E-TTN ro'yxat")
    listed = await env.client.get(f"{ETTN}?transfer_id={transfer['id']}", headers=shop.h("storekeeper"))
    assert [x["id"] for x in listed.json()["items"]] == [ettn_id]
    none = await env.client.get(f"{ETTN}?status=registered", headers=shop.h("storekeeper"))
    assert none.json()["items"] == []
    denied = await env.client.post(f"{ETTN}/{ettn_id}/sign-challenge", headers=shop.h("storekeeper"))
    assert (denied.status_code, err(denied)) == (403, "PERMISSION_DENIED")
