"""Daily stock notifications recorded to ``outbox_jobs(kind='telegram')`` (27 B2; QT-M04-02, QT-M04-07).

Bosqich 2 only records the events; nothing sends them (Bosqich 4).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.modules.accounting.wiring import business_today
from app.modules.inventory.infrastructure.queue import SaqEnqueuer
from app.workers.cron import CRON_JOBS
from app.workers.jobs import FUNCTIONS
from tests.support.catalog import Env, Shop, catalog_env_fixture
from tests.support.inventory import (
    issue,
    new_product,
    receive,
    rows,
    set_setting,
    use_account,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]


async def _run_daily(env: Env, shop: Shop) -> None:
    queue = SaqEnqueuer(env.settings.redis_url.get_secret_value(), env.settings.queue_name)
    await queue.enqueue("inventory_daily", shop.tenant_id)
    assert await env.drain() == 1


async def _events(env: Env, shop: Shop, event: str) -> list[dict[str, Any]]:
    return await rows(
        env, shop.tenant_id,
        "SELECT kind, status, payload, idempotency_key FROM app.outbox_jobs WHERE payload ->> 'event' = :e "
        "ORDER BY payload ->> 'expiry_date', payload ->> 'product_name'",
        e=event,
    )  # fmt: skip


async def test_qt_m04_07_expiry_soon_events(env: Env) -> None:
    shop = await env.shop("Muddat")
    wh = await use_account(env, shop)
    milk, yogurt = await new_product(env, shop, "Sut"), await new_product(env, shop, "Qatiq")
    today = business_today()
    soon, _ = await receive(env, shop, wh, milk, "6.000", "60000.00", expiry=today + timedelta(days=7))
    await receive(env, shop, wh, milk, "2.000", "20000.00", expiry=today + timedelta(days=8))
    await receive(env, shop, wh, yogurt, "1.000", "9000.00", expiry=today + timedelta(days=2))
    await issue(env, shop, wh, yogurt, "1.000")  # consumed lot → no event
    await issue(env, shop, wh, milk, "1.000")  # 5 left in the soon lot
    await _run_daily(env, shop)
    [event] = await _events(env, shop, "expiry_soon")
    assert (event["kind"], event["status"]) == ("telegram", "queued")
    assert event["payload"] == {
        "event": "expiry_soon", "product_id": str(milk), "product_name": "Sut", "lot_id": str(soon.lot_id),
        "warehouse_id": str(wh), "branch_id": str(shop.branch_id), "qty_left": "5.000",
        "expiry_date": str(today + timedelta(days=7)), "days_left": 7,
    }  # fmt: skip
    assert event["idempotency_key"] == f"expiry_soon:{soon.lot_id}:{today}"
    await _run_daily(env, shop)  # the same day again → recorded once
    assert len(await _events(env, shop, "expiry_soon")) == 1
    await set_setting(env, shop, "expiry_warning_days", 10)
    await _run_daily(env, shop)
    assert len(await _events(env, shop, "expiry_soon")) == 2  # the 8-day lot now too


async def test_qt_m04_02_low_stock_event(env: Env) -> None:
    shop = await env.shop("Kam qoldiq")
    wh = await use_account(env, shop)
    cola = await new_product(env, shop, "Coca-Cola 1.5L", min_stock="5.000")
    fanta = await new_product(env, shop, "Fanta 1L")
    water = await new_product(env, shop, "Suv", min_stock="1.000")
    await receive(env, shop, wh, cola, "3.000", "30000.00")
    await receive(env, shop, wh, fanta, "1.000", "7000.00")
    await receive(env, shop, wh, water, "10.000", "10000.00")
    await _run_daily(env, shop)
    [event] = await _events(env, shop, "low_stock")
    assert event["payload"] == {
        "event": "low_stock", "product_id": str(cola), "product_name": "Coca-Cola 1.5L",
        "warehouse_id": str(wh), "branch_id": str(shop.branch_id), "qty": "3.000", "min_stock": "5.000",
    }  # fmt: skip
    await set_setting(env, shop, "low_stock_check_enabled", False)
    bread = await new_product(env, shop, "Non", min_stock="2.000")
    await receive(env, shop, wh, bread, "1.000", "3000.00")  # low too, but the check is off
    await _run_daily(env, shop)
    assert len(await _events(env, shop, "low_stock")) == 1


def test_no_worker_consumes_telegram_events_and_crons_are_registered() -> None:
    names = {name for name, _ in FUNCTIONS}
    assert not any("telegram" in n or "outbox" in n for n in names)  # sending is Bosqich 4
    assert {"inventory_daily", "inventory_recost", "inventory_recost_sweep"} <= names
    crons = {job.function.__name__ for job in CRON_JOBS}
    assert {"inventory_daily_fanout", "inventory_recost_sweep_fanout"} <= crons
