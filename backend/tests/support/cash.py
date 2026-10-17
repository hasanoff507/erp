"""Helpers for the cash / shifts / approvals / VAT tests (Bosqich 3, b3-cash slice).

Real app + PostgreSQL/Redis (the catalog test setup). POS events are delivered by calling the cash
module's sync handlers exactly as the sync module does — one tenant transaction per event, the handler's
``AppError`` rolls everything back (:func:`push`). Sales/payments that the cash slice only *reads* are
inserted with SQL under RLS (:func:`add_sale`, :func:`add_cash_move`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction, unscoped_transaction
from app.core.errors import AppError
from app.modules.access.domain.permissions import SystemRole
from app.modules.auth.application.passwords import hash_pin
from app.modules.cash.wiring import sync_handlers
from app.modules.sync.application.handlers import EventContext, HandlerResult
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings
from tests.support.ordering import TXN_ORDER

API = "/api/v1"
PIN = "4321"
ROLES = (SystemRole.OWNER, SystemRole.MANAGER, SystemRole.CASHIER, SystemRole.ACCOUNTANT)


@dataclass
class Till:
    """A shop with one register and one bound device (plus a second device for mismatch tests)."""

    shop: Shop
    register_id: UUID
    device_id: UUID
    other_device_id: UUID


@dataclass
class Pushed:
    result: HandlerResult | None = None
    error: AppError | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> str | None:
        return None if self.error is None else self.error.code.value

    @property
    def server(self) -> Mapping[str, Any]:
        assert self.result is not None, self.error
        assert self.result.server is not None
        return self.result.server


async def sql(db: Database, tenant_id: UUID, query: str, **params: Any) -> list[Any]:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        result = await s.execute(text(query), params)
        return list(result.all()) if result.returns_rows else []


async def one(db: Database, tenant_id: UUID, query: str, **params: Any) -> Any:
    rows = await sql(db, tenant_id, query, **params)
    return rows[0][0] if rows else None


async def set_pin(db: Database, user_id: UUID, pin: str = PIN) -> None:
    async with db.session_factory() as s, unscoped_transaction(s):
        await s.execute(
            text("SELECT app.auth_set_credentials(:u, NULL, :p)"), {"u": user_id, "p": hash_pin(pin)}
        )


async def make_till(env: Env, name: str = "Kassa do'kon") -> Till:
    shop = await env.shop(name, *ROLES)
    register_id = uuid7()
    device_id = uuid7()
    other = uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) VALUES (:id, :t, :b, 'K1', 'web')"
            ),
            {"id": register_id, "t": shop.tenant_id, "b": shop.branch_id},
        )
        for dev in (device_id, other):
            await s.execute(
                text(
                    "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind) VALUES (:id, :t, :c, 'web')"
                ),
                {"id": dev, "t": shop.tenant_id, "c": register_id},
            )
    for role in ("owner", "manager", "cashier"):
        await set_pin(env.db, shop.user_ids[role])
    return Till(shop, register_id, device_id, other)


async def push(
    env: Env,
    till: Till,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    actor: str = "cashier",
    device_id: UUID | None = None,
    created_at: datetime | None = None,
    received_at: datetime | None = None,
    actor_bound: Any = None,
) -> Pushed:
    """Deliver one POS event to the cash handler the way ``/sync/push`` does (one transaction)."""
    handler = sync_handlers(env.settings, env.db)[event_type]
    now = datetime.now(UTC)
    ctx = EventContext(
        tenant_id=till.shop.tenant_id,
        device_id=device_id or till.device_id,
        branch_id=till.shop.branch_id,
        cash_register_id=till.register_id,
        client_event_id=uuid7(),
        seq=1,
        event_type=event_type,
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
    for callback in out.result.after_commit:
        await callback()
    return out


async def open_shift(env: Env, till: Till, opening: str = "0.00", *, actor: str = "cashier") -> UUID:
    shift_id = uuid7()
    shift_no = (await one(
        env.db, till.shop.tenant_id, "SELECT COALESCE(max(shift_no), 0) + 1 FROM app.shifts WHERE cash_register_id = :c",
        c=till.register_id,
    ))  # fmt: skip
    res = await push(
        env, till, "shift.opened",
        {"id": str(shift_id), "cash_register_id": str(till.register_id), "shift_no": shift_no, "opening_cash": opening},
        actor=actor,
    )  # fmt: skip
    assert res.error is None, res.error and (res.error.code, res.error.params, res.error.details)
    return shift_id


async def add_sale(
    env: Env,
    till: Till,
    shift_id: UUID,
    payments: Sequence[tuple[str, str, str | None]],
    *,
    vat: str = "0.00",
    discount: str = "0.00",
) -> UUID:
    """A posted sale with ``payments`` = (method, amount, card_entry_mode) and its cash_moves rows."""
    tenant = till.shop.tenant_id
    sale_id = uuid7()
    total = sum((Decimal(a) for _, a, _ in payments), Decimal("0"))
    async with env.db.session_factory() as s, tenant_transaction(s, tenant):
        product_id = (await s.execute(text("SELECT id FROM app.products LIMIT 1"))).scalar()
        if product_id is None:
            product_id = uuid7()
            await s.execute(
                text(
                    "INSERT INTO app.products (id, tenant_id, name, unit_code, vat_rate) VALUES (:id, :t, 'Non', 'box', 12)"
                ),
                {"id": product_id, "t": tenant},
            )
        await s.execute(
            text(
                "INSERT INTO app.sales (id, tenant_id, branch_id, doc_date, status, shift_id, cash_register_id, "
                "total_amount, created_by, posted_at) VALUES (:id, :t, :b, :d, 'posted', :s, :c, :tot, :u, now())"
            ),
            {"id": sale_id, "t": tenant, "b": till.shop.branch_id, "d": datetime.now(UTC).date(), "s": shift_id,
             "c": till.register_id, "tot": total, "u": till.shop.user_ids["cashier"]},
        )  # fmt: skip
        await s.execute(
            text(
                "INSERT INTO app.sale_lines (tenant_id, sale_id, line_no, product_id, qty, price, discount_amount, "
                "discount_source, vat_rate, vat_amount, line_total) VALUES (:t, :s, 1, :p, 1, :price, :disc, :src, "
                "12, :vat, :tot)"
            ),
            {"t": tenant, "s": sale_id, "p": product_id, "price": total + Decimal(discount),
             "disc": Decimal(discount), "src": "manual" if Decimal(discount) > 0 else None,
             "vat": Decimal(vat), "tot": total},
        )  # fmt: skip
        for method, amount, mode in payments:
            tx_id = None
            if mode == "integrated":
                tx_id = await _card_tx(s, till, shift_id, amount)
            await s.execute(
                text(
                    "INSERT INTO app.sale_payments (tenant_id, sale_id, method, amount, card_entry_mode, "
                    "card_terminal_transaction_id, rrn, card_mask, card_type, card_type_source, manual_reason, "
                    "qr_type) VALUES (:t, :s, :m, :a, :mode, :tx, :rrn, :mask, :ct, :cts, :mr, :qr)"
                ),
                {
                    "t": tenant, "s": sale_id, "m": method, "a": Decimal(amount), "mode": mode, "tx": tx_id,
                    "rrn": "123456789012" if mode == "integrated" else None,
                    "mask": "8600****1234" if mode == "integrated" else None,
                    "ct": "personal" if mode == "integrated" else None,
                    "cts": "terminal" if mode == "integrated" else None,
                    "mr": "standalone_terminal" if mode == "manual" else None,
                    "qr": "static" if method == "uzqr" else None,
                },
            )  # fmt: skip
            if method != "debt":
                await s.execute(
                    text(
                        "INSERT INTO app.cash_moves (tenant_id, cash_register_id, shift_id, amount, method, doc_type, "
                        "doc_id) VALUES (:t, :c, :s, :a, :m, 'sales', :d)"
                    ),
                    {
                        "t": tenant,
                        "c": till.register_id,
                        "s": shift_id,
                        "a": Decimal(amount),
                        "m": method,
                        "d": sale_id,
                    },
                )
    return sale_id


async def _card_tx(s: Any, till: Till, shift_id: UUID, amount: str) -> UUID:
    terminal = (await s.execute(text("SELECT id FROM app.card_terminals LIMIT 1"))).scalar()
    if terminal is None:
        terminal = uuid7()
        await s.execute(
            text(
                "INSERT INTO app.card_terminals (id, tenant_id, branch_id, cash_register_id, name, vendor, adapter, "
                "driver, created_by) VALUES (:id, :t, :b, :c, 'T1', 'fake', 'fake', 'fake', :u)"
            ),
            {
                "id": terminal,
                "t": till.shop.tenant_id,
                "b": till.shop.branch_id,
                "c": till.register_id,
                "u": till.shop.user_ids["owner"],
            },
        )
    tx_id = uuid7()
    await s.execute(
        text(
            "INSERT INTO app.card_terminal_transactions (id, tenant_id, branch_id, card_terminal_id, cash_register_id, "
            "shift_id, kind, amount, approved_amount, status, rrn, card_mask, card_type, card_type_source, "
            "resolved_by, requested_at, resolved_at, created_by) VALUES (:id, :t, :b, :ct, :c, :s, 'purchase', :a, :a, "
            "'approved', '123456789012', '8600****1234', 'personal', 'terminal', 'auto', now(), now(), :u)"
        ),
        {"id": tx_id, "t": till.shop.tenant_id, "b": till.shop.branch_id, "ct": terminal, "c": till.register_id,
         "s": shift_id, "a": Decimal(amount), "u": till.shop.user_ids["cashier"]},
    )  # fmt: skip
    return tx_id


async def add_cash_move(
    env: Env, till: Till, shift_id: UUID, amount: str, doc_type: str = "debt_payments"
) -> None:
    await sql(
        env.db, till.shop.tenant_id,
        "INSERT INTO app.cash_moves (tenant_id, cash_register_id, shift_id, amount, method, doc_type, doc_id) "
        "VALUES (:t, :c, :s, :a, 'cash', :dt, :d)",
        t=till.shop.tenant_id, c=till.register_id, s=shift_id, a=Decimal(amount), dt=doc_type, d=uuid7(),
    )  # fmt: skip


async def ledger(
    db: Database, tenant_id: UUID, doc_type: str, doc_id: UUID
) -> list[tuple[str, str, str, dict[str, Any]]]:
    rows = await sql(
        db, tenant_id,
        "SELECT account_dt, account_kt, amount, analytics FROM app.ledger_entries WHERE doc_type = :t AND doc_id = :d "
        f"ORDER BY {TXN_ORDER}, id",
        t=doc_type, d=doc_id,
    )  # fmt: skip
    return [(r[0], r[1], format(r[2], "f"), r[3]) for r in rows]


async def outbox_events(admin_engine: AsyncEngine, tenant_id: UUID, event: str) -> list[dict[str, Any]]:
    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT payload FROM app.outbox_jobs WHERE tenant_id = :t AND payload->>'event' = :e"),
            {"t": tenant_id, "e": event},
        )
        return [r[0] for r in rows]


def movement(till: Till, shift_id: UUID, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(uuid7()), "cash_register_id": str(till.register_id), "shift_id": str(shift_id),
        "direction": "out", "reason": "other", "amount": "40000.00", "comment": "Boshqa",
    }  # fmt: skip
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


@pytest.fixture(name="env")
async def cash_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(migrated_db, redis_url, tmp_path / "files", fiscal_provider="fake")
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)
