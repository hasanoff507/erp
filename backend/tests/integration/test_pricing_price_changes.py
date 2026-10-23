"""Price history and price-change documents (19 §4, US-M09-01/02, QT-M09-01/09) — real app + DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.pricing.domain.resolution import PriceRecord, effective_price
from tests.support.catalog import Env, catalog_env_fixture, create_product, set_limit, set_price

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

API = "/api/v1"


def err(response: Any) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def _doc(env: Env, shop: Any, lines: list[dict[str, Any]], role: str = "owner", **kw: Any) -> Any:
    return await env.client.post(
        f"{API}/price-changes", json={"doc_date": "2026-10-16", "lines": lines}, headers=shop.h(role, **kw)
    )


async def _records(env: Env, tenant_id: Any) -> list[PriceRecord]:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        rows = await s.execute(
            text("SELECT id, product_id, branch_id, price, valid_from FROM app.product_prices")
        )
        return [
            PriceRecord(id=r[0], product_id=r[1], branch_id=r[2], price=r[3], valid_from=r[4]) for r in rows
        ]


async def test_qt_m09_01_manager_updates_price_old_one_goes_to_history(env: Env) -> None:
    """US-M09-01: 12000 → 13000 by the Manager (8.3% ≤ 10%), effective from ``valid_from``."""
    shop = await env.shop("Narx tarixi", SystemRole.OWNER, SystemRole.MANAGER)
    p = await create_product(env.client, shop)
    first = await set_price(env.client, shop, p["id"], "12000.0000")
    assert first["status"] == "posted" and first["number"] == "C-01-2026-000001"
    valid_from = (datetime.now(UTC) + timedelta(seconds=1)).replace(microsecond=0)
    created = await _doc(
        env,
        shop,
        [{"product_id": p["id"], "new_price": "13000.0000", "valid_from": valid_from.isoformat()}],
        role="manager",
    )
    assert created.status_code == 201, created.text
    doc = created.json()
    assert doc["status"] == "draft" and doc["number"] is None
    assert doc["lines"][0]["old_price"] == "12000.0000" and doc["lines"][0]["new_price"] == "13000.0000"
    posted = await env.client.post(f"{API}/price-changes/{doc['id']}/post", headers=shop.h("manager"))
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "posted" and posted.json()["number"] == "C-01-2026-000002"
    assert posted.json()["warnings"] == []

    history = await env.client.get(f"{API}/products/{p['id']}/prices", headers=shop.h("manager", key=None))
    assert history.status_code == 200
    items = history.json()["items"]
    assert [i["price"] for i in items] == ["13000.0000", "12000.0000"]
    assert items[0]["valid_to"] is None and items[1]["valid_to"] == items[0]["valid_from"]
    assert items[0]["price_change_doc_id"] == doc["id"]
    assert items[0]["set_by"] == str(shop.user_ids["manager"])
    assert history.json()["next_cursor"] is None
    page1 = (
        await env.client.get(
            f"{API}/products/{p['id']}/prices", params={"limit": 1}, headers=shop.h(key=None)
        )
    ).json()
    assert len(page1["items"]) == 1 and page1["next_cursor"]
    page2 = await env.client.get(
        f"{API}/products/{p['id']}/prices",
        params={"limit": 1, "cursor": page1["next_cursor"]},
        headers=shop.h(key=None),
    )
    assert [i["price"] for i in page2.json()["items"]] == ["12000.0000"] and page2.json()[
        "next_cursor"
    ] is None

    records = await _records(env, shop.tenant_id)
    pid = records[0].product_id
    before = valid_from - timedelta(milliseconds=1)
    assert effective_price(records, product_id=pid, branch_id=None, at=before) == Decimal("12000.0000")
    assert effective_price(records, product_id=pid, branch_id=shop.branch_id, at=valid_from) == Decimal(
        "13000.0000"
    )

    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        labels = (
            await s.execute(text("SELECT count(*) FROM app.label_print_queue WHERE reason = 'price_changed'"))
        ).scalar_one()
        audit = (
            await s.execute(text("SELECT count(*) FROM app.audit_log WHERE action = 'price_changed'"))
        ).scalar_one()
    assert labels == 1  # one pending label per product (US-M09-04)
    assert audit == 2


async def test_us_m09_02_over_limit_goes_to_pending_approval(env: Env) -> None:
    """>10% by the Manager → 202 pending_approval + approval_requests(kind=price_change); price unchanged."""
    shop = await env.shop("Tasdiq", SystemRole.OWNER, SystemRole.MANAGER)
    p = await create_product(env.client, shop)
    await set_price(env.client, shop, p["id"], "12000.0000")
    doc = (await _doc(env, shop, [{"product_id": p["id"], "new_price": "14000.0000"}], role="manager")).json()
    posted = await env.client.post(f"{API}/price-changes/{doc['id']}/post", headers=shop.h("manager"))
    assert posted.status_code == 202, posted.text
    body = posted.json()
    assert body["status"] == "pending_approval" and body["approval_request_id"]
    assert body["warnings"] == ["APPROVAL_REQUIRED"] and body["number"] is None
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        req = (
            await s.execute(
                text(
                    "SELECT kind, permission_code, requested_value, linked_doc_type, linked_doc_id, status, "
                    "requested_by, branch_id, expires_at > now() FROM app.approval_requests WHERE id = :id"
                ),
                {"id": body["approval_request_id"]},
            )
        ).one()
        prices = (await s.execute(text("SELECT count(*) FROM app.product_prices"))).scalar_one()
    assert req[0:4] == ("price_change", "prices.approve", Decimal("16.6667"), "price_changes")
    assert str(req[4]) == doc["id"] and req[5] == "pending" and req[6] == shop.user_ids["manager"]
    assert req[7] == shop.branch_id and req[8] is True
    assert prices == 1  # not in force until approved
    again = await env.client.post(f"{API}/price-changes/{doc['id']}/post", headers=shop.h("manager"))
    assert again.status_code == 409 and err(again) == "DOC_INVALID_STATE"
    # the owner (prices.approve, unlimited) posts a 50% change directly
    owner_doc = (await _doc(env, shop, [{"product_id": p["id"], "new_price": "18000.0000"}])).json()
    owner_post = await env.client.post(f"{API}/price-changes/{owner_doc['id']}/post", headers=shop.h())
    assert owner_post.status_code == 200 and owner_post.json()["status"] == "posted"
    repost = await env.client.post(f"{API}/price-changes/{owner_doc['id']}/post", headers=shop.h())
    assert repost.status_code == 409 and err(repost) == "DOC_NOT_DRAFT"


async def test_role_limit_value_is_used_and_no_base_means_no_check(env: Env) -> None:
    shop = await env.shop("Limit", SystemRole.OWNER, SystemRole.MANAGER)
    await set_limit(env.db, shop.tenant_id, "manager", "prices.approve", "20.0000")
    p = await create_product(env.client, shop)
    fresh = await create_product(env.client, shop, "Yangi tovar")
    await set_price(env.client, shop, p["id"], "10000.0000")
    within = await set_price(env.client, shop, p["id"], "11900.0000", role="manager")  # 19% ≤ 20%
    assert within["status"] == "posted"
    over = await set_price(env.client, shop, p["id"], "15000.0000", role="manager")  # 26% > 20%
    assert over["status"] == "pending_approval"
    first_price = await set_price(env.client, shop, fresh["id"], "99999.0000", role="manager")
    assert first_price["status"] == "posted"  # no base price → no limit check (19 §4)


async def test_branch_price_and_branch_scope(env: Env) -> None:
    shop = await env.shop("Filial narxi", SystemRole.OWNER)
    p = await create_product(env.client, shop)
    await set_price(env.client, shop, p["id"], "12000.0000")
    branch = await env.client.post(
        f"{API}/price-changes",
        json={"doc_date": "2026-10-16", "lines": [{"product_id": p["id"], "new_price": "11500.0000",
                                                    "branch_id": str(shop.branch_id)}]},
        headers=shop.h(branch=shop.branch_id),
    )  # fmt: skip
    assert branch.status_code == 201 and branch.json()["branch_id"] == str(shop.branch_id)
    assert (
        await env.client.post(f"{API}/price-changes/{branch.json()['id']}/post", headers=shop.h())
    ).status_code == 200
    history = await env.client.get(
        f"{API}/products/{p['id']}/prices",
        params={"branch_id": str(shop.branch_id)},
        headers=shop.h(key=None),
    )
    assert [i["price"] for i in history.json()["items"]] == ["11500.0000"]
    globals_ = await env.client.get(f"{API}/products/{p['id']}/prices", headers=shop.h(key=None))
    assert [i["price"] for i in globals_.json()["items"]] == ["12000.0000"]
    records = await _records(env, shop.tenant_id)
    now = datetime.now(UTC)
    pid = records[0].product_id
    assert effective_price(records, product_id=pid, branch_id=shop.branch_id, at=now) == Decimal("11500.0000")
    assert effective_price(records, product_id=pid, branch_id=uuid7(), at=now) == Decimal("12000.0000")
    unknown_branch = await _doc(
        env, shop, [{"product_id": p["id"], "new_price": "1.0000", "branch_id": str(uuid7())}]
    )
    assert unknown_branch.status_code == 422
    foreign_header = await _doc(env, shop, [{"product_id": p["id"], "new_price": "1.0000"}], branch=uuid7())
    assert foreign_header.status_code == 403 and err(foreign_header) == "BRANCH_SCOPE_DENIED"


async def test_restricted_manager_cannot_set_global_prices(env: Env) -> None:
    shop = await env.shop("Cheklangan", SystemRole.OWNER, SystemRole.MANAGER)
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.memberships SET branch_ids = ARRAY[CAST(:b AS uuid)] WHERE user_id = :u"),
            {"b": str(shop.branch_id), "u": shop.user_ids["manager"]},
        )
    p = await create_product(env.client, shop)
    global_line = await _doc(env, shop, [{"product_id": p["id"], "new_price": "1.0000"}], role="manager")
    assert global_line.status_code == 403 and err(global_line) == "BRANCH_SCOPE_DENIED"
    own = await _doc(
        env,
        shop,
        [{"product_id": p["id"], "new_price": "1.0000", "branch_id": str(shop.branch_id)}],
        role="manager",
    )
    assert own.status_code == 201 and own.json()["branch_id"] == str(shop.branch_id)


async def test_validation_permissions_rls_and_idempotency(env: Env) -> None:
    a = await env.shop("Narx A", SystemRole.OWNER, SystemRole.CASHIER, SystemRole.STOREKEEPER)
    b = await env.shop("Narx B")
    p = await create_product(env.client, a)
    line = {"product_id": p["id"], "new_price": "5000.0000"}
    for price in ("0.0000", "-1.0000"):
        bad = await _doc(env, a, [{**line, "new_price": price}])
        assert bad.status_code == 422 and err(bad) == "VALIDATION_ERROR"
    assert (await _doc(env, a, [{**line, "new_price": "5000.00"}])).status_code == 422  # 4 decimals (17 §3)
    assert (await _doc(env, a, [line, line])).status_code == 422  # duplicate product/branch
    assert (await _doc(env, a, [])).status_code == 422
    for role in ("cashier", "storekeeper"):
        denied = await _doc(env, a, [line], role=role)
        assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    # RLS: B cannot price A's product nor post A's document
    foreign = await _doc(env, b, [line])
    assert foreign.status_code == 422
    assert foreign.json()["error"]["details"][0]["message_key"] == "validation.product_not_found"
    doc = (await _doc(env, a, [line])).json()
    stolen = await env.client.post(f"{API}/price-changes/{doc['id']}/post", headers=b.h())
    assert stolen.status_code == 404 and stolen.json()["error"]["params"]["resource"] == "price_change"
    # archived product
    await env.client.post(f"{API}/products/{p['id']}/archive", headers=a.h())
    archived = await _doc(env, a, [line])
    assert archived.status_code == 409 and err(archived) == "RESOURCE_ARCHIVED"


async def test_idempotent_replay_of_post_price_changes(env: Env) -> None:
    shop = await env.shop("Narx idempotent")
    p = await create_product(env.client, shop)
    body = {"doc_date": "2026-10-16", "lines": [{"product_id": p["id"], "new_price": "7000.0000"}]}
    headers = shop.h(key="price-change-1")
    first = await env.client.post(f"{API}/price-changes", json=body, headers=headers)
    second = await env.client.post(f"{API}/price-changes", json=body, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json() and second.headers.get("idempotent-replayed") == "true"
    post_key = shop.h(key="price-change-1-post")
    posted = await env.client.post(f"{API}/price-changes/{first.json()['id']}/post", headers=post_key)
    replayed = await env.client.post(f"{API}/price-changes/{first.json()['id']}/post", headers=post_key)
    assert posted.status_code == replayed.status_code == 200 and posted.json() == replayed.json()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        docs = (await s.execute(text("SELECT count(*) FROM app.price_changes"))).scalar_one()
        prices = (await s.execute(text("SELECT count(*) FROM app.product_prices"))).scalar_one()
    assert docs == 1 and prices == 1
