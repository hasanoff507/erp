"""POS-13 debt payment via a dynamic checkout — Click / Payme / Uzum / dynamic UzQR (18 §12.2 + §16; B4 WEB-10
moved to B5). ``debt_payment.created`` with ``checkout_ref`` consumes a confirmed checkout exactly once; postings per
13 §2.14 (``Dt 5710 / Kt 4010``, analytics ``payment_method``)."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.db.base import uuid7
from tests.support.debts import customer, debt_payment, debt_sale, deliver_debt, item, ledger, open_docs
from tests.support.payments import (
    PayEnv,
    confirm,
    connect_all,
    create_checkout,
    get_checkout,
    payments_env_fixture,
)
from tests.support.sales import D, make_pos, rows

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["payments_env_fixture"]


@pytest.mark.parametrize("provider", ["click", "payme", "uzum", "uzqr"])
async def test_pos13_debt_payment_via_checkout(env: PayEnv, provider: str) -> None:
    pos = await make_pos(env, account="2910")
    keys = await connect_all(env, pos)
    cid = await customer(env, pos)
    a = await item(env, pos, "50000.0000")
    await debt_sale(env, pos, cid, [(a, "2.000", "50000.0000")])
    checkout = await create_checkout(env, pos, provider, "30000.00")
    extra = {"qr_type": "dynamic"} if provider == "uzqr" else {}
    tx = checkout["provider_tx_id"] or "pending-tx"
    early = debt_payment(pos, cid, "30000.00", await open_docs(env, pos, cid), method=provider,
                         checkout_ref=checkout["checkout_ref"], provider_tx_id=tx, **extra)  # fmt: skip
    pending = await deliver_debt(env, pos, "debt_payment.created", early)
    assert (
        pending.code == "PAYMENT_NOT_CONFIRMED"
    )  # online only; «to'lov kutilmoqda» until the provider confirms
    tx = await confirm(env, keys, provider, checkout)
    if provider == "uzum":  # dynamic QR poll could also confirm; the Merchant API webhook already did
        assert (await get_checkout(env, pos, checkout["checkout_ref"]))["provider_tx_id"] == tx
    wrong_tx = debt_payment(pos, cid, "30000.00", await open_docs(env, pos, cid), method=provider,
                            checkout_ref=checkout["checkout_ref"], provider_tx_id="forged", **extra)  # fmt: skip
    assert (await deliver_debt(env, pos, "debt_payment.created", wrong_tx)).code == "PAYMENT_NOT_CONFIRMED"
    wrong_amount = debt_payment(pos, cid, "29000.00", await open_docs(env, pos, cid), method=provider,
                                checkout_ref=checkout["checkout_ref"], provider_tx_id=tx, **extra)  # fmt: skip
    assert (
        await deliver_debt(env, pos, "debt_payment.created", wrong_amount)
    ).code == "PAYMENT_NOT_CONFIRMED"
    payload = debt_payment(pos, cid, "30000.00", await open_docs(env, pos, cid), method=provider,
                           checkout_ref=checkout["checkout_ref"], provider_tx_id=tx, **extra)  # fmt: skip
    res = await deliver_debt(env, pos, "debt_payment.created", payload)
    assert res.error is None, (res.error.code, res.error.params, res.error.details) if res.error else None
    assert res.server["remaining_balance"] == "70000.00"
    assert await ledger(env, pos, payload["id"]) == {("5710", "4010"): D("30000.00")}  # 13 §2.14
    entries = await rows(env.db, pos.tenant_id,
                         "SELECT analytics FROM app.ledger_entries WHERE doc_id = :d", d=payload["id"])  # fmt: skip
    assert all(e["analytics"].get("payment_method") == provider for e in entries)
    stored = await rows(env.db, pos.tenant_id, "SELECT method, provider_tx_id, checkout_ref, status "
                        "FROM app.debt_payments WHERE id = :d", d=payload["id"])  # fmt: skip
    assert stored == [{"method": provider, "provider_tx_id": tx, "checkout_ref": UUID(checkout["checkout_ref"]),
                       "status": "posted"}]  # fmt: skip
    assert (await get_checkout(env, pos, checkout["checkout_ref"]))["status"] == "consumed"
    receipt = await rows(env.db, pos.tenant_id, "SELECT kind FROM app.fiscal_receipts WHERE debt_payment_id = :d",
                         d=payload["id"])  # fmt: skip
    assert receipt == [{"kind": "debt_settlement"}]
    replay = debt_payment(pos, cid, "30000.00", await open_docs(env, pos, cid), method=provider,
                          checkout_ref=checkout["checkout_ref"], provider_tx_id=tx, **extra)  # fmt: skip
    again = await deliver_debt(env, pos, "debt_payment.created", replay)
    assert again.code == "PAYMENT_NOT_CONFIRMED"  # one checkout — one payment, never counted twice


async def test_pos13_checkout_of_another_register_is_refused(env: PayEnv) -> None:
    pos = await make_pos(env, account="2910")
    keys = await connect_all(env, pos)
    cid = await customer(env, pos)
    a = await item(env, pos, "10000.0000")
    await debt_sale(env, pos, cid, [(a, "1.000", "10000.0000")])
    checkout = await create_checkout(env, pos, "click", "10000.00")
    tx = await confirm(env, keys, "click", checkout)
    payload = debt_payment(pos, cid, "10000.00", await open_docs(env, pos, cid), method="payme",
                           checkout_ref=checkout["checkout_ref"], provider_tx_id=tx)  # fmt: skip
    assert (await deliver_debt(env, pos, "debt_payment.created", payload)).code == "PAYMENT_NOT_CONFIRMED"
    payload = debt_payment(pos, cid, "10000.00", await open_docs(env, pos, cid), method="click",
                           checkout_ref=str(uuid7()), provider_tx_id=tx)  # fmt: skip
    assert (await deliver_debt(env, pos, "debt_payment.created", payload)).code == "PAYMENT_NOT_CONFIRMED"
