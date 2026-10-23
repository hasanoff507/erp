"""Branches, tax-category history, warehouses, cash registers (20 #30–#40i) — US-M14-03/04, QT-M14-02…05."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.branches.domain.model import month_start, next_month_start, tashkent_today
from app.modules.branches.wiring import TurnoverRate, turnover_rate_on
from tests.conftest import MigratedDb
from tests.support.branches import (
    Shop,
    add_cash_register,
    add_device,
    add_extra_registers,
    add_member,
    add_posted_sale,
    add_product,
    add_stock,
    api,
    audit_rows,
    execute,
    make_shop,
    open_shift,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def client(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[httpx.AsyncClient]:
    async with api(migrated_db, redis_url) as (_, c):
        yield c


async def _rate(db: Database, shop: Shop, branch_id: UUID | str, on: date) -> TurnoverRate:
    async with db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        return await turnover_rate_on(s, shop.tenant_id, UUID(str(branch_id)), on)


async def _create_branch(client: httpx.AsyncClient, shop: Shop, **body: Any) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/branches", json={"name": "Yunusobod-1", **body}, headers=shop.owner.headers(write=True)
    )
    assert r.status_code == 201, r.text
    created: dict[str, Any] = r.json()
    return created


# --- US-M14-03 / QT-M14-02 -------------------------------------------------------------------------


async def test_qt_m14_02_new_branch_is_its_own_warehouse_and_cash_unit(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M14-02: name, address, cash registers → an independent warehouse/cash unit inside the tenant."""
    shop = await make_shop(app_db, client)
    created = await _create_branch(client, shop, address="Toshkent, Amir Temur 1")
    assert created["code"] == "02"  # next free two-digit code after the default "01"
    assert created["version"] == 1 and created["address"] == "Toshkent, Amir Temur 1"
    assert created["warehouse"]["type"] == "store" and created["warehouse"]["inventory_account"] == "2920"
    stock_branch = await _create_branch(client, shop, name="Ombor filiali", warehouse={"type": "stock"})
    assert stock_branch["code"] == "03"
    assert stock_branch["warehouse"]["inventory_account"] == "2910"
    explicit = await _create_branch(client, shop, name="Kod bilan", code="A1")
    assert explicit["code"] == "A1"
    dup = await client.post(
        "/api/v1/branches", json={"name": "Takror", "code": "01"}, headers=shop.owner.headers(write=True)
    )
    assert dup.status_code == 422
    assert dup.json()["error"]["details"] == [{"field": "code", "message_key": "validation.duplicate"}]

    branch_id = created["id"]
    warehouses = await client.get(
        "/api/v1/warehouses", params={"branch_id": branch_id}, headers=shop.owner.headers()
    )
    assert warehouses.status_code == 200
    assert [w["id"] for w in warehouses.json()["items"]] == [created["warehouse"]["id"]]
    all_wh = (await client.get("/api/v1/warehouses", headers=shop.owner.headers())).json()["items"]
    assert len(all_wh) == 4  # one per branch (MVP)

    # the plan includes 1 cash register — the default branch's "Kassa 1" (provisioned like signup does),
    # so already the first register of a new branch needs the extra_register add-on
    first_body = {"branch_id": branch_id, "name": "Kassa 1", "kind": "web"}
    blocked_first = await client.post(
        "/api/v1/cash-registers", json=first_body, headers=shop.owner.headers(write=True)
    )
    assert blocked_first.status_code == 403
    assert blocked_first.json()["error"]["code"] == "ADDON_REQUIRED"
    assert blocked_first.json()["error"]["params"] == {
        "addon_code": "extra_register",
        "limit": 1,
        "active": 1,
    }
    await add_extra_registers(app_db, shop.tenant_id, 1)
    first = await client.post(
        "/api/v1/cash-registers", json=first_body, headers=shop.owner.headers(write=True)
    )
    assert first.status_code == 201, first.text
    assert first.json()["ofd_status"] == "pending" and first.json()["version"] == 1
    second_body = {"branch_id": branch_id, "name": "Kassa 2", "kind": "android"}
    blocked = await client.post(
        "/api/v1/cash-registers", json=second_body, headers=shop.owner.headers(write=True)
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ADDON_REQUIRED"
    assert blocked.json()["error"]["params"] == {"addon_code": "extra_register", "limit": 2, "active": 2}
    await add_extra_registers(app_db, shop.tenant_id, 1)
    second = await client.post(
        "/api/v1/cash-registers", json=second_body, headers=shop.owner.headers(write=True)
    )
    assert second.status_code == 201, second.text

    registers = await client.get(
        "/api/v1/cash-registers", params={"branch_id": branch_id}, headers=shop.owner.headers()
    )
    items = registers.json()["items"]
    assert {i["name"] for i in items} == {"Kassa 1", "Kassa 2"}
    assert all(i["branch_id"] == branch_id and i["fm_state"] == "unknown" for i in items)

    audit = await audit_rows(admin_engine, shop.tenant_id, "branch.created")
    assert len(audit) == 3 and audit[0]["entity_id"] == UUID(branch_id)
    assert len(await audit_rows(admin_engine, shop.tenant_id, "cash_register.created")) == 2


async def test_branch_list_detail_and_branch_scope(client: httpx.AsyncClient, app_db: Database) -> None:
    shop = await make_shop(app_db, client)
    other = await _create_branch(client, shop, name="Chilonzor-3")
    listed = await client.get("/api/v1/branches", headers=shop.owner.headers())
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2 and body["page"] == 1
    assert [b["code"] for b in body["items"]] == ["01", "02"]
    assert body["items"][0]["is_default"] is True
    assert set(body["items"][0]) == {
        "id", "name", "code", "address", "is_default", "settlement_category", "activity_type", "version",
    }  # fmt: skip

    # a manager bound to the new branch only (memberships.branch_ids, 15 §2.4)
    manager = await add_member(app_db, client, shop, SystemRole.MANAGER, branch_ids=(UUID(other["id"]),))
    mine = (await client.get("/api/v1/branches", headers=manager.headers())).json()
    assert [b["id"] for b in mine["items"]] == [other["id"]] and mine["total"] == 1
    denied = await client.get(f"/api/v1/branches/{shop.branch_id}", headers=manager.headers())
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"
    ok = await client.get(f"/api/v1/branches/{other['id']}", headers=manager.headers())
    assert ok.status_code == 200
    header_denied = await client.get(
        "/api/v1/branches", headers=manager.headers(**{"X-Branch-Id": str(shop.branch_id)})
    )
    assert header_denied.status_code == 403
    wh = await client.get(
        "/api/v1/warehouses", params={"branch_id": str(shop.branch_id)}, headers=manager.headers()
    )
    assert wh.status_code == 403
    only_mine = (await client.get("/api/v1/warehouses", headers=manager.headers())).json()["items"]
    assert {w["branch_id"] for w in only_mine} == {other["id"]}
    # settings.branches is the owner's: a manager cannot create or edit branches
    forbidden = await client.post(
        "/api/v1/branches", json={"name": "Menejer"}, headers=manager.headers(write=True)
    )
    assert forbidden.status_code == 403


async def test_branch_detail_today_sales_and_stock_value(client: httpx.AsyncClient, app_db: Database) -> None:
    """US-M14-01 short totals: computed from sales / stock_balances, zero when empty."""
    shop = await make_shop(app_db, client)
    empty = await client.get(f"/api/v1/branches/{shop.branch_id}", headers=shop.owner.headers())
    assert empty.status_code == 200, empty.text
    assert empty.json()["today_sales"] == "0.00" and empty.json()["stock_value"] == "0.00"

    product = await add_product(app_db, shop.tenant_id)
    await add_stock(app_db, shop.tenant_id, shop.warehouse_id, product, "10.000", "150000.00")
    register = await add_cash_register(app_db, shop.tenant_id, shop.branch_id)
    device = await add_device(app_db, shop.tenant_id, register)
    shift = await open_shift(app_db, shop.tenant_id, shop.branch_id, register, device, shop.owner.user_id)
    today = tashkent_today()
    for total, day in (("120000.00", today), ("5000.50", today), ("99999.00", today - timedelta(days=1))):
        await add_posted_sale(
            app_db, shop.tenant_id, shop.branch_id, shift, register, shop.owner.user_id, total, day
        )
    detail = (await client.get(f"/api/v1/branches/{shop.branch_id}", headers=shop.owner.headers())).json()
    assert detail["today_sales"] == "125000.50"
    assert detail["stock_value"] == "150000.00"
    assert detail["is_default"] is True and detail["settlement_category"] == "city_100k_plus"


# --- US-M14-04 / QT-M14-03 / QT-M14-04 / QT-M14-05 ---------------------------------------------------


async def test_qt_m14_03_other_settlement_category_rate_2pct(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    shop = await make_shop(app_db, client)
    created = await _create_branch(client, shop, settlement_category="other")
    assert created["settlement_category"] == "other"
    history = await client.get(f"/api/v1/branches/{created['id']}/tax-settings", headers=shop.owner.headers())
    assert history.status_code == 200
    today = tashkent_today()
    assert history.json()["items"] == [
        {
            "valid_from": month_start(today).isoformat(),
            "settlement_category": "other",
            "activity_type": "retail",
        }
    ]
    rate = await _rate(app_db, shop, created["id"], today)
    assert (rate.settlement_category, rate.rate_code, rate.rate_pct) == (
        "other",
        "retail_other",
        Decimal("2.00"),
    )


async def test_qt_m14_04_no_category_defaults_to_city_4pct(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    """QT-M14-04: no category chosen → city_100k_plus (4%, most conservative); the UI shows the verify hint."""
    shop = await make_shop(app_db, client)
    created = await _create_branch(client, shop)
    assert created["settlement_category"] == "city_100k_plus" and created["activity_type"] == "retail"
    rate = await _rate(app_db, shop, created["id"], tashkent_today())
    assert (rate.rate_code, rate.rate_pct) == ("retail_city_100k_plus", Decimal("4.00"))


async def test_qt_m14_05_future_category_change_keeps_old_rate_for_current_month(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M14-05: other → city_100k_plus from the 1st of next month; the current month keeps 2%."""
    shop = await make_shop(app_db, client)
    created = await _create_branch(client, shop, settlement_category="other")
    today = tashkent_today()
    switch = next_month_start(today)
    r = await client.post(
        f"/api/v1/branches/{created['id']}/tax-settings",
        json={
            "valid_from": switch.isoformat(),
            "settlement_category": "city_100k_plus",
            "activity_type": "retail",
        },
        headers=shop.owner.headers(write=True),
    )
    assert r.status_code == 201, r.text
    assert r.json() == {
        "branch_id": created["id"], "valid_from": switch.isoformat(), "settlement_category": "city_100k_plus",
        "activity_type": "retail",
    }  # fmt: skip
    this_month = await _rate(app_db, shop, created["id"], today)
    next_month = await _rate(app_db, shop, created["id"], switch)
    assert (this_month.settlement_category, this_month.rate_pct) == ("other", Decimal("2.00"))
    assert (next_month.settlement_category, next_month.rate_pct) == ("city_100k_plus", Decimal("4.00"))
    # the branch still shows the category in force today
    detail = (await client.get(f"/api/v1/branches/{created['id']}", headers=shop.owner.headers())).json()
    assert detail["settlement_category"] == "other"

    past = await client.post(
        f"/api/v1/branches/{created['id']}/tax-settings",
        json={
            "valid_from": (month_start(today) - timedelta(days=1)).isoformat(),
            "settlement_category": "remote_mountain",
            "activity_type": "retail",
        },
        headers=shop.owner.headers(write=True),
    )
    assert past.status_code == 422
    assert past.json()["error"]["details"] == [
        {"field": "valid_from", "message_key": "validation.past_period"}
    ]
    assert len(await audit_rows(admin_engine, shop.tenant_id, "branch_tax_category_changed")) == 1


async def test_patch_branch_upserts_current_month_and_keeps_history(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    """20 #33: a category change on PATCH → branch_tax_settings(valid_from = 1st of this month), last wins."""
    shop = await make_shop(app_db, client)
    # the signup default branch has no history; pretend it exists since an earlier month
    created_at = month_start(tashkent_today()) - timedelta(days=40)
    await execute(
        app_db,
        shop.tenant_id,
        "UPDATE app.branches SET created_at = :at WHERE id = :id",
        at=created_at,
        id=shop.branch_id,
    )
    url = f"/api/v1/branches/{shop.branch_id}"
    r = await client.patch(
        url, json={"settlement_category": "other", "address": "Yangi manzil", "version": 1},
        headers=shop.owner.headers(write=True),
    )  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["settlement_category"] == "other" and r.json()["version"] == 2
    assert r.json()["address"] == "Yangi manzil"
    again = await client.patch(
        url,
        json={"settlement_category": "remote_mountain", "version": 2},
        headers=shop.owner.headers(write=True),
    )
    assert again.status_code == 200 and again.json()["version"] == 3
    history = (await client.get(f"{url}/tax-settings", headers=shop.owner.headers())).json()
    this_month = month_start(tashkent_today()).isoformat()
    assert [(i["valid_from"], i["settlement_category"]) for i in history["items"]] == [
        (this_month, "remote_mountain"),  # same month twice → one row, the last change wins
        (month_start(created_at).isoformat(), "city_100k_plus"),  # baseline: earlier months keep the old rate
    ]
    last_month = await _rate(app_db, shop, shop.branch_id, month_start(tashkent_today()) - timedelta(days=1))
    assert last_month.rate_pct == Decimal("4.00")
    now = await _rate(app_db, shop, shop.branch_id, tashkent_today())
    assert (now.rate_code, now.rate_pct) == ("retail_remote_mountain", Decimal("1.00"))

    stale = await client.patch(
        url, json={"name": "Eski", "version": 1}, headers=shop.owner.headers(write=True)
    )
    assert stale.status_code == 409 and stale.json()["error"]["params"]["current_version"] == 3
    name_only = await client.patch(
        url, json={"name": "Markaz", "version": 3}, headers=shop.owner.headers(write=True)
    )
    assert name_only.json()["name"] == "Markaz"
    assert len((await client.get(f"{url}/tax-settings", headers=shop.owner.headers())).json()["items"]) == 2


async def test_warehouse_patch_and_account_lock(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    url = f"/api/v1/warehouses/{shop.warehouse_id}"
    r = await client.patch(
        url,
        json={"inventory_account": "2910", "name": "Zaxira", "version": 1},
        headers=shop.owner.headers(write=True),
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "id": str(shop.warehouse_id), "name": "Zaxira", "type": "store", "inventory_account": "2910", "version": 2,
    }  # fmt: skip
    product = await add_product(app_db, shop.tenant_id)
    await add_stock(app_db, shop.tenant_id, shop.warehouse_id, product, "1.000", "1000.00")
    locked = await client.patch(
        url, json={"inventory_account": "2920", "version": 2}, headers=shop.owner.headers(write=True)
    )
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "WAREHOUSE_ACCOUNT_LOCKED"
    renamed = await client.patch(
        url, json={"name": "Asosiy", "version": 2}, headers=shop.owner.headers(write=True)
    )
    assert renamed.status_code == 200 and renamed.json()["inventory_account"] == "2910"
    bad = await client.patch(
        url, json={"inventory_account": "4010", "version": 3}, headers=shop.owner.headers(write=True)
    )
    assert bad.status_code == 422
    audit = await audit_rows(admin_engine, shop.tenant_id, "warehouse.updated")
    assert audit[0]["before"] == {"inventory_account": "2920", "name": "Asosiy ombor"}


async def test_cash_register_patch_fiscal_pair_and_archive(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    # the plan's "Kassa 1" is provisioned with the tenant (as signup does, CORR-07b)
    provisioned = (await client.get("/api/v1/cash-registers", headers=shop.owner.headers())).json()["items"]
    assert [(i["name"], i["branch_id"], i["version"]) for i in provisioned] == [
        ("Kassa 1", str(shop.branch_id), 1)
    ]
    register = provisioned[0]["id"]
    url = f"/api/v1/cash-registers/{register}"

    renamed = await client.patch(
        url, json={"name": "Asosiy kassa", "version": 1}, headers=shop.owner.headers(write=True)
    )
    assert renamed.status_code == 200
    assert renamed.json() == {
        "id": register, "name": "Asosiy kassa", "fiscal_agent_id": None, "fiscal_local_device_id": None, "version": 2,
    }  # fmt: skip
    half = await client.patch(
        url, json={"fiscal_agent_id": str(uuid7()), "version": 2}, headers=shop.owner.headers(write=True)
    )
    assert half.status_code == 422
    assert half.json()["error"]["details"][0]["message_key"] == "validation.fiscal_agent_pair"
    unknown_agent = await client.patch(
        url,
        json={"fiscal_agent_id": str(uuid7()), "fiscal_local_device_id": "fm-1", "version": 2},
        headers=shop.owner.headers(write=True),
    )
    assert unknown_agent.status_code == 422
    assert unknown_agent.json()["error"]["details"] == [
        {"field": "fiscal_agent_id", "message_key": "validation.not_found"}
    ]
    cleared = await client.patch(
        url, json={"fiscal_agent_id": None, "fiscal_local_device_id": None, "version": 2},
        headers=shop.owner.headers(write=True),
    )  # fmt: skip
    assert cleared.status_code == 200 and cleared.json()["version"] == 2  # nothing changed
    stale = await client.patch(url, json={"name": "X", "version": 1}, headers=shop.owner.headers(write=True))
    assert stale.status_code == 409

    # a manager has cash_register.manage but not settings.branches (fiscal agent binding)
    manager = await add_member(app_db, client, shop, SystemRole.MANAGER)
    m_rename = await client.patch(
        url, json={"name": "Menejer kassasi", "version": 2}, headers=manager.headers(write=True)
    )
    assert m_rename.status_code == 200
    m_fiscal = await client.patch(
        url, json={"fiscal_agent_id": None, "fiscal_local_device_id": None, "version": 3},
        headers=manager.headers(write=True),
    )  # fmt: skip
    assert m_fiscal.status_code == 403

    full = await client.post(
        "/api/v1/cash-registers",
        json={"branch_id": str(shop.branch_id), "name": "Kassa 2", "kind": "web"},
        headers=shop.owner.headers(write=True),
    )
    assert full.status_code == 403  # plan limit 1
    archived = await client.post(f"{url}/archive", json={}, headers=shop.owner.headers(write=True))
    assert archived.status_code == 200, archived.text
    assert archived.json()["id"] == register and archived.json()["archived_at"]
    again = await client.post(f"{url}/archive", json={}, headers=shop.owner.headers(write=True))
    assert again.status_code == 409 and again.json()["error"]["code"] == "RESOURCE_ARCHIVED"
    patch_archived = await client.patch(
        url, json={"name": "Y", "version": 4}, headers=shop.owner.headers(write=True)
    )
    assert patch_archived.status_code == 409 and patch_archived.json()["error"]["code"] == "RESOURCE_ARCHIVED"
    # archiving frees the slot (US-M17-02 edge case)
    freed = await client.post(
        "/api/v1/cash-registers",
        json={"branch_id": str(shop.branch_id), "name": "Kassa 2", "kind": "web"},
        headers=shop.owner.headers(write=True),
    )
    assert freed.status_code == 201
    active = (await client.get("/api/v1/cash-registers", headers=shop.owner.headers())).json()["items"]
    assert [i["name"] for i in active] == ["Kassa 2"]
    with_archived = await client.get(
        "/api/v1/cash-registers", params={"include_archived": "true"}, headers=shop.owner.headers()
    )
    assert len(with_archived.json()["items"]) == 2
    assert len(await audit_rows(admin_engine, shop.tenant_id, "cash_register.archived")) == 1


async def test_rls_other_tenant_branch_resources_are_not_found(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    shop_a = await make_shop(app_db, client, "A")
    shop_b = await make_shop(app_db, client, "B")
    register_a = await add_cash_register(app_db, shop_a.tenant_id, shop_a.branch_id)
    hb = shop_b.owner.headers
    assert (await client.get(f"/api/v1/branches/{shop_a.branch_id}", headers=hb())).status_code == 404
    assert (
        await client.get(f"/api/v1/branches/{shop_a.branch_id}/tax-settings", headers=hb())
    ).status_code == 404
    patch = await client.patch(
        f"/api/v1/branches/{shop_a.branch_id}", json={"name": "X1", "version": 1}, headers=hb(write=True)
    )
    assert patch.status_code == 404
    wh = await client.patch(
        f"/api/v1/warehouses/{shop_a.warehouse_id}", json={"name": "X", "version": 1}, headers=hb(write=True)
    )
    assert wh.status_code == 404
    cr = await client.patch(
        f"/api/v1/cash-registers/{register_a}", json={"name": "X", "version": 1}, headers=hb(write=True)
    )
    assert cr.status_code == 404
    arch = await client.post(f"/api/v1/cash-registers/{register_a}/archive", json={}, headers=hb(write=True))
    assert arch.status_code == 404
    foreign_branch = await client.post(
        "/api/v1/cash-registers",
        json={"branch_id": str(shop_a.branch_id), "name": "X", "kind": "web"},
        headers=hb(write=True),
    )
    assert foreign_branch.status_code == 422
    assert [b["id"] for b in (await client.get("/api/v1/branches", headers=hb())).json()["items"]] == [
        str(shop_b.branch_id)
    ]
    own = (await client.get("/api/v1/cash-registers", headers=hb())).json()["items"]
    assert [(i["name"], i["branch_id"]) for i in own] == [("Kassa 1", str(shop_b.branch_id))]  # only B's own
