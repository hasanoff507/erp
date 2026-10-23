"""E-ishonchnoma (19 §8a; 21 §6; 12 ``powers_of_attorney``; BP-01 1a; qaror #63; DoD-03 acceptance criteria)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.integrations.einvoice.application.ports import PoaState
from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter
from tests.support.edocs import POA, ROLES, Env, Shop, edocs_env_fixture, err, poll, rows, run_docs, sign
from tests.support.purchasing import create_supplier

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["edocs_env_fixture"]


async def _create(env: Env, shop: Shop, supplier: str, **extra: Any) -> Any:
    body = {"supplier_id": supplier, "employee_user_id": str(shop.user_ids["storekeeper"]), "doc_date": "2026-10-10",
            **extra}  # fmt: skip
    return await env.client.post(POA, json=body, headers=shop.h("storekeeper", branch=shop.branch_id))


async def test_poa_create_sign_send_and_supplier_accepts(env: Env) -> None:
    """``POST`` (``purchases.create``) → ``pending_signature`` (``valid_to`` = from + 10 days); the Buxgalter signs
    (``einvoice.sign``) → ``202 sending`` + ``poa_send`` → operator → ``sent`` (``number``, ``sent_at``); the
    supplier's answer is polled → ``accepted`` (``responded_at``)."""
    shop = await env.shop("Ishonchnoma", *ROLES)
    supplier = (await create_supplier(env.client, shop))["id"]
    created = await _create(env, shop, supplier, valid_from="2026-10-10")
    assert created.status_code == 201, created.text
    poa = created.json()
    assert (poa["status"], poa["valid_from"], poa["valid_to"], poa["number"], poa["version"]) == (
        "pending_signature", "2026-10-10", "2026-10-20", None, 1,
    )  # fmt: skip
    url = f"{POA}/{poa['id']}"
    denied = await env.client.post(
        f"{url}/sign-challenge", headers=shop.h("storekeeper", branch=shop.branch_id)
    )
    assert (denied.status_code, err(denied)) == (403, "PERMISSION_DENIED")
    sending = await sign(env, shop, url, role="accountant", branch=shop.branch_id)
    assert (sending.status_code, sending.json()) == (202, {"id": poa["id"], "status": "sending"})
    port = FakeEInvoiceAdapter()
    [outcome] = await run_docs(env, shop, port)
    assert (outcome.kind, outcome.doc_status) == ("poa_send", "sent")
    got = (await env.client.get(url, headers=shop.h("storekeeper", branch=shop.branch_id))).json()
    assert got["status"] == "sent" and got["number"].startswith("FAKE-POA-") and got["sent_at"]
    port.poa_states[got["operator_doc_id"]] = PoaState("accepted")
    assert (await poll(env, shop, port)).updated_poa == 1
    final = (await env.client.get(url, headers=shop.h("storekeeper", branch=shop.branch_id))).json()
    assert final["status"] == "accepted" and final["responded_at"]
    listed = await env.client.get(
        f"{POA}?supplier_id={supplier}&status=accepted", headers=shop.h("accountant")
    )
    assert [x["id"] for x in listed.json()["items"]] == [poa["id"]]


async def test_poa_validation_cancel_and_failed_resign(env: Env) -> None:
    """``valid_to < valid_from`` → 422; unknown supplier → 404; cancel only before signing (409 after);
    a rejected send → ``failed`` (``last_error``) → signed again → ``sending``; the supplier's ``rejected``
    answer keeps ``reject_reason``."""
    shop = await env.shop("Ishonchnoma 2", *ROLES)
    supplier = (await create_supplier(env.client, shop))["id"]
    bad = await _create(env, shop, supplier, valid_from="2026-10-10", valid_to="2026-10-01")
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["message_key"] == "validation.valid_to_before_valid_from"
    missing = await _create(env, shop, str(UUID(int=7)))
    assert (missing.status_code, missing.json()["error"]["params"]["resource"]) == (404, "counterparty")
    first = (await _create(env, shop, supplier)).json()
    cancelled = await env.client.post(
        f"{POA}/{first['id']}/cancel",
        json={"reason": "kerak emas"},
        headers=shop.h("storekeeper", branch=shop.branch_id),
    )
    assert cancelled.json() == {"id": first["id"], "status": "cancelled"}
    second = (await _create(env, shop, supplier)).json()
    url = f"{POA}/{second['id']}"
    await sign(env, shop, url, role="accountant", branch=shop.branch_id, expect=202)
    late = await env.client.post(
        f"{url}/cancel", json={"reason": "x"}, headers=shop.h("storekeeper", branch=shop.branch_id)
    )
    assert (late.status_code, err(late)) == (409, "DOC_INVALID_STATE")
    [outcome] = await run_docs(env, shop, FakeEInvoiceAdapter(reject_send=True))
    assert (outcome.status, outcome.doc_status) == ("failed", "failed")
    failed = (await env.client.get(url, headers=shop.h("accountant"))).json()
    assert failed["status"] == "failed" and "rejected" in failed["last_error"]
    again = await sign(env, shop, url, role="accountant", branch=shop.branch_id)
    assert again.json()["status"] == "sending"
    port = FakeEInvoiceAdapter()
    await run_docs(env, shop, port)
    sent = (await env.client.get(url, headers=shop.h("accountant"))).json()
    port.poa_states[sent["operator_doc_id"]] = PoaState("rejected", "Muddati qisqa")
    await poll(env, shop, port)
    [row] = await rows(env, shop.tenant_id, "SELECT status, reject_reason FROM app.powers_of_attorney WHERE id = :i",
                       i=UUID(second["id"]))  # fmt: skip
    assert (row["status"], row["reject_reason"]) == ("rejected", "Muddati qisqa")


async def test_poa_default_valid_from_is_today(env: Env) -> None:
    """19 §8a: ``valid_from`` defaults to the business day, ``valid_to`` to +10 days."""
    from app.modules.accounting.wiring import business_today

    shop = await env.shop("Ishonchnoma 3", *ROLES)
    supplier = (await create_supplier(env.client, shop))["id"]
    body = (await _create(env, shop, supplier)).json()
    today = business_today()
    assert (date.fromisoformat(body["valid_from"]), date.fromisoformat(body["valid_to"])) == (
        today, today + timedelta(days=10),
    )  # fmt: skip
