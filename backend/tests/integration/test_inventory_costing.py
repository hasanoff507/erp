"""Stock toolkit — receipts, FIFO/AVECO issues, returns, blocked qty, cancels (13 §3.1–§3.2a, 23 §2.1–§2.3).

QT-M04-01, QT-M04-05, QT-M04-06, QT-M04-09, QT-M04-10 at the primitive level (the goods-receipt /
sale documents come later); every number is the 13 §3.2 / 31 "Misol — QT-M04-05" example.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.inventory.wiring import Allocation, return_pieces
from tests.support.catalog import Env, catalog_env_fixture
from tests.support.inventory import (
    D,
    avg,
    balance,
    issue,
    ledger,
    lots,
    moves,
    new_product,
    receive,
    set_method,
    stock_txn,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]


async def _two_receipts(env: Env, method: str) -> tuple[object, object, object]:
    shop = await env.shop(f"Kirim {method}")
    await set_method(env, shop, method)
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "100.000", "800000.00")
    await receive(env, shop, wh, p, "50.000", "450000.00")
    return shop, wh, p


async def test_qt_m04_01_receipt_raises_balance_and_creates_a_lot(env: Env) -> None:
    shop = await env.shop("QT-M04-01")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    res, jobs = await receive(env, shop, wh, p, "48.000", "384000.00")
    assert jobs == []
    assert res.unit_cost == D("8000.0000")
    assert await balance(env, shop, wh, p) == (D("48.000"), D("384000.00"))
    [lot] = await lots(env, shop, p)
    assert (lot["qty_in"], lot["qty_left"], lot["unit_cost"]) == (D("48.000"), D("48.000"), D("8000.0000"))
    [move] = await moves(env, shop, p)
    assert (move["qty"], move["cost_amount"], move["lot_id"]) == (D("48.000"), D("384000.00"), lot["id"])
    state = await avg(env, shop, wh, p)  # AVECO (the default) keeps avg_costs from the first receipt
    assert state == {"qty": D("48.000"), "avg_cost": D("8000.0000"), "total_value": D("384000.00")}


async def test_receipt_amount_is_the_line_total_not_qty_times_rounded_unit_cost(env: Env) -> None:
    """3 units for 1000.00: unit_cost 333.3333 (4 dp), the move/balance keep exactly 1000.00."""
    shop = await env.shop("Line total")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    res, _ = await receive(env, shop, wh, p, "3.000", "1000.00")
    assert res.unit_cost == D("333.3333")
    assert await balance(env, shop, wh, p) == (D("3.000"), D("1000.00"))
    # last unit out takes the residual: 333.33 + 333.33 + 333.34 = 1000.00, inventory exactly 0.00
    costs = [(await issue(env, shop, wh, p, "1.000"))[0].cost for _ in range(3)]
    assert costs == [D("333.33"), D("333.33"), D("333.34")]
    assert await balance(env, shop, wh, p) == (D("0.000"), D("0.00"))


async def test_qt_m04_05_fifo_cogs(env: Env) -> None:
    """13 §3.2 / 31 "Misol — QT-M04-05": Dt 9120 / Kt 2910 "980000.00"; 30 × 9000.0000 = 270000.00 left."""
    shop, wh, p = await _two_receipts(env, "fifo")
    res, doc, line = await issue(env, shop, wh, p, "120.000", account_dt="9120")
    assert res.cost == D("980000.00") and res.pending_qty == 0
    first, second = await lots(env, shop, p)
    assert [a.as_json() for a in res.allocations] == [
        {"lot_id": str(first["id"]), "qty": "100.000", "unit_cost": "8000.0000", "pending": False},
        {"lot_id": str(second["id"]), "qty": "20.000", "unit_cost": "9000.0000", "pending": False},
    ]
    assert (first["qty_left"], second["qty_left"]) == (D("0.000"), D("30.000"))
    assert await balance(env, shop, wh, p) == (D("30.000"), D("270000.00"))
    [entry] = await ledger(env, shop, doc)
    assert (entry["account_dt"], entry["account_kt"], entry["amount"]) == ("9120", "2910", D("980000.00"))
    assert entry["analytics"] == {
        "stock_cost": True, "product_id": str(p), "warehouse_id": str(wh), "line_id": str(line),
        "lot_ids": sorted([str(first["id"]), str(second["id"])]),
    }  # fmt: skip
    issued = list(await moves(env, shop, p, doc))
    assert [(m["qty"], m["cost_amount"]) for m in issued] == [
        (D("-100.000"), D("-800000.00")),
        (D("-20.000"), D("-180000.00")),
    ]


async def test_qt_m04_06_aveco_cogs(env: Env) -> None:
    """13 §3.2 AVECO: avg 8333.3333 after receipt 2; COGS 1000000.00; remaining value 250000.00 (old − COGS)."""
    shop, wh, p = await _two_receipts(env, "aveco")
    state = await avg(env, shop, wh, p)
    assert state == {"qty": D("150.000"), "avg_cost": D("8333.3333"), "total_value": D("1250000.00")}
    res, doc, _ = await issue(env, shop, wh, p, "120.000")
    assert res.cost == D("1000000.00")
    assert {a.unit_cost for a in res.allocations} == {D("8333.3333")}
    state = await avg(env, shop, wh, p)
    assert state == {"qty": D("30.000"), "avg_cost": D("8333.3333"), "total_value": D("250000.00")}
    assert await balance(env, shop, wh, p) == (D("30.000"), D("250000.00"))
    # quantities still leave the lots FIFO (13 §3.1, 11 §7)
    first, second = await lots(env, shop, p)
    assert (first["qty_left"], second["qty_left"]) == (D("0.000"), D("30.000"))
    [entry] = await ledger(env, shop, doc)
    assert (entry["account_dt"], entry["account_kt"], entry["amount"]) == ("9120", "2910", D("1000000.00"))
    # the moves of the issue sum exactly to the COGS
    assert sum(m["cost_amount"] for m in await moves(env, shop, p, doc)) == D("-1000000.00")
    # the last 30 units take exactly the remaining 250000.00 (inventory 0.00 at zero stock)
    rest, _, _ = await issue(env, shop, wh, p, "30.000")
    assert rest.cost == D("250000.00")
    assert await avg(env, shop, wh, p) == {
        "qty": D("0.000"),
        "avg_cost": D("8333.3333"),
        "total_value": D("0.00"),
    }


async def test_qt_m04_09_fifo_return_goes_back_to_original_lots_in_reverse_order(env: Env) -> None:
    """13 §3.2a FIFO: 5 of the 120 come back to lot 2 (reverse allocation order) at 9000.0000 — not the
    current FIFO lot cost; unit costs never change."""
    shop, wh, p = await _two_receipts(env, "fifo")
    sale, doc, line = await issue(env, shop, wh, p, "120.000")
    await receive(env, shop, wh, p, "10.000", "120000.00")  # a later, dearer lot (12000.0000)
    pieces = return_pieces(sale.allocations, D("0.000"), D("5.000"))
    assert pieces == [Allocation(sale.allocations[1].lot_id, D("5.000"), D("9000.0000"))]
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        amount, _ = await txn.return_to_lots(wh, p, pieces, doc_type="returns", doc_id=doc, line_id=line)
    assert amount == D("45000.00")
    first, second, third = await lots(env, shop, p)
    assert [x["qty_left"] for x in (first, second, third)] == [D("0.000"), D("35.000"), D("10.000")]
    assert [x["unit_cost"] for x in (first, second, third)] == [
        D("8000.0000"),
        D("9000.0000"),
        D("12000.0000"),
    ]
    # a further 30 returned: 25 more to lot 2 (20 issued − 5 already back … only 15 left), then lot 1
    more = return_pieces(sale.allocations, D("5.000"), D("30.000"))
    assert [(x.lot_id, x.qty) for x in more] == [
        (sale.allocations[1].lot_id, D("15.000")),
        (sale.allocations[0].lot_id, D("15.000")),
    ]


async def test_qt_m04_10_aveco_return_at_original_unit_cost(env: Env) -> None:
    """13 §3.2a AVECO: return 5 at the original 8333.3333 after avg moved → total_value += 41666.67."""
    shop, wh, p = await _two_receipts(env, "aveco")
    sale, doc, line = await issue(env, shop, wh, p, "120.000")  # avg 8333.3333, 30 left worth 250000.00
    await receive(env, shop, wh, p, "10.000", "120000.00")  # avg → (250000 + 120000) / 40 = 9250.0000
    assert (await avg(env, shop, wh, p))["avg_cost"] == D("9250.0000")
    pieces = return_pieces(sale.allocations, D("0.000"), D("5.000"))
    assert [x.unit_cost for x in pieces] == [D("8333.3333")]
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        amount, _ = await txn.return_to_lots(wh, p, pieces, doc_type="returns", doc_id=doc, line_id=line)
    assert amount == D("41666.67")  # ROUND_HALF_UP(5 × 8333.3333, 2), not 5 × 9250
    state = await avg(env, shop, wh, p)
    # total 370000.00 + 41666.67 = 411666.67 over 45 units → 9148.1482
    assert state == {"qty": D("45.000"), "avg_cost": D("9148.1482"), "total_value": D("411666.67")}


async def test_specific_lot_issue_and_insufficient_stock(env: Env) -> None:
    shop, wh, p = await _two_receipts(env, "fifo")
    _, second = await lots(env, shop, p)
    res, _, _ = await issue(env, shop, wh, p, "10.000", lot_id=second["id"])
    assert [(a.lot_id, a.qty, a.unit_cost) for a in res.allocations] == [
        (second["id"], D("10.000"), D("9000.0000"))
    ]
    with pytest.raises(AppError) as exc:
        await issue(env, shop, wh, p, "41.000", lot_id=second["id"])
    assert exc.value.code is ErrorCode.INSUFFICIENT_STOCK
    assert exc.value.params == {"lot_id": str(second["id"]), "available": "40.000"}
    assert (await lots(env, shop, p))[1]["qty_left"] == D("40.000")  # rolled back


async def test_blocked_qty_is_never_issued_and_expired_return_consumes_it(env: Env) -> None:
    """13 §2.5: blocked units stay in stock, FIFO skips them; the write-off of the expired return
    lowers blocked_qty and qty_left together."""
    shop = await env.shop("Blocked")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "10.000", "100000.00")
    [lot] = await lots(env, shop, p)
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.block(lot["id"], D("4.000"))
    with pytest.raises(AppError) as exc:
        await issue(env, shop, wh, p, "7.000", lot_id=lot["id"])
    assert exc.value.code is ErrorCode.INSUFFICIENT_STOCK and exc.value.params["available"] == "6.000"
    res, _, _ = await issue(env, shop, wh, p, "3.000", account_dt="9430", lot_id=lot["id"], from_blocked=True)
    assert res.cost == D("30000.00")
    [lot] = await lots(env, shop, p)
    assert (lot["qty_left"], lot["blocked_qty"]) == (D("7.000"), D("1.000"))


async def test_cancel_issue_restores_lots_and_reverses_moves(env: Env) -> None:
    shop, wh, p = await _two_receipts(env, "fifo")
    res, doc, _ = await issue(env, shop, wh, p, "120.000")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        reversed_ids = await txn.reverse_issue("write_offs", doc)
    assert len(reversed_ids) == 2
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("100.000"), D("50.000")]
    assert await balance(env, shop, wh, p) == (D("150.000"), D("1250000.00"))
    doc_moves = await moves(env, shop, p, doc)
    originals = {m["id"] for m in doc_moves if m["reversal_of_id"] is None}
    assert {m["reversal_of_id"] for m in doc_moves if m["reversal_of_id"]} == originals
    assert sum(m["qty"] for m in doc_moves) == 0 and sum(m["cost_amount"] for m in doc_moves) == 0
    assert res.cost == D("980000.00")


async def test_cancel_aveco_issue_puts_the_value_back(env: Env) -> None:
    shop, wh, p = await _two_receipts(env, "aveco")
    _, doc, _ = await issue(env, shop, wh, p, "120.000")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_issue("write_offs", doc)
    assert await avg(env, shop, wh, p) == {
        "qty": D("150.000"), "avg_cost": D("8333.3333"), "total_value": D("1250000.00"),
    }  # fmt: skip


async def test_cancel_receipt_lot_already_consumed(env: Env) -> None:
    shop = await env.shop("Consumed")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    res, _ = await receive(env, shop, wh, p, "10.000", "100000.00")
    [lot] = await lots(env, shop, p)
    doc = (await moves(env, shop, p))[0]["doc_id"]
    await issue(env, shop, wh, p, "1.000")
    with pytest.raises(AppError) as exc:
        async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
            await txn.reverse_receipt("goods_receipts", doc)
    assert exc.value.code is ErrorCode.LOT_ALREADY_CONSUMED and exc.value.params == {"lot_id": str(lot["id"])}
    assert res.lot_id == lot["id"]


async def test_cancel_untouched_receipt(env: Env) -> None:
    shop = await env.shop("Untouched")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "100.000", "800000.00")
    _, _ = await receive(env, shop, wh, p, "50.000", "450000.00")
    doc = (await moves(env, shop, p))[1]["doc_id"]
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_receipt("goods_receipts", doc)
    assert await balance(env, shop, wh, p) == (D("100.000"), D("800000.00"))
    assert await avg(env, shop, wh, p) == {
        "qty": D("100.000"),
        "avg_cost": D("8000.0000"),
        "total_value": D("800000.00"),
    }
    assert [x["qty_left"] for x in await lots(env, shop, p)] == [D("100.000"), D("0.000")]


async def test_lock_once_per_transaction_and_unlocked_key_refused(env: Env) -> None:
    shop = await env.shop("Lock rules")
    wh = await use_account(env, shop)
    p, q = await new_product(env, shop, "A"), await new_product(env, shop, "B")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (s, txn):
        with pytest.raises(RuntimeError, match="not locked"):
            await txn.issue(wh, q, D("1.000"), doc_type="write_offs", doc_id=p, line_id=p)
        from app.modules.inventory.wiring import stock_service

        with pytest.raises(RuntimeError, match="once per transaction"):
            await stock_service().lock(s, shop.tenant_id, [(wh, q)])
    assert Decimal("0") == 0


# --- review fixes (ACC-01, ACC-03, ACC-04, ACC-15) -----------------------------------------------------
async def _a_then_b(env: Env, method: str) -> tuple[Any, UUID, UUID, UUID, UUID]:
    """Lot A 10 × 100.00, lot B 10 × 200.00 (AVECO avg 150.0000); returns (shop, wh, p, doc B, lot B)."""
    from app.core.db.base import uuid7

    shop = await env.shop(f"A+B {method}")
    await set_method(env, shop, method)
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "10.000", "1000.00")
    doc_b = uuid7()
    res_b, _ = await receive(env, shop, wh, p, "10.000", "2000.00", doc_id=doc_b)
    return shop, wh, p, doc_b, res_b.lot_id


async def test_aveco_cancel_receipt_after_a_later_issue_is_refused(env: Env) -> None:
    """ACC-01 (13 §3.1): FIFO quantities left lot B untouched, but its value is in the issue's COGS
    (10 × 150.0000 = 1500.00) — cancelling B would leave −500.00 for 10 units → 409."""
    shop, wh, p, doc_b, lot_b = await _a_then_b(env, "aveco")
    res, _, _ = await issue(env, shop, wh, p, "10.000")
    assert res.cost == D("1500.00")
    with pytest.raises(AppError) as exc:
        async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
            await txn.reverse_receipt("goods_receipts", doc_b)
    assert exc.value.code is ErrorCode.LOT_ALREADY_CONSUMED and exc.value.params == {"lot_id": str(lot_b)}
    assert await balance(env, shop, wh, p) == (D("10.000"), D("1500.00"))
    assert await avg(env, shop, wh, p) == {
        "qty": D("10.000"), "avg_cost": D("150.0000"), "total_value": D("1500.00"),
    }  # fmt: skip


async def test_aveco_cancel_receipt_without_later_issue(env: Env) -> None:
    shop, wh, p, doc_b, _ = await _a_then_b(env, "aveco")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_receipt("goods_receipts", doc_b)
    assert await balance(env, shop, wh, p) == (D("10.000"), D("1000.00"))
    assert await avg(env, shop, wh, p) == {
        "qty": D("10.000"), "avg_cost": D("100.0000"), "total_value": D("1000.00"),
    }  # fmt: skip


async def test_aveco_cancel_receipt_after_the_later_issue_was_cancelled(env: Env) -> None:
    shop, wh, p, doc_b, _ = await _a_then_b(env, "aveco")
    _, issue_doc, _ = await issue(env, shop, wh, p, "10.000")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_issue("write_offs", issue_doc)
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_receipt("goods_receipts", doc_b)
    assert await balance(env, shop, wh, p) == (D("10.000"), D("1000.00"))
    state = await avg(env, shop, wh, p)
    assert state is not None and state["avg_cost"] == D("100.0000")


async def test_fifo_cancel_untouched_receipt_after_a_later_issue_is_allowed(env: Env) -> None:
    shop, wh, p, doc_b, lot_b = await _a_then_b(env, "fifo")
    res, _, _ = await issue(env, shop, wh, p, "10.000")
    assert res.cost == D("1000.00")  # lot A only
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_receipt("goods_receipts", doc_b)
    assert await balance(env, shop, wh, p) == (D("0.000"), D("0.00"))
    assert [(x["id"], x["qty_left"]) for x in await lots(env, shop, p)][1] == (lot_b, D("0.000"))


async def test_fifo_lot_exhaust_takes_the_lot_remaining_value(env: Env) -> None:
    """ACC-03 (13 §3.1): lot A 3 for 100.00 (33.3333), lot B 1 × 50.00; three single issues →
    33.33, 33.33, 33.34 (the lot's residue leaves with it); register 50.00 = 150.00 − cost ledger."""
    shop = await env.shop("Lot exhaust")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "3.000", "100.00")
    await receive(env, shop, wh, p, "1.000", "50.00")
    costs, docs = [], []
    for _ in range(3):
        res, doc, _ = await issue(env, shop, wh, p, "1.000")
        costs.append(res.cost)
        docs.append(doc)
    assert costs == [D("33.33"), D("33.33"), D("33.34")]
    assert await balance(env, shop, wh, p) == (D("1.000"), D("50.00"))
    credited = [e["amount"] for d in docs for e in await ledger(env, shop, d) if e["account_kt"] == "2910"]
    assert D("150.00") - sum(credited, D("0.00")) == D("50.00")


