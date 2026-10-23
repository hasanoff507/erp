"""Helpers for the sales / returns / fiscal tests (Bosqich 3, b3-sales slice).

Real app + PostgreSQL/Redis (the catalog setup) with ``ERP_FISCAL_PROVIDER=fake``. POS events are delivered
by calling the sales/returns sync handlers exactly as ``/sync/push`` does — one tenant transaction per event,
an ``AppError`` rolls everything back, ``after_commit`` callbacks run after COMMIT (:func:`deliver`). The
shift is opened with SQL (the cash slice owns ``shift.opened``); products, prices and stock go through the
real catalog / price-change APIs and the stock toolkit.

``cash_sale_payload`` is the minimal valid ``sale.created`` payload (also used by the sync load test).
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

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.core.errors import AppError
from app.core.money import line_total, money_str, vat_from_gross
from app.modules.access.domain.permissions import SystemRole
from app.modules.integrations.fiscal.wiring import fake_fiscal_adapter
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncEventHandler
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings, create_product, set_price
from tests.support.inventory import receive, use_account
from tests.support.ordering import TXN_ORDER

API = "/api/v1"
ROLES = (SystemRole.OWNER, SystemRole.MANAGER, SystemRole.CASHIER, SystemRole.ACCOUNTANT)
D = Decimal


@dataclass
class Pos:
    shop: Shop
    register_id: UUID
    device_id: UUID
    other_device_id: UUID
    warehouse_id: UUID
    shift_id: UUID
    receipt_seq: int = 0

    @property
    def tenant_id(self) -> UUID:
        return self.shop.tenant_id

    @property
    def branch_id(self) -> UUID:
        return self.shop.branch_id

    def next_seq(self) -> int:
        self.receipt_seq += 1
        return self.receipt_seq


@dataclass
class Pushed:
    result: HandlerResult | None = None
    error: AppError | None = None
    ctx: EventContext | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> str | None:
        return None if self.error is None else self.error.code.value

    @property
    def server(self) -> Mapping[str, Any]:
        assert self.result is not None, self.error and (
            self.error.code,
            self.error.params,
            self.error.details,
        )
        assert self.result.server is not None
        return self.result.server

    @property
    def fields(self) -> list[str]:
        return [d.field for d in self.error.details] if self.error else []

    @property
    def keys(self) -> list[str]:
        return [d.message_key for d in self.error.details] if self.error else []

    @property
    def exception_kinds(self) -> list[str]:
        return [e.kind for e in self.result.sync_exceptions] if self.result else []


async def rows(db: Database, tenant_id: UUID, query: str, **params: Any) -> list[dict[str, Any]]:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        result = await s.execute(text(query), params)
        return [dict(r._mapping) for r in result.all()] if result.returns_rows else []


async def one(db: Database, tenant_id: UUID, query: str, **params: Any) -> Any:
    found = await rows(db, tenant_id, query, **params)
    return next(iter(found[0].values())) if found else None


async def execute(db: Database, tenant_id: UUID, query: str, **params: Any) -> None:
    await rows(db, tenant_id, query, **params)


async def open_shift_sql(
    db: Database, pos_shop: Shop, register_id: UUID, device_id: UUID, user_id: UUID
) -> UUID:
    shift_id = uuid7()
    no = await one(db, pos_shop.tenant_id, "SELECT COALESCE(max(shift_no), 0) + 1 FROM app.shifts WHERE cash_register_id = :c",
                   c=register_id)  # fmt: skip
    await execute(
        db, pos_shop.tenant_id,
        "INSERT INTO app.shifts (id, tenant_id, branch_id, cash_register_id, device_id, shift_no, opened_by) "
        "VALUES (:id, :t, :b, :c, :d, :n, :u)",
        id=shift_id, t=pos_shop.tenant_id, b=pos_shop.branch_id, c=register_id, d=device_id, n=no, u=user_id,
    )  # fmt: skip
    return shift_id


async def make_pos(env: Env, name: str = "Savdo do'koni", *, account: str = "2920") -> Pos:
    """A shop (owner/manager/cashier/accountant) with register ``K1``, two devices, an open shift of the first
    device, the register's fiscal module ``ok`` and the default warehouse booked to ``account``."""
    shop = await env.shop(name, *ROLES)
    register_id, device_id, other = uuid7(), uuid7(), uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text("INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind, fm_state) "
                 "VALUES (:id, :t, :b, 'K1', 'web', 'ok')"),
            {"id": register_id, "t": shop.tenant_id, "b": shop.branch_id},
        )  # fmt: skip
        for dev in (device_id, other):
            await s.execute(
                text(
                    "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind) VALUES (:id, :t, :c, 'web')"
                ),
                {"id": dev, "t": shop.tenant_id, "c": register_id},
            )
    warehouse = await use_account(env, shop, account)
    shift = await open_shift_sql(env.db, shop, register_id, device_id, shop.user_ids["cashier"])
    return Pos(shop, register_id, device_id, other, warehouse, shift)


