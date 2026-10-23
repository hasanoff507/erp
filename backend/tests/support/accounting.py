"""Helpers for the B5 accounting tests (ledger adjustments, period closings, M11 statements, M10 register).

Real app + PostgreSQL/Redis (the sales setup: fake FM, so POS events can be delivered too). Every
date-sensitive test owns its tenant and derives its months from :func:`months_ago` — never "the current month"
of another test (COMMON test hygiene §3).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import business_today
from tests.support.auth import new_phone
from tests.support.catalog import Env, Shop
from tests.support.sales import execute, one, rows, sales_env_fixture

API = "/api/v1"
ADJ = f"{API}/ledger-adjustments"
PC = f"{API}/period-closings"
D = Decimal
ROLES = (SystemRole.OWNER, SystemRole.ACCOUNTANT, SystemRole.CASHIER, SystemRole.MANAGER)

__all__ = ["Env", "Shop", "sales_env_fixture"]


def months_ago(n: int, today: date | None = None) -> date:
    """First day of the month ``n`` months before the current Tashkent month."""
    first = (today or business_today()).replace(day=1)
    for _ in range(n):
        first = (first - timedelta(days=1)).replace(day=1)
    return first


def month_end(first: date) -> date:
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return nxt - timedelta(days=1)


def label(first: date) -> str:
    return f"{first.year:04d}-{first.month:02d}"


def err(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


def keys(response: httpx.Response) -> list[str]:
    return [d["message_key"] for d in response.json()["error"]["details"]]


async def shop(env: Env, name: str = "Buxgalteriya do'koni") -> Shop:
    return await env.shop(name, *ROLES)


async def set_go_live(env: Env, s: Shop, day: date) -> None:
    await execute(env.db, s.tenant_id, "UPDATE app.tenants SET go_live_date = :d", d=day)


async def customer(env: Env, s: Shop, name: str = "Aliyev Vali") -> UUID:
    cid = uuid7()
    await execute(
        env.db, s.tenant_id,
        "INSERT INTO app.counterparties (id, tenant_id, kind, name, phone, is_customer) "
        "VALUES (:id, :t, 'person', :n, :p, true)",
        id=cid, t=s.tenant_id, n=name, p=new_phone(),
    )  # fmt: skip
    return cid


async def adjust(
    env: Env,
    s: Shop,
    dt: str,
    kt: str,
    amount: str,
    *,
    day: date | None = None,
    role: str = "accountant",
    comment: str = "Tuzatish",
    **extra: Any,
) -> httpx.Response:
    body: dict[str, Any] = {
        "branch_id": str(s.branch_id),
        "doc_date": (day or business_today()).isoformat(),
        "account_dt": dt,
        "account_kt": kt,
        "amount": amount,
        "comment": comment,
        **extra,
    }
    return await env.client.post(ADJ, json=body, headers=s.h(role))


async def adjust_ok(env: Env, s: Shop, dt: str, kt: str, amount: str, **kw: Any) -> dict[str, Any]:
    response = await adjust(env, s, dt, kt, amount, **kw)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def add_ledger(
    env: Env, s: Shop, dt: str, kt: str, amount: str, day: date, doc_type: str = "sales", **analytics: str
) -> None:
    """A ``ledger_entries`` row of a synthetic document."""
    await execute(
        env.db, s.tenant_id,
        "INSERT INTO app.ledger_entries (tenant_id, entry_date, branch_id, account_dt, account_kt, amount, "
        "doc_type, doc_id, analytics) VALUES (:t, :d, :b, :dt, :kt, CAST(:a AS numeric), :dtp, :doc, "
        "CAST(:an AS jsonb))",
        t=s.tenant_id, d=day, b=s.branch_id, dt=dt, kt=kt, a=amount, dtp=doc_type, doc=uuid7(),
        an=json.dumps(analytics),
    )  # fmt: skip


async def ledger_of(env: Env, s: Shop, doc_id: str | UUID) -> list[dict[str, Any]]:
    return await rows(
        env.db, s.tenant_id,
        "SELECT entry_date, account_dt, account_kt, amount, analytics, reversal_of_id FROM app.ledger_entries "
        "WHERE doc_id = :d ORDER BY (reversal_of_id IS NOT NULL), id",
        d=UUID(str(doc_id)),
    )  # fmt: skip


async def balance(env: Env, s: Shop, account: str, **analytics: str) -> Decimal:
    value = await one(
        env.db, s.tenant_id,
        "SELECT COALESCE(sum(CASE WHEN account_dt = :a THEN amount ELSE -amount END), 0) FROM app.ledger_entries "
        "WHERE (account_dt = :a OR account_kt = :a) AND analytics @> CAST(:an AS jsonb)",
        a=account, an=json.dumps(analytics),
    )  # fmt: skip
    return D(value)


async def receivable(env: Env, s: Shop, cid: UUID) -> Decimal:
    value = await one(
        env.db, s.tenant_id,
        "SELECT balance FROM app.debt_balances WHERE counterparty_id = :c AND direction = 'receivable'", c=cid,
    )  # fmt: skip
    return D(value) if value is not None else D("0.00")


async def close_sql(env: Env, s: Shop, period: date) -> None:
    """A month closed directly (the precondition of tests that are not about closing itself)."""
    await execute(
        env.db, s.tenant_id,
        "INSERT INTO app.period_closings (tenant_id, period, closed_by) VALUES (:t, :p, :u)",
        t=s.tenant_id, p=period.replace(day=1), u=s.user_ids["owner"],
    )  # fmt: skip


async def readiness(env: Env, s: Shop, period: date) -> dict[str, Any]:
    response = await env.client.get(f"{PC}/{label(period)}/readiness", headers=s.h("accountant", key=None))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def close(env: Env, s: Shop, period: date, role: str = "owner") -> httpx.Response:
    return await env.client.post(PC, json={"period": label(period)}, headers=s.h(role))
