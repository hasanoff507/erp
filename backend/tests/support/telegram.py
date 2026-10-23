"""Helpers for the M18 Telegram tests (Bosqich 4, b4-telegram slice).

Real app + PostgreSQL/Redis (the catalog test setup) with the webhook secret configured and ``ERP_TELEGRAM_FAKE``
on. Linking goes through the real REST + webhook path (:func:`link`); messages are sent by the real
:class:`TelegramSender` with an in-process :class:`FakeTelegram` (:func:`sweep`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.notifications.wiring import (
    FakeTelegram,
    Outcome,
    daily_report_service,
    event_recorder,
    telegram_sender,
)
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings

API = "/api/v1"
WEBHOOK = f"{API}/notifications/telegram/webhook"
SECRET = "test-webhook-secret-0123456789-abcdef"
BOT = "erp_test_bot"
_update_ids = iter(range(10_000_000, 99_999_999))


@pytest.fixture(name="env")
async def telegram_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(
        migrated_db,
        redis_url,
        tmp_path / "files",
        telegram_webhook_secret=SECRET,
        telegram_bot_username=BOT,
        telegram_fake=True,
    )
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)


def start_update(
    chat_id: int, text_: str, *, lang: str = "uz", update_id: int | None = None
) -> dict[str, Any]:
    return {
        "update_id": update_id if update_id is not None else next(_update_ids),
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "T", "language_code": lang},
            "text": text_,
        },
    }


async def webhook(env: Env, update: Mapping[str, Any], *, secret: str | None = SECRET) -> Any:
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {}
    return await env.client.post(WEBHOOK, json=dict(update), headers=headers)


async def link_start(env: Env, shop: Shop, role: str = "owner") -> dict[str, Any]:
    res = await env.client.post(f"{API}/notifications/telegram/link-start", headers=shop.h(role))
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


async def link(env: Env, shop: Shop, role: str, chat_id: int) -> str:
    """BO-20 «Telegram ulash» + ``/start <code>`` in the bot; returns the bot's reply text."""
    code = (await link_start(env, shop, role))["link_code"]
    res = await webhook(env, start_update(chat_id, f"/start {code}"))
    assert res.status_code == 200, res.text
    reply: str = res.json()["text"]
    return reply


async def record(
    env: Env, tenant_id: UUID, kind: str, payload: Mapping[str, Any], key: str | None = None
) -> None:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        assert await event_recorder().record_event(s, tenant_id, kind, payload, key or f"test:{uuid7()}")


async def sweep(env: Env, tenant_id: UUID, port: FakeTelegram) -> list[Outcome]:
    sender = telegram_sender(env.db.session_factory, env.settings, port)
    assert sender is not None
    return await sender.process_due(tenant_id)


async def rows(env: Env, tenant_id: UUID, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        result = await s.execute(text(sql), params)
        return [dict(r._mapping) for r in result.all()] if result.returns_rows else []


async def scalar(env: Env, tenant_id: UUID, sql: str, **params: Any) -> Any:
    found = await rows(env, tenant_id, sql, **params)
    return next(iter(found[0].values())) if found else None


async def set_setting(env: Env, shop: Shop, items: list[dict[str, Any]], role: str = "owner") -> Any:
    return await env.client.patch(f"{API}/notification-settings", json={"items": items}, headers=shop.h(role))


class FixedSummary:
    """A daily summary source with fixed numbers (contract 5 shape) — records the calls."""

    def __init__(self, sales_total: str = "1500000.00") -> None:
        self.sales_total = sales_total
        self.calls: list[tuple[UUID, date, tuple[UUID, ...] | None]] = []

    async def for_day(
        self, s: AsyncSession, tenant_id: UUID, day: date, branch_ids: Any
    ) -> Mapping[str, Any]:
        self.calls.append((tenant_id, day, tuple(branch_ids) if branch_ids else None))
        total = {
            "branch_id": str(tenant_id), "branch_name": "", "sales_total": self.sales_total,
            "receipts_count": 42, "avg_receipt": "35714.29", "returns_total": "20000.00",
            "revenue": "1339285.71", "cogs": "900000.00", "expenses": "100000.00", "net_profit": "339285.71",
            "cash_on_hand": "750000.00", "new_debts": "120000.00", "debt_payments": "80000.00",
            "overdue_debt_total": "45000.00", "low_stock_count": 3,
        }  # fmt: skip
        return {
            "tenant_id": str(tenant_id), "day": day.isoformat(), "branches": [total], "total": total,
            "cash_registers": [],
            "debtors_due_tomorrow": [{"counterparty_id": str(uuid7()), "name": "Aziz aka", "phone": None,
                                      "amount_due": "50000.00", "due_date": day.isoformat()}],
            "unsynced_devices": True, "unsynced_device_count": 1,
        }  # fmt: skip


async def run_daily(env: Env, tenant_id: UUID, source: Any, now: Any) -> dict[str, Any]:
    return await daily_report_service(env.db.session_factory, source).run(tenant_id, now)
