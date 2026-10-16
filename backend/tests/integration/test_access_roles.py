"""Roles & permissions API (20 #24–#29) — US-M13-01/02/03 role side, QT-M13-01/02/03. Real PG + Redis."""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from app.modules.access.domain.permissions import DEFAULT_MATRIX, TENANT_PERMISSION_CODES, SystemRole
from tests.conftest import MigratedDb
from tests.support.branches import add_member, api, audit_rows, make_shop, permission_probe, role_id

pytestmark = [pytest.mark.db, pytest.mark.redis]

PROBE = permission_probe(
    "sales.create", "stock.count.create", "prices.edit", "discount.give", "returns.approve", "settings.users"
)


@pytest.fixture
async def client(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[httpx.AsyncClient]:
    async with api(migrated_db, redis_url, PROBE) as (_, c):
        yield c


def _perms(body: dict[str, Any]) -> dict[str, str | None]:
    return {p["code"]: p["limit_value"] for p in body["permissions"]}


def _fmt(limit: Decimal | None) -> str | None:
    return None if limit is None else format(limit.quantize(Decimal("0.0001")), "f")


async def _probe(client: httpx.AsyncClient, token: str, code: str) -> httpx.Response:
    return await client.get(f"/api/v1/probe/{code}", headers={"Authorization": f"Bearer {token}"})


async def test_roles_list_and_permissions_catalog(client: httpx.AsyncClient, app_db: Database) -> None:
    shop = await make_shop(app_db, client)
    r = await client.get("/api/v1/roles", headers=shop.owner.headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 5 and body["page"] == 1 and body["size"] == 50
    assert [i["name"] for i in body["items"]] == ["Egasi", "Menejer", "Kassir", "Omborchi", "Buxgalter"]
    assert all(i["is_system"] and i["version"] == 1 for i in body["items"])
    assert [i["system_code"] for i in body["items"]] == [
        "owner",
        "manager",
        "cashier",
        "storekeeper",
        "accountant",
    ]

    page2 = await client.get("/api/v1/roles", params={"page": 2, "size": 2}, headers=shop.owner.headers())
    assert [i["name"] for i in page2.json()["items"]] == ["Kassir", "Omborchi"]

    cat = await client.get("/api/v1/permissions-catalog", headers=shop.owner.headers())
    assert cat.status_code == 200
    items = {i["code"]: i for i in cat.json()["items"]}
    assert set(items) == set(TENANT_PERMISSION_CODES)
    assert "platform.admin" not in items
    assert items["discount.give"]["requires_limit"] is True
    assert items["sales.create"]["requires_limit"] is False
    assert items["cash.withdraw"]["module"] == "M16"
    assert all(i["description"] for i in items.values())


async def test_role_crud_conflicts_and_audit(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    h = shop.owner.headers
    created = await client.post("/api/v1/roles", json={"name": "  Kassir-omborchi "}, headers=h(write=True))
    assert created.status_code == 201, created.text
    role = created.json()
    assert role["name"] == "Kassir-omborchi" and role["is_system"] is False and role["version"] == 1
    assert created.headers["Location"].endswith(f"/roles/{role['id']}")

    dup = await client.post("/api/v1/roles", json={"name": "kassir-OMBORCHI"}, headers=h(write=True))
    assert dup.status_code == 422
    assert dup.json()["error"]["details"] == [{"field": "name", "message_key": "validation.duplicate"}]
    too_long = await client.post("/api/v1/roles", json={"name": "x" * 51}, headers=h(write=True))
    assert too_long.status_code == 422
    no_key = await client.post("/api/v1/roles", json={"name": "Kalitsiz"}, headers=h())
    assert no_key.status_code == 422
    assert no_key.json()["error"]["details"][0]["field"] == "Idempotency-Key"

    renamed = await client.patch(
        f"/api/v1/roles/{role['id']}", json={"name": "Sotuvchi", "version": 1}, headers=h(write=True)
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json() == {"id": role["id"], "name": "Sotuvchi", "version": 2}
    stale = await client.patch(
        f"/api/v1/roles/{role['id']}", json={"name": "Boshqa", "version": 1}, headers=h(write=True)
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"
    assert stale.json()["error"]["params"]["current_version"] == 2

    cashier_role = await role_id(app_db, shop.tenant_id, SystemRole.CASHIER)
    system = await client.patch(
        f"/api/v1/roles/{cashier_role}", json={"name": "Kassa", "version": 1}, headers=h(write=True)
    )
    assert system.status_code == 409
    assert system.json()["error"]["code"] == "SYSTEM_ROLE_READONLY"

    created_audit = await audit_rows(admin_engine, shop.tenant_id, "role_created")
    assert created_audit[0]["after"] == {"name": "Kassir-omborchi"}
    updated_audit = await audit_rows(admin_engine, shop.tenant_id, "role_updated")
    assert updated_audit[0]["before"] == {"name": "Kassir-omborchi"}
    assert updated_audit[0]["after"] == {"name": "Sotuvchi"}


async def test_put_permissions_validation(client: httpx.AsyncClient, app_db: Database) -> None:
    shop = await make_shop(app_db, client)
    cashier_role = await role_id(app_db, shop.tenant_id, SystemRole.CASHIER)
    owner_role = await role_id(app_db, shop.tenant_id, SystemRole.OWNER)

    async def put(role: object, permissions: list[dict[str, Any]]) -> httpx.Response:
        return await client.put(
            f"/api/v1/roles/{role}/permissions",
            json={"permissions": permissions},
            headers=shop.owner.headers(write=True),
        )

    cases: list[tuple[list[dict[str, Any]], str, str]] = [
        ([{"code": "no.such.code"}], "permissions[0].code", "validation.unknown_permission"),
        ([{"code": "platform.admin"}], "permissions[0].code", "validation.unknown_permission"),
        (
            [{"code": "sales.create", "limit_value": "5.00"}],
            "permissions[0].limit_value",
            "validation.limit_not_allowed",
        ),
        (
            [{"code": "discount.give", "limit_value": "100.01"}],
            "permissions[0].limit_value",
            "validation.max_value",
        ),
        ([{"code": "settings.tenant"}], "permissions[0].code", "validation.owner_only_permission"),
        ([{"code": "sales.create"}, {"code": "sales.create"}], "permissions[1].code", "validation.duplicate"),
    ]
    for permissions, field, key in cases:
        r = await put(cashier_role, permissions)
        assert r.status_code == 422, (permissions, r.text)
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"
        assert {"field": field, "message_key": key} in r.json()["error"]["details"], permissions

    bad_number = await put(cashier_role, [{"code": "discount.give", "limit_value": "-1"}])
    assert bad_number.status_code == 422  # pattern: non-negative decimal string
    owner = await put(owner_role, [{"code": "sales.create"}])
    assert owner.status_code == 422
    assert owner.json()["error"]["details"] == [
        {"field": "permissions", "message_key": "validation.owner_role_readonly"}
    ]


async def test_qt_m13_01_role_grants_its_permissions(client: httpx.AsyncClient, app_db: Database) -> None:
    """QT-M13-01 / US-M13-01: a member with the Kassir role gets exactly the Kassir role_permissions."""
    shop = await make_shop(app_db, client)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    cashier_role = await role_id(app_db, shop.tenant_id, SystemRole.CASHIER)

    r = await client.get(f"/api/v1/roles/{cashier_role}/permissions", headers=shop.owner.headers())
    assert r.status_code == 200, r.text
    assert r.json()["role_id"] == str(cashier_role)
    expected = {code: _fmt(limit) for code, limit in DEFAULT_MATRIX[SystemRole.CASHIER].items()}
    assert _perms(r.json()) == expected
    assert _perms(r.json())["discount.give"] == "5.0000"

    assert (await _probe(client, cashier.token, "sales.create")).status_code == 200
    assert (await _probe(client, cashier.token, "discount.give")).json() == {"limit": "5.0000"}
    assert (await _probe(client, cashier.token, "returns.approve")).json() == {"limit": "100000.0000"}
    denied = await _probe(client, cashier.token, "prices.edit")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"
    # role management itself is settings.users (owner only by default)
    assert (await client.get("/api/v1/roles", headers=cashier.headers())).status_code == 403


async def test_qt_m13_02_two_roles_union_and_most_generous_limit(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    """QT-M13-02 / US-M13-02: Kassir + Omborchi → union of both; overlapping limit → the higher one wins."""
    shop = await make_shop(app_db, client)
    storekeeper_role = await role_id(app_db, shop.tenant_id, SystemRole.STOREKEEPER)
    both = await add_member(app_db, client, shop, SystemRole.CASHIER, extra_role_ids=(storekeeper_role,))
    assert (await _probe(client, both.token, "sales.create")).status_code == 200  # Kassir only
    assert (await _probe(client, both.token, "stock.count.create")).status_code == 200  # Omborchi only
    assert (await _probe(client, both.token, "prices.edit")).status_code == 403  # neither

    # a custom role with a higher discount limit: the most generous limit applies (M13 chekka holat)
    h = shop.owner.headers
    senior = (await client.post("/api/v1/roles", json={"name": "Katta kassir"}, headers=h(write=True))).json()
    put = await client.put(
        f"/api/v1/roles/{senior['id']}/permissions",
        json={"permissions": [{"code": "discount.give", "limit_value": "8.00"}]},
        headers=h(write=True),
    )
    assert put.status_code == 200, put.text
    assert _perms(put.json()) == {"discount.give": "8.0000"}
    mixed = await add_member(app_db, client, shop, SystemRole.CASHIER, extra_role_ids=(senior["id"],))
    assert (await _probe(client, mixed.token, "discount.give")).json() == {"limit": "8.0000"}

    unlimited = (await client.post("/api/v1/roles", json={"name": "Cheksiz"}, headers=h(write=True))).json()
    await client.put(
        f"/api/v1/roles/{unlimited['id']}/permissions",
        json={"permissions": [{"code": "discount.give", "limit_value": None}]},
        headers=h(write=True),
    )
    free = await add_member(app_db, client, shop, SystemRole.CASHIER, extra_role_ids=(unlimited["id"],))
    assert (await _probe(client, free.token, "discount.give")).json() == {"limit": None}  # NULL = unlimited


async def test_qt_m13_03_limit_change_takes_effect_immediately(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M13-03 / US-M13-03: discount.give 5.00 → 8.00 applies to the existing token at once."""
    shop = await make_shop(app_db, client)
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    cashier_role = await role_id(app_db, shop.tenant_id, SystemRole.CASHIER)
    assert (await _probe(client, cashier.token, "discount.give")).json() == {"limit": "5.0000"}

    current = _perms(
        (await client.get(f"/api/v1/roles/{cashier_role}/permissions", headers=shop.owner.headers())).json()
    )
    wanted = {**current, "discount.give": "8.00"}
    body = {"permissions": [{"code": c, "limit_value": v} for c, v in wanted.items()]}
    key = shop.owner.headers(write=True)
    r = await client.put(f"/api/v1/roles/{cashier_role}/permissions", json=body, headers=key)
    assert r.status_code == 200, r.text
    assert _perms(r.json())["discount.give"] == "8.0000"

    # same cashier token, no re-login: the live role_permissions row decides
    assert (await _probe(client, cashier.token, "discount.give")).json() == {"limit": "8.0000"}

    # idempotent replay of the same PUT: stored response, nothing re-applied
    replay = await client.put(f"/api/v1/roles/{cashier_role}/permissions", json=body, headers=key)
    assert replay.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert replay.json() == r.json()

    audit = await audit_rows(admin_engine, shop.tenant_id, "role_permissions_changed")
    assert len(audit) == 1
    assert audit[0]["user_id"] == shop.owner.user_id
    assert audit[0]["before"]["permissions"]["discount.give"] == "5.0000"
    assert audit[0]["after"]["permissions"]["discount.give"] == "8.0000"

    # revoking a permission is just as immediate
    without_sales = {c: v for c, v in wanted.items() if c != "sales.create"}
    body = {"permissions": [{"code": c, "limit_value": v} for c, v in without_sales.items()]}
    r = await client.put(
        f"/api/v1/roles/{cashier_role}/permissions", json=body, headers=shop.owner.headers(write=True)
    )
    assert r.status_code == 200
    assert (await _probe(client, cashier.token, "sales.create")).status_code == 403
    roles = (await client.get("/api/v1/roles", headers=shop.owner.headers())).json()["items"]
    assert next(i for i in roles if i["id"] == str(cashier_role))["version"] == 3


async def test_rls_other_tenant_role_is_not_found(client: httpx.AsyncClient, app_db: Database) -> None:
    shop_a = await make_shop(app_db, client, "A do'kon")
    shop_b = await make_shop(app_db, client, "B do'kon")
    foreign = await role_id(app_db, shop_a.tenant_id, SystemRole.CASHIER)
    hb = shop_b.owner.headers
    assert (await client.get(f"/api/v1/roles/{foreign}/permissions", headers=hb())).status_code == 404
    patch = await client.patch(
        f"/api/v1/roles/{foreign}", json={"name": "X", "version": 1}, headers=hb(write=True)
    )
    assert patch.status_code == 404
    put = await client.put(
        f"/api/v1/roles/{foreign}/permissions", json={"permissions": []}, headers=hb(write=True)
    )
    assert put.status_code == 404
    assert put.json()["error"]["code"] == "NOT_FOUND"
    names = [i["name"] for i in (await client.get("/api/v1/roles", headers=hb())).json()["items"]]
    assert len(names) == 5  # only B's own roles
