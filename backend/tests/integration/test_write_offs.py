"""Write-offs (19 §15, 13 §2.12, §4.3, US-M04-06, QT-M04-08): cost line ``Dt 9430|4730|9410 / Kt inv_acct``,
gift VAT ``Dt 9430 / Kt 6410`` + ``vat_moves`` for VAT payers, the 202 approval path over the
``stock.writeoff`` limit, blocked quantity only for ``expired_return``; storno on cancel."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from tests.support.catalog import Env, Shop, set_limit, set_price
from tests.support.inventory import (
    D,
    balance,
    close_period,
    err,
    execute,
    lots,
    moves,
    new_product,
    rows,
    scalar,
    set_method,
    set_setting,
    stock_txn,
    use_account,
)
from tests.support.inventory_docs import (
    WRITE_OFFS,
    doc_ledger,
    docs_env_fixture,
    entries,
    ok,
    stock_in,
    today,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["docs_env_fixture"]


def _line(product: UUID, qty: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "product_id": str(product),
        "qty": qty,
        "reason": reason,
        **{k: str(v) if isinstance(v, UUID) else v for k, v in extra.items()},
    }


async def _create(
    env: Env, shop: Shop, wh: UUID, lines: list[dict[str, Any]], *, role: str = "owner", doc_date: date | None = None,
    **extra: Any,
) -> Any:  # fmt: skip
    body = {"warehouse_id": str(wh), "doc_date": str(doc_date or today()), "lines": lines, **extra}
    return await env.client.post(WRITE_OFFS, json=body, headers=shop.h(role))


async def _post(env: Env, shop: Shop, doc_id: str, role: str = "owner") -> Any:
    return await env.client.post(f"{WRITE_OFFS}/{doc_id}/post", headers=shop.h(role))


async def _setup(env: Env, name: str, method: str = "fifo", *roles: SystemRole) -> tuple[Shop, UUID]:
    shop = await env.shop(name, *(roles or (SystemRole.OWNER,)))
    await set_method(env, shop, method)
    return shop, await use_account(env, shop, "2910")


async def test_qt_m04_08_expired_lot_write_off_books_dt_9430_kt_2910(env: Env) -> None:
    shop, wh = await _setup(env, "QT-M04-08")
    milk = await new_product(env, shop, "Sut 1L")
    expired = date(2026, 1, 31)
    lot = await stock_in(env, shop, wh, milk, "4.000", "24000.00", expiry=expired)
    await stock_in(env, shop, wh, milk, "6.000", "42000.00")
    created = await ok(await _create(env, shop, wh, [_line(milk, "4.000", "expired", lot_id=lot)]), 201)
    assert created["status"] == "draft" and created["lines"][0]["expiry_date"] == "2026-01-31"
    posted = await ok(await _post(env, shop, created["id"]))
    assert posted["status"] == "posted" and posted["number"].startswith("L-01-")
    assert posted["lines"][0]["cost_amount"] == "24000.00" and posted["total_cost"] == "24000.00"
    assert [m["qty"] for m in await moves(env, shop, milk, UUID(created["id"]))] == [D("-4.000")]
    led = await doc_ledger(env, shop, created["id"])
    assert entries(led) == [("9430", "2910", D("24000.00"))]
    assert led[0]["analytics"]["reason"] == "expired" and led[0]["analytics"]["lot_ids"] == [str(lot)]
    assert await balance(env, shop, wh, milk) == (D("6.000"), D("42000.00"))
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.vat_moves") == 0
    audit = await rows(env, shop.tenant_id, "SELECT action FROM app.audit_log WHERE entity = 'write_offs'")
    assert {a["action"] for a in audit} == {"write_off.created", "write_off.posted"}


async def test_13_2_12_reason_matrix_responsible_promo_and_fifo(env: Env) -> None:
    shop, wh = await _setup(env, "13 2.12 matrix")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "3.000", "3000.00")  # 1000
    await stock_in(env, shop, wh, p, "10.000", "15000.00")  # 1500
    keeper = shop.user_ids["owner"]
    damaged = await ok(
        await _create(env, shop, wh, [_line(p, "4.000", "damaged")], responsible_user_id=str(keeper)), 201
    )
    await ok(await _post(env, shop, damaged["id"]))
    led = await doc_ledger(env, shop, damaged["id"])
    assert entries(led) == [("4730", "2910", D("4500.00"))]  # FIFO 3 × 1000 + 1 × 1500
    assert led[0]["analytics"]["employee_id"] == str(keeper)

    no_ref = await _create(env, shop, wh, [_line(p, "1.000", "gift", gift_kind="promo_justified")])
    assert no_ref.status_code == 422 and no_ref.json()["error"]["details"][0]["field"] == "promo_order_ref"
    promo = await ok(
        await _create(
            env, shop, wh, [_line(p, "2.000", "gift", gift_kind="promo_justified")],
            promo_order_ref="Buyruq №7, 2026-10-01", responsible_user_id=str(keeper),
        ),
        201,
    )  # fmt: skip
    await ok(await _post(env, shop, promo["id"]))
    assert entries(await doc_ledger(env, shop, promo["id"])) == [
        ("9410", "2910", D("3000.00"))
    ]  # no VAT, no 4730
    other = await ok(await _create(env, shop, wh, [_line(p, "1.000", "other")]), 201)
    await ok(await _post(env, shop, other["id"]))
    assert entries(await doc_ledger(env, shop, other["id"])) == [("9430", "2910", D("1500.00"))]
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.vat_moves") == 0

    manual = await _create(env, shop, wh, [_line(p, "1.000", "expired_return")])
    assert manual.status_code == 422 and manual.json()["error"]["details"][0]["field"] == "lines[0].reason"
    no_kind = await _create(env, shop, wh, [_line(p, "1.000", "gift")])
    assert no_kind.status_code == 422
    stray = await _create(env, shop, wh, [_line(p, "1.000", "damaged", gift_kind="other")])
    assert stray.status_code == 422


async def test_gift_other_books_vat_from_the_market_value(env: Env) -> None:
    shop, wh = await _setup(env, "Gift VAT")
    p = await new_product(env, shop)  # vat_rate 12.00
    await set_price(env.client, shop, str(p), "11200.0000")
    await stock_in(env, shop, wh, p, "5.000", "40000.00")  # 8000
    doc = await ok(await _create(env, shop, wh, [_line(p, "2.000", "gift", gift_kind="other")]), 201)
    await ok(await _post(env, shop, doc["id"]))
    led = await doc_ledger(env, shop, doc["id"])
    assert entries(led) == [("9430", "2910", D("16000.00")), ("9430", "6410", D("2400.00"))]
    assert led[1]["analytics"]["market_value"] == "20000.00"  # 11200 / 1.12 × 2
    [vat] = await rows(
        env, shop.tenant_id, "SELECT kind, base_amount, vat_amount, doc_type, period FROM app.vat_moves"
    )
    assert (vat["kind"], vat["base_amount"], vat["vat_amount"], vat["doc_type"]) == (
        "output", D("20000.00"), D("2400.00"), "write_offs",
    )  # fmt: skip
    assert vat["period"] == today().replace(day=1)

    no_price = await new_product(env, shop, "Narxsiz")
    await stock_in(env, shop, wh, no_price, "2.000", "10000.00")
    doc2 = await ok(await _create(env, shop, wh, [_line(no_price, "2.000", "gift", gift_kind="other")]), 201)
    await ok(await _post(env, shop, doc2["id"]))
    assert entries(await doc_ledger(env, shop, doc2["id"])) == [
        ("9430", "2910", D("10000.00")),
        ("9430", "6410", D("1200.00")),  # no retail price: the cost is the base
    ]

    zero = await new_product(env, shop, "QQSsiz", vat_rate="0.00")
    await set_price(env.client, shop, str(zero), "5000.0000")
    await stock_in(env, shop, wh, zero, "1.000", "4000.00")
    doc3 = await ok(await _create(env, shop, wh, [_line(zero, "1.000", "gift", gift_kind="other")]), 201)
    await ok(await _post(env, shop, doc3["id"]))
    assert entries(await doc_ledger(env, shop, doc3["id"])) == [("9430", "2910", D("4000.00"))]

    cancelled = await ok(
        await env.client.post(f"{WRITE_OFFS}/{doc['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    )
    assert cancelled["status"] == "cancelled"
    vats = await rows(
        env, shop.tenant_id, "SELECT base_amount, vat_amount FROM app.vat_moves WHERE doc_id = :d ORDER BY created_at",
        d=UUID(doc["id"]),
    )  # fmt: skip
    assert [(v["base_amount"], v["vat_amount"]) for v in vats] == [
        (D("20000.00"), D("2400.00")), (D("-20000.00"), D("-2400.00")),
    ]  # fmt: skip
    assert entries(await doc_ledger(env, shop, doc["id"]))[2:] == [
        ("2910", "9430", D("16000.00")), ("6410", "9430", D("2400.00")),
    ]  # fmt: skip
    assert await balance(env, shop, wh, p) == (D("5.000"), D("40000.00"))


async def test_turnover_regime_gift_has_no_vat(env: Env) -> None:
    shop, wh = await _setup(env, "Gift turnover")
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.tenant_tax_regimes (tenant_id, valid_from, regime, created_by) VALUES (:t, :d, 'turnover', :u) "
        "ON CONFLICT (tenant_id, valid_from) DO UPDATE SET regime = 'turnover'",
        t=shop.tenant_id, d=today() - timedelta(days=40), u=shop.user_ids["owner"],
    )  # fmt: skip
    p = await new_product(env, shop)
    await set_price(env.client, shop, str(p), "11200.0000")
    await stock_in(env, shop, wh, p, "2.000", "16000.00")
    doc = await ok(await _create(env, shop, wh, [_line(p, "2.000", "gift", gift_kind="other")]), 201)
    await ok(await _post(env, shop, doc["id"]))
    assert entries(await doc_ledger(env, shop, doc["id"])) == [("9430", "2910", D("16000.00"))]
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.vat_moves") == 0


async def test_over_limit_post_requests_approval_then_posts_once_approved(env: Env) -> None:
    shop, wh = await _setup(env, "Write-off limit", "fifo", SystemRole.OWNER, SystemRole.MANAGER)
    await set_limit(env.db, shop.tenant_id, "manager", "stock.writeoff", "10000.00")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "10.000", "30000.00")  # 3000
    small = await ok(await _create(env, shop, wh, [_line(p, "3.000", "damaged")], role="manager"), 201)
    assert (await ok(await _post(env, shop, small["id"], "manager")))["status"] == "posted"  # 9000 ≤ 10000

    big = await ok(await _create(env, shop, wh, [_line(p, "5.000", "damaged")], role="manager"), 201)
    first = await _post(env, shop, big["id"], "manager")
    assert first.status_code == 202, first.text
    body = first.json()
    assert body["status"] == "draft" and body["approval_request_id"] and body["approval_status"] == "pending"
    [req] = await rows(
        env, shop.tenant_id,
        "SELECT id, kind, permission_code, requested_value, linked_doc_type, linked_doc_id, status, context "
        "FROM app.approval_requests",
    )  # fmt: skip
    assert (req["kind"], req["permission_code"], req["requested_value"], req["linked_doc_type"]) == (
        "write_off_over_limit", "stock.writeoff", D("15000.0000"), "write_offs",
    )  # fmt: skip
    assert str(req["linked_doc_id"]) == big["id"] and req["context"]["estimated_cost"] == "15000.00"
    [tg] = await rows(
        env, shop.tenant_id, "SELECT payload, status FROM app.outbox_jobs WHERE kind = 'telegram'"
    )
    assert tg["payload"]["event"] == "over_limit_action" and tg["payload"]["amount"] == "15000.00"
    assert tg["payload"]["approval_request_id"] == str(req["id"])
    assert await balance(env, shop, wh, p) == (D("7.000"), D("21000.00"))  # nothing moved
    again = await _post(env, shop, big["id"], "manager")
    assert again.status_code == 202 and again.json()["approval_request_id"] == str(req["id"])
    assert await scalar(env, shop.tenant_id, "SELECT count(*) FROM app.approval_requests") == 1
    assert (await ok(await env.client.get(f"{WRITE_OFFS}/{big['id']}", headers=shop.h(key=None))))[
        "approval_status"
    ] == "pending"

    await execute(
        env, shop.tenant_id,
        "UPDATE app.approval_requests SET status = 'approved', resolved_by = :u, resolved_at = now() WHERE id = :id",
        u=shop.user_ids["owner"], id=req["id"],
    )  # fmt: skip
    posted = await ok(await _post(env, shop, big["id"], "manager"))
    assert posted["status"] == "posted" and posted["total_cost"] == "15000.00"
    assert await scalar(env, shop.tenant_id, "SELECT status FROM app.approval_requests") == "consumed"
    assert await balance(env, shop, wh, p) == (D("2.000"), D("6000.00"))
    owner_big = await ok(await _create(env, shop, wh, [_line(p, "2.000", "damaged")]), 201)
    assert (await ok(await _post(env, shop, owner_big["id"])))["status"] == "posted"  # owner: unlimited


async def test_expired_return_consumes_blocked_quantity(env: Env) -> None:
    shop, wh = await _setup(env, "Expired return")
    p = await new_product(env, shop)
    lot = await stock_in(env, shop, wh, p, "5.000", "10000.00", expiry=date(2026, 2, 1))
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.block(lot, D("2.000"))  # the restock=false return of Bosqich 3 (qaror #48)
    doc_id, line_id = uuid7(), uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.write_offs (id, tenant_id, branch_id, warehouse_id, doc_date, created_by) "
        "VALUES (:id, :t, :b, :w, :d, :u)",
        id=doc_id, t=shop.tenant_id, b=shop.branch_id, w=wh, d=today(), u=shop.user_ids["owner"],
    )  # fmt: skip
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.write_off_lines (id, tenant_id, write_off_id, line_no, product_id, lot_id, qty, reason) "
        "VALUES (:id, :t, :wo, 1, :p, :lot, 2, 'expired_return')",
        id=line_id, t=shop.tenant_id, wo=doc_id, p=p, lot=lot,
    )  # fmt: skip
    posted = await ok(await _post(env, shop, str(doc_id)))
    assert posted["lines"][0]["cost_amount"] == "4000.00"
    [row] = await lots(env, shop, p)
    assert (row["qty_left"], row["blocked_qty"]) == (D("3.000"), D("0.000"))
    assert entries(await doc_ledger(env, shop, doc_id)) == [("9430", "2910", D("4000.00"))]

    blocked_lot = await stock_in(env, shop, wh, p, "1.000", "2000.00")
    async with stock_txn(env, shop.tenant_id, [(wh, p)]) as (_, txn):
        await txn.block(blocked_lot, D("1.000"))
    plain = await ok(await _create(env, shop, wh, [_line(p, "1.000", "damaged", lot_id=blocked_lot)]), 201)
    refused = await _post(env, shop, plain["id"])  # blocked units never leave by an ordinary write-off
    assert refused.status_code == 422 and err(refused) == "INSUFFICIENT_STOCK"
    assert refused.json()["error"]["params"] == {"lot_id": str(blocked_lot), "available": "0.000"}


async def test_stock_errors_aveco_cost_cancel_and_period(env: Env) -> None:
    shop, wh = await _setup(env, "Write-off errors", "aveco")
    p, q = await new_product(env, shop, "P"), await new_product(env, shop, "Q")
    lot = await stock_in(env, shop, wh, p, "100.000", "800000.00")
    await stock_in(env, shop, wh, p, "50.000", "450000.00")  # avg 8333.3333
    other_lot = await stock_in(env, shop, wh, q, "1.000", "1000.00")
    mismatch = await _create(env, shop, wh, [_line(p, "1.000", "damaged", lot_id=other_lot)])
    assert (
        mismatch.status_code == 422 and mismatch.json()["error"]["details"][0]["field"] == "lines[0].lot_id"
    )
    too_much = await ok(await _create(env, shop, wh, [_line(p, "101.000", "damaged", lot_id=lot)]), 201)
    refused = await _post(env, shop, too_much["id"])
    assert refused.status_code == 422 and err(refused) == "INSUFFICIENT_STOCK"
    assert refused.json()["error"]["params"]["available"] == "100.000"

    doc = await ok(await _create(env, shop, wh, [_line(p, "120.000", "damaged")]), 201)
    posted = await ok(await _post(env, shop, doc["id"]))
    assert posted["total_cost"] == "1000000.00"  # 13 §3.2 AVECO
    assert entries(await doc_ledger(env, shop, doc["id"])) == [("9430", "2910", D("1000000.00"))]
    cancelled = await ok(
        await env.client.post(f"{WRITE_OFFS}/{doc['id']}/cancel", json={"reason": "xato"}, headers=shop.h())
    )
    assert cancelled["status"] == "cancelled"
    assert entries(await doc_ledger(env, shop, doc["id"]))[1] == ("2910", "9430", D("1000000.00"))
    assert await balance(env, shop, wh, p) == (D("150.000"), D("1250000.00"))
    draft = await ok(await _create(env, shop, wh, [_line(p, "1.000", "damaged")]), 201)
    assert (
        await ok(
            await env.client.post(
                f"{WRITE_OFFS}/{draft['id']}/cancel", json={"reason": "x"}, headers=shop.h()
            )
        )
    )["status"] == "cancelled"

    await set_setting(env, shop, "negative_stock_policy", "block")
    over = await ok(await _create(env, shop, wh, [_line(q, "2.000", "damaged")]), 201)
    blocked = await _post(env, shop, over["id"])
    assert blocked.status_code == 422 and err(blocked) == "NEGATIVE_STOCK_NOT_ALLOWED"

    last_month = today().replace(day=1) - timedelta(days=1)
    old = await ok(await _create(env, shop, wh, [_line(q, "1.000", "damaged")], doc_date=last_month), 201)
    await close_period(env, shop, last_month)
    closed = await _post(env, shop, old["id"])
    assert closed.status_code == 409 and err(closed) == "PERIOD_CLOSED"

    listed = await ok(await env.client.get(WRITE_OFFS, params={"status": "draft"}, headers=shop.h(key=None)))
    assert {x["id"] for x in listed["items"]} == {too_much["id"], over["id"], old["id"]}


async def test_permissions_scope_and_rls(env: Env) -> None:
    shop, wh = await _setup(env, "Write-off perms", "fifo", SystemRole.OWNER, SystemRole.CASHIER)
    p = await new_product(env, shop)
    denied = await _create(env, shop, wh, [_line(p, "1.000", "damaged")], role="cashier")
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    doc = await ok(await _create(env, shop, wh, [_line(p, "1.000", "damaged")]), 201)
    other = await env.shop("Write-off other tenant")
    assert (await env.client.get(f"{WRITE_OFFS}/{doc['id']}", headers=other.h(key=None))).status_code == 404
    key = "wo-post-1"
    await stock_in(env, shop, wh, p, "2.000", "2000.00")
    first = await env.client.post(f"{WRITE_OFFS}/{doc['id']}/post", headers=shop.h(key=key))
    replay = await env.client.post(f"{WRITE_OFFS}/{doc['id']}/post", headers=shop.h(key=key))
    assert first.status_code == replay.status_code == 200 and replay.json() == first.json()
    assert await balance(env, shop, wh, p) == (D("1.000"), D("1000.00"))


async def test_gift_vat_line_carries_tax_type_vat(env: Env) -> None:
    """ACC-05: the gift VAT line ``Dt 9430 / Kt 6410`` is tagged ``tax_type='vat'`` (tax reports by type)."""
    shop, wh = await _setup(env, "Gift VAT tax_type")
    p = await new_product(env, shop)  # vat_rate 12.00
    await set_price(env.client, shop, str(p), "11200.0000")  # VAT included
    await stock_in(env, shop, wh, p, "1.000", "8000.00")
    doc = await ok(await _create(env, shop, wh, [_line(p, "1.000", "gift", gift_kind="other")]), 201)
    await ok(await _post(env, shop, doc["id"]))
    [vat_line] = [e for e in await doc_ledger(env, shop, doc["id"]) if e["account_kt"] == "6410"]
    assert (vat_line["account_dt"], vat_line["amount"]) == ("9430", D("1200.00"))
    assert vat_line["analytics"]["tax_type"] == "vat"


async def test_approval_covers_only_the_estimate_it_was_given(env: Env) -> None:
    """SEC-07: approved at 150,000; the AVECO estimate later grows to 180,000 → a new request (202), the
    old approval is not consumed."""
    shop, wh = await _setup(env, "Write-off approval value", "aveco", SystemRole.OWNER, SystemRole.MANAGER)
    await set_limit(env.db, shop.tenant_id, "manager", "stock.writeoff", "100000.00")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "10.000", "150000.00")  # avg 15000
    doc = await ok(await _create(env, shop, wh, [_line(p, "10.000", "damaged")], role="manager"), 201)
    first = await _post(env, shop, doc["id"], "manager")
    assert first.status_code == 202, first.text
    old_id = first.json()["approval_request_id"]
    await execute(
        env, shop.tenant_id,
        "UPDATE app.approval_requests SET status = 'approved', resolved_by = :u, resolved_at = now() WHERE id = :id",
        u=shop.user_ids["owner"], id=UUID(old_id),
    )  # fmt: skip
    await stock_in(env, shop, wh, p, "10.000", "210000.00")  # avg (150000 + 210000) / 20 = 18000

    second = await _post(env, shop, doc["id"], "manager")
    assert second.status_code == 202, second.text
    new_id = second.json()["approval_request_id"]
    assert new_id != old_id and second.json()["approval_status"] == "pending"
    found = await rows(
        env,
        shop.tenant_id,
        "SELECT id, status, requested_value FROM app.approval_requests ORDER BY requested_at",
    )
    assert [(str(r["id"]), r["status"], r["requested_value"]) for r in found] == [
        (old_id, "approved", D("150000.0000")), (new_id, "pending", D("180000.0000")),
    ]  # fmt: skip
    assert await balance(env, shop, wh, p) == (D("20.000"), D("360000.00"))  # nothing moved

    await execute(
        env, shop.tenant_id,
        "UPDATE app.approval_requests SET status = 'approved', resolved_by = :u, resolved_at = now() WHERE id = :id",
        u=shop.user_ids["owner"], id=UUID(new_id),
    )  # fmt: skip
    posted = await ok(await _post(env, shop, doc["id"], "manager"))
    assert posted["status"] == "posted" and posted["total_cost"] == "180000.00"
    statuses = await rows(env, shop.tenant_id, "SELECT id, status FROM app.approval_requests")
    assert {str(r["id"]): r["status"] for r in statuses} == {old_id: "approved", new_id: "consumed"}


async def test_doc_date_after_the_business_day_is_refused_on_create_and_post(env: Env) -> None:
    """ACC-13 (13 §5.2, 19 §0): ``doc_date`` > business today → 422 ``validation.doc_date_in_future``."""
    shop, wh = await _setup(env, "Write-off future date")
    p = await new_product(env, shop)
    await stock_in(env, shop, wh, p, "2.000", "2000.00")
    tomorrow = today() + timedelta(days=1)
    created = await _create(env, shop, wh, [_line(p, "1.000", "damaged")], doc_date=tomorrow)
    assert created.status_code == 422, created.text
    detail = created.json()["error"]["details"][0]
    assert (detail["field"], detail["message_key"]) == ("doc_date", "validation.doc_date_in_future")

    doc = await ok(await _create(env, shop, wh, [_line(p, "1.000", "damaged")]), 201)
    await execute(
        env,
        shop.tenant_id,
        "UPDATE app.write_offs SET doc_date = :d WHERE id = :id",
        d=tomorrow,
        id=UUID(doc["id"]),
    )
    posted = await _post(env, shop, doc["id"])
    assert posted.status_code == 422 and err(posted) == "VALIDATION_ERROR", posted.text
    detail = posted.json()["error"]["details"][0]
    assert (detail["field"], detail["message_key"]) == ("doc_date", "validation.doc_date_in_future")
    assert await balance(env, shop, wh, p) == (D("2.000"), D("2000.00"))