async def test_cancel_expired_return_write_off_restores_blocked_qty(env: Env) -> None:
    """ACC-04 (13 §2.5): an issue from the blocked part, reversed with its line in
    ``to_blocked_line_ids``, gives the units back blocked: qty_left 10, blocked 5, available 5."""
    shop = await env.shop("Blocked back")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    await receive(env, shop, wh, p, "10.000", "100000.00")
    [lot] = await lots(env, shop, p)
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.block(lot["id"], D("5.000"))
    _, doc, line = await issue(
        env, shop, wh, p, "2.000", account_dt="9430", lot_id=lot["id"], from_blocked=True
    )
    [lot] = await lots(env, shop, p)
    assert (lot["qty_left"], lot["blocked_qty"]) == (D("8.000"), D("3.000"))
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.reverse_issue("write_offs", doc, to_blocked_line_ids=[line])
    [lot] = await lots(env, shop, p)
    assert (lot["qty_left"], lot["blocked_qty"]) == (D("10.000"), D("5.000"))
    assert lot["qty_left"] - lot["blocked_qty"] == D("5.000")
    assert await balance(env, shop, wh, p) == (D("10.000"), D("100000.00"))


async def test_fifo_last_purchase_cost_ignores_a_stale_aveco_average(env: Env) -> None:
    """ACC-15 (13 §2.11): after AVECO (avg 9000.0000) → FIFO, a product with no goods-receipt lot and a
    register of 4 × 10000 is valued at the register average 10000.0000, not the stale avg_costs row."""
    from datetime import UTC, date, datetime

    from app.core.db.base import uuid7
    from app.modules.accounting.wiring import business_today
    from app.modules.inventory.domain.stock_counts import surplus_unit_cost
    from app.modules.inventory.wiring import CostPosting

    this_year = business_today().year
    last_year_at = datetime(this_year - 1, 6, 1, 7, 0, tzinfo=UTC)
    shop = await env.shop("AVECO→FIFO cost")
    await set_method(env, shop, "aveco", date(this_year - 1, 1, 1))
    wh = await use_account(env, shop)
    p = await new_product(env, shop)
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.receive(
            wh, p, D("4.000"), D("36000.00"), source_doc_type="stock_openings", source_doc_id=uuid7(),
            source_line_id=uuid7(), received_at=last_year_at, moved_at=last_year_at,
        )  # fmt: skip
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.issue(
            wh, p, D("4.000"), doc_type="write_offs", doc_id=uuid7(), line_id=uuid7(), moved_at=last_year_at,
            cost=CostPosting(account_dt="9430", entry_date=date(this_year - 1, 6, 1)),
        )  # fmt: skip
    state = await avg(env, shop, wh, p)
    assert state is not None and state["avg_cost"] == D("9000.0000")
    await set_method(env, shop, "fifo", date(this_year, 1, 1))
    await receive(env, shop, wh, p, "4.000", "40000.00", source="transfers")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        assert txn.method == "fifo"
        last = await txn.last_purchase_cost(wh, p)
        bal = txn.balance((wh, p))
    assert last is None
    state = await avg(env, shop, wh, p)
    assert state is not None and state["avg_cost"] == D("9000.0000")  # the stale AVECO row is still there
    assert surplus_unit_cost(last, bal.qty, bal.value) == D("10000.0000")
