"""Helpers for the supplier-payment and tax-settlement tests (Bosqich 4: 19 §11, 20 #8a–#8d).

Same real app + PostgreSQL/Redis as the purchasing tests (``purchasing_env_fixture``); receipts go through
the API, registers are asserted with SQL under RLS.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.core.db.base import uuid7
from app.modules.accounting.wiring import business_today
from tests.support.inventory import execute, rows, scalar
from tests.support.ordering import TXN_ORDER
from tests.support.purchasing import API, Env, Shop

SP = f"{API}/supplier-payments"
TS = f"{API}/tax-settlements"
D = Decimal


async def pay(
    client: httpx.AsyncClient,
    shop: Shop,
    supplier_id: str,
    amount: str,
    *,
    method: str = "bank",
    role: str = "owner",
    key: str | None = "auto",
    branch: UUID | None = None,
    **extra: Any,
) -> httpx.Response:
    body: dict[str, Any] = {
        "supplier_id": supplier_id,
        "amount": amount,
        "method": method,
        "doc_date": str(business_today()),
        **extra,
    }
    return await client.post(SP, json=body, headers=shop.h(role, branch=branch or shop.branch_id, key=key))


async def ledger_of(env: Env, shop: Shop, doc_id: str | UUID) -> list[tuple[str, str, Decimal]]:
    found = await rows(
        env, shop.tenant_id,
        f"SELECT account_dt, account_kt, amount FROM app.ledger_entries WHERE doc_id = :d ORDER BY {TXN_ORDER}, id",
        d=UUID(str(doc_id)),
    )  # fmt: skip
    return [(r["account_dt"], r["account_kt"], r["amount"]) for r in found]


async def debt_of(env: Env, shop: Shop, doc_id: str | UUID) -> list[Decimal]:
    found = await rows(
        env, shop.tenant_id,
        f"SELECT amount FROM app.debt_moves WHERE doc_id = :d ORDER BY {TXN_ORDER}, id",
        d=UUID(str(doc_id)),
    )  # fmt: skip
    return [r["amount"] for r in found]


async def vat_of(env: Env, shop: Shop, doc_id: str | UUID) -> list[tuple[str, Decimal, Decimal]]:
    found = await rows(
        env, shop.tenant_id,
        f"SELECT kind, base_amount, vat_amount FROM app.vat_moves WHERE doc_id = :d ORDER BY {TXN_ORDER}, id",
        d=UUID(str(doc_id)),
    )  # fmt: skip
    return [(r["kind"], r["base_amount"], r["vat_amount"]) for r in found]


async def cash_of(env: Env, shop: Shop, doc_id: str | UUID) -> list[tuple[Decimal, str, Any]]:
    found = await rows(
        env, shop.tenant_id,
        f"SELECT amount, method, shift_id FROM app.cash_moves WHERE doc_id = :d ORDER BY {TXN_ORDER}, id",
        d=UUID(str(doc_id)),
    )  # fmt: skip
    return [(r["amount"], r["method"], r["shift_id"]) for r in found]


async def payable(env: Env, shop: Shop, supplier_id: str) -> Decimal:
    value = await scalar(
        env, shop.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'payable'",
        c=UUID(supplier_id),
    )  # fmt: skip
    return value if value is not None else D("0.00")


async def account_balance(env: Env, shop: Shop, account: str, **analytics: str) -> Decimal:
    """Debit-minus-credit balance of ``account`` (optionally filtered by analytics containment)."""
    import json

    value = await scalar(
        env, shop.tenant_id,
        "SELECT COALESCE(sum(CASE WHEN account_dt = :a THEN amount ELSE -amount END), 0) FROM app.ledger_entries "
        "WHERE (account_dt = :a OR account_kt = :a) AND analytics @> CAST(:an AS jsonb)",
        a=account, an=json.dumps(analytics),
    )  # fmt: skip
    return D(value)


async def link_einvoice(
    env: Env, shop: Shop, receipt_id: str, supplier_id: str, risk_flag: str, *, total: str, vat: str
) -> UUID:
    """An accepted incoming e-invoice with ``risk_flag`` linked to the draft receipt (from-einvoice is B5)."""
    einvoice_id = uuid7()
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.einvoices (id, tenant_id, direction, operator, counterparty_id, status, risk_flag, "
        "total_amount, vat_amount) VALUES (:id, :t, 'in', 'faktura', :c, 'accepted', :r, CAST(:tot AS numeric), "
        "CAST(:vat AS numeric))",
        id=einvoice_id, t=shop.tenant_id, c=UUID(supplier_id), r=risk_flag, tot=total, vat=vat,
    )  # fmt: skip
    await execute(
        env, shop.tenant_id, "UPDATE app.goods_receipts SET einvoice_id = :e WHERE id = :id",
        e=einvoice_id, id=UUID(receipt_id),
    )  # fmt: skip
    return einvoice_id


async def add_vat_move(env: Env, shop: Shop, kind: str, base: str, vat: str, period: Any) -> None:
    """A ``vat_moves`` row of a synthetic document (tax-settlement figures)."""
    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.vat_moves (tenant_id, period, kind, base_amount, vat_amount, doc_type, doc_id) "
        "VALUES (:t, :p, :k, CAST(:b AS numeric), CAST(:v AS numeric), 'sales', :d)",
        t=shop.tenant_id, p=period, k=kind, b=base, v=vat, d=uuid7(),
    )  # fmt: skip


async def add_ledger(
    env: Env,
    shop: Shop,
    dt: str,
    kt: str,
    amount: str,
    day: Any,
    branch_id: UUID | None = None,
    **analytics: str,
) -> None:
    """A ``ledger_entries`` row of a synthetic document (period turnovers for the settlements)."""
    import json

    await execute(
        env, shop.tenant_id,
        "INSERT INTO app.ledger_entries (tenant_id, entry_date, branch_id, account_dt, account_kt, amount, doc_type, "
        "doc_id, analytics) VALUES (:t, :d, :b, :dt, :kt, CAST(:a AS numeric), 'sales', :doc, CAST(:an AS jsonb))",
        t=shop.tenant_id, d=day, b=branch_id or shop.branch_id, dt=dt, kt=kt, a=amount, doc=uuid7(),
        an=json.dumps(analytics),
    )  # fmt: skip
