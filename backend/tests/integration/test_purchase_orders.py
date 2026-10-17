"""Purchase orders (19 §10, US-M07-01, QT-M07-01, QT-M07-07) — real app + PostgreSQL/Redis."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.access.domain.permissions import SystemRole
from app.modules.purchasing.application.module import PurchasingModule
from tests.support.purchasing import (
    API,
    Env,
    Shop,
    create_po,
    create_product,
    create_supplier,
    err,
    post_receipt,
    purchasing_env_fixture,
    warehouse_of,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["purchasing_env_fixture"]


async def _setup(env: Env, name: str, *roles: SystemRole) -> tuple[Shop, dict[str, Any], UUID, list[str]]:
    shop = await env.shop(name, *(roles or (SystemRole.OWNER,)))
    supplier = await create_supplier(env.client, shop)
    warehouse = await warehouse_of(env.db, shop)
    products = [(await create_product(env.client, shop, f"Tovar {n}"))["id"] for n in range(2)]
    return shop, supplier, warehouse, products


def _module(env: Env) -> PurchasingModule:
    module: PurchasingModule = env.app.state.purchasing
    return module


async def _set_status(env: Env, shop: Shop, po_id: str, status: str) -> None:
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.purchase_orders SET status = :st WHERE id = :id"),
            {"st": status, "id": UUID(po_id)},
        )


async def test_qt_m07_01_purchase_order_draft_then_sent(env: Env) -> None:
    """US-M07-01: the Manager creates a purchase order (draft), then sends it (sent, Z-… number)."""
    shop, supplier, warehouse, (p1, p2) = await _setup(env, "Xaridnoma", SystemRole.OWNER, SystemRole.MANAGER)
    c = env.client
    created = await c.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse),
            "doc_date": "2026-10-16",
            "lines": [
                {"product_id": p1, "qty": "50.000", "price": "12000.0000"},
                {"product_id": p2, "qty": "2.500"},
            ],
            "comment": "Kam qolgan tovarlar",
        },
        headers=shop.h("manager", branch=shop.branch_id),
    )
    assert created.status_code == 201, created.text
    po = created.json()
    assert created.headers["location"].endswith(po["id"])
    assert po["status"] == "draft" and po["number"] is None and po["sent_at"] is None
    assert po["branch_id"] == str(shop.branch_id) and po["warehouse_id"] == str(warehouse)
    assert po["supplier"] == {"id": supplier["id"], "name": supplier["name"], "stir": "301234567"}
    assert po["created_by"] == str(shop.user_ids["manager"]) and po["created_by_name"]
    assert po["total"] == "600000.00" and po["line_count"] == 2
    assert [(ln["line_no"], ln["qty"], ln["price"], ln["amount"]) for ln in po["lines"]] == [
        (1, "50.000", "12000.0000", "600000.00"),
        (2, "2.500", None, None),
    ]
    assert po["lines"][0]["product_name"] == "Tovar 0"
    assert po["received_lines"] == [
        {"product_id": p1, "ordered_qty": "50.000", "received_qty": "0.000"},
        {"product_id": p2, "ordered_qty": "2.500", "received_qty": "0.000"},
    ]

    sent = await c.post(f"{API}/purchase-orders/{po['id']}/send", json={}, headers=shop.h("manager"))
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "sent" and body["number"] == "Z-01-2026-000001" and body["sent_at"]
    got = await c.get(f"{API}/purchase-orders/{po['id']}", headers=shop.h("manager", key=None))
    assert got.status_code == 200 and got.json() == body

    second = await create_po(c, shop, supplier["id"], warehouse, [{"product_id": p1, "qty": "1.000"}])
    sent2 = await c.post(f"{API}/purchase-orders/{second['id']}/send", headers=shop.h())
    assert sent2.json()["number"] == "Z-01-2026-000002"

    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        actions = (
            (
                await s.execute(
                    text(
                        "SELECT action FROM app.audit_log WHERE entity = 'purchase_orders' AND entity_id = :id "
                        "ORDER BY at, id"
                    ),
                    {"id": UUID(po["id"])},
                )
            )
            .scalars()
            .all()
        )
    assert actions == ["purchase_order.created", "purchase_order.sent"]


async def test_purchase_order_state_machine_negatives(env: Env) -> None:
    shop, supplier, warehouse, (p1, _) = await _setup(env, "Holatlar")
    c = env.client
    po = await create_po(c, shop, supplier["id"], warehouse, [{"product_id": p1, "qty": "5.000"}])
    url = f"{API}/purchase-orders/{po['id']}"

    assert (await c.post(f"{url}/send", headers=shop.h())).status_code == 200
    again = await c.post(f"{url}/send", headers=shop.h())
    assert again.status_code == 409 and err(again) == "DOC_INVALID_STATE"
    assert again.json()["error"]["params"] == {"expected_status": "draft", "actual_status": "sent"}

    # sent → editable; partially_received → not editable, but cancellable
    edited = await c.patch(url, json={"comment": "yangi"}, headers=shop.h())
    assert edited.status_code == 200 and edited.json()["comment"] == "yangi"
    await _set_status(env, shop, po["id"], "partially_received")
    partial = await c.patch(url, json={"comment": "x"}, headers=shop.h())
    assert partial.status_code == 409 and err(partial) == "DOC_INVALID_STATE"

    await _set_status(env, shop, po["id"], "closed")
    for response in (
        await c.patch(url, json={"comment": "x"}, headers=shop.h()),
        await c.post(f"{url}/cancel", json={"reason": "kerak emas"}, headers=shop.h()),
    ):
        assert response.status_code == 409 and err(response) == "PURCHASE_ORDER_CLOSED"
    closed_send = await c.post(f"{url}/send", headers=shop.h())
    assert closed_send.status_code == 409 and err(closed_send) == "DOC_INVALID_STATE"

    await _set_status(env, shop, po["id"], "partially_received")
    cancelled = await c.post(f"{url}/cancel", json={"reason": "Yetkazib beruvchi rad etdi"}, headers=shop.h())
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled" and body["cancel_reason"] == "Yetkazib beruvchi rad etdi"
    assert body["cancelled_at"] is not None
    twice = await c.post(f"{url}/cancel", json={"reason": "yana"}, headers=shop.h())
    assert twice.status_code == 409 and err(twice) == "DOC_INVALID_STATE"
    on_cancelled = await c.patch(url, json={"comment": "x"}, headers=shop.h())
    assert on_cancelled.status_code == 409 and err(on_cancelled) == "DOC_INVALID_STATE"
    no_reason = await c.post(f"{url}/cancel", json={}, headers=shop.h())
    assert no_reason.status_code == 422

    draft = await create_po(c, shop, supplier["id"], warehouse, [{"product_id": p1, "qty": "1.000"}])
    dropped = await c.post(
        f"{API}/purchase-orders/{draft['id']}/cancel", json={"reason": "xato"}, headers=shop.h()
    )
    assert dropped.status_code == 200 and dropped.json()["status"] == "cancelled"
    assert dropped.json()["number"] is None  # a cancelled draft never takes a number

    missing = await c.post(f"{API}/purchase-orders/{uuid7()}/send", headers=shop.h())
    assert missing.status_code == 404 and missing.json()["error"]["params"] == {"resource": "purchase_order"}


async def test_patch_replaces_lines_and_fields(env: Env) -> None:
    shop, supplier, warehouse, (p1, p2) = await _setup(env, "Tahrir")
    c = env.client
    po = await create_po(c, shop, supplier["id"], warehouse, [{"product_id": p1, "qty": "5.000"}])
    other = await create_supplier(c, shop, name="Boshqa MChJ", stir="301234599")
    patched = await c.patch(
        f"{API}/purchase-orders/{po['id']}",
        json={
            "supplier_id": other["id"],
            "doc_date": "2026-10-18",
            "lines": [
                {"product_id": p2, "qty": "3.000", "price": "100.5000"},
                {"product_id": p1, "qty": "1.000"},
            ],
        },
        headers=shop.h(branch=shop.branch_id),
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["supplier_id"] == other["id"] and body["doc_date"] == "2026-10-18"
    assert [(ln["line_no"], ln["product_id"], ln["qty"]) for ln in body["lines"]] == [
        (1, p2, "3.000"),
        (2, p1, "1.000"),
    ]
    assert body["total"] == "301.50" and body["status"] == "draft"
    for payload, field in (
        ({"lines": []}, "lines"),
        ({"supplier_id": None}, "supplier_id"),
        ({"lines": [{"product_id": p1, "qty": "0.000"}]}, "lines[0].qty"),
    ):
        bad = await c.patch(f"{API}/purchase-orders/{po['id']}", json=payload, headers=shop.h())
        assert bad.status_code == 422, payload
        assert any(d["field"] == field for d in bad.json()["error"]["details"]), bad.text


async def test_purchase_order_reference_validation(env: Env) -> None:
    shop, supplier, warehouse, (p1, p2) = await _setup(env, "Havolalar")
    c = env.client
    customer = (
        await c.post(
            f"{API}/counterparties",
            json={"kind": "person", "name": "Mijoz", "phone": "+998901234500"},
            headers=shop.h(),
        )
    ).json()
    archived = await create_supplier(c, shop, name="Arxiv MChJ", stir="301234511")
    await c.post(f"{API}/counterparties/{archived['id']}/archive", headers=shop.h())

    async def attempt(**override: Any) -> Any:
        body: dict[str, Any] = {
            "supplier_id": supplier["id"],
            "warehouse_id": str(warehouse),
            "doc_date": "2026-10-16",
            "lines": [{"product_id": p1, "qty": "1.000"}],
            **override,
        }
        return await c.post(f"{API}/purchase-orders", json=body, headers=shop.h(branch=shop.branch_id))

    not_supplier = await attempt(supplier_id=customer["id"])
    assert not_supplier.status_code == 422
    assert not_supplier.json()["error"]["details"] == [
        {"field": "supplier_id", "message_key": "validation.not_a_supplier"}
    ]
    gone = await attempt(supplier_id=archived["id"])
    assert gone.status_code == 409 and err(gone) == "RESOURCE_ARCHIVED"
    unknown = await attempt(supplier_id=str(uuid7()))
    assert unknown.status_code == 404 and unknown.json()["error"]["params"] == {"resource": "counterparty"}
    bad_wh = await attempt(warehouse_id=str(uuid7()))
    assert bad_wh.status_code == 422 and bad_wh.json()["error"]["details"][0]["field"] == "warehouse_id"
    for lines, field, key in (
        ([{"product_id": p1, "qty": "0.000"}], "lines[0].qty", "validation.positive"),
        ([{"product_id": p1, "qty": "1.000"}, {"product_id": p1, "qty": "2.000"}], "lines[1].product_id",
         "validation.duplicate"),
        ([{"product_id": str(uuid7()), "qty": "1.000"}], "lines[0].product_id", "validation.product_not_found"),
        ([{"product_id": p1, "qty": "1.000", "price": "-1.0000"}], "lines[0].price", "validation.min_value"),
    ):  # fmt: skip
        response = await attempt(lines=lines)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"] == [{"field": field, "message_key": key}]
    for body in ({"lines": []}, {"lines": [{"product_id": p1, "qty": "1"}]}):
        assert (await attempt(**body)).status_code == 422
    await c.post(f"{API}/products/{p2}/archive", headers=shop.h())
    archived_product = await attempt(lines=[{"product_id": p2, "qty": "1.000"}])
    assert archived_product.status_code == 409 and err(archived_product) == "RESOURCE_ARCHIVED"

    # a warehouse of another branch does not belong to X-Branch-Id
    other_branch = uuid7()
    other_wh = uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.branches (id, tenant_id, code, name, settlement_category, activity_type) "
                "VALUES (:id, :t, '02', 'Ikkinchi', 'other', 'retail')"
            ),
            {"id": other_branch, "t": shop.tenant_id},
        )
        await s.execute(
            text(
                "INSERT INTO app.warehouses (id, tenant_id, branch_id, name, type, inventory_account) "
                "VALUES (:id, :t, :b, 'Ombor 2', 'store', '2920')"
            ),
            {"id": other_wh, "t": shop.tenant_id, "b": other_branch},
        )
    mismatch = await attempt(warehouse_id=str(other_wh))
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["details"] == [
        {"field": "warehouse_id", "message_key": "validation.warehouse_not_in_branch"}
    ]
    no_header = await c.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "warehouse_id": str(other_wh),
            "doc_date": "2026-10-16",
            "lines": [{"product_id": p1, "qty": "1.000"}],
        },
        headers=shop.h(),
    )
    assert no_header.status_code == 201 and no_header.json()["branch_id"] == str(other_branch)
    sent = await c.post(f"{API}/purchase-orders/{no_header.json()['id']}/send", headers=shop.h())
    assert sent.json()["number"] == "Z-02-2026-000001"


async def test_received_lines_and_status_refresh(env: Env) -> None:
    """19 §10: ``received_lines`` from POSTED receipts by ``po_id``; the stored status follows receipts."""
    shop, supplier, warehouse, (p1, p2) = await _setup(env, "Qabul")
    c = env.client
    po = await create_po(
        c,
        shop,
        supplier["id"],
        warehouse,
        [{"product_id": p1, "qty": "50.000"}, {"product_id": p2, "qty": "10.000"}],
    )
    await c.post(f"{API}/purchase-orders/{po['id']}/send", headers=shop.h())
    links = _module(env).po_receipts

    async def refresh() -> str:
        async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
            return await links.refresh_status(s, UUID(po["id"]))

    async def received() -> list[tuple[str, str, str]]:
        got = await c.get(f"{API}/purchase-orders/{po['id']}", headers=shop.h(key=None))
        return [(r["product_id"], r["ordered_qty"], r["received_qty"]) for r in got.json()["received_lines"]]

    common = {"po_id": po["id"], "supplier_id": supplier["id"], "warehouse_id": warehouse}
    await post_receipt(env.db, shop, lines=[(p1, "48.000")], **common)
    await post_receipt(env.db, shop, lines=[(p1, "2.000"), (p2, "10.000")], status="draft", **common)
    await post_receipt(
        env.db, shop, po_id=None, supplier_id=supplier["id"], warehouse_id=warehouse, lines=[(p2, "9.000")]
    )
    assert await refresh() == "partially_received"
    assert await received() == [(p1, "50.000", "48.000"), (p2, "10.000", "0.000")]

    second = await post_receipt(env.db, shop, lines=[(p1, "2.000"), (p2, "10.000")], **common)
    assert await refresh() == "closed"
    assert (await c.get(f"{API}/purchase-orders/{po['id']}", headers=shop.h(key=None))).json()[
        "status"
    ] == "closed"
    assert await received() == [(p1, "50.000", "50.000"), (p2, "10.000", "10.000")]

    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.goods_receipts SET status = 'cancelled' WHERE id = :id"), {"id": second}
        )
    assert await refresh() == "partially_received"  # a cancelled receipt reopens the order

    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("UPDATE app.goods_receipts SET status = 'cancelled' WHERE po_id = :id"),
            {"id": UUID(po["id"])},
        )
    assert await refresh() == "sent"

    # draft and cancelled orders are never moved by receipts
    draft = await create_po(c, shop, supplier["id"], warehouse, [{"product_id": p1, "qty": "1.000"}])
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        assert await links.refresh_status(s, UUID(draft["id"])) == "draft"


async def test_qt_m07_07_receipt_against_cancelled_po_is_closed(env: Env) -> None:
    """QT-M07-07 (PO side): only ``sent``/``partially_received`` orders accept goods receipts."""
    shop, supplier, warehouse, (p1, p2) = await _setup(env, "Yopiq PO")
    c = env.client
    po = await create_po(
        c,
        shop,
        supplier["id"],
        warehouse,
        [{"product_id": p1, "qty": "5.000", "price": "10.0000"}, {"product_id": p2, "qty": "1.000"}],
    )
    links = _module(env).po_receipts

    async def check() -> Any:
        async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
            return await links.assert_open_for_receipt(s, UUID(po["id"]), lock=True)

    with pytest.raises(AppError) as draft_exc:
        await check()
    assert (
        draft_exc.value.code == "PURCHASE_ORDER_CLOSED" and draft_exc.value.params["actual_status"] == "draft"
    )

    await c.post(f"{API}/purchase-orders/{po['id']}/send", headers=shop.h())
    opened = await check()
    assert opened.status == "sent"
    assert [(str(ln.product_id), str(ln.qty), ln.price) for ln in opened.lines] == [
        (p1, "5.000", opened.lines[0].price),
        (p2, "1.000", None),
    ]
    assert str(opened.lines[0].price) == "10.0000"

    await c.post(f"{API}/purchase-orders/{po['id']}/cancel", json={"reason": "bekor"}, headers=shop.h())
    with pytest.raises(AppError) as exc:
        await check()
    assert exc.value.code == "PURCHASE_ORDER_CLOSED" and exc.value.status_code == 409
    assert exc.value.params["actual_status"] == "cancelled"

    with pytest.raises(AppError) as missing:
        async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
            await links.assert_open_for_receipt(s, uuid7())
    assert missing.value.code == "NOT_FOUND"


async def test_list_filters_and_cursor(env: Env) -> None:
    shop, supplier, warehouse, (p1, _) = await _setup(env, "Ro'yxat")
    c = env.client
    other = await create_supplier(c, shop, name="Ikkinchi MChJ", stir="301234598")
    ids = []
    for n, (sup, day) in enumerate(
        ((supplier["id"], "2026-10-01"), (other["id"], "2026-10-10"), (supplier["id"], "2026-10-20"))
    ):
        po = await create_po(
            c, shop, sup, warehouse, [{"product_id": p1, "qty": f"{n + 1}.000"}], doc_date=day
        )
        ids.append(po["id"])
    await c.post(f"{API}/purchase-orders/{ids[0]}/send", headers=shop.h())

    async def listing(**params: Any) -> dict[str, Any]:
        response = await c.get(f"{API}/purchase-orders", params=params, headers=shop.h(key=None))
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    everything = await listing()
    assert [i["id"] for i in everything["items"]] == ids[::-1] and everything["next_cursor"] is None
    assert "lines" not in everything["items"][0] and everything["items"][0]["line_count"] == 1
    first = await listing(limit=2)
    assert [i["id"] for i in first["items"]] == [ids[2], ids[1]] and first["next_cursor"]
    rest = await listing(limit=2, cursor=first["next_cursor"])
    assert [i["id"] for i in rest["items"]] == [ids[0]] and rest["next_cursor"] is None
    assert [i["id"] for i in (await listing(status="sent"))["items"]] == [ids[0]]
    assert [i["id"] for i in (await listing(supplier_id=other["id"]))["items"]] == [ids[1]]
    window = await listing(**{"from": "2026-10-05", "to": "2026-10-15"})
    assert [i["id"] for i in window["items"]] == [ids[1]]
    assert [i["id"] for i in (await listing(search="Z-01"))["items"]] == [ids[0]]
    assert [i["id"] for i in (await listing(search="ikkinchi"))["items"]] == [ids[1]]
    bad = await c.get(f"{API}/purchase-orders", params={"cursor": "%%%"}, headers=shop.h(key=None))
    assert bad.status_code == 422


async def test_purchase_order_permissions(env: Env) -> None:
    shop, supplier, warehouse, (p1, _) = await _setup(
        env, "PO ruxsat", SystemRole.OWNER, SystemRole.CASHIER, SystemRole.ACCOUNTANT, SystemRole.STOREKEEPER
    )
    c = env.client
    body = {
        "supplier_id": supplier["id"],
        "warehouse_id": str(warehouse),
        "doc_date": "2026-10-16",
        "lines": [{"product_id": p1, "qty": "1.000"}],
    }
    for role in ("cashier", "accountant"):
        denied = await c.post(f"{API}/purchase-orders", json=body, headers=shop.h(role))
        assert denied.status_code == 403 and err(denied) == "PERMISSION_DENIED", role
    po = await c.post(f"{API}/purchase-orders", json=body, headers=shop.h("storekeeper"))
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    for role in ("cashier", "accountant"):
        for response in (
            await c.post(f"{API}/purchase-orders/{po_id}/send", headers=shop.h(role)),
            await c.patch(f"{API}/purchase-orders/{po_id}", json={"comment": "x"}, headers=shop.h(role)),
            await c.post(f"{API}/purchase-orders/{po_id}/cancel", json={"reason": "x"}, headers=shop.h(role)),
        ):
            assert response.status_code == 403, role
        # reads need stock.view (Kassir and Buxgalter have it)
        assert (
            await c.get(f"{API}/purchase-orders/{po_id}", headers=shop.h(role, key=None))
        ).status_code == 200
        assert (await c.get(f"{API}/purchase-orders", headers=shop.h(role, key=None))).status_code == 200


async def test_purchase_orders_are_tenant_isolated(env: Env) -> None:
    shop_a, _, _, _ = await _setup(env, "PO tenant A")
    shop_b, supplier_b, warehouse_b, (pb, _) = await _setup(env, "PO tenant B")
    c = env.client
    po_b = await create_po(c, shop_b, supplier_b["id"], warehouse_b, [{"product_id": pb, "qty": "1.000"}])
    url = f"{API}/purchase-orders/{po_b['id']}"
    for response in (
        await c.get(url, headers=shop_a.h(key=None)),
        await c.patch(url, json={"comment": "hack"}, headers=shop_a.h()),
        await c.post(f"{url}/send", headers=shop_a.h()),
        await c.post(f"{url}/cancel", json={"reason": "hack"}, headers=shop_a.h()),
    ):
        assert response.status_code == 404 and err(response) == "NOT_FOUND"
    assert (await c.get(f"{API}/purchase-orders", headers=shop_a.h(key=None))).json()["items"] == []
    # tenant B's supplier/warehouse/product ids are invisible to tenant A
    cross = await c.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier_b["id"],
            "warehouse_id": str(warehouse_b),
            "doc_date": "2026-10-16",
            "lines": [{"product_id": pb, "qty": "1.000"}],
        },
        headers=shop_a.h(),
    )
    assert cross.status_code == 404 and cross.json()["error"]["params"] == {"resource": "counterparty"}
    untouched = (await c.get(url, headers=shop_b.h(key=None))).json()
    assert untouched["status"] == "draft" and untouched["comment"] is None


async def test_purchase_order_idempotent_replays(env: Env) -> None:
    shop, supplier, warehouse, (p1, _) = await _setup(env, "PO takror")
    c = env.client
    key = str(uuid7())
    body = {
        "supplier_id": supplier["id"],
        "warehouse_id": str(warehouse),
        "doc_date": "2026-10-16",
        "lines": [{"product_id": p1, "qty": "1.000"}],
    }
    first = await c.post(f"{API}/purchase-orders", json=body, headers=shop.h(key=key))
    replay = await c.post(f"{API}/purchase-orders", json=body, headers=shop.h(key=key))
    assert first.status_code == replay.status_code == 201
    assert replay.headers.get("idempotent-replayed") == "true" and replay.json() == first.json()
    po_id = first.json()["id"]
    send_key = str(uuid7())
    sent = await c.post(f"{API}/purchase-orders/{po_id}/send", headers=shop.h(key=send_key))
    sent_again = await c.post(f"{API}/purchase-orders/{po_id}/send", headers=shop.h(key=send_key))
    assert sent.status_code == sent_again.status_code == 200
    assert sent_again.json() == sent.json() and sent_again.headers.get("idempotent-replayed") == "true"
    assert (await c.get(f"{API}/purchase-orders", headers=shop.h(key=None))).json()["items"][0]["number"] == (
        "Z-01-2026-000001"
    )
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        count = (await s.execute(text("SELECT count(*) FROM app.purchase_orders"))).scalar_one()
    assert count == 1
