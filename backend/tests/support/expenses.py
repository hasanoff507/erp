"""Helpers for the expenses tests (Bosqich 4, b4-expenses slice).

Real app + PostgreSQL/Redis (the cash test setup: :func:`tests.support.cash.cash_env_fixture`). POS
``expense.created`` events are delivered by calling the expenses sync handler exactly as ``/sync/push``
does — one tenant transaction per event (:func:`push_expense`).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.accounting.wiring import business_today
from app.modules.expenses.wiring import sync_handlers
from app.modules.sync.application.handlers import EventContext
from tests.support.cash import Pushed, Till, one, sql
from tests.support.catalog import Env
from tests.support.ordering import TXN_ORDER

API = "/api/v1"


async def category_id(env: Env, tenant_id: UUID, code: str) -> UUID:
    value = await one(env.db, tenant_id, "SELECT id FROM app.expense_categories WHERE code = :c", c=code)
    assert value is not None, code
    return UUID(str(value))


def expense_body(category: UUID, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "doc_date": business_today().isoformat(),
        "category_id": str(category),
        "amount": "500000.00",
        "source": "bank",
    }
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


def pos_payload(till: Till, shift_id: UUID, category: UUID, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(uuid7()),
        "doc_date": business_today().isoformat(),
        "branch_id": str(till.shop.branch_id),
        "cash_register_id": str(till.register_id),
        "shift_id": str(shift_id),
        "category_id": str(category),
        "amount": "40000.00",
        "comment": "Suv",
    }
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


async def push_expense(
    env: Env,
    till: Till,
    payload: Mapping[str, Any],
    *,
    actor: str = "cashier",
    created_at: datetime | None = None,
    received_at: datetime | None = None,
    actor_bound: Any = None,
) -> Pushed:
    """Deliver one ``expense.created`` the way ``/sync/push`` does (one transaction, rollback on error)."""
    handler = sync_handlers(env.settings, env.db)["expense.created"]
    now = datetime.now(UTC)
    ctx = EventContext(
        tenant_id=till.shop.tenant_id,
        device_id=till.device_id,
        branch_id=till.shop.branch_id,
        cash_register_id=till.register_id,
        client_event_id=uuid7(),
        seq=1,
        event_type="expense.created",
        created_at=created_at or now,
        received_at=received_at or now,
        actor_user_id=till.shop.user_ids[actor],
        session_user_id=till.shop.user_ids[actor],
        actor_bound=actor_bound,
    )
    out = Pushed()
    try:
        async with (
            env.db.session_factory() as s,
            tenant_transaction(s, ctx.tenant_id, user_id=ctx.actor_user_id),
        ):
            out.result = await handler(s, ctx, payload)
    except AppError as exc:
        out.error = exc
    return out


async def cash_moves(env: Env, tenant_id: UUID, doc_id: UUID) -> list[tuple[str, str, str]]:
    rows = await sql(
        env.db, tenant_id,
        "SELECT amount, method, doc_type FROM app.cash_moves WHERE doc_id = :d "
        f"ORDER BY {TXN_ORDER}, id", d=doc_id,
    )  # fmt: skip
    return [(format(r[0], "f"), r[1], r[2]) for r in rows]


async def ledger_lines(env: Env, tenant_id: UUID, doc_id: UUID) -> list[tuple[str, str, str, bool]]:
    """``(Dt, Kt, amount, is_reversal)`` of ``doc_type='expenses'`` in write order."""
    rows = await sql(
        env.db, tenant_id,
        "SELECT account_dt, account_kt, amount, reversal_of_id IS NOT NULL FROM app.ledger_entries "
        f"WHERE doc_type = 'expenses' AND doc_id = :d ORDER BY {TXN_ORDER}, id", d=doc_id,
    )  # fmt: skip
    return [(r[0], r[1], format(r[2], "f"), bool(r[3])) for r in rows]
