"""Public entry points of the OTP delivery adapters (23 §1 ``wiring.py``).

The auth module (and later notifications) builds its channel senders only through here. Every
sender has the same structural interface: ``async send(destination, text) -> bool`` — ``False``
means "not delivered, try the next channel" (14 §4.2).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.modules.integrations.otp.infrastructure.eskiz import ESKIZ_TEST_TEXT, EskizSmsSender
from app.modules.integrations.otp.infrastructure.fakes import FakeMessage, FakeOutbox, FakeSender
from app.modules.integrations.otp.infrastructure.telegram import TelegramBotSender

__all__ = [
    "ESKIZ_TEST_TEXT",
    "EskizSmsSender",
    "FakeMessage",
    "FakeOutbox",
    "FakeSender",
    "TelegramBotSender",
    "build_eskiz_sender",
    "build_telegram_sender",
]


def build_telegram_sender(
    http: Callable[[], httpx.AsyncClient], *, token: str, base_url: str
) -> TelegramBotSender:
    return TelegramBotSender(http, token=token, base_url=base_url)


def build_eskiz_sender(
    http: Callable[[], httpx.AsyncClient],
    *,
    base_url: str,
    email: str | None,
    password: str | None,
    sender: str,
    test_mode: bool,
) -> EskizSmsSender:
    return EskizSmsSender(
        http, base_url=base_url, email=email, password=password, sender=sender, test_mode=test_mode
    )
