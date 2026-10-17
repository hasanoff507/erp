"""Counterparties (18 §11.2–11.4, 19 §9, US-M08-05, QT-RLS-07) — real app + PostgreSQL/Redis."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.debts.wiring import DebtMoveInput, debt_register
from tests.support.purchasing import (
    API,
    Env,
    create_supplier,
    err,
    fake_einvoice,
    purchasing_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["purchasing_env_fixture"]


async def test_counterparty_crud_version_archive(env: Env) -> None:
    shop = await env.shop("Kontragent CRUD")
    c = env.client
    supplier = await create_supplier(
        c,
        shop,
        legal_address="Toshkent",
        bank_account="20208000900123456001",
        bank_mfo="00014",
        vat_payer=True,
    )
    assert supplier["is_supplier"] is True and supplier["is_customer"] is False
    assert supplier["version"] == 1 and supplier["stir"] == "301234567" and supplier["archived_at"] is None
    customer = await c.post(
        f"{API}/counterparties",
        json={"kind": "person", "name": "  Aziz aka ", "phone": "90 123-45-67", "notify_consent": True},
        headers=shop.h(),
    )
    assert customer.status_code == 201, customer.text
    cust = customer.json()
    assert customer.headers["location"].endswith(cust["id"])
    assert cust["name"] == "Aziz aka" and cust["phone"] == "+998901234567"
    assert cust["is_customer"] is True and cust["is_supplier"] is False
    assert cust["notify_consent"] is True and cust["notify_consent_at"] is not None
    assert cust["credit_limit"] is None

    got = await c.get(f"{API}/counterparties/{supplier['id']}", headers=shop.h(key=None))
    assert got.status_code == 200 and got.json() == supplier

    page = (await c.get(f"{API}/counterparties", headers=shop.h(key=None))).json()
    assert page["total"] == 2 and page["page"] == 1 and page["size"] == 50
    assert {i["receivable_balance"] for i in page["items"]} == {"0.00"}
    suppliers = (
        await c.get(f"{API}/counterparties", params={"is_supplier": "true"}, headers=shop.h(key=None))
    ).json()
    assert [i["id"] for i in suppliers["items"]] == [supplier["id"]]
    by_phone = (
        await c.get(f"{API}/counterparties", params={"search": "901234"}, headers=shop.h(key=None))
    ).json()
    assert [i["id"] for i in by_phone["items"]] == [cust["id"]]
    by_name = (
        await c.get(f"{API}/counterparties", params={"search": "mega"}, headers=shop.h(key=None))
    ).json()
    assert [i["id"] for i in by_name["items"]] == [supplier["id"]]
    by_kind = (
        await c.get(f"{API}/counterparties", params={"kind": "person"}, headers=shop.h(key=None))
    ).json()
    assert [i["id"] for i in by_kind["items"]] == [cust["id"]]

    patched = await c.patch(
        f"{API}/counterparties/{cust['id']}",
        json={"version": 1, "credit_limit": "500000.00", "notify_consent": False},
        headers=shop.h(),
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["version"] == 2 and body["credit_limit"] == "500000.00"
    assert body["notify_consent"] is False and body["notify_consent_at"] is None
    stale = await c.patch(
        f"{API}/counterparties/{cust['id']}", json={"version": 1, "name": "X"}, headers=shop.h()
    )
    assert stale.status_code == 409 and err(stale) == "VERSION_CONFLICT"
    assert stale.json()["error"]["params"]["current_version"] == 2
    missing_version = await c.patch(
        f"{API}/counterparties/{cust['id']}", json={"name": "X"}, headers=shop.h()
    )
    assert missing_version.status_code == 422

    archived = await c.post(f"{API}/counterparties/{supplier['id']}/archive", json={}, headers=shop.h())
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    active = (await c.get(f"{API}/counterparties", headers=shop.h(key=None))).json()
    assert [i["id"] for i in active["items"]] == [cust["id"]]
    only_archived = (
        await c.get(f"{API}/counterparties", params={"archived": "true"}, headers=shop.h(key=None))
    ).json()
    assert [i["id"] for i in only_archived["items"]] == [supplier["id"]]
    on_archived = await c.patch(
        f"{API}/counterparties/{supplier['id']}", json={"version": 2, "name": "Y"}, headers=shop.h()
    )
    assert on_archived.status_code == 409 and err(on_archived) == "RESOURCE_ARCHIVED"
    restored = await c.post(f"{API}/counterparties/{supplier['id']}/unarchive", headers=shop.h())
    assert restored.status_code == 200 and restored.json()["archived_at"] is None

    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        actions = (
            (
                await s.execute(
                    text("SELECT action FROM app.audit_log WHERE entity = 'counterparties' ORDER BY at, id")
                )
            )
            .scalars()
            .all()
        )
    assert actions == [
        "counterparty.created",
        "counterparty.created",
        "counterparty.updated",
        "counterparty.archived",
        "counterparty.unarchived",
    ]


@pytest.mark.parametrize(
    ("body", "field", "key"),
    [
        ({"kind": "company", "name": "MChJ", "is_supplier": True}, "stir", "validation.required"),
        (
            {"kind": "company", "name": "MChJ", "is_supplier": True, "stir": "12345"},
            "stir",
            "validation.stir_format",
        ),
        ({"kind": "person", "name": "Ali"}, "phone", "validation.required"),
        ({"kind": "person", "name": "Ali", "phone": "+99890123"}, "phone", "validation.phone_format"),
        ({"kind": "person", "name": "Ali", "phone": "abc"}, "phone", "validation.phone_format"),
        (
            {"kind": "person", "name": "Ali", "phone": "+998901234567", "standing_discount_pct": "120.00"},
            "standing_discount_pct",
            "validation.range",
        ),
        (
            {"kind": "person", "name": "Ali", "phone": "+998901234567", "credit_limit": "-1.00"},
            "credit_limit",
            "validation.min_value",
        ),
    ],
)
async def test_counterparty_validation(env: Env, body: dict[str, object], field: str, key: str) -> None:
    shop = await env.shop("Validatsiya")
    response = await env.client.post(f"{API}/counterparties", json=body, headers=shop.h())
    assert response.status_code == 422, response.text
    assert err(response) == "VALIDATION_ERROR"
    assert response.json()["error"]["details"] == [{"field": field, "message_key": key}]


async def test_counterparty_unknown_fields_and_money_format_are_rejected(env: Env) -> None:
    shop = await env.shop("Format")
    for body in (
        {"kind": "person", "name": "Ali", "phone": "+998901234567", "tenant_id": str(uuid7())},
        {"kind": "person", "name": "Ali", "phone": "+998901234567", "credit_limit": 100},
        {"kind": "bank", "name": "Ali", "phone": "+998901234567"},
    ):
        response = await env.client.post(f"{API}/counterparties", json=body, headers=shop.h())
        assert response.status_code == 422 and err(response) == "VALIDATION_ERROR", body


async def test_counterparty_permissions_by_role(env: Env) -> None:
    shop = await env.shop(
        "Ruxsatlar", SystemRole.OWNER, SystemRole.CASHIER, SystemRole.STOREKEEPER, SystemRole.ACCOUNTANT
    )
    c = env.client
    supplier = await create_supplier(c, shop)
    quick = {"kind": "person", "name": "Mijoz", "phone": "+998901112233"}

    # Kassir: quick customer (debts.create) yes, archive (debts.create, 18 §11.4) yes; supplier / limits /
    # lookup — no
    ok = await c.post(f"{API}/counterparties", json=quick, headers=shop.h("cashier"))
    assert ok.status_code == 201, ok.text
    customer = ok.json()
    for body in (
        {"kind": "company", "name": "Sup", "stir": "301234568", "is_supplier": True},
        {**quick, "credit_limit": "100000.00"},
        {**quick, "stir": "301234569"},
    ):
        denied = await c.post(f"{API}/counterparties", json=body, headers=shop.h("cashier"))
        assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED", body
    denied = await c.post(
        f"{API}/counterparties/lookup-by-stir", json={"stir": "301234567"}, headers=shop.h("cashier")
    )
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    for action in ("archive", "unarchive"):
        done = await c.post(f"{API}/counterparties/{customer['id']}/{action}", headers=shop.h("cashier"))
        assert done.status_code == 200, (action, done.text)
    patch = await c.patch(
        f"{API}/counterparties/{customer['id']}", json={"version": 1, "name": "X"}, headers=shop.h("cashier")
    )
    assert patch.status_code == 403
    assert (await c.get(f"{API}/counterparties", headers=shop.h("cashier", key=None))).status_code == 200
    balance = await c.get(
        f"{API}/counterparties/{customer['id']}/debt-balance", headers=shop.h("cashier", key=None)
    )
    assert balance.status_code == 200

    # Buxgalter: no purchases.create / debts.create → cannot create a supplier, can read (stock.view)
    denied = await c.post(
        f"{API}/counterparties",
        json={"kind": "company", "name": "Sup2", "stir": "301234570", "is_supplier": True},
        headers=shop.h("accountant"),
    )
    assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED"
    assert (
        await c.get(f"{API}/counterparties/{supplier['id']}", headers=shop.h("accountant", key=None))
    ).status_code == 200

    # Omborchi: purchases.create — suppliers yes (create, patch, archive), limits / customers no
    created = await c.post(
        f"{API}/counterparties",
        json={"kind": "company", "name": "Sup3", "stir": "301234571", "is_supplier": True},
        headers=shop.h("storekeeper"),
    )
    assert created.status_code == 201, created.text
    sup3 = created.json()
    renamed = await c.patch(
        f"{API}/counterparties/{sup3['id']}",
        json={"version": 1, "name": "Sup3 MChJ"},
        headers=shop.h("storekeeper"),
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Sup3 MChJ"
    limit = await c.patch(
        f"{API}/counterparties/{sup3['id']}",
        json={"version": 2, "credit_limit": "1.00"},
        headers=shop.h("storekeeper"),
    )
    assert limit.status_code == 403 and err(limit) == "PERMISSION_DENIED"
    on_customer = await c.patch(
        f"{API}/counterparties/{customer['id']}",
        json={"version": 1, "name": "Y"},
        headers=shop.h("storekeeper"),
    )
    assert on_customer.status_code == 403
    customer_create = await c.post(f"{API}/counterparties", json=quick, headers=shop.h("storekeeper"))
    assert customer_create.status_code == 403
    archived = await c.post(f"{API}/counterparties/{sup3['id']}/archive", headers=shop.h("storekeeper"))
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    restored = await c.post(f"{API}/counterparties/{sup3['id']}/unarchive", headers=shop.h("storekeeper"))
    assert restored.status_code == 200 and restored.json()["archived_at"] is None


async def test_sec_10_purchases_only_role_archives_suppliers_only(env: Env) -> None:
    """18 §11.4: without ``debts.limit.manage`` / ``debts.create``, ``purchases.create`` may archive or
    unarchive a supplier only — a customer-only counterparty → 403 PERMISSION_DENIED, row untouched."""
    shop = await env.shop("SEC-10", SystemRole.OWNER, SystemRole.STOREKEEPER)
    c = env.client
    supplier = await create_supplier(c, shop)
    made = await c.post(
        f"{API}/counterparties",
        json={"kind": "person", "name": "Faqat mijoz", "phone": "+998901112244"},
        headers=shop.h(),
    )
    assert made.status_code == 201, made.text
    customer = made.json()
    for action in ("archive", "unarchive"):
        denied = await c.post(
            f"{API}/counterparties/{customer['id']}/{action}", json={}, headers=shop.h("storekeeper")
        )
        assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED", action
    still = await c.get(f"{API}/counterparties/{customer['id']}", headers=shop.h(key=None))
    assert still.json()["archived_at"] is None
    archived = await c.post(f"{API}/counterparties/{supplier['id']}/archive", headers=shop.h("storekeeper"))
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    # the owner (debts.limit.manage) archives the customer-only row
    owner = await c.post(f"{API}/counterparties/{customer['id']}/archive", headers=shop.h())
    assert owner.status_code == 200 and owner.json()["archived_at"] is not None


async def test_debt_balance_endpoint(env: Env) -> None:
    shop = await env.shop("Qarz qoldig'i")
    supplier = await create_supplier(env.client, shop)
    url = f"{API}/counterparties/{supplier['id']}/debt-balance"
    empty = await env.client.get(url, headers=shop.h(key=None))
    assert empty.status_code == 200 and empty.json() == {"payable": "0.00", "receivable": "0.00"}

    register = debt_register()
    cp = UUID(supplier["id"])
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await register.post(
            s,
            shop.tenant_id,
            [
                DebtMoveInput(cp, "payable", Decimal("1250000.00"), "goods_receipts", uuid7()),
                DebtMoveInput(cp, "receivable", Decimal("15.50"), "supplier_returns", uuid7()),
            ],
        )
    full = await env.client.get(url, headers=shop.h(key=None))
    assert full.json() == {"payable": "1250000.00", "receivable": "15.50"}
    listed = (await env.client.get(f"{API}/counterparties", headers=shop.h(key=None))).json()["items"][0]
    assert listed["payable_balance"] == "1250000.00" and listed["receivable_balance"] == "15.50"
    missing = await env.client.get(f"{API}/counterparties/{uuid7()}/debt-balance", headers=shop.h(key=None))
    assert missing.status_code == 404 and missing.json()["error"]["params"] == {"resource": "counterparty"}


async def test_lookup_by_stir_suggests_without_saving(env: Env) -> None:
    shop = await env.shop("STIR")
    c = env.client
    url = f"{API}/counterparties/lookup-by-stir"
    found = await c.post(url, json={"stir": "305123456"}, headers=shop.h())
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["stir"] == "305123456" and body["kind"] == "company" and body["name"]
    assert len(body["bank_account"]) == 20 and len(body["bank_mfo"]) == 5
    assert body["existing_counterparty_id"] is None
    again = await c.post(url, json={"stir": "305123456"}, headers=shop.h())
    assert again.json() == body  # deterministic fake
    count = (await c.get(f"{API}/counterparties", headers=shop.h(key=None))).json()["total"]
    assert count == 0  # suggest-only

    supplier = await create_supplier(c, shop, stir="305123456")
    linked = await c.post(url, json={"stir": "305123456"}, headers=shop.h())
    assert linked.json()["existing_counterparty_id"] == supplier["id"]

    bad = await c.post(url, json={"stir": "12AB"}, headers=shop.h())
    assert (
        bad.status_code == 422
        and bad.json()["error"]["details"][0]["message_key"] == "validation.stir_format"
    )
    fake = fake_einvoice(env)
    fake.unknown_stirs.add("399999999")
    unknown = await c.post(url, json={"stir": "399999999"}, headers=shop.h())
    assert unknown.status_code == 404 and unknown.json()["error"]["params"] == {"resource": "company"}
    fake.fail = True
    down = await c.post(url, json={"stir": "305123456"}, headers=shop.h())
    assert down.status_code == 503 and err(down) == "EINVOICE_PROVIDER_UNAVAILABLE"
    fake.fail = False


async def test_qt_rls_07_counterparties_are_tenant_isolated(env: Env) -> None:
    """QT-RLS-07 (endpoint level): tenant A never sees, reads or edits tenant B's counterparty."""
    shop_a = await env.shop("Tenant A")
    shop_b = await env.shop("Tenant B")
    b_cp = await create_supplier(env.client, shop_b, name="Faqat B ta'minotchi")
    c = env.client
    search = (
        await c.get(f"{API}/counterparties", params={"search": "Faqat B"}, headers=shop_a.h(key=None))
    ).json()
    assert search == {"items": [], "total": 0, "page": 1, "size": 50}
    for response in (
        await c.get(f"{API}/counterparties/{b_cp['id']}", headers=shop_a.h(key=None)),
        await c.get(f"{API}/counterparties/{b_cp['id']}/debt-balance", headers=shop_a.h(key=None)),
        await c.patch(
            f"{API}/counterparties/{b_cp['id']}", json={"version": 1, "name": "hack"}, headers=shop_a.h()
        ),
        await c.post(f"{API}/counterparties/{b_cp['id']}/archive", headers=shop_a.h()),
    ):
        assert response.status_code == 404 and err(response) == "NOT_FOUND"
        assert "Faqat B" not in response.text
    still = await c.get(f"{API}/counterparties/{b_cp['id']}", headers=shop_b.h(key=None))
    assert still.json()["name"] == "Faqat B ta'minotchi" and still.json()["archived_at"] is None


async def test_create_counterparty_idempotent_replay(env: Env) -> None:
    shop = await env.shop("Idempotent")
    key = str(uuid7())
    body = {"kind": "person", "name": "Takror", "phone": "+998931234567"}
    first = await env.client.post(f"{API}/counterparties", json=body, headers=shop.h(key=key))
    second = await env.client.post(f"{API}/counterparties", json=body, headers=shop.h(key=key))
    assert first.status_code == second.status_code == 201
    assert second.headers.get("idempotent-replayed") == "true"
    assert second.json() == first.json()
    reused = await env.client.post(
        f"{API}/counterparties", json={**body, "name": "Boshqa"}, headers=shop.h(key=key)
    )
    assert reused.status_code == 422 and err(reused) == "IDEMPOTENCY_KEY_REUSED"
    no_key = await env.client.post(f"{API}/counterparties", json=body, headers=shop.h(key=None))
    assert no_key.status_code == 422
    assert (await env.client.get(f"{API}/counterparties", headers=shop.h(key=None))).json()["total"] == 1