async def new_item(
    env: Env,
    pos: Pos,
    name: str = "Coca-Cola 1.5L",
    *,
    price: str = "12000.00",
    stock: str | None = "10.000",
    cost: str = "8000.00",
    **extra: Any,
) -> UUID:
    """A product with a current price and (optionally) ``stock`` units at ``cost`` per unit."""
    product = UUID((await create_product(env.client, pos.shop, name, **extra))["id"])
    await set_price(env.client, pos.shop, str(product), format(D(price).quantize(D("0.0001")), "f"))
    if stock is not None:
        amount = money_str(D(stock) * D(cost))
        await receive(env, pos.shop, pos.warehouse_id, product, stock, amount)
    return product


def sale_line(
    product_id: UUID,
    *,
    qty: str = "1.000",
    price: str = "12000.0000",
    vat_rate: str = "12.00",
    unit_code: str = "box",
    discount: str | None = None,
    source: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    disc = D(discount) if discount else D("0")
    total = line_total(D(qty), D(price), disc)
    body: dict[str, Any] = {
        "id": str(uuid7()), "product_id": str(product_id), "unit_code": unit_code, "qty": qty, "price": price,
        "vat_rate": vat_rate, "line_total": money_str(total), "vat_amount": money_str(vat_from_gross(total, vat_rate)),
    }  # fmt: skip
    if discount:
        body.update(discount_amount=discount, discount_source=source or "manual")
    body.update(extra)
    return body


def sale_payload(
    pos: Pos,
    lines: Sequence[Mapping[str, Any]],
    payments: Sequence[Mapping[str, Any]] | None = None,
    *,
    receipt_seq: int | str | None = "auto",
    is_offline: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    total = sum((D(ln["line_total"]) for ln in lines), D("0.00"))
    pays = list(payments) if payments is not None else [{"method": "cash", "amount": money_str(total)}]
    only_debt = all(p["method"] == "debt" for p in pays)
    seq = (None if only_debt else pos.next_seq()) if receipt_seq == "auto" else receipt_seq
    body: dict[str, Any] = {
        "id": str(uuid7()), "branch_id": str(pos.branch_id), "cash_register_id": str(pos.register_id),
        "shift_id": str(pos.shift_id), "receipt_seq": seq, "temp_number": f"{pos.device_id}-{uuid7().hex[-12:]}",
        "doc_date": datetime.now(UTC).date().isoformat(), "lines": list(lines), "payments": pays,
        "is_offline": is_offline,
    }  # fmt: skip
    if is_offline:
        body["offline_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    body.update(extra)
    return body


async def sold_lines(env: Env, pos: Pos, sale_id: str) -> list[dict[str, Any]]:
    return await rows(
        env.db, pos.tenant_id,
        "SELECT id, product_id, qty, price, vat_rate, line_total FROM app.sale_lines WHERE sale_id = :d ORDER BY line_no",
        d=sale_id,
    )  # fmt: skip


def return_line(product_id: Any, *, sale_line_id: Any = None, qty: str = "1.000", price: str = "12000.0000",
                **extra: Any) -> dict[str, Any]:  # fmt: skip
    body: dict[str, Any] = {
        "sale_line_id": str(sale_line_id) if sale_line_id else None, "product_id": str(product_id), "qty": qty,
        "price": price, "vat_rate": "12.00",
    }  # fmt: skip
    body.update(extra)
    return body


def return_payload(
    pos: Pos,
    lines: Sequence[Mapping[str, Any]],
    *,
    sale_id: Any = None,
    refund_method: str = "cash",
    receipt_seq: int | str | None = "auto",
    is_offline: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(uuid7()), "branch_id": str(pos.branch_id), "shift_id": str(pos.shift_id),
        "cash_register_id": str(pos.register_id), "receipt_seq": pos.next_seq() if receipt_seq == "auto" else receipt_seq,
        "sale_id": str(sale_id) if sale_id else None, "is_offline": is_offline, "reason": "defective",
        "refund_method": refund_method, "lines": list(lines),
    }  # fmt: skip
    body.update(extra)
    return body


def cash_sale_payload(
    *,
    sale_id: UUID,
    branch_id: UUID,
    cash_register_id: UUID,
    shift_id: UUID,
    product_id: UUID,
    unit_code: str = "box",
    price: str = "12000.0000",
    qty: str = "1.000",
    vat_rate: str = "12.00",
    receipt_seq: int = 1,
    is_offline: bool = False,
) -> dict[str, Any]:
    """The minimal valid one-line cash ``sale.created`` payload (18 §4.1)."""
    line = sale_line(product_id, qty=qty, price=price, vat_rate=vat_rate, unit_code=unit_code)
    body: dict[str, Any] = {
        "id": str(sale_id), "branch_id": str(branch_id), "cash_register_id": str(cash_register_id),
        "shift_id": str(shift_id), "receipt_seq": receipt_seq, "temp_number": f"T-{sale_id.hex[:12]}",
        "doc_date": datetime.now(UTC).date().isoformat(), "lines": [line],
        "payments": [{"method": "cash", "amount": line["line_total"]}], "is_offline": is_offline,
    }  # fmt: skip
    if is_offline:
        body["offline_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return body


def _handlers(env: Env) -> dict[str, SyncEventHandler]:
    from app.modules.returns.wiring import sync_handlers as returns_handlers
    from app.modules.sales.wiring import sync_handlers as sales_handlers

    return {**sales_handlers(env.settings, env.db), **returns_handlers(env.settings, env.db)}


async def deliver(
    env: Env,
    pos: Pos,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    actor: str = "cashier",
    device_id: UUID | None = None,
    created_at: datetime | None = None,
    received_at: datetime | None = None,
    run_after: bool = False,
    actor_bound: Any = None,
) -> Pushed:
    """One POS event through the sales/returns handler, the way ``/sync/push`` delivers it.

    ``after_commit`` callbacks (fiscal ``enqueue``, recost) only run with ``run_after=True`` — tests drain
    the fiscal outbox explicitly with :func:`fiscalize`."""
    handler = _handlers(env)[event_type]
    now = datetime.now(UTC)
    ctx = EventContext(
        tenant_id=pos.tenant_id, device_id=device_id or pos.device_id, branch_id=pos.branch_id,
        cash_register_id=pos.register_id, client_event_id=uuid7(), seq=1, event_type=event_type,
        created_at=created_at or now, received_at=received_at or now,
        actor_user_id=pos.shop.user_ids[actor], session_user_id=pos.shop.user_ids[actor], actor_bound=actor_bound,
    )  # fmt: skip
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
    if run_after:
        for callback in out.result.after_commit:
            await callback()
    return out


async def sell(env: Env, pos: Pos, payload: Mapping[str, Any], **kw: Any) -> Pushed:
    res = await deliver(env, pos, "sale.created", payload, **kw)
    assert res.error is None, (res.error.code, res.error.params, res.error.details) if res.error else None
    return res


async def fiscalize(env: Env, pos: Pos) -> int:
    """Run the ``ofd_send`` outbox of the tenant with the fake FM (the cron sweeper path).

    Jobs enqueued "due now" (``next_run_at = now()`` of an earlier transaction) are moved an hour back first:
    the test DB clock can step backwards (~1 s), and the claim (``next_run_at <= now()``) would then skip them.
    Jobs scheduled later (retry backoff) are left alone."""
    from app.modules.integrations.fiscal.wiring import ofd_send_service

    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.outbox_jobs SET next_run_at = now() - interval '1 hour' WHERE kind = 'ofd_send' "
        "AND status IN ('queued', 'retry') AND next_run_at <= now() + interval '5 seconds'",
    )  # fmt: skip
    done = await ofd_send_service(env.db.session_factory, env.settings).process_due(pos.tenant_id)
    return len(done)


async def ledger_rows(env: Env, pos: Pos, doc_id: UUID) -> list[tuple[str, str, Decimal, dict[str, Any]]]:
    found = await rows(
        env.db, pos.tenant_id,
        "SELECT account_dt, account_kt, amount, analytics FROM app.ledger_entries WHERE doc_id = :d "
        f"ORDER BY {TXN_ORDER}, id",
        d=doc_id,
    )  # fmt: skip
    return [(r["account_dt"], r["account_kt"], r["amount"], r["analytics"]) for r in found]


def sums(entries: Sequence[tuple[str, str, Decimal, dict[str, Any]]]) -> dict[tuple[str, str], Decimal]:
    out: dict[tuple[str, str], Decimal] = {}
    for dt, kt, amount, _ in entries:
        out[(dt, kt)] = out.get((dt, kt), D("0.00")) + amount
    return out


async def bind_terminal(env: Env, pos: Pos) -> UUID:
    """A fake integrated card terminal bound to the register (``card_entry_mode='integrated'`` path)."""
    body = {
        "branch_id": str(pos.branch_id), "cash_register_id": str(pos.register_id), "name": "T1", "vendor": "fake",
        "adapter": "fake", "driver": "fake", "is_default": True,
    }  # fmt: skip
    response = await env.client.post(f"{API}/card-terminals", json=body, headers=pos.shop.h("owner"))
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def card_result(
    pos: Pos, terminal_id: UUID, amount: str, *, kind: str = "purchase", original: UUID | None = None
) -> dict[str, Any]:
    """An approved ``CardResult`` produced by the fake terminal (what the POS puts into ``card_result``)."""
    from app.modules.integrations.card_terminal.application.ports import (
        CardPurchaseRequest,
        CardRefundRequest,
        TerminalRef,
    )
    from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
    from app.modules.integrations.card_terminal.infrastructure.fake import FakeCardTerminalAdapter

    tiyin = int(D(amount) * 100)
    attempt = uuid7()
    terminal = TerminalRef(card_terminal_id=terminal_id)
    fake = FakeCardTerminalAdapter()
    if kind == "refund":
        result = await fake.refund(
            CardRefundRequest(
                attempt_id=attempt, terminal=terminal, amount_tiyin=tiyin, original_attempt_id=original
            )
        )
    else:
        result = await fake.purchase(
            CardPurchaseRequest(attempt_id=attempt, terminal=terminal, amount_tiyin=tiyin,
                                cash_register_id=pos.register_id, client_event_id=uuid7())
        )  # fmt: skip
    out: dict[str, Any] = card_result_from_port(
        result, card_terminal_id=terminal_id, requested_amount_tiyin=tiyin, resolved_by="auto",
        original_attempt_id=original,
    )  # fmt: skip
    return out


async def add_customer(
    env: Env, pos: Pos, *, credit_limit: str | None = None, standing: str | None = None, kind: str = "person"
) -> UUID:
    cid = uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.counterparties (id, tenant_id, kind, name, is_customer, credit_limit, standing_discount_pct) "
        "VALUES (:id, :t, :k, 'Mijoz', true, CAST(:l AS numeric), CAST(:s AS numeric))",
        id=cid, t=pos.tenant_id, k=kind, l=credit_limit, s=standing,
    )  # fmt: skip
    return cid


def reset_fake_fm() -> None:
    fake = fake_fiscal_adapter()
    fake.fail = None
    fake.ack = True
    fake.device_state = "ok"
    fake.calls.clear()


@pytest.fixture(name="env")
async def sales_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    reset_fake_fm()
    settings = catalog_settings(
        migrated_db, redis_url, tmp_path / "files", fiscal_provider="fake", card_fake_terminals=True
    )
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)
    reset_fake_fm()
