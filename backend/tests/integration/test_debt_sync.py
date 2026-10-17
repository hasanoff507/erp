"""Debt book over ``/sync/push`` and ``/sync/pull`` (18 §11.1, §12.2; 16 §1, §3, §5).

QT-M08-04 (new limit reaches the POS at once), QT-M08-08 (quick customer + debt sale in one push), the
``customers`` scope ``open_debt_docs[]`` and ``debt_payment.created`` accepted end to end."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.money import line_total, money_str, vat_from_gross
from app.modules.accounting.wiring import business_today
from app.shared.debt_allocation import allocate_json
from tests.support.auth import new_phone
from tests.support.catalog import set_price
from tests.support.inventory import new_product
from tests.support.inventory_docs import stock_in
from tests.support.sales import open_shift_sql
from tests.support.sync import Pos as SyncPos
from tests.support.sync import (
    SyncEnv,
    event,
    execute,
    pos_device,
    pull_all,
    push_ok,
    rows,
    scalar,
    settle_clock,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]
API = "/api/v1"


async def _setup(env: SyncEnv, name: str) -> tuple[SyncPos, UUID, UUID]:
    shop = await env.shop(name)
    pos = await pos_device(env, shop)
    assert pos.register_id is not None
    await execute(
        env.db,
        shop.tenant_id,
        "UPDATE app.cash_registers SET fm_state = 'ok' WHERE id = :r",
        r=pos.register_id,
    )
    shift = await open_shift_sql(env.db, shop, pos.register_id, pos.device_id, pos.user_id)
    wh = UUID(str(await scalar(env.db, shop.tenant_id, "SELECT id FROM app.warehouses LIMIT 1")))
    product = await new_product(env, shop, "Shakar 1kg")
    await set_price(env.client, shop, str(product), "15000.0000")
    await stock_in(env, shop, wh, product, "50.000", "500000.00")
    return pos, shift, product


def _sale(pos: SyncPos, shift: UUID, product: UUID, cid: UUID, qty: str = "2.000") -> dict[str, Any]:
    total = line_total(qty, "15000.0000")
    line = {
        "id": str(uuid7()),
        "product_id": str(product),
        "unit_code": "box",
        "qty": qty,
        "price": "15000.0000",
        "vat_rate": "12.00",
        "line_total": money_str(total),
        "vat_amount": money_str(vat_from_gross(total, "12.00")),
    }
    return {
        "id": str(uuid7()),
        "branch_id": str(pos.branch_id),
        "cash_register_id": str(pos.register_id),
        "shift_id": str(shift),
        "receipt_seq": None,
        "temp_number": f"{pos.device_id}-{uuid7().hex[-8:]}",
        "doc_date": business_today().isoformat(),
        "counterparty_id": str(cid),
        "lines": [line],
        "payments": [{"method": "debt", "amount": money_str(total), "due_date": "2030-01-31"}],
        "is_offline": True,
        "offline_since": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


async def _customers(
    env: SyncEnv, pos: SyncPos, cursor: str | None = None
) -> tuple[list[dict[str, Any]], str]:
    await settle_clock(env, pos.shop.tenant_id)
    pages = await pull_all(env, pos, "customers", cursor)
    return [c for p in pages for c in p["customers"]], pages[-1]["cursor"]


async def test_qt_m08_08_quick_customer_and_debt_sale_in_one_push(env: SyncEnv) -> None:
    pos, shift, product = await _setup(env, "quick-customer")
    cid = uuid7()
    customer = {"id": str(cid), "kind": "person", "name": "Karimov Anvar", "phone": "90 123 45 67"}
    results = await push_ok(
        env,
        pos,
        [
            event(pos, "counterparty.created", customer),
            event(pos, "sale.created", _sale(pos, shift, product, cid)),
        ],
    )
    assert [r["status"] for r in results] == ["accepted", "accepted"], results
    assert results[0]["server"] == {"id": str(cid)}
    assert results[1]["server"]["fiscal"]["status"] == "deferred"
    row = (
        await rows(
            env.db,
            pos.shop.tenant_id,
            "SELECT name, phone, is_customer, credit_limit FROM app.counterparties WHERE id = :c",
            c=cid,
        )
    )[0]
    assert row == {
        "name": "Karimov Anvar",
        "phone": "+998901234567",
        "is_customer": True,
        "credit_limit": None,
    }
    moves = await rows(
        env.db,
        pos.shop.tenant_id,
        "SELECT amount, due_date FROM app.debt_moves WHERE counterparty_id = :c",
        c=cid,
    )
    assert [(m["amount"], m["due_date"]) for m in moves] == [(30000, date(2030, 1, 31))]
    # replay of the same customer under a new event id (lost answer) — same row; another body under the id → 422
    again = await push_ok(env, pos, [event(pos, "counterparty.created", customer)])
    assert again[0]["status"] == "accepted"
    clash = await push_ok(env, pos, [event(pos, "counterparty.created", customer | {"name": "Boshqa"})])
    assert clash[0]["status"] == "rejected", clash
    assert clash[0]["details"][0]["field"] == "id", clash[0]["details"]


async def test_pull_customers_open_debt_docs_and_qt_m08_04_limit_delta(env: SyncEnv) -> None:
    pos, shift, product = await _setup(env, "pull-customers")
    cid = uuid7()
    await push_ok(
        env,
        pos,
        [
            event(pos, "counterparty.created", {"id": str(cid), "name": "Ali", "phone": new_phone()}),
            event(pos, "sale.created", _sale(pos, shift, product, cid, "3.000")),
        ],
    )
    customers, cursor = await _customers(env, pos)
    me = next(c for c in customers if c["id"] == str(cid))
    assert me["receivable_balance"] == "45000.00" and me["credit_limit"] is None
    (doc,) = me["open_debt_docs"]
    assert (doc["doc_type"], doc["open_amount"], doc["due_date"]) == ("sales", "45000.00", "2030-01-31")
    assert doc["lines"][0]["name"] == "Shakar 1kg" and doc["lines"][0]["settled_amount"] == "0.00"
    # QT-M08-04: the manager raises the limit — the next delta pull carries it to every register
    version = await scalar(
        env.db, pos.shop.tenant_id, "SELECT version FROM app.counterparties WHERE id = :c", c=cid
    )
    patched = await env.client.patch(
        f"{API}/counterparties/{cid}",
        json={"version": version, "credit_limit": "800000.00"},
        headers=pos.shop.h("owner"),
    )
    assert patched.status_code == 200, patched.text
    delta, cursor = await _customers(env, pos, cursor)
    assert [(c["id"], c["credit_limit"]) for c in delta] == [(str(cid), "800000.00")]
    # a POS payment (built with the shared allocation over the pulled cache) is accepted end to end
    pay_id = str(uuid7())
    result = allocate_json("45000.00", me["open_debt_docs"])
    payment = {
        "id": pay_id,
        "counterparty_id": str(cid),
        "branch_id": str(pos.branch_id),
        "cash_register_id": str(pos.register_id),
        "shift_id": str(shift),
        "receipt_seq": 1,
        "is_offline": False,
        "amount": "45000.00",
        "method": "cash",
        "allocations": result["allocations"],
        "fiscal_lines": result["fiscal_lines"],
    }
    (res,) = await push_ok(env, pos, [event(pos, "debt_payment.created", payment)])
    assert res["status"] == "accepted", res
    assert res["server"]["remaining_balance"] == "0.00" and res["server"]["fiscal"]["status"] == "pending"
    after, _ = await _customers(env, pos, cursor)
    me = next(c for c in after if c["id"] == str(cid))
    assert me["receivable_balance"] == "0.00" and me["open_debt_docs"] == []


async def test_debt_payment_validation_rules(env: SyncEnv) -> None:
    pos, shift, product = await _setup(env, "debt-pay-rules")
    cid = uuid7()
    await push_ok(
        env,
        pos,
        [
            event(pos, "counterparty.created", {"id": str(cid), "name": "Vali", "phone": new_phone()}),
            event(pos, "sale.created", _sale(pos, shift, product, cid)),
        ],
    )
    base = {
        "id": str(uuid7()),
        "counterparty_id": str(cid),
        "branch_id": str(pos.branch_id),
        "cash_register_id": str(pos.register_id),
        "shift_id": str(shift),
        "receipt_seq": 7,
        "is_offline": True,
        "offline_since": datetime.now(UTC).isoformat(),
        "amount": "10000.00",
        "method": "cash",
        "allocations": [],
        "fiscal_lines": [{"qty": "1.000", "amount": "10000.00", "vat_rate": "0.00", "vat_amount": "0.00"}],
    }
    cases = {
        "bank": (base | {"method": "bank"}, "method"),
        "uzqr_offline": (base | {"method": "uzqr", "qr_type": "static"}, "method"),
        "card_requisites": (
            base
            | {
                "method": "card",
                "card_entry_mode": "manual",
                "manual_reason": "standalone_terminal",
                "rrn": "123456",
            },
            "rrn",
        ),
        "lines_total": (base | {"amount": "9000.00"}, "fiscal_lines"),
        "unknown_customer": (base | {"counterparty_id": str(uuid7())}, None),
    }
    events = [
        event(pos, "debt_payment.created", payload | {"id": str(uuid7())}) for payload, _ in cases.values()
    ]
    results = await push_ok(env, pos, events)
    for (name, (_, field)), res in zip(cases.items(), results, strict=True):
        assert res["status"] == "rejected", name
        if field is None:
            assert (res["error_code"], res["retryable"]) == ("DEPENDENCY_NOT_SYNCED", True), name
        else:
            assert res["details"][0]["field"] == field, (name, res["details"])
    # a manual card payment on a register without a terminal (standalone) is accepted: no requisites, 5710
    card = base | {
        "id": str(uuid7()),
        "method": "card",
        "card_entry_mode": "manual",
        "manual_reason": "standalone_terminal",
    }
    (res,) = await push_ok(env, pos, [event(pos, "debt_payment.created", card)])
    assert res["status"] == "accepted", res
    entries = await rows(
        env.db,
        pos.shop.tenant_id,
        "SELECT account_dt, account_kt, analytics FROM app.ledger_entries WHERE doc_id = :d",
        d=card["id"],
    )
    assert [(e["account_dt"], e["account_kt"]) for e in entries] == [("5710", "4010")]
    assert entries[0]["analytics"]["payment_method"] == "card"
    # the offline device thought there was nothing open: the server allocates, the device lines stay on the receipt
    assert "debt_allocation_mismatch" in str(
        await rows(
            env.db, pos.shop.tenant_id, "SELECT kind FROM app.sync_exceptions WHERE doc_id = :d", d=card["id"]
        )
    )
