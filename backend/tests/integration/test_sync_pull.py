"""``GET /sync/pull`` (16 §1, §3.2; 18 §17): scopes, row shapes, composite cursor, tombstones, snapshot
objects (``null`` = unchanged), device checks — contract ``.claude-scratch/b3/contracts/sync-pull.md``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from tests.support.catalog import set_price
from tests.support.inventory import new_product, set_method
from tests.support.inventory_docs import stock_in, use_account
from tests.support.sync import (
    SyncEnv,
    execute,
    pos_device,
    pull,
    pull_ok,
    rows,
    settle_clock,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]


def ean13(body12: str) -> str:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body12))
    return body12 + str((10 - total % 10) % 10)


def by_id(rows_: list[dict[str, Any]], entity: str | None = None) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in rows_ if entity is None or r.get("entity") == entity}


async def test_snapshot_contains_every_scope_with_the_contract_shapes(env: SyncEnv) -> None:
    shop = await env.shop("pull-shapes")
    await set_method(env, shop, "fifo")
    wh = await use_account(env, shop, "2910")
    cola = await new_product(env, shop, "Cola")
    await stock_in(env, shop, wh, cola, "12.000", "60000.00")
    code = ean13("478000000001")
    added = await env.client.post(f"/api/v1/products/{cola}/barcodes", json={"barcode": code, "kind": "ean"},
                                  headers=shop.h())  # fmt: skip
    assert added.status_code == 201, added.text
    await set_price(env.client, shop, str(cola), "15000.0000")
    customer = await env.client.post(
        "/api/v1/counterparties",
        json={"kind": "person", "name": "Ali", "phone": "+998901234567", "credit_limit": "500000.00"},
        headers=shop.h(),
    )
    assert customer.status_code == 201, customer.text
    cust_id = customer.json()["id"]
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.debt_balances (tenant_id, counterparty_id, direction, balance) VALUES (:t, :c, 'receivable', 350000)",
        t=shop.tenant_id, c=UUID(cust_id),
    )  # fmt: skip
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.marking_codes (tenant_id, code, product_id, status) VALUES "
        "(:t, 'MC-SOLD', :p, 'sold'), (:t, 'MC-STOCK', :p, 'in_stock')",
        t=shop.tenant_id, p=cola,
    )  # fmt: skip
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.discount_rules (tenant_id, name, scope, kind, value, valid_from) "
        "VALUES (:t, 'Aksiya', 'all', 'percent', 5, CURRENT_DATE - 1), (:t, 'Eski', 'all', 'percent', 9, CURRENT_DATE - 9)",
        t=shop.tenant_id,
    )  # fmt: skip
    await execute(
        env.db,
        shop.tenant_id,
        "UPDATE app.discount_rules SET valid_to = CURRENT_DATE - 2 WHERE name = 'Eski'",
    )
    pos = await pos_device(env, shop)
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.card_terminals (tenant_id, branch_id, cash_register_id, name, vendor, adapter, driver, "
        "created_by) VALUES (:t, :b, :cr, 'Kassa 1 terminal', 'fake', 'fake', 'fake', :u)",
        t=shop.tenant_id, b=pos.branch_id, cr=pos.register_id, u=pos.user_id,
    )  # fmt: skip

    await settle_clock(env, shop.tenant_id)
    page = await pull_ok(env, pos)  # scope=all, empty cursor = first snapshot
    assert page["has_more"] is False
    assert page["device"] == {"id": str(pos.device_id), "branch_id": str(pos.branch_id),
                              "cash_register_id": str(pos.register_id)}  # fmt: skip
    product = by_id(page["catalog"], "product")[str(cola)]
    assert (product["name"], product["unit_code"], product["vat_rate"], product["deleted"]) == (
        "Cola",
        "box",
        "12.00",
        False,
    )
    assert any(r["entity"] == "unit" and r["id"] == "box" for r in page["catalog"])
    assert by_id(page["barcodes"])[str(cola)]["barcodes"] == [
        {"barcode": code, "kind": "ean", "units_per_barcode": "1.000"}
    ]
    [price] = by_id(page["prices"])[str(cola)]["prices"]
    assert (price["price"], price["branch_id"]) == ("15000.0000", None)
    cust = by_id(page["customers"])[cust_id]
    assert (cust["receivable_balance"], cust["credit_limit"], cust["open_debt_docs"], cust["deleted"]) == (
        "350000.00", "500000.00", [], False,
    )  # fmt: skip
    stock = by_id(page["stock"])[f"{wh}:{cola}"]
    assert (stock["qty"], stock["product_id"]) == ("12.000", str(cola))
    assert [m["code"] for m in page["marking_codes"]] == ["MC-SOLD"]  # snapshot: sold/pending only
    [register] = [r for r in page["fiscal"] if r["entity"] == "cash_register"]
    assert (register["id"], register["fm_state"]) == (str(pos.register_id), "unknown")
    staff = {m["user_id"]: m for m in page["permissions"]["staff"]}
    me = staff[str(pos.user_id)]
    assert me["active"] is True and "owner" in me["role_codes"]
    assert {"code": "transfer.create", "limit_value": None} in me["permissions"]
    assert page["permissions"]["staff_source"] in ("auth", "unavailable")
    limits = {u["user_id"]: u["limits"] for u in page["limits"]["users"]}
    assert limits[str(pos.user_id)]["discount.give"] is None
    assert page["shift"]["open_shift"] is None and page["shift"]["cash_register_id"] == str(pos.register_id)
    settings = page["settings"]
    assert [r["name"] for r in settings["discount_rules"]] == ["Aksiya"]
    assert (
        settings["card_manual_fallback"] == "manager_approval"
    )  # active terminal on this register (16 §2.1)
    assert (
        settings["weight_barcode_templates"][0]["prefixes"] == ["22"] and settings["weight_barcode_version"]
    )
    [terminal] = settings["card_terminals"]
    assert terminal["cash_register_id"] == str(pos.register_id) and "pan" not in terminal
    assert settings["subscription"]["status"] in ("trial", "active")
    for key in ("permissions", "limits", "shift", "settings"):
        assert page[key]["digest"]

    # the next pull: nothing changed → empty deltas, snapshot objects null (unchanged since the cursor)
    again = await pull_ok(env, pos, cursor=page["cursor"])
    assert again["catalog"] == [] and again["customers"] == [] and again["prices"] == []
    assert (again["permissions"], again["limits"], again["shift"], again["settings"]) == (
        None,
        None,
        None,
        None,
    )


async def test_deltas_tombstones_and_per_scope_cursors(env: SyncEnv) -> None:
    shop = await env.shop("pull-delta")
    cola = await new_product(env, shop, "Cola")
    sprite = await new_product(env, shop, "Sprite")
    code = ean13("478000000002")
    bc = await env.client.post(f"/api/v1/products/{cola}/barcodes", json={"barcode": code, "kind": "ean"},
                               headers=shop.h())  # fmt: skip
    assert bc.status_code == 201, bc.text
    pos = await pos_device(env, shop)
    await settle_clock(env, shop.tenant_id)
    first = await pull_ok(env, pos)
    cursor = first["cursor"]
    # changes after the snapshot
    await env.client.post(f"/api/v1/products/{sprite}/archive", headers=shop.h())
    deleted = await env.client.delete(f"/api/v1/products/{cola}/barcodes/{bc.json()['id']}", headers=shop.h())
    assert deleted.status_code == 204, deleted.text
    await set_price(env.client, shop, str(cola), "9000.0000")
    await settle_clock(env, shop.tenant_id)
    delta = await pull_ok(env, pos, cursor=cursor)
    products = by_id(delta["catalog"], "product")
    assert products[str(sprite)]["deleted"] is True  # archived → tombstone
    assert (
        by_id(delta["barcodes"])[str(cola)]["barcodes"] == []
    )  # 0027a trigger: the deletion reaches the device
    assert [p["price"] for p in by_id(delta["prices"])[str(cola)]["prices"]] == ["9000.0000"]
    # the scope=all cursor works as a per-scope cursor; other positions are carried through
    only_catalog = await pull_ok(env, pos, scope="catalog", cursor=cursor)
    assert set(only_catalog) >= {"catalog"} and "prices" not in only_catalog
    assert str(sprite) in by_id(only_catalog["catalog"], "product")
    later = await pull_ok(env, pos, scope="prices", cursor=only_catalog["cursor"])
    assert str(cola) in by_id(later["prices"])  # prices position untouched by the catalog-only pull


async def test_late_committed_rows_are_not_skipped_by_the_settle_window(env: SyncEnv) -> None:
    """A row whose ``updated_at`` is older than the cursor position but newer than now − settle waits."""
    shop = await env.shop("pull-settle")
    pos = await pos_device(env, shop)
    original = env.module.pull._cfg
    env.module.pull._cfg = type(original)(500, 1000, 3600.0)  # nothing has settled yet
    try:
        await new_product(env, shop, "Yangi")
        page = await pull_ok(env, pos, scope="catalog")
        assert not [r for r in page["catalog"] if r.get("entity") == "product"]
    finally:
        env.module.pull._cfg = original
    await settle_clock(env, shop.tenant_id)
    page = await pull_ok(env, pos, scope="catalog", cursor=page["cursor"])
    assert [r["name"] for r in page["catalog"] if r.get("entity") == "product"] == ["Yangi"]


async def test_pull_validation_and_device_rules(env: SyncEnv) -> None:
    shop = await env.shop("pull-errors")
    pos = await pos_device(env, shop)
    bad_scope = await pull(env, pos, scope="catalog,nope")
    assert bad_scope.status_code == 422 and bad_scope.json()["error"]["details"][0]["field"] == "scope"
    bad_cursor = await pull(env, pos, cursor="not-a-cursor")
    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["error"]["details"][0] == {
        "field": "cursor",
        "message_key": "validation.cursor_invalid",
    }
    too_big = await pull(env, pos, page_size=5000)
    assert too_big.status_code == 422
    before = datetime.now(UTC) - timedelta(seconds=5)
    assert (await pull(env, pos, scope="shift")).status_code == 200
    seen = (
        await rows(
            env.db, shop.tenant_id, "SELECT last_seen_at FROM app.devices WHERE id = :d", d=pos.device_id
        )
    )[0]
    assert seen["last_seen_at"] >= before
    await execute(
        env.db, shop.tenant_id, "UPDATE app.devices SET revoked_at = now() WHERE id = :d", d=pos.device_id
    )
    await env.app.state.redis.flushdb()
    revoked = await pull(env, pos)
    assert revoked.status_code == 403 and revoked.json()["error"]["code"] == "DEVICE_REVOKED"


async def test_permissions_scope_lists_branch_staff_and_blocked_users(env: SyncEnv) -> None:
    shop = await env.shop("pull-staff")
    pos = await pos_device(env, shop, SystemRole.CASHIER)
    from tests.support.sync import add_actor

    other_branch = uuid7()
    blocked = await add_actor(env, pos, SystemRole.CASHIER)
    await execute(
        env.db, shop.tenant_id, "UPDATE app.memberships SET status = 'blocked' WHERE user_id = :u", u=blocked
    )
    await execute(
        env.db, shop.tenant_id,
        "INSERT INTO app.branches (id, tenant_id, code, name, settlement_category, activity_type) "
        "VALUES (:id, :t, '09', 'Boshqa', 'other', 'retail')", id=other_branch, t=shop.tenant_id,
    )  # fmt: skip
    elsewhere = await add_actor(env, pos, SystemRole.CASHIER, branch_ids=(other_branch,))
    page = await pull_ok(env, pos, scope="permissions,limits")
    staff = {m["user_id"]: m for m in page["permissions"]["staff"]}
    assert staff[str(blocked)]["active"] is False and staff[str(blocked)]["permissions"] == []
    assert str(elsewhere) not in staff
    me = staff[str(pos.user_id)]
    assert {"code": "discount.give", "limit_value": "5.0000"} in me["permissions"]
    limits = {u["user_id"]: u["limits"] for u in page["limits"]["users"]}
    assert limits[str(pos.user_id)]["returns.approve"] == "100000.0000"
    assert limits[str(blocked)] == {}


async def test_sync_07_running_writer_holds_the_cursor_back(env: SyncEnv) -> None:
    """SYNC-07 / 16 §3.2: a long writer stamps rows with its start time and commits late; the pull watermark
    never passes the start of a still-open application transaction, so its rows are not skipped."""
    import asyncio

    from sqlalchemy import text

    from app.core.db.session import tenant_transaction

    shop = await env.shop("sync-07")
    slow_item = await new_product(env, shop, "Import tovari")
    fast_item = await new_product(env, shop, "Tez tovar")
    pos = await pos_device(env, shop)
    await settle_clock(env, shop.tenant_id)
    base = (await pull_ok(env, pos, scope="prices"))["cursor"]
    insert = text("INSERT INTO app.product_prices (tenant_id, product_id, price) VALUES (:t, :p, 100)")
    async with env.db.session_factory() as long_s, tenant_transaction(long_s, shop.tenant_id):
        await long_s.execute(insert, {"t": shop.tenant_id, "p": slow_item})  # stamped now, not committed
        await asyncio.sleep(0.05)
        await execute(env.db, shop.tenant_id, "INSERT INTO app.product_prices (tenant_id, product_id, price) "
                      "VALUES (:t, :p, 200)", t=shop.tenant_id, p=fast_item)  # fmt: skip
        await asyncio.sleep(env.settings.sync_pull_settle_s + 2.5)  # past the fixed settle window
        held = await pull_ok(env, pos, scope="prices", cursor=base)
        assert held["prices"] == []  # the committed newer row waits behind the running writer
    await settle_clock(env, shop.tenant_id)
    after = await pull_ok(env, pos, scope="prices", cursor=held["cursor"])
    assert {r["product_id"] for r in after["prices"]} == {str(slow_item), str(fast_item)}
