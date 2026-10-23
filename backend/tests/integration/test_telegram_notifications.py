"""Telegram sender + daily report (21 §11; US-M18-02/03, US-M04-02; QT-M18-02, -03, -06, QT-M04-02).

Events recorded by the modules (``outbox_jobs(kind='telegram')``, B2-T10/B3-T18) are fanned out to the recipients
and delivered through the real sender with a :class:`FakeTelegram`.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import text as sql_text

from app.core.db.session import tenant_transaction
from app.core.queue import make_queue
from app.modules.access.domain.permissions import SystemRole
from app.modules.notifications.wiring import DAILY_REPORT_JOB, TELEGRAM_SWEEP_JOB, FakeTelegram
from app.workers.cron import CRON_JOBS
from app.workers.jobs import FUNCTIONS
from tests.support.catalog import Env
from tests.support.inventory import add_branch, add_user, new_product, receive, use_account
from tests.support.telegram import (
    FixedSummary,
    link,
    record,
    rows,
    run_daily,
    scalar,
    set_setting,
    sweep,
    telegram_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["telegram_env_fixture"]

TASHKENT = timedelta(hours=5)


def at_tashkent(day: datetime, hhmm: time) -> datetime:
    return datetime.combine(day.date(), hhmm, tzinfo=UTC) - TASHKENT


async def test_qt_m18_03_cash_variance_sent_immediately(env: Env) -> None:
    shop = await env.shop("Kassa farqi", SystemRole.OWNER, SystemRole.CASHIER)
    await link(env, shop, "owner", 1001)
    payload = {"shift_id": "s", "shift_no": 7, "branch_id": str(shop.branch_id), "expected_cash": "500000.00",
               "counted_cash": "480000.00", "variance": "-20000.00", "kind": "shortage"}  # fmt: skip
    await record(env, shop.tenant_id, "cash_variance", payload, "cash_variance:1")
    port = FakeTelegram()
    outcomes = await sweep(env, shop.tenant_id, port)
    assert [o.status for o in outcomes] == ["fanned_out", "sent"]
    [text] = port.to("1001")
    assert "Smena kassa farqi" in text and "-20 000.00 so'm" in text and "Smena: 7" in text
    assert "Filial:" in text
    [log] = await rows(
        env, shop.tenant_id, "SELECT channel, recipient, template, status FROM app.notifications_log"
    )
    assert log == {"channel": "telegram", "recipient": "1001", "template": "cash_variance", "status": "sent"}
    jobs = await rows(env, shop.tenant_id, "SELECT status, payload->>'deliver_to' AS to FROM app.outbox_jobs "
                      "WHERE kind = 'telegram' ORDER BY id")  # fmt: skip
    assert [(j["status"], j["to"]) for j in jobs] == [("done", None), ("done", str(shop.user_ids["owner"]))]
    # nothing is sent twice; the cashier (no telegram link, no rights) receives nothing
    assert await sweep(env, shop.tenant_id, port) == []
    # disabled kind → not sent (yoqilgan bo'lsa)
    assert (await set_setting(env, shop, [{"kind": "cash_variance", "enabled": False}])).status_code == 200
    await record(env, shop.tenant_id, "cash_variance", payload, "cash_variance:2")
    assert [o.status for o in await sweep(env, shop.tenant_id, port)] == ["fanned_out"]
    assert len(port.to("1001")) == 1


async def test_qt_m18_06_and_qt_m04_02_low_stock_toggle_and_manager_delivery(env: Env) -> None:
    shop = await env.shop("Kam qoldiq TG", SystemRole.OWNER, SystemRole.MANAGER)
    await link(env, shop, "owner", 2001)
    await link(env, shop, "manager", 2002)
    assert (await set_setting(env, shop, [{"kind": "low_stock", "enabled": False}])).status_code == 200
    wh = await use_account(env, shop)
    cola = await new_product(env, shop, "Coca-Cola 1.5L", min_stock="5.000")
    await receive(env, shop, wh, cola, "3.000", "30000.00")
    # the real daily stock check (B2) records the event — the internal list/flag exists regardless (BO-03)
    from app.modules.inventory.tasks import inventory_daily

    await inventory_daily({"db": env.db, "settings": env.settings}, tenant_id=shop.tenant_id)
    assert await scalar(
        env, shop.tenant_id, "SELECT count(*) FROM app.outbox_jobs WHERE payload->>'event' = 'low_stock' "
        "AND payload->>'deliver_to' IS NULL",
    ) == 1  # fmt: skip
    port = FakeTelegram()
    await sweep(env, shop.tenant_id, port)
    assert port.to("2001") == []  # QT-M18-06: the owner switched low_stock off
    [text] = port.to("2002")  # US-M04-02: the manager is notified
    assert "Kam qolgan tovar" in text and "Coca-Cola 1.5L" in text and "Qoldiq: 3" in text
    assert "Minimal chegara: 5" in text


async def test_branch_scope_and_audience_permissions(env: Env) -> None:
    shop = await env.shop("Filiallar TG", SystemRole.OWNER)
    other_branch, _ = await add_branch(env, shop, "B2", "Chilonzor")
    await add_user(env, shop, "manager_b2", SystemRole.MANAGER, (other_branch,))
    await add_user(env, shop, "storekeeper", SystemRole.STOREKEEPER)
    await link(env, shop, "owner", 3001)
    await link(env, shop, "manager_b2", 3002)
    port = FakeTelegram()
    await record(env, shop.tenant_id, "low_stock", {"product_name": "Non", "branch_id": str(shop.branch_id)})
    await record(env, shop.tenant_id, "low_stock", {"product_name": "Sut", "branch_id": str(other_branch)})
    await record(
        env, shop.tenant_id, "over_limit_action", {"kind": "returns", "requested_value": "300000.00"}
    )
    await sweep(env, shop.tenant_id, port)
    main_name = await scalar(
        env, shop.tenant_id, "SELECT name FROM app.branches WHERE id = :b", b=shop.branch_id
    )
    owner_texts = port.to("3001")
    assert len(owner_texts) == 3  # the owner sees every branch
    assert sorted(t.split("\n")[1] for t in owner_texts if "Kam qolgan" in t) == sorted(
        [f"Filial: {main_name}", "Filial: Chilonzor"]
    )
    manager_texts = port.to("3002")
    assert len(manager_texts) == 2 and any("Sut" in t for t in manager_texts)
    assert not any("Non" in t for t in manager_texts)  # another branch's event is not his
    assert any("Limitdan katta amal" in t for t in manager_texts)  # tenant-wide event


async def test_retry_backoff_dead_letter_and_blocked_chat(env: Env) -> None:
    shop = await env.shop("Qayta urinish")
    await link(env, shop, "owner", 4001)
    await record(env, shop.tenant_id, "low_stock", {"product_name": "A"})
    down = FakeTelegram(fail_with="transient", retry_after_s=120)
    outcomes = await sweep(env, shop.tenant_id, down)
    assert [o.status for o in outcomes] == ["fanned_out", "retry"]
    [job] = await rows(
        env, shop.tenant_id, "SELECT status, attempts, next_run_at > now() + interval '100 seconds' AS later, "
        "last_error FROM app.outbox_jobs WHERE payload ? 'deliver_to'",
    )  # fmt: skip
    assert (job["status"], job["attempts"], job["later"]) == (
        "retry",
        1,
        True,
    )  # Telegram retry_after honoured
    assert job["last_error"].startswith("transient")
    assert await sweep(env, shop.tenant_id, down) == []  # not due yet
    # the 10th failed try is final → dead letter + log 'failed'
    await rows(env, shop.tenant_id, "UPDATE app.outbox_jobs SET attempts = 9, next_run_at = now() "
               "WHERE payload ? 'deliver_to'")  # fmt: skip
    assert [o.status for o in await sweep(env, shop.tenant_id, down)] == ["failed"]
    [job] = await rows(
        env, shop.tenant_id, "SELECT status, attempts FROM app.outbox_jobs WHERE payload ? 'deliver_to'"
    )
    assert job == {"status": "failed", "attempts": 10}
    assert await scalar(env, shop.tenant_id, "SELECT status FROM app.notifications_log") == "failed"
    # the user blocked the bot → the link becomes inactive (21 §11), nothing more is attempted
    await record(env, shop.tenant_id, "low_stock", {"product_name": "B"})
    gone = FakeTelegram(blocked_chats={"4001"})
    assert [o.status for o in await sweep(env, shop.tenant_id, gone)] == ["fanned_out", "failed"]
    assert await scalar(env, shop.tenant_id, "SELECT revoked_at IS NOT NULL FROM app.telegram_links") is True
    await record(env, shop.tenant_id, "low_stock", {"product_name": "C"})
    assert [o.status for o in await sweep(env, shop.tenant_id, gone)] == ["fanned_out"]
    assert gone.calls == 1


async def test_stale_and_unknown_events_are_not_sent(env: Env) -> None:
    shop = await env.shop("Eski voqea")
    await link(env, shop, "owner", 4101)
    await record(env, shop.tenant_id, "low_stock", {"product_name": "Eski"}, "old:1")
    await rows(env, shop.tenant_id, "UPDATE app.outbox_jobs SET created_at = now() - interval '25 hours' "
               "WHERE idempotency_key = 'old:1'")  # fmt: skip
    port = FakeTelegram()
    assert [o.status for o in await sweep(env, shop.tenant_id, port)] == ["stale"]
    assert port.sent == []
    # a misconfigured port leaves due jobs untouched (no Telegram configured → nothing dead-lettered)
    from app.modules.notifications.wiring import telegram_sender

    assert (
        telegram_sender(env.db.session_factory, env.settings.model_copy(update={"telegram_fake": False}))
        is None
    )


async def test_qt_m18_02_daily_report_at_configured_time(env: Env) -> None:
    shop = await env.shop("Kunlik", SystemRole.OWNER, SystemRole.MANAGER, SystemRole.CASHIER)
    await link(env, shop, "owner", 5001)
    await link(env, shop, "manager", 5002)
    assert (
        await set_setting(env, shop, [{"kind": "daily_report", "enabled": True, "time": "20:00"}])
    ).status_code == 200
    manager = shop.user_ids["manager"]
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id, user_id=manager):
        await s.execute(sql_text("UPDATE app.users SET locale = 'ru' WHERE id = :u"), {"u": manager})
    source = FixedSummary()
    today = datetime.now(UTC) + TASHKENT
    # 19:59 Tashkent — owner's time (20:00) not reached, manager's default 21:00 neither
    assert (await run_daily(env, shop.tenant_id, source, at_tashkent(today, time(19, 59))))["queued"] == 0
    # 20:05 → only the owner's report
    assert (await run_daily(env, shop.tenant_id, source, at_tashkent(today, time(20, 5))))["queued"] == 1
    assert (await run_daily(env, shop.tenant_id, source, at_tashkent(today, time(20, 10))))[
        "queued"
    ] == 0  # once
    # 21:00 → the manager too (default time)
    assert (await run_daily(env, shop.tenant_id, source, at_tashkent(today, time(21, 0))))["queued"] == 1
    assert [c[2] for c in source.calls] == [None, None]  # every branch (None) — one summary per run and scope
    port = FakeTelegram()
    await sweep(env, shop.tenant_id, port)
    [owner_text] = port.to("5001")
    assert owner_text.startswith("📊 Kunlik hisobot — " + today.date().isoformat())
    for part in ("Savdo: 1 500 000.00 so'm", "Cheklar: 42", "Sof foyda: 339 285.71 so'm",
                 "Naqd kassada: 750 000.00 so'm", "Yangi qarzlar: 120 000.00 so'm",
                 "Qaytgan qarzlar: 80 000.00 so'm", "Ertaga to'lashi kerak:", "Aziz aka — 50 000.00 so'm",
                 "Diqqat: kam qolgan tovar: 3"):  # fmt: skip
        assert part in owner_text, part
    [manager_text] = port.to("5002")
    assert "Ежедневный отчёт" in manager_text and "Продажи: 1 500 000.00 сум" in manager_text
    keys = await rows(env, shop.tenant_id, "SELECT idempotency_key FROM app.outbox_jobs ORDER BY id")
    assert {k["idempotency_key"] for k in keys} == {
        f"daily_report:{shop.user_ids['owner']}:{today.date().isoformat()}",
        f"daily_report:{shop.user_ids['manager']}:{today.date().isoformat()}",
    }
    # disabled daily report → nothing; no summary source (reports module missing) → no-op
    await set_setting(env, shop, [{"kind": "daily_report", "enabled": False}])
    tomorrow = today + timedelta(days=1)
    queued = await run_daily(env, shop.tenant_id, source, at_tashkent(tomorrow, time(22, 0)))
    assert queued["queued"] == 1  # only the manager's
    from app.modules.notifications.application.daily_report import DailyReportService
    from app.modules.notifications.infrastructure.notifications_sql import SqlNotificationRepository

    none = DailyReportService(env.db.session_factory, SqlNotificationRepository(), None)
    assert (await none.run(shop.tenant_id))["queued"] == 0


async def test_worker_jobs_registered_and_run(env: Env) -> None:
    names = dict(FUNCTIONS)
    for job in (TELEGRAM_SWEEP_JOB, DAILY_REPORT_JOB, "notifications_telegram_sweep_fanout",
                "notifications_daily_report_fanout"):  # fmt: skip
        assert job in names
    crons = {c.function.__name__: c.cron for c in CRON_JOBS}
    assert crons["notifications_telegram_sweep_fanout"] == "* * * * *"
    assert crons["notifications_daily_report_fanout"] == "*/5 * * * *"
    shop = await env.shop("Worker TG")
    await link(env, shop, "owner", 6001)
    await record(env, shop.tenant_id, "expiry_soon", {"product_name": "Sut", "expiry_date": "2026-10-20",
                                                      "days_left": 3, "qty_left": "4.000"})  # fmt: skip
    queue = make_queue(env.settings.redis_url.get_secret_value(), env.settings.queue_name)
    await queue.connect()
    try:
        await queue.enqueue(TELEGRAM_SWEEP_JOB, tenant_id=str(shop.tenant_id))
    finally:
        await queue.disconnect()
    assert await env.drain() == 1  # ERP_TELEGRAM_FAKE in this env → the in-process fake
    [log] = await rows(env, shop.tenant_id, "SELECT template, status FROM app.notifications_log")
    assert log == {"template": "expiry_soon", "status": "sent"}


async def test_qt_m18_02_daily_report_uses_reports_daily_summary(env: Env) -> None:
    """Contract 5: the default source is ``reports.daily_summary()`` (frozen dataclasses → JSON snapshot)."""
    from app.modules.notifications.wiring import daily_report_service, daily_summary_source

    source = daily_summary_source()
    assert source is not None, "app.modules.reports.wiring.daily_summary() is missing"
    shop = await env.shop("Haqiqiy hisobot")
    await link(env, shop, "owner", 7001)
    today = datetime.now(UTC) + TASHKENT
    result = await daily_report_service(env.db.session_factory).run(
        shop.tenant_id, at_tashkent(today, time(23, 0))
    )
    assert result["queued"] == 1
    report = await scalar(env, shop.tenant_id, "SELECT payload->'report' FROM app.outbox_jobs")
    assert report["day"] == today.date().isoformat() and report["total"]["sales_total"] == "0.00"
    port = FakeTelegram()
    await sweep(env, shop.tenant_id, port)
    [text] = port.to("7001")
    assert "Savdo: 0.00 so'm" in text and "Sof foyda: 0.00 so'm" in text
