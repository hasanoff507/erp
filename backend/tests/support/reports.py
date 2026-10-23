"""Helpers for the M12 report tests (Bosqich 4, b4-reports slice).

Sales/returns go through the real B3 sync handlers (``tests.support.sales``); a second branch gets its own
register, device, open shift and ``store`` warehouse. Documents of slices built in parallel (expenses, debt
payments) are minimal SQL fixtures written exactly as their posting rules (13 §2.14, §2.17) put them into the
registers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.core.db.base import uuid7
from app.modules.accounting.wiring import business_today
from tests.support.catalog import Shop
from tests.support.inventory import add_branch, receive
from tests.support.sales import (
    D,
    Env,
    Pos,
    execute,
    open_shift_sql,
    sale_line,
    sale_payload,
    sell,
)

API = "/api/v1"


def doc_day() -> date:
    """The business day (Asia/Tashkent) every fixture of these tests is dated with."""
    return business_today()


async def get(env: Env, shop: Shop, path: str, role: str = "owner", **params: Any) -> httpx.Response:
    clean = {k: str(v) for k, v in params.items() if v is not None}
    return await env.client.get(f"{API}{path}", params=clean, headers=shop.h(role, key=None))


async def ok(env: Env, shop: Shop, path: str, role: str = "owner", **params: Any) -> dict[str, Any]:
    response = await get(env, shop, path, role, **params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def second_pos(env: Env, pos: Pos, code: str = "02", name: str = "Chilonzor") -> Pos:
    """Branch ``code`` of the same tenant with register ``K2``, a device, an open shift and a 2920 warehouse."""
    branch_id, warehouse = await add_branch(env, pos.shop, code, name)
    register_id, device_id, other = uuid7(), uuid7(), uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind, fm_state) "
        "VALUES (:id, :t, :b, 'K2', 'web', 'ok')",
        id=register_id, t=pos.tenant_id, b=branch_id,
    )  # fmt: skip
    for dev in (device_id, other):
        await execute(
            env.db, pos.tenant_id,
            "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind) VALUES (:id, :t, :c, 'web')",
            id=dev, t=pos.tenant_id, c=register_id,
        )  # fmt: skip
    shop = Shop(pos.tenant_id, branch_id, pos.shop.tokens, pos.shop.user_ids)
    shift = await open_shift_sql(env.db, shop, register_id, device_id, shop.user_ids["cashier"])
    return Pos(shop, register_id, device_id, other, warehouse, shift)


async def stock_in(env: Env, pos: Pos, product: UUID, qty: str = "10.000", cost: str = "8000.00") -> None:
    await receive(env, pos.shop, pos.warehouse_id, product, qty, format(D(qty) * D(cost), ".2f"))


async def sell_lines(
    env: Env,
    pos: Pos,
    lines: list[dict[str, Any]],
    payments: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> str:
    extra.setdefault("doc_date", doc_day().isoformat())
    payload = sale_payload(pos, lines, payments, **extra)
    await sell(env, pos, payload, actor="owner")
    return str(payload["id"])


async def sell_one(
    env: Env, pos: Pos, product: UUID, *, qty: str = "1.000", price: str = "12000.0000", **line: Any
) -> str:
    return await sell_lines(env, pos, [sale_line(product, qty=qty, price=price, **line)])


async def post_expense(
    env: Env,
    pos: Pos,
    amount: str,
    *,
    account: str = "9410",
    category: str = "Ijara",
    day: date | None = None,
) -> UUID:
    """A posted cash expense as 13 §2.17 writes it: ``expenses`` row + ``Dt <account> / Kt 5010``."""
    category_id, expense_id = uuid7(), uuid7()
    when = day or business_today()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.expense_categories (id, tenant_id, name, default_account) VALUES (:id, :t, :n, :a)",
        id=category_id, t=pos.tenant_id, n=f"{category} {category_id.hex[-6:]}", a=account,
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.expenses (id, tenant_id, branch_id, number, doc_date, status, category_id, amount, source, "
        "cash_register_id, shift_id, created_by, posted_at) VALUES (:id, :t, :b, :n, :d, 'posted', :c, "
        "CAST(:amt AS numeric), 'cash', :r, :s, :u, now())",
        id=expense_id, t=pos.tenant_id, b=pos.branch_id, n=f"X-{expense_id.hex[-6:]}", d=when, c=category_id,
        amt=amount, r=pos.register_id, s=pos.shift_id, u=pos.shop.user_ids["owner"],
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.ledger_entries (tenant_id, entry_date, branch_id, account_dt, account_kt, amount, doc_type, "
        "doc_id, analytics) VALUES (:t, :d, :b, :a, '5010', CAST(:amt AS numeric), 'expenses', :x, "
        "jsonb_build_object('expense_category_id', CAST(:c AS text), 'cash_register_id', CAST(:r AS text)))",
        t=pos.tenant_id, d=when, b=pos.branch_id, a=account, amt=amount, x=expense_id, c=str(category_id),
        r=str(pos.register_id),
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.cash_moves (tenant_id, cash_register_id, shift_id, amount, method, doc_type, doc_id) "
        "VALUES (:t, :r, :s, -CAST(:amt AS numeric), 'cash', 'expenses', :x)",
        t=pos.tenant_id, r=pos.register_id, s=pos.shift_id, amt=amount, x=expense_id,
    )  # fmt: skip
    return category_id


async def post_debt_payment(env: Env, pos: Pos, customer: UUID, sale_id: str, amount: str) -> UUID:
    """A posted bank debt payment as 13 §2.14 writes the registers: allocation to ``sale_id`` + ``debt_moves −``
    + ``debt_balances``."""
    payment_id = uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.debt_payments (id, tenant_id, branch_id, number, doc_date, status, counterparty_id, method, "
        "amount, created_by, posted_at) VALUES (:id, :t, :b, :n, :d, 'posted', :c, 'bank', CAST(:a AS numeric), :u, "
        "now())",
        id=payment_id, t=pos.tenant_id, b=pos.branch_id, n=f"Q-{payment_id.hex[-6:]}", d=business_today(),
        c=customer, a=amount, u=pos.shop.user_ids["owner"],
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.debt_payment_allocations (tenant_id, debt_payment_id, target_doc_type, target_doc_id, amount) "
        "VALUES (:t, :p, 'sales', CAST(:s AS uuid), CAST(:a AS numeric))",
        t=pos.tenant_id, p=payment_id, s=sale_id, a=amount,
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.debt_moves (tenant_id, counterparty_id, direction, amount, doc_type, doc_id) "
        "VALUES (:t, :c, 'receivable', -CAST(:a AS numeric), 'debt_payments', :p)",
        t=pos.tenant_id, c=customer, a=amount, p=payment_id,
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.debt_balances SET balance = balance - CAST(:a AS numeric) "
        "WHERE counterparty_id = :c AND direction = 'receivable'",
        a=amount, c=customer,
    )  # fmt: skip
    return payment_id


async def mark_unsynced(env: Env, pos: Pos, pending: int = 3) -> None:
    """The register's first device reported ``pending`` unsent outbox events in its last push (16 §3.1)."""
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.devices SET outbox_pending_count = :n, outbox_oldest_pending_at = now() - interval '2 hours', "
        "outbox_reported_at = now() WHERE id = :d",
        n=pending, d=pos.device_id,
    )  # fmt: skip


def money(value: Any) -> Decimal:
    return Decimal(str(value))
