"""Helpers for the counterparties / debt register / purchase-order tests (Bosqich 2).

Same real app + PostgreSQL/Redis setup as the catalog tests, with the fake e-invoice operator
(``ERP_EINVOICE_PROVIDER=fake``). ``post_receipt`` inserts receipt rows with SQL under RLS (the PO
status tests); goods receipts / supplier returns go through the API (``create_receipt``, ``post_gr``,
``create_return``, ``post_sr``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.debts.application.module import DebtsModule
from app.modules.integrations.einvoice.wiring import FakeEInvoiceAdapter
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings, create_product

API = "/api/v1"

__all__ = [
    "API",
    "GR",
    "SR",
    "Env",
    "Shop",
    "create_po",
    "create_product",
    "create_receipt",
    "create_return",
    "create_supplier",
    "err",
    "fake_einvoice",
    "gr_line",
    "post_gr",
    "post_receipt",
    "post_sr",
    "posted_receipt",
    "purchasing_env_fixture",
    "warehouse_of",
]


def err(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


def fake_einvoice(env: Env) -> FakeEInvoiceAdapter:
    debts = cast(DebtsModule, env.app.state.debts)
    assert isinstance(debts.einvoice, FakeEInvoiceAdapter)
    return debts.einvoice


async def warehouse_of(db: Database, shop: Shop, branch_id: UUID | None = None) -> UUID:
    async with db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        value: UUID = (
            await s.execute(
                text("SELECT id FROM app.warehouses WHERE branch_id = :b ORDER BY created_at LIMIT 1"),
                {"b": branch_id or shop.branch_id},
            )
        ).scalar_one()
    return value


async def create_supplier(
    client: httpx.AsyncClient,
    shop: Shop,
    name: str = '"Mega Trade" MChJ',
    *,
    role: str = "owner",
    **extra: Any,
) -> dict[str, Any]:
    body = {"kind": "company", "name": name, "stir": "301234567", "is_supplier": True, **extra}
    response = await client.post(f"{API}/counterparties", json=body, headers=shop.h(role))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def create_po(
    client: httpx.AsyncClient,
    shop: Shop,
    supplier_id: str,
    warehouse_id: UUID,
    lines: Sequence[dict[str, Any]],
    *,
    role: str = "owner",
    doc_date: str = "2026-10-16",
    **extra: Any,
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": str(warehouse_id),
            "doc_date": doc_date,
            "lines": list(lines),
            **extra,
        },
        headers=shop.h(role, branch=shop.branch_id),
    )
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def post_receipt(
    db: Database,
    shop: Shop,
    *,
    po_id: str | UUID | None,
    supplier_id: str | UUID,
    warehouse_id: UUID,
    lines: Sequence[tuple[str | UUID, str]],
    status: str = "posted",
) -> UUID:
    """A goods receipt (``status`` posted/draft/cancelled) with ``lines`` of (product_id, qty) — SQL under RLS."""
    receipt_id = uuid7()
    async with db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.goods_receipts (id, tenant_id, branch_id, doc_date, status, supplier_id, po_id, "
                "warehouse_id, created_by, posted_at) VALUES (:id, :t, :b, :d, :status, :sup, :po, :wh, :u, "
                "CASE WHEN :status = 'posted' THEN now() END)"
            ),
            {
                "id": receipt_id, "t": shop.tenant_id, "b": shop.branch_id, "d": date(2026, 10, 17),
                "status": status, "sup": UUID(str(supplier_id)), "po": None if po_id is None else UUID(str(po_id)),
                "wh": warehouse_id, "u": shop.user_ids["owner"],
            },
        )  # fmt: skip
        for n, (product_id, qty) in enumerate(lines, start=1):
            await s.execute(
                text(
                    "INSERT INTO app.receipt_lines (id, tenant_id, receipt_id, line_no, product_id, qty, cost, "
                    "vat_rate) VALUES (:id, :t, :r, :n, :p, CAST(:q AS numeric), 1000, 12)"
                ),
                {
                    "id": uuid7(),
                    "t": shop.tenant_id,
                    "r": receipt_id,
                    "n": n,
                    "p": UUID(str(product_id)),
                    "q": qty,
                },
            )
    return receipt_id


@pytest.fixture(name="env")
async def purchasing_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(migrated_db, redis_url, tmp_path / "files", einvoice_provider="fake")
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)


# --- goods receipts / supplier returns (19 §8, §12) -------------------------------------------------
GR = f"{API}/goods-receipts"
SR = f"{API}/supplier-returns"


def gr_line(
    product_id: str | UUID, qty: str, cost: str | None = None, vat_rate: str | None = "12.00", **extra: Any
) -> dict[str, Any]:
    line: dict[str, Any] = {"product_id": str(product_id), "qty": qty, **extra}
    if cost is not None:
        line["cost"] = cost
    if vat_rate is not None:
        line["vat_rate"] = vat_rate
    return line


async def create_receipt(
    client: httpx.AsyncClient,
    shop: Shop,
    supplier_id: str | None,
    warehouse_id: UUID,
    lines: Sequence[dict[str, Any]],
    *,
    role: str = "owner",
    doc_date: str | date | None = None,
    expect: int = 201,
    **extra: Any,
) -> dict[str, Any]:
    from app.modules.accounting.wiring import business_today

    body: dict[str, Any] = {
        "warehouse_id": str(warehouse_id),
        "doc_date": str(doc_date or business_today()),
        "lines": list(lines),
        **extra,
    }
    if supplier_id is not None:
        body["supplier_id"] = supplier_id
    response = await client.post(GR, json=body, headers=shop.h(role, branch=shop.branch_id))
    assert response.status_code == expect, response.text
    created: dict[str, Any] = response.json()
    return created


async def post_gr(
    client: httpx.AsyncClient, shop: Shop, receipt_id: str, *, role: str = "owner", key: str | None = "auto"
) -> httpx.Response:
    return await client.post(f"{GR}/{receipt_id}/post", headers=shop.h(role, branch=shop.branch_id, key=key))


async def posted_receipt(
    client: httpx.AsyncClient,
    shop: Shop,
    supplier_id: str,
    warehouse_id: UUID,
    lines: Sequence[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    draft = await create_receipt(client, shop, supplier_id, warehouse_id, lines, **extra)
    posted = await post_gr(client, shop, draft["id"])
    assert posted.status_code == 200, posted.text
    body: dict[str, Any] = posted.json()
    return body


async def create_return(
    client: httpx.AsyncClient,
    shop: Shop,
    receipt: dict[str, Any],
    picks: Sequence[tuple[int, str]],
    *,
    role: str = "owner",
    reason: str = "expired",
    doc_date: str | date | None = None,
    expect: int = 201,
) -> dict[str, Any]:
    """A supplier-return draft of ``(receipt line index, qty)`` picks (lot = the lot of that line)."""
    from app.modules.accounting.wiring import business_today

    lines = [
        {"receipt_line_id": receipt["lines"][i]["id"], "lot_id": receipt["lines"][i]["lot_id"], "qty": q}
        for i, q in picks
    ]
    response = await client.post(
        SR,
        json={"receipt_id": receipt["id"], "doc_date": str(doc_date or business_today()), "reason": reason,
              "lines": lines},
        headers=shop.h(role, branch=shop.branch_id),
    )  # fmt: skip
    assert response.status_code == expect, response.text
    body: dict[str, Any] = response.json()
    return body


async def post_sr(
    client: httpx.AsyncClient, shop: Shop, return_id: str, *, role: str = "owner", key: str | None = "auto"
) -> httpx.Response:
    return await client.post(f"{SR}/{return_id}/post", headers=shop.h(role, branch=shop.branch_id, key=key))
