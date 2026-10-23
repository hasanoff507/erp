"""Telegram Bot API ``sendMessage`` adapter of the M18 sender (21 §11; D2: httpx, no bot framework).

Same bot and settings as the OTP channel (``ERP_TELEGRAM_BOT_TOKEN``, ``ERP_TELEGRAM_API_BASE_URL``, the
outbound HTTP client of ``auth.wiring.outbound_http``); unlike the OTP sender — which only needs "delivered
or not" to fall back to SMS — the outbox needs the failure class (21 §0): ``429``/5xx/network →
``transient`` (``retry_after`` kept), ``403`` or ``400 chat not found`` → ``blocked`` (the link becomes
inactive), ``401`` → ``auth``, any other 4xx → ``invalid``. The token is part of the URL path, so the URL
is never logged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import structlog

from app.modules.notifications.application.ports import TelegramSendResult
from app.modules.notifications.domain.render import MAX_TEXT

log = structlog.get_logger(__name__)

_GONE_MARKERS = ("chat not found", "user is deactivated", "bot was blocked", "bot was kicked")


class TelegramBotAdapter:
    def __init__(self, http: Callable[[], httpx.AsyncClient], *, token: str, base_url: str) -> None:
        self._http = http
        self._url = f"{base_url.rstrip('/')}/bot{token}/sendMessage"

    async def send_message(self, chat_id: str, text: str) -> TelegramSendResult:
        try:
            async with self._http() as client:
                response = await client.post(
                    self._url,
                    json={"chat_id": chat_id, "text": text[:MAX_TEXT], "disable_web_page_preview": True},
                )
            body: Any = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            return TelegramSendResult(False, "transient", type(exc).__name__)
        if not isinstance(body, dict):
            body = {}
        if response.status_code == 200 and body.get("ok") is True:
            return TelegramSendResult(True)
        description = str(body.get("description") or f"HTTP {response.status_code}")[:500]
        status = response.status_code
        log.warning("telegram_send_rejected", status=status, description=description)
        if status == 429 or status >= 500:
            params = body.get("parameters")
            retry_after = params.get("retry_after") if isinstance(params, dict) else None
            return TelegramSendResult(
                False, "transient", description, retry_after if isinstance(retry_after, int) else None
            )
        if status == 401:
            return TelegramSendResult(False, "auth", description)
        if status == 403 or any(marker in description.lower() for marker in _GONE_MARKERS):
            return TelegramSendResult(False, "blocked", description)
        return TelegramSendResult(False, "invalid", description)
