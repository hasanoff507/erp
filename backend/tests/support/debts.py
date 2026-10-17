"""Helpers for the debt-book tests (Bosqich 4, b4-debts slice — 18 §11.1, §12; 13 §2.13–§2.15a).

Builds on the sales helpers (real app + PostgreSQL/Redis, ``ERP_FISCAL_PROVIDER=fake``): a POS with an open
shift sells on debt through the real ``sale.created`` handler; debt-book POS events go through the debts sync
handlers exactly as ``/sync/push`` delivers them (one tenant transaction per event; ``AppError`` rolls back).
Device payloads are built with the SAME shared allocation the POS uses (``app.shared.debt_allocation``) over the
``/sync/pull`` ``open_debt_docs`` rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.sync.application.handlers import EventContext, SyncEventHandler
from app.shared.debt_allocation import allocate_json
from tests.support.auth import new_phone
from tests.support.catalog import Env
from tests.support.sales import (
    API,
    D,
    Pos,
    Pushed,
    execute,
    new_item,
    one,
    rows,
    sale_line,
    sale_payload,
    sell,
)

__all__ = [
    "API",
    "D",
    "Env",
    "Pos",
    "Pushed",
    "customer",
    "debt_handlers",
    "debt_payment",
    "debt_sale",
    "deliver_debt",
    "execute",
    "ledger",
    "one",
    "open_docs",
    "rows",
]


async def customer(env: Env, pos: Pos, *, limit: str | None = None, name: str = "Aliyev Vali") -> UUID:
    cid = uuid7()
    await execute(
        env.db,
        pos.tenant_id,
        "INSERT INTO app.counterparties (id, tenant_id, kind, name, phone, is_customer, credit_limit) "
        "VALUES (:id, :t, 'person', :n, :p, true, CAST(:l AS numeric))",
        id=cid,
        t=pos.tenant_id,
        n=name,
        p=new_phone(),
        l=limit,
    )
    return cid


async def debt_sale(
    env: Env,
    pos: Pos,
    cid: UUID,
    lines: Sequence[tuple[UUID, str, str]],
    *,
    due: str | None = None,
    paid_cash: str | None = None,
    is_offline: bool = False,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """A sale on debt: ``lines`` = (product, qty, price 4 dp); optional cash part (mixed sale)."""
    body = [sale_line(p, qty=q, price=pr) for p, q, pr in lines]
    total = sum((D(ln["line_total"]) for ln in body), D("0.00"))
    cash = D(paid_cash) if paid_cash else D("0.00")
    debt: dict[str, Any] = {"method": "debt", "amount": format(total - cash, "f")}
    if due:
        debt["due_date"] = due
    pays = [debt] if not paid_cash else [{"method": "cash", "amount": paid_cash}, debt]
    payload = sale_payload(pos, body, pays, counterparty_id=str(cid), is_offline=is_offline)
    await sell(env, pos, payload, created_at=created_at)
    return payload


async def item(env: Env, pos: Pos, price: str, name: str | None = None) -> UUID:
    return await new_item(
        env, pos, name or f"Tovar {uuid7().hex[-6:]}", price=price, stock="100.000", cost="1.00"
    )


def debt_handlers(env: Env) -> dict[str, SyncEventHandler]:
    from app.modules.debts.wiring import sync_handlers

    return dict(sync_handlers(env.settings, env.db))


async def deliver_debt(
    env: Env,
    pos: Pos,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    actor: str = "cashier",
    device_id: UUID | None = None,
    created_at: datetime | None = None,
) -> Pushed:
    handler = debt_handlers(env)[event_type]
    now = datetime.now(UTC)
    ctx = EventContext(
        tenant_id=pos.tenant_id,
        device_id=device_id or pos.device_id,
        branch_id=pos.branch_id,
        cash_register_id=pos.register_id,
        client_event_id=uuid7(),
        seq=1,
        event_type=event_type,
        created_at=created_at or now,
        received_at=now,
        actor_user_id=pos.shop.user_ids[actor],
        session_user_id=pos.shop.user_ids[actor],
    )
    out = Pushed(ctx=ctx)
    try:
        async with (
            env.db.session_factory() as s,
            tenant_transaction(s, ctx.tenant_id, user_id=ctx.actor_user_id),
        ):
            out.result = await handler(s, ctx, payload)
    except AppError as exc:
        out.error = exc
    return out


async def open_docs(env: Env, pos: Pos, cid: UUID) -> list[dict[str, Any]]:
    """The 16 §1 ``open_debt_docs`` rows of a customer (what ``/sync/pull`` sends the POS)."""
    from app.modules.debts.wiring import open_debt_docs

    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        return (await open_debt_docs(s, [cid]))[cid]


def debt_payment(
    pos: Pos,
    cid: UUID,
    amount: str,
    docs: Sequence[Mapping[str, Any]],
    *,
    method: str = "cash",
    is_offline: bool = False,
    promise_date: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """A ``debt_payment.created`` payload the POS builds from its ``open_debt_docs`` cache (18 §12.2)."""
    result = allocate_json(amount, docs)
    body: dict[str, Any] = {
        "id": str(uuid7()),
        "counterparty_id": str(cid),
        "branch_id": str(pos.branch_id),
        "cash_register_id": str(pos.register_id),
        "shift_id": str(pos.shift_id),
        "receipt_seq": pos.next_seq(),
        "is_offline": is_offline,
        "amount": amount,
        "method": method,
        "allocations": result["allocations"],
        "fiscal_lines": result["fiscal_lines"],
    }
    if is_offline:
        body["offline_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if promise_date:
        body["promise_date"] = promise_date
    body.update(extra)
    return body


async def ledger(env: Env, pos: Pos, doc_id: Any) -> dict[tuple[str, str], Decimal]:
    found = await rows(
        env.db,
        pos.tenant_id,
        "SELECT account_dt, account_kt, amount FROM app.ledger_entries WHERE doc_id = :d",
        d=doc_id,
    )
    out: dict[tuple[str, str], Decimal] = {}
    for r in found:
        key = (r["account_dt"], r["account_kt"])
        out[key] = out.get(key, D("0.00")) + r["amount"]
    return out


async def set_go_live(env: Env, pos: Pos, day: date) -> None:
    await execute(env.db, pos.tenant_id, "UPDATE app.tenants SET go_live_date = :d", d=day)
