"""Telegram Bot API ``sendMessage`` adapter (21 §11, §11.1) — the primary OTP channel (qaror #34).

``send`` never raises for a provider problem (bot blocked by the user, ``chat not found``,
network error, 5xx): it returns ``False`` and the caller falls back to SMS. The bot token is part
of the URL path, so the URL is never logged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

import httpx
import structlog

log = structlog.get_logger(__name__)

_MAX_TEXT: Final = 4096


class TelegramBotSender:
    def __init__(self, http: Callable[[], httpx.AsyncClient], *, token: str, base_url: str) -> None:
        self._http = http
        self._url = f"{base_url.rstrip('/')}/bot{token}/sendMessage"

    async def send(self, destination: str, text: str) -> bool:
        """``destination`` is the Telegram ``chat_id``."""
        try:
            async with self._http() as client:
                response = await client.post(
                    self._url, json={"chat_id": destination, "text": text[:_MAX_TEXT]}
                )
            body: Any = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("telegram_send_failed", error=type(exc).__name__)
            return False
        if response.status_code != 200 or not isinstance(body, dict) or body.get("ok") is not True:
            description = body.get("description") if isinstance(body, dict) else None
            log.warning("telegram_send_rejected", status=response.status_code, description=description)
            return False
        return True
