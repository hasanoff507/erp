"""Products, barcodes, categories, units (19 §1–§3, US-M09-05, QT-M09-05/08) — real app + PostgreSQL/Redis."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from app.core.db.session import tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.catalog.domain.barcodes import is_valid_ean13, is_weight_prefixed
from tests.support.catalog import Env, catalog_env_fixture, create_product, product_body
from tests.support.ordering import TXN_ORDER

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

API = "/api/v1"


def err(response: Any) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def test_product_crud_version_archive(env: Env) -> None:
    shop = await env.shop("Katalog CRUD")
    c = env.client
    created = await c.post(
        f"{API}/products",
        json=product_body("Coca-Cola 1.5L", name_ru="Кока-кола 1.5Л", barcode="4780000000012", min_stock="5.000",
                          mxik_code="02202001001000000"),
        headers=shop.h(),
    )  # fmt: skip
    assert created.status_code == 201, created.text
    p = created.json()
    assert (
        p["version"] == 1
        and p["vat_rate"] == "12.00"
        and p["min_stock"] == "5.000"
        and p["is_marked"] is False
    )
    assert created.headers["location"].endswith(p["id"])
    assert p["barcodes"] == [
        {
            "id": p["barcodes"][0]["id"],
            "barcode": "4780000000012",
            "kind": "ean",
            "units_per_barcode": "1.000",
        }
    ]
    got = await c.get(f"{API}/products/{p['id']}", headers=shop.h(key=None))
    assert got.status_code == 200 and got.json() == p

    patched = await c.patch(
        f"{API}/products/{p['id']}", json={"version": 1, "name_ru": None}, headers=shop.h()
    )
    assert patched.status_code == 200 and patched.json()["version"] == 2 and patched.json()["name_ru"] is None
    stale = await c.patch(f"{API}/products/{p['id']}", json={"version": 1, "name": "X"}, headers=shop.h())
    assert stale.status_code == 409 and err(stale) == "VERSION_CONFLICT"
    assert stale.json()["error"]["params"]["current_version"] == 2
    no_version = await c.patch(f"{API}/products/{p['id']}", json={"name": "X"}, headers=shop.h())
    assert no_version.status_code == 422 and err(no_version) == "VALIDATION_ERROR"

    archived = await c.post(f"{API}/products/{p['id']}/archive", json={"reason": "eski"}, headers=shop.h())
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    blocked = await c.patch(f"{API}/products/{p['id']}", json={"version": 3, "name": "Y"}, headers=shop.h())
    assert blocked.status_code == 409 and err(blocked) == "RESOURCE_ARCHIVED"
    listed = await c.get(f"{API}/products", headers=shop.h(key=None))
    assert listed.json()["total"] == 0
    listed = await c.get(f"{API}/products", params={"archived": "true"}, headers=shop.h(key=None))
    assert listed.json()["total"] == 1
    restored = await c.post(f"{API}/products/{p['id']}/unarchive", headers=shop.h())
    assert restored.status_code == 200 and restored.json()["archived_at"] is None

    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        actions = [
            r[0]
            for r in await s.execute(
                text(f"SELECT action FROM app.audit_log WHERE entity_id = :id ORDER BY {TXN_ORDER}, id"),
                {"id": p["id"]},
            )
        ]
        queued = (
            await s.execute(
                text("SELECT count(*) FROM app.label_print_queue WHERE product_id = :id AND reason = 'new'"),
                {"id": p["id"]},
            )
        ).scalar_one()
    assert actions == [
        "product_created", "product_updated", "product_archived", "product_unarchived"
    ]  # fmt: skip
    assert queued == 1  # US-M09-04 "Yangi tovarlar"


async def test_product_validation_rules(env: Env) -> None:
    shop = await env.shop("Katalog validatsiya")
    c = env.client

    async def post(**body: Any) -> Any:
        return await c.post(f"{API}/products", json=body, headers=shop.h())

    bad_mxik = await post(**product_body(mxik_code="12345"))
    assert bad_mxik.status_code == 422 and err(bad_mxik) == "MXIK_CODE_INVALID"
    no_vat = await post(name="A", unit_code="box")
    assert no_vat.status_code == 422
    assert no_vat.json()["error"]["details"][0]["message_key"] == "validation.vat_rate_or_exemption_required"
    exempt = await post(name="Non", unit_code="kg", vat_exemption_code="IMT-1", is_weighed=True)
    assert exempt.status_code == 201 and exempt.json()["vat_rate"] is None
    wrong_rate = await post(**product_body(vat_rate="15.00"))
    assert wrong_rate.status_code == 422
    marked = await post(**product_body(is_marked=True))
    assert marked.status_code == 422 and marked.json()["error"]["details"][0]["field"] == "marking_group_code"
    marked_ok = await post(**product_body("Suv", is_marked=True, marking_group_code="water_beverages"))
    assert marked_ok.status_code == 201
    unit = await post(**product_body(unit_code="tonna"))
    assert unit.status_code == 422 and unit.json()["error"]["details"][0]["field"] == "unit_code"
    extra = await post(**product_body(price="1.00"))
    assert extra.status_code == 422  # extra="forbid"
    bad_category = await post(**product_body(category_id="01933a1e-7c9a-7c3a-9b1e-2f6a8e9d0c1a"))
    assert bad_category.status_code == 422


async def test_qt_m09_08_barcode_duplicate_within_tenant(env: Env) -> None:
    shop = await env.shop("Shtrix takror")
    other = await env.shop("Boshqa do'kon")
    coca = await create_product(env.client, shop, "Coca-Cola 1.5L", barcode="4780000000012")
    beef = await create_product(env.client, shop, "Mol go'shti (kg)", unit_code="kg")
    dup = await env.client.post(
        f"{API}/products/{beef['id']}/barcodes",
        json={"barcode": "4780000000012", "kind": "ean"},
        headers=shop.h(),
    )
    assert dup.status_code == 409 and err(dup) == "BARCODE_DUPLICATE"
    dup_create = await env.client.post(
        f"{API}/products", json=product_body("Fanta", barcode="4780000000012"), headers=shop.h()
    )
    assert dup_create.status_code == 409 and err(dup_create) == "BARCODE_DUPLICATE"
    # the failed create rolled back entirely — no orphan "Fanta"
    found = await env.client.get(f"{API}/products", params={"search": "Fanta"}, headers=shop.h(key=None))
    assert found.json()["total"] == 0
    # unique per tenant, not globally
    await create_product(env.client, other, "Coca-Cola", barcode="4780000000012")
    assert coca["barcodes"][0]["barcode"] == "4780000000012"


async def test_barcode_sub_resource(env: Env) -> None:
    shop = await env.shop("Shtrix-kodlar")
    p = await create_product(env.client, shop)
    url = f"{API}/products/{p['id']}/barcodes"
    box = await env.client.post(
        url,
        json={"barcode": "14780000000019", "kind": "ean", "units_per_barcode": "12.000"},
        headers=shop.h(),
    )
    assert box.status_code == 201 and box.json()["units_per_barcode"] == "12.000"
    bad_internal = await env.client.post(
        url, json={"barcode": "4780000000012", "kind": "internal"}, headers=shop.h()
    )
    assert bad_internal.status_code == 422
    listed = await env.client.get(url, headers=shop.h(key=None))
    assert [b["barcode"] for b in listed.json()["items"]] == ["14780000000019"]
    deleted = await env.client.delete(f"{url}/{box.json()['id']}", headers=shop.h())
    assert deleted.status_code == 204
    again = await env.client.delete(f"{url}/{box.json()['id']}", headers=shop.h())
    assert again.status_code == 404 and again.json()["error"]["params"]["resource"] == "product_barcode"


async def test_qt_m09_05_internal_barcode_generation(env: Env) -> None:
    """US-M09-05: 13-digit EAN-13, ``04`` prefix, valid check digit, unique in tenant, never 20–29."""
    shop = await env.shop("Ichki kod")
    p1 = await create_product(env.client, shop, "Tvorog (shtrix-kodsiz)", unit_code="kg")
    p2 = await create_product(env.client, shop, "Somsa")
    # a code typed by hand that occupies the first sequence value must be skipped, not collide
    taken = await env.client.post(
        f"{API}/products/{p2['id']}/barcodes",
        json={"barcode": "0400000000008", "kind": "internal"},
        headers=shop.h(),
    )
    assert taken.status_code == 201
    key = "internal-gen-1"
    first = await env.client.post(
        f"{API}/products/{p1['id']}/barcodes/internal-generate", json={}, headers=shop.h(key=key)
    )
    assert first.status_code == 201, first.text
    code = first.json()["barcode"]
    assert first.json() == {"barcode": code, "kind": "internal", "units_per_barcode": "1.000"}
    assert len(code) == 13 and code.startswith("04") and is_valid_ean13(code) and not is_weight_prefixed(code)
    assert code != "0400000000008"
    # double click with the same Idempotency-Key → same code, no second barcode
    replay = await env.client.post(
        f"{API}/products/{p1['id']}/barcodes/internal-generate", json={}, headers=shop.h(key=key)
    )
    assert replay.status_code == 201 and replay.json() == first.json()
    assert replay.headers.get("idempotent-replayed") == "true"
    second = await env.client.post(f"{API}/products/{p2['id']}/barcodes/internal-generate", headers=shop.h())
    assert second.status_code == 201 and second.json()["barcode"] not in (code, "0400000000008")
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        codes = [
            r[0]
            for r in await s.execute(text("SELECT barcode FROM app.product_barcodes WHERE kind='internal'"))
        ]
        audit = (
            await s.execute(
                text("SELECT count(*) FROM app.audit_log WHERE action = 'internal_barcode_generated'")
            )
        ).scalar_one()
    assert sorted(codes) == sorted({"0400000000008", code, second.json()["barcode"]})
    assert audit == 2
    archived = await env.client.post(f"{API}/products/{p1['id']}/archive", headers=shop.h())
    assert archived.status_code == 200
    refused = await env.client.post(f"{API}/products/{p1['id']}/barcodes/internal-generate", headers=shop.h())
    assert refused.status_code == 409 and err(refused) == "RESOURCE_ARCHIVED"


async def test_list_search_filters_and_low_stock(env: Env) -> None:
    shop = await env.shop("Ro'yxat")
    cat = await env.client.post(f"{API}/product-categories", json={"name": "Ichimliklar"}, headers=shop.h())
    cola = await create_product(env.client, shop, "Coca-Cola 1.5L", barcode="4780000000012",
                                category_id=cat.json()["id"], min_stock="10.000")  # fmt: skip
    await create_product(env.client, shop, "Pepsi 1L", name_ru="Пепси", min_stock="1.000")
    await create_product(env.client, shop, "Mol go'shti", unit_code="kg", is_weighed=True)
    h = shop.h(key=None)

    async def names(**params: Any) -> list[str]:
        r = await env.client.get(f"{API}/products", params=params, headers=h)
        assert r.status_code == 200, r.text
        return [i["name"] for i in r.json()["items"]]

    assert await names(search="cola") == ["Coca-Cola 1.5L"]
    assert await names(search="4780000000012") == ["Coca-Cola 1.5L"]
    assert await names(search="пепси") == ["Pepsi 1L"]
    assert await names(category_id=cat.json()["id"]) == ["Coca-Cola 1.5L"]
    assert await names(is_weighed="true") == ["Mol go'shti"]
    page = (await env.client.get(f"{API}/products", params={"page": 2, "size": 2}, headers=h)).json()
    assert page["total"] == 3 and page["page"] == 2 and page["size"] == 2 and len(page["items"]) == 1
    too_big = await env.client.get(f"{API}/products", params={"size": 201}, headers=h)
    assert too_big.status_code == 422
    # stock: cola 4 (< 10) → low; pepsi 5 (> 1) → not low
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        wh = (
            await s.execute(text("SELECT id FROM app.warehouses WHERE branch_id = :b"), {"b": shop.branch_id})
        ).scalar_one()
        pepsi = (await s.execute(text("SELECT id FROM app.products WHERE name = 'Pepsi 1L'"))).scalar_one()
        for pid, q in ((cola["id"], "4"), (pepsi, "5")):
            await s.execute(
                text(
                    "INSERT INTO app.stock_balances (tenant_id, warehouse_id, product_id, qty) VALUES (:t, :w, :p, :q)"
                ),
                {"t": shop.tenant_id, "w": wh, "p": pid, "q": q},
            )
    assert await names(low_stock="true") == ["Coca-Cola 1.5L"]
    scoped = await env.client.get(
        f"{API}/products", params={"low_stock": "true"}, headers={**h, "X-Branch-Id": str(shop.branch_id)}
    )
    assert [i["name"] for i in scoped.json()["items"]] == ["Coca-Cola 1.5L"]


async def test_categories_and_units(env: Env) -> None:
    shop = await env.shop("Kategoriyalar")
    c = env.client
    root = (await c.post(f"{API}/product-categories", json={"name": "Oziq-ovqat"}, headers=shop.h())).json()
    child_r = await c.post(
        f"{API}/product-categories", json={"name": "Sut", "parent_id": root["id"]}, headers=shop.h()
    )
    assert child_r.status_code == 201
    child = child_r.json()
    assert child["parent_id"] == root["id"] and child["version"] == 1
    listed = (
        await c.get(f"{API}/product-categories", params={"parent_id": root["id"]}, headers=shop.h(key=None))
    ).json()
    assert [i["name"] for i in listed["items"]] == ["Sut"] and listed["total"] == 1
    cycle = await c.patch(
        f"{API}/product-categories/{root['id']}",
        json={"version": 1, "parent_id": child["id"]},
        headers=shop.h(),
    )
    assert (
        cycle.status_code == 422
        and cycle.json()["error"]["details"][0]["message_key"] == "validation.category_cycle"
    )
    renamed = await c.patch(f"{API}/product-categories/{child['id']}", json={"version": 1, "name": "Sut mahsulotlari"},
                            headers=shop.h())  # fmt: skip
    assert renamed.status_code == 200 and renamed.json()["version"] == 2
    conflict = await c.patch(
        f"{API}/product-categories/{child['id']}", json={"version": 1, "name": "Z"}, headers=shop.h()
    )
    assert conflict.status_code == 409 and err(conflict) == "VERSION_CONFLICT"

    p = await create_product(c, shop, "Qatiq", category_id=child["id"])
    has = await c.post(f"{API}/product-categories/{child['id']}/archive", json={}, headers=shop.h())
    assert has.status_code == 409 and err(has) == "CATEGORY_HAS_PRODUCTS"
    await c.post(f"{API}/products/{p['id']}/archive", headers=shop.h())
    ok = await c.post(f"{API}/product-categories/{child['id']}/archive", json={}, headers=shop.h())
    assert ok.status_code == 200 and ok.json()["archived_at"] is not None
    on_archived = await c.post(
        f"{API}/products", json=product_body(category_id=child["id"]), headers=shop.h()
    )
    assert on_archived.status_code == 422
    missing = await c.post(f"{API}/product-categories/{p['id']}/archive", json={}, headers=shop.h())
    assert missing.status_code == 404 and missing.json()["error"]["params"]["resource"] == "product_category"

    units = await c.get(f"{API}/units", headers=shop.h(key=None))
    assert units.status_code == 200
    assert {"code": "kg", "is_fractional": True} in units.json()["items"]
    assert {u["code"] for u in units.json()["items"]} >= {"pcs", "kg", "l", "m", "box"}


async def test_permissions_per_19(env: Env) -> None:
    shop = await env.shop("Ruxsatlar", SystemRole.OWNER, SystemRole.CASHIER, SystemRole.STOREKEEPER)
    p = await create_product(env.client, shop)
    c = env.client
    # cashier: stock.view only
    assert (await c.get(f"{API}/products", headers=shop.h("cashier", key=None))).status_code == 200
    assert (await c.get(f"{API}/units", headers=shop.h("cashier", key=None))).status_code == 200
    for method, url, body in (
        ("POST", f"{API}/products", product_body("Kassir tovari")),
        ("PATCH", f"{API}/products/{p['id']}", {"version": 1, "name": "X"}),
        ("POST", f"{API}/products/{p['id']}/archive", {}),
        ("POST", f"{API}/products/{p['id']}/barcodes/internal-generate", {}),
        ("POST", f"{API}/product-categories", {"name": "X"}),
        ("GET", f"{API}/products/{p['id']}/barcodes", None),
        ("GET", f"{API}/mxik-codes?query=suv", None),
    ):
        r = await c.request(method, url, json=body, headers=shop.h("cashier"))
        assert r.status_code == 403 and err(r) == "PERMISSION_DENIED", (method, url, r.text)
    # storekeeper: catalog.manage
    made = await c.post(
        f"{API}/products", json=product_body("Omborchi tovari"), headers=shop.h("storekeeper")
    )
    assert made.status_code == 201
    no_token = await c.get(f"{API}/products")
    assert no_token.status_code == 401


async def test_rls_other_tenant_product_is_404(env: Env) -> None:
    a = await env.shop("RLS A")
    b = await env.shop("RLS B")
    p = await create_product(env.client, a, barcode="4780000000111")
    c = env.client
    for method, url, body in (
        ("GET", f"{API}/products/{p['id']}", None),
        ("PATCH", f"{API}/products/{p['id']}", {"version": 1, "name": "hack"}),
        ("POST", f"{API}/products/{p['id']}/archive", {}),
        ("GET", f"{API}/products/{p['id']}/barcodes", None),
        ("POST", f"{API}/products/{p['id']}/barcodes", {"barcode": "123", "kind": "ean"}),
        ("POST", f"{API}/products/{p['id']}/barcodes/internal-generate", {}),
        ("GET", f"{API}/products/{p['id']}/prices", None),
    ):
        r = await c.request(method, url, json=body, headers=b.h())
        assert r.status_code == 404 and err(r) == "NOT_FOUND", (method, url, r.text)
        assert r.json()["error"]["params"]["resource"] == "product"
    assert (await c.get(f"{API}/products", params={"search": "4780000000111"}, headers=b.h(key=None))).json()[
        "total"
    ] == 0
    # B cannot attach A's category either (FKs alone ignore RLS)
    cat = (await c.post(f"{API}/product-categories", json={"name": "A kat"}, headers=a.h())).json()
    cross = await c.post(f"{API}/products", json=product_body(category_id=cat["id"]), headers=b.h())
    assert cross.status_code == 422


async def test_idempotent_replay_of_post_products(env: Env) -> None:
    shop = await env.shop("Idempotent")
    headers = shop.h(key="create-product-1")
    first = await env.client.post(f"{API}/products", json=product_body("Bir marta"), headers=headers)
    second = await env.client.post(f"{API}/products", json=product_body("Bir marta"), headers=headers)
    assert first.status_code == second.status_code == 201
    assert second.json() == first.json() and second.headers.get("idempotent-replayed") == "true"
    reused = await env.client.post(f"{API}/products", json=product_body("Boshqa"), headers=headers)
    assert reused.status_code == 422 and err(reused) == "IDEMPOTENCY_KEY_REUSED"
    missing = await env.client.post(
        f"{API}/products", json=product_body("Kalitsiz"), headers=shop.h(key=None)
    )
    assert missing.status_code == 422 and missing.json()["error"]["details"][0]["field"] == "Idempotency-Key"
    total = (await env.client.get(f"{API}/products", headers=shop.h(key=None))).json()["total"]
    assert total == 1
