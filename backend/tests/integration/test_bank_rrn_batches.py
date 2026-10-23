"""BO-24 — card bank credits matched to terminal settlement batches (B5-T05 BO-24 part; 13 §2.18a, 20 #55g).

A statement line without an RRN registry whose purpose names a terminal TID is matched to that terminal's open
``card_terminal_settlements`` batches (``Σ net_total`` within 5%), the batches are linked to the draft, and
posting links nothing else; the RRN registry path stays as in QT-M11-15 (``test_bank_settlements.py``)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from tests.support.bank import API, D15, D16, balance, bank_till, card_purchase, statement, transit_in, upload
from tests.support.cash import Till, cash_env_fixture, one
from tests.support.catalog import Env

__all__ = ["cash_env_fixture"]

pytestmark = pytest.mark.asyncio


async def _batch(env: Env, till: Till, tid: str, total: str, day: object) -> UUID:
    batch_id = uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, till.shop.tenant_id):
        terminal = (
            await s.execute(text("SELECT id FROM app.card_terminals WHERE tid = :t"), {"t": tid})
        ).scalar()
        await s.execute(
            text(
                "INSERT INTO app.card_terminal_settlements (id, tenant_id, branch_id, card_terminal_id, batch_no, "
                "business_date, settled_at, purchase_count, purchase_total, refund_count, refund_total, "
                "expected_count, expected_total, status) VALUES (:id, :t, :b, :c, :n, :d, :at, 1, :p, 0, 0, 1, :p, "
                "'matched')"
            ),
            {"id": batch_id, "t": till.shop.tenant_id, "b": till.shop.branch_id, "c": terminal,
             "n": f"B{batch_id.hex[-6:]}", "d": day, "at": datetime.now(UTC), "p": Decimal(total)},
        )  # fmt: skip
    return batch_id


async def test_bank_rrn_terminal_batch_matching_by_tid(env: Env) -> None:
    till = await bank_till(env, "Batch do'kon")
    await card_purchase(env, till, "000000000101", "500000.00", D16, tid="T1")
    await card_purchase(env, till, "000000000102", "300000.00", D16, tid="T1")
    await card_purchase(env, till, "000000000201", "100000.00", D16, tid="T2")
    b1 = await _batch(env, till, "T1", "800000.00", D16)
    b2 = await _batch(env, till, "T2", "100000.00", D16)
    # the acquirer pays terminal T1's batch minus 1% commission, naming the TID but no RRN registry;
    # the whole day (900 000.00) would not fit the 5% tolerance — only the batch does
    content = statement({"number": "901", "amount": "792000.00", "purpose": "Эквайринг возмещение TID T1"})
    res = await env.client.post(f"{API}/imports", **upload(content), headers=till.shop.h("accountant"))
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["drafts_created"] == 1 and out["unmatched_lines"] == [], out
    draft = (
        await env.client.get(f"{API}/{out['draft_ids'][0]}", headers=till.shop.h("accountant", key=None))
    ).json()
    assert (draft["method"], draft["gross_amount"], draft["commission_amount"]) == (
        "card",
        "800000.00",
        "8000.00",
    )
    assert (draft["settled_from"], draft["settled_to"]) == (D16.isoformat(), D16.isoformat())
    linked = await one(env.db, till.shop.tenant_id, "SELECT bank_settlement_id FROM app.card_terminal_settlements "
                       "WHERE id = :id", id=b1)  # fmt: skip
    assert linked == UUID(draft["id"])
    ok = await env.client.post(f"{API}/{draft['id']}/post", json={}, headers=till.shop.h("accountant"))
    assert ok.status_code == 200, ok.text
    # posting links only the matched batch — T2's batch of the same day stays open
    assert await one(env.db, till.shop.tenant_id, "SELECT bank_settlement_id FROM app.card_terminal_settlements "
                     "WHERE id = :id", id=b2) is None  # fmt: skip
    assert await balance(env, till, "card") == "100000.00"
    # a second import of another line cannot take the T1 batch again
    again = statement({"number": "902", "amount": "99000.00", "purpose": "Эквайринг возмещение TID T2"})
    res = await env.client.post(f"{API}/imports", **upload(again), headers=till.shop.h("accountant"))
    second = (await env.client.get(f"{API}/{res.json()['draft_ids'][0]}",
                                   headers=till.shop.h("accountant", key=None))).json()  # fmt: skip
    assert second["gross_amount"] == "100000.00"
    assert await one(env.db, till.shop.tenant_id, "SELECT bank_settlement_id FROM app.card_terminal_settlements "
                     "WHERE id = :id", id=b2) == UUID(second["id"])  # fmt: skip
    # cancelling the first settlement releases its batch
    await env.client.post(
        f"{API}/{draft['id']}/cancel", json={"reason": "qayta"}, headers=till.shop.h("accountant")
    )
    assert await one(env.db, till.shop.tenant_id, "SELECT bank_settlement_id FROM app.card_terminal_settlements "
                     "WHERE id = :id", id=b1) is None  # fmt: skip


async def test_bank_rrn_terminal_less_card_never_by_batch(env: Env) -> None:
    """A terminal-less (manual) card receipt has no batch and no RRN — it is matched by amount/date only."""
    till = await bank_till(env, "Manual karta")
    await transit_in(env, till, "card", "200000.00", D15)
    content = statement({"number": "903", "amount": "198000.00", "purpose": "Возмещение по картам"})
    res = await env.client.post(f"{API}/imports", **upload(content), headers=till.shop.h("accountant"))
    out = res.json()
    assert out["drafts_created"] == 1
    draft = (
        await env.client.get(f"{API}/{out['draft_ids'][0]}", headers=till.shop.h("accountant", key=None))
    ).json()
    assert (draft["gross_amount"], draft["settled_from"]) == ("200000.00", D15.isoformat())
    assert await one(env.db, till.shop.tenant_id, "SELECT count(*) FROM app.card_terminal_settlements") == 0
