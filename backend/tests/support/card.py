"""Helpers for the card-terminal tests (qaror #71) — real app, real PostgreSQL/Redis.

``env`` fixture = the catalog env with ``ERP_CARD_FAKE_TERMINALS=true``; :func:`card_shop` builds a tenant with
owner/manager/cashier, two cash registers (``Kassa-1`` with the fake terminal ``T1``, ``Kassa-2`` without), a
device and an open shift. The POS side is simulated with the Python :class:`FakeCardTerminalAdapter` and
:func:`card_result_from_port` (same mapping as the web client ``toCardResult``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.access.domain.permissions import SystemRole
from app.modules.integrations.card_terminal.application.ports import CardPurchaseRequest, TerminalRef
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.infrastructure.fake import FakeCardTerminalAdapter
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings, make_shop
from tests.support.ordering import TXN_ORDER

API = "/api/v1"
ROLES = (SystemRole.OWNER, SystemRole.MANAGER, SystemRole.CASHIER)


@pytest.fixture(name="env")
async def card_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(migrated_db, redis_url, tmp_path / "files", card_fake_terminals=True)
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)


@dataclass
class CardShop:
    shop: Shop
    register1: UUID  # Kassa-1 — T1 bound (is_default)
    register2: UUID  # Kassa-2 — no terminal
    device_id: UUID
    shift_id: UUID
    terminal: dict[str, Any]
    fake: FakeCardTerminalAdapter = field(default_factory=FakeCardTerminalAdapter)

    @property
    def tenant_id(self) -> UUID:
        return self.shop.tenant_id

    @property
    def branch_id(self) -> UUID:
        return self.shop.branch_id

    @property
    def terminal_id(self) -> UUID:
        return UUID(self.terminal["id"])

    def h(self, role: str = "cashier", **kw: Any) -> dict[str, str]:
        return self.shop.h(role, **kw)

    def uid(self, role: str) -> UUID:
        return self.shop.user_ids[role]


async def _register(db: Database, tenant_id: UUID, branch_id: UUID, name: str) -> UUID:
    rid = uuid7()
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) "
                "VALUES (:id, :t, :b, :n, 'web')"
            ),
            {"id": rid, "t": tenant_id, "b": branch_id, "n": name},
        )
    return rid


async def card_shop(env: Env, name: str = "Karta do'koni") -> CardShop:
    shop = await make_shop(env.db, env.client, name, ROLES)
    r1 = await _register(env.db, shop.tenant_id, shop.branch_id, "Kassa-1")
    r2 = await _register(env.db, shop.tenant_id, shop.branch_id, "Kassa-2")
    device_id, shift_id = uuid7(), uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind) VALUES (:id, :t, :c, 'web')"
            ),
            {"id": device_id, "t": shop.tenant_id, "c": r1},
        )
        await s.execute(
            text(
                "INSERT INTO app.shifts (id, tenant_id, branch_id, cash_register_id, device_id, shift_no, "
                "opened_by) VALUES (:id, :t, :b, :c, :d, 1, :u)"
            ),
            {"id": shift_id, "t": shop.tenant_id, "b": shop.branch_id, "c": r1, "d": device_id,
             "u": shop.user_ids["cashier"]},
        )  # fmt: skip
    terminal = await create_terminal(env.client, shop, register=r1)
    return CardShop(shop, r1, r2, device_id, shift_id, terminal)


async def create_terminal(
    client: httpx.AsyncClient, shop: Shop, *, register: UUID | None, name: str = "T1", **extra: Any
) -> dict[str, Any]:
    body = {
        "branch_id": str(shop.branch_id), "cash_register_id": None if register is None else str(register),
        "name": name, "vendor": "fake", "adapter": "fake", "driver": "fake", "is_default": register is not None,
        **extra,
    }  # fmt: skip
    response = await client.post(f"{API}/card-terminals", json=body, headers=shop.h("owner"))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def create_sale(
    env: Env, cs: CardShop, *, total: str = "12000.00", client_event_id: UUID | None = None
) -> UUID:
    sale_id = uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await s.execute(
            text(
                "INSERT INTO app.sales (id, tenant_id, branch_id, doc_date, shift_id, cash_register_id, "
                "total_amount, created_by, device_id, client_event_id) VALUES (:id, :t, :b, :d, :s, :c, "
                ":total, :u, :dev, :e)"
            ),
            {"id": sale_id, "t": cs.tenant_id, "b": cs.branch_id, "d": date(2026, 10, 17), "s": cs.shift_id,
             "c": cs.register1, "total": total, "u": cs.uid("cashier"), "dev": cs.device_id, "e": client_event_id},
        )  # fmt: skip
    return sale_id


async def pos_purchase(
    cs: CardShop, amount_tiyin: int, *, attempt_id: UUID | None = None, bin_rule_type: str | None = None
) -> tuple[UUID, dict[str, Any]]:
    """What the POS does: call the terminal, map the ``CardTxResult`` to a ``CardResult``."""
    attempt = attempt_id or uuid7()
    req = CardPurchaseRequest(
        attempt_id=attempt, terminal=TerminalRef(card_terminal_id=cs.terminal_id), amount_tiyin=amount_tiyin,
        cash_register_id=cs.register1, client_event_id=uuid7(),
    )  # fmt: skip
    result = await cs.fake.purchase(req)
    return attempt, card_result_from_port(
        result, card_terminal_id=cs.terminal_id, requested_amount_tiyin=amount_tiyin, resolved_by="auto",
        bin_rule_type=bin_rule_type,
    )  # fmt: skip


def tx_body(
    cs: CardShop,
    attempt_id: UUID,
    amount: str,
    result: dict[str, Any] | None,
    *,
    kind: str = "purchase",
    original: UUID | None = None,
    client_event_id: UUID | None = None,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(attempt_id), "card_terminal_id": str(cs.terminal_id), "cash_register_id": str(cs.register1),
        "shift_id": str(cs.shift_id), "kind": kind, "amount": amount,
        "original_transaction_id": None if original is None else str(original),
        "client_event_id": None if client_event_id is None else str(client_event_id),
        "requested_at": datetime.now(UTC).isoformat(), "status": None if result else "pending", "result": result,
        "card_manual_approval": approval,
    }  # fmt: skip


async def post_tx(env: Env, cs: CardShop, body: dict[str, Any], role: str = "cashier") -> httpx.Response:
    return await env.client.post(
        f"{API}/card-terminal-transactions", json=body, headers=cs.h(role, key=None)
    )  # no Idempotency-Key (18 §16a.3)


async def scalar(env: Env, cs: CardShop, sql: str, **params: Any) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        return (await s.execute(text(sql), params)).scalar()


async def audit_actions(env: Env, cs: CardShop, entity_id: UUID) -> list[str]:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        rows = await s.execute(
            text(f"SELECT action FROM app.audit_log WHERE entity_id = :e ORDER BY {TXN_ORDER}, id"),
            {"e": entity_id},
        )
        return [r[0] for r in rows]


async def set_fallback(env: Env, cs: CardShop, value: str | None) -> None:
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        if value is None:
            await s.execute(text("UPDATE app.tenants SET settings = settings - 'card_manual_fallback'"))
        else:
            await s.execute(
                text(
                    "UPDATE app.tenants SET settings = jsonb_set(settings, '{card_manual_fallback}', to_jsonb(CAST(:v AS text)))"
                ),
                {"v": value},
            )


def err(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code
