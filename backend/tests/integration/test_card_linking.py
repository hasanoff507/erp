"""SYNC-04 (F-7): a sale event whose card attempt already backs another document is ACCEPTED with
``warnings=["CARD_TRANSACTION_MISMATCH"]`` and one ``card_result_mismatch`` exception (16 §2.1, 18 §4.1)."""

from __future__ import annotations

import pytest

from tests.support.catalog import Env
from tests.support.sales import (
    bind_terminal,
    card_result,
    deliver,
    make_pos,
    new_item,
    rows,
    sale_line,
    sale_payload,
    sales_env_fixture,
)

__all__ = ["sales_env_fixture"]

pytestmark = pytest.mark.asyncio


async def test_sync04_attempt_linked_to_other_sale_is_accepted_with_mismatch(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos)
    terminal = await bind_terminal(env, pos)
    result = await card_result(pos, terminal, "12000.00")
    pay = {"method": "card", "amount": "12000.00", "card_entry_mode": "integrated", "card_result": result}
    first = sale_payload(pos, [sale_line(product)], [pay])
    a = await deliver(env, pos, "sale.created", first)
    assert a.error is None
    second = sale_payload(pos, [sale_line(product)], [pay])
    b = await deliver(env, pos, "sale.created", second)
    assert b.error is None, b.code
    assert b.result is not None and "CARD_TRANSACTION_MISMATCH" in b.result.warnings
    exceptions = [e for e in b.result.sync_exceptions if e.kind == "card_result_mismatch"]
    assert len(exceptions) == 1 and exceptions[0].details["reason"] == "linked_to_other_document"
    linked = await rows(
        env.db, pos.tenant_id, "SELECT doc_id FROM app.card_terminal_transactions WHERE id = :i",
        i=result["attempt_id"],
    )  # fmt: skip
    assert str(linked[0]["doc_id"]) == first["id"]
    pay_b = await rows(
        env.db, pos.tenant_id, "SELECT * FROM app.sale_payments WHERE sale_id = :d", d=second["id"]
    )
    assert pay_b[0]["card_entry_mode"] == "integrated"
    assert str(pay_b[0]["card_terminal_transaction_id"]) != result["attempt_id"]
