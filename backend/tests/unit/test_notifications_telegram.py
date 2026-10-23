"""M18 pure parts: delivery policy, retry backoff (21 §11), message texts, Bot API error classes, settings guard."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.modules.notifications.domain.events import EVENT_KINDS
from app.modules.notifications.domain.policy import (
    AUDIENCE,
    KIND_ORDER,
    MAX_ATTEMPTS,
    backoff_seconds,
    daily_report_due,
    exhausted,
    local_now,
    parse_hhmm,
    retry_delay,
)
from app.modules.notifications.domain.render import fmt_money, lang_of, render, render_event
from app.modules.notifications.infrastructure.telegram_bot import TelegramBotAdapter
from app.modules.notifications.wiring import FakeTelegram, telegram_port


def test_every_event_kind_has_an_order_and_an_audience() -> None:
    assert set(KIND_ORDER) == EVENT_KINDS and len(KIND_ORDER) == len(EVENT_KINDS)
    assert set(AUDIENCE) == EVENT_KINDS
    assert AUDIENCE["low_stock"] == "stock.view"  # US-M04-02: the manager (stock.view) is notified


def test_21_11_retry_policy() -> None:
    assert [backoff_seconds(n) for n in range(1, 8)] == [10, 20, 40, 80, 160, 300, 300]
    assert retry_delay(1, 0.0) == timedelta(seconds=10)
    assert retry_delay(1, 1.0) == timedelta(seconds=11)  # 10 % jitter
    assert retry_delay(1, 0.0, retry_after_s=60) == timedelta(seconds=60)  # Telegram 429 retry_after
    assert retry_delay(6, 0.0, retry_after_s=5) == timedelta(seconds=300)
    assert not exhausted(MAX_ATTEMPTS - 1) and exhausted(MAX_ATTEMPTS) and MAX_ATTEMPTS == 10
    with pytest.raises(ValueError, match="attempts"):
        backoff_seconds(0)


def test_daily_report_time_rules() -> None:
    assert parse_hhmm("21:00") == time(21, 0) and parse_hhmm("09:05") == time(9, 5)
    for bad in ("24:00", "9:00", "21:60", "21-00", ""):
        assert parse_hhmm(bad) is None
    moment = local_now(datetime(2026, 10, 17, 16, 0, tzinfo=UTC))  # 21:00 Tashkent
    assert moment.hour == 21 and daily_report_due(moment, time(21, 0))
    assert not daily_report_due(moment, time(21, 1))


def test_texts_uz_ru_and_money_format() -> None:
    assert fmt_money("1234567.5", "uz") == "1 234 567.50 so'm"
    assert fmt_money("-20000", "ru") == "-20 000.00 сум"
    assert lang_of("ru-RU") == "ru" and lang_of(None) == "uz" and lang_of("uz") == "uz"
    payload = {"product_name": "Cola", "qty": "3.000", "min_stock": "5.000", "ignored": "x"}
    assert render_event("low_stock", payload, "uz", branch_name="Markaz") == (
        "⚠️ Kam qolgan tovar\nFilial: Markaz\nTovar: Cola\nQoldiq: 3\nMinimal chegara: 5"
    )
    assert render_event("low_stock", payload, "ru").startswith("⚠️ Заканчивается товар\nТовар: Cola")
    offline = render_event("offline_48h", {"stage": "40h"}, "uz")
    assert "40 soat (qizil)" in offline
    assert render("daily_report", {"report": {}}, "uz").startswith("📊 Kunlik hisobot")
    assert len(render_event("low_stock", {"product_name": "x" * 5000}, "uz")) == 4096


def _adapter(status: int, body: Any) -> TelegramBotAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/botTOKEN/sendMessage"
        return httpx.Response(status, json=body)

    return TelegramBotAdapter(
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        token="TOKEN",
        base_url="https://tg.test",
    )


@pytest.mark.parametrize(
    ("status", "body", "kind", "retry_after"),
    [
        (200, {"ok": True, "result": {}}, None, None),
        (
            429,
            {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 7}},
            "transient",
            7,
        ),
        (502, {"ok": False, "description": "Bad Gateway"}, "transient", None),
        (403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}, "blocked", None),
        (400, {"ok": False, "description": "Bad Request: chat not found"}, "blocked", None),
        (400, {"ok": False, "description": "Bad Request: message is too long"}, "invalid", None),
        (401, {"ok": False, "description": "Unauthorized"}, "auth", None),
    ],
)
async def test_bot_api_error_classes(
    status: int, body: Any, kind: str | None, retry_after: int | None
) -> None:
    result = await _adapter(status, body).send_message("1", "salom")
    assert result.ok is (kind is None)
    assert result.error_kind == kind and result.retry_after_s == retry_after


async def test_bot_api_network_error_is_transient() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    adapter = TelegramBotAdapter(
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(boom)), token="T", base_url="https://tg.test"
    )
    result = await adapter.send_message("1", "x")
    assert (result.ok, result.error_kind) == (False, "transient")


def test_fake_only_behind_setting_and_refused_in_prod() -> None:
    assert telegram_port(Settings(_env_file=None)) is None  # no token, no fake → not configured
    assert isinstance(telegram_port(Settings(_env_file=None, telegram_fake=True)), FakeTelegram)
    with pytest.raises(ValueError, match="ERP_TELEGRAM_FAKE"):
        Settings(_env_file=None, environment="prod", telegram_fake=True)
    with pytest.raises(ValueError, match="ERP_TELEGRAM_WEBHOOK_SECRET"):
        Settings(_env_file=None, environment="staging", telegram_bot_token="t", auth_secret="s" * 40)


def test_sec01_branch_restricted_recipient_skips_tenant_wide_debt_events() -> None:
    """SEC-01 / F7: ``debt_due_today`` / ``debt_aging_60`` list every debtor of the tenant — a member limited to
    some branches never gets them; branch events still follow the branch rule."""
    from uuid import uuid4

    from app.modules.notifications.application.ports import Recipient
    from app.modules.notifications.application.sender import TENANT_WIDE_KINDS, sees_branch

    branch = uuid4()
    everyone = Recipient(uuid4(), "1", "uz", (), None)
    restricted = Recipient(uuid4(), "2", "uz", (branch,), None)
    assert {"debt_due_today", "debt_aging_60"} == TENANT_WIDE_KINDS
    for kind in TENANT_WIDE_KINDS:
        assert sees_branch(everyone, None, kind)
        assert not sees_branch(restricted, None, kind)
    assert sees_branch(restricted, branch, "low_stock") and sees_branch(restricted, None, "low_stock")
    assert not sees_branch(restricted, uuid4(), "low_stock")


def test_b5_offline_stage_int_and_fm_locked_render_as_text() -> None:
    assert "40 soat (qizil)" in render_event("offline_48h", {"stage": 40}, "uz")
    assert "фискальный модуль заблокирован" in render_event("offline_48h", {"stage": "fm_locked"}, "ru")


def test_b5_agent_kinds_render_and_have_audience() -> None:
    text = render_event("onec_agent_paired", {"name": "DOKON-PC", "state": "connected"}, "uz")
    assert "Do'kon agenti" in text and "DOKON-PC" in text and "connected" in text
    assert "Предупреждение агента" in render_event("onec_base_error", {"reason": "machine_hash"}, "ru")
