"""Telegram linking, settings and log (US-M18-01, 20 #66–#71, 07 BO-20; QT-M18-01, QT-M18-05).

Real app + PostgreSQL/Redis; the bot side goes through the real webhook (secret header, ``/start <code>``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.modules.access.domain.permissions import SystemRole
from app.modules.notifications.domain.policy import KIND_ORDER
from app.modules.notifications.wiring import FakeTelegram
from tests.support.catalog import Env
from tests.support.telegram import (
    API,
    BOT,
    link,
    link_start,
    record,
    rows,
    scalar,
    set_setting,
    start_update,
    sweep,
    telegram_env_fixture,
    webhook,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["telegram_env_fixture"]

STATUS = f"{API}/notifications/telegram/status"
UNLINK = f"{API}/notifications/telegram/link"
SETTINGS = f"{API}/notification-settings"
LOG = f"{API}/notifications-log"


async def test_qt_m18_01_one_time_code_links_chat_to_tenant(env: Env) -> None:
    shop = await env.shop("Telegram ulash")
    started = await link_start(env, shop)
    code = started["link_code"]
    assert len(code) >= 16 and started["bot_url"] == f"https://t.me/{BOT}?start={code}"
    assert started["expires_at"]
    status = (await env.client.get(STATUS, headers=shop.h(key=None))).json()
    assert status == {"linked": False, "chat_id": None, "linked_at": None}

    # Telegram's secret header is mandatory
    assert (await webhook(env, start_update(5001, f"/start {code}"), secret=None)).status_code == 403
    bad = await webhook(env, start_update(5001, f"/start {code}"), secret="wrong")
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"

    res = await webhook(env, start_update(5001, f"/start {code}"))
    assert res.status_code == 200
    reply = res.json()
    assert reply["method"] == "sendMessage" and reply["chat_id"] == "5001"
    assert "ulandi" in reply["text"] and "Telegram ulash" in reply["text"]  # tenant name in the confirmation
    status = (await env.client.get(STATUS, headers=shop.h(key=None))).json()
    assert status["linked"] is True and status["chat_id"] == "5001" and status["linked_at"]
    [row] = await rows(env, shop.tenant_id, "SELECT user_id, chat_id, revoked_at FROM app.telegram_links")
    assert row == {"user_id": shop.user_ids["owner"], "chat_id": "5001", "revoked_at": None}
    assert (
        await scalar(
            env, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'telegram_linked'"
        )
        == 1
    )

    # single use: the same code again does nothing
    again = await webhook(env, start_update(6001, f"/start {code}"))
    assert "yaroqsiz" in again.json()["text"]
    assert await scalar(env, shop.tenant_id, "SELECT chat_id FROM app.telegram_links") == "5001"


async def test_link_code_replaced_expired_and_duplicate_updates(env: Env) -> None:
    shop = await env.shop("Kod")
    first = (await link_start(env, shop))["link_code"]
    second = (await link_start(env, shop))["link_code"]
    # a new link-start invalidates the previous code (ru reply for a ru Telegram client)
    old = await webhook(env, start_update(7001, f"/start {first}", lang="ru"))
    assert "недействительна" in old.json()["text"]
    # unknown / malformed codes and plain messages → help, nothing linked
    assert "yaroqsiz" in (await webhook(env, start_update(7001, "/start nope"))).json()["text"]
    assert "Sozlamalar" in (await webhook(env, start_update(7001, "/start"))).json()["text"]
    assert "Sozlamalar" in (await webhook(env, start_update(7001, "salom"))).json()["text"]
    # Telegram re-delivers an update: processed once
    update = start_update(7001, f"/start {second}", update_id=424242)
    assert "ulandi" in (await webhook(env, update)).json()["text"]
    assert (await webhook(env, update)).json() == {}
    # group chats are ignored
    group = start_update(7002, f"/start {second}")
    group["message"]["chat"]["type"] = "group"
    assert (await webhook(env, group)).json() == {}
    # TTL: an expired code is gone from the store
    third = (await link_start(env, shop))["link_code"]
    await env.app.state.redis.flushdb()
    assert "yaroqsiz" in (await webhook(env, start_update(7003, f"/start {third}"))).json()["text"]
    assert await scalar(env, shop.tenant_id, "SELECT chat_id FROM app.telegram_links") == "7001"


async def test_ep_68_unlink_and_permissions(env: Env) -> None:
    shop = await env.shop("Uzish", SystemRole.OWNER, SystemRole.MANAGER, SystemRole.CASHIER)
    # telegram.link — owner and manager; the cashier has neither telegram.link nor notifications.manage
    denied = await env.client.post(f"{API}/notifications/telegram/link-start", headers=shop.h("cashier"))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "PERMISSION_DENIED"
    assert (await env.client.get(SETTINGS, headers=shop.h("manager", key=None))).status_code == 403
    assert (await env.client.get(LOG, headers=shop.h("cashier", key=None))).status_code == 403
    missing = await env.client.post(f"{API}/notifications/telegram/link-start", headers=shop.h(key=None))
    assert missing.status_code == 422  # Idempotency-Key is mandatory (20 #66)

    await link(env, shop, "manager", 8001)
    assert (await env.client.delete(UNLINK, headers=shop.h("owner"))).status_code == 404  # owner not linked
    assert (await env.client.delete(UNLINK, headers=shop.h("manager"))).status_code == 204
    status = (await env.client.get(STATUS, headers=shop.h("manager", key=None))).json()
    assert status["linked"] is False
    assert (await env.client.delete(UNLINK, headers=shop.h("manager"))).status_code == 404
    assert (
        await scalar(
            env, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'telegram_unlinked'"
        )
        == 1
    )
    # linking again re-activates the same row with the new chat
    await link(env, shop, "manager", 8002)
    [row] = await rows(env, shop.tenant_id, "SELECT chat_id, revoked_at FROM app.telegram_links")
    assert row == {"chat_id": "8002", "revoked_at": None}


async def test_qt_m18_05_blocked_user_link_revoked_and_nothing_sent(env: Env) -> None:
    shop = await env.shop("Bloklash", SystemRole.OWNER, SystemRole.MANAGER)
    await link(env, shop, "owner", 9001)
    await link(env, shop, "manager", 9002)
    port = FakeTelegram()
    # an alert is fanned out to both, then the owner blocks the manager before the delivery
    await record(
        env, shop.tenant_id, "low_stock", {"product_name": "Cola", "qty": "1.000", "min_stock": "5.000"}
    )
    sender_outcomes = await sweep(env, shop.tenant_id, FakeTelegram(fail_with="transient"))
    assert sorted(o.status for o in sender_outcomes) == ["fanned_out", "retry", "retry"]
    manager = shop.user_ids["manager"]
    blocked = await env.client.patch(
        f"{API}/admin/users/{manager}", json={"status": "blocked"}, headers=shop.h("owner")
    )
    assert blocked.status_code == 200, blocked.text
    [row] = await rows(
        env, shop.tenant_id, "SELECT revoked_at FROM app.telegram_links WHERE user_id = :u", u=manager
    )
    assert row["revoked_at"] is not None  # revoked in the blocking transaction
    await rows(env, shop.tenant_id, "UPDATE app.outbox_jobs SET next_run_at = now() WHERE status = 'retry'")
    outcomes = await sweep(env, shop.tenant_id, port)
    assert sorted(o.status for o in outcomes) == ["sent", "skipped"]
    assert port.to("9002") == [] and len(port.to("9001")) == 1
    # a new event goes only to the owner
    await record(env, shop.tenant_id, "low_stock", {"product_name": "Fanta"})
    await sweep(env, shop.tenant_id, port)
    assert port.to("9002") == [] and len(port.to("9001")) == 2


async def test_ep_69_70_settings_defaults_update_and_validation(env: Env) -> None:
    shop = await env.shop("Sozlama")
    got = (await env.client.get(SETTINGS, headers=shop.h(key=None))).json()["items"]
    assert [i["kind"] for i in got][:3] == ["daily_report", "low_stock", "expiry_soon"] and len(got) == len(
        KIND_ORDER
    )
    assert all(i["enabled"] for i in got)
    assert got[0]["time"] == "21:00" and all(i["time"] is None for i in got[1:])

    res = await set_setting(
        env, shop, [{"kind": "low_stock", "enabled": False}, {"kind": "daily_report", "enabled": True,
                                                              "time": "22:30"}]
    )  # fmt: skip
    assert res.status_code == 200, res.text
    items = {i["kind"]: i for i in res.json()["items"]}
    assert items["low_stock"]["enabled"] is False and items["daily_report"]["time"] == "22:30"
    # enabled toggle without time keeps the configured time
    res = await set_setting(env, shop, [{"kind": "daily_report", "enabled": False}])
    assert {i["kind"]: i for i in res.json()["items"]}["daily_report"] == {
        "kind": "daily_report",
        "enabled": False,
        "time": "22:30",
    }
    assert await scalar(
        env, shop.tenant_id,
        "SELECT count(*) FROM app.audit_log WHERE action = 'notification_settings_updated'",
    ) == 2  # fmt: skip

    def fields(response: Any) -> set[tuple[str, str]]:
        assert response.status_code == 422, response.text
        return {(d["field"], d["message_key"]) for d in response.json()["error"]["details"]}

    assert fields(await set_setting(env, shop, [{"kind": "nope", "enabled": True}])) == {
        ("items[0].kind", "validation.invalid_choice")
    }
    assert fields(
        await set_setting(env, shop, [{"kind": "low_stock", "enabled": True, "time": "21:00"}])
    ) == {("items[0].time", "validation.not_allowed")}
    assert fields(
        await set_setting(env, shop, [{"kind": "daily_report", "enabled": True, "time": "25:00"}])
    ) == {("items[0].time", "validation.invalid_format")}
    dup = [{"kind": "low_stock", "enabled": True}, {"kind": "low_stock", "enabled": False}]
    assert fields(await set_setting(env, shop, dup)) == {("items[1].kind", "validation.duplicate")}
    # idempotent replay
    key = "settings-replay-1"
    first = await env.client.patch(
        SETTINGS, json={"items": [{"kind": "cash_variance", "enabled": False}]}, headers=shop.h(key=key)
    )
    replay = await env.client.patch(
        SETTINGS, json={"items": [{"kind": "cash_variance", "enabled": False}]}, headers=shop.h(key=key)
    )
    assert first.status_code == replay.status_code == 200 and first.json() == replay.json()


async def test_ep_71_notifications_log_page(env: Env) -> None:
    shop = await env.shop("Jurnal")
    await link(env, shop, "owner", 9101)
    port = FakeTelegram()
    for name in ("A", "B", "C"):
        await record(env, shop.tenant_id, "low_stock", {"product_name": name})
    await sweep(env, shop.tenant_id, port)
    assert len(port.sent) == 3
    page = (await env.client.get(f"{LOG}?limit=2", headers=shop.h(key=None))).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    item = page["items"][0]
    assert {k: item[k] for k in ("channel", "recipient", "template", "status", "cost")} == {
        "channel": "telegram",
        "recipient": "9101",
        "template": "low_stock",
        "status": "sent",
        "cost": None,
    }
    rest = (
        await env.client.get(f"{LOG}?limit=2&cursor={page['next_cursor']}", headers=shop.h(key=None))
    ).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    ids = [UUID(i["id"]) for i in page["items"] + rest["items"]]
    assert ids == sorted(ids, reverse=True)
    assert (await env.client.get(f"{LOG}?status=failed", headers=shop.h(key=None))).json()["items"] == []
    assert (await env.client.get(f"{LOG}?cursor=%%%", headers=shop.h(key=None))).status_code == 422
