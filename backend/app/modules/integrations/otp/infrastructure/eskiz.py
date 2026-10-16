"""Eskiz.uz SMS adapter (21 §10) — the fallback OTP channel only (qaror #34, 26 #45).

* ``POST /api/auth/login`` (email + password) → bearer token, cached in memory and renewed after
  25 days or on a ``401`` (one retry);
* ``POST /api/message/sms/send`` (``mobile_phone`` without ``+``, ``message``, ``from``);
* ``ERP_ESKIZ_TEST_MODE=true`` (until the Eskiz contract, 26 #45): Eskiz accepts only its fixed test
  text, so that text is sent instead of the real message — the code is **not** delivered by SMS in
  test mode (the delivery path, auth and limits are still exercised).

``send`` returns ``False`` on any provider/network failure; it never raises.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any, Final

import httpx
import structlog

log = structlog.get_logger(__name__)

ESKIZ_TEST_TEXT: Final = "Bu Eskiz dan test"
_TOKEN_TTL_S: Final = 25 * 86400


class EskizSmsSender:
    def __init__(
        self,
        http: Callable[[], httpx.AsyncClient],
        *,
        base_url: str,
        email: str | None,
        password: str | None,
        sender: str,
        test_mode: bool,
    ) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._sender = sender
        self.test_mode = test_mode
        self._token: str | None = None
        self._token_at = 0.0
        self._lock = asyncio.Lock()

    async def send(self, destination: str, text: str) -> bool:
        """``destination`` is the phone (``+998XXXXXXXXX``)."""
        if not self._email or not self._password:
            log.warning("eskiz_not_configured")
            return False
        message = ESKIZ_TEST_TEXT if self.test_mode else text
        if self.test_mode:
            log.warning("eskiz_test_mode_text_replaced")
        form = {"mobile_phone": destination.lstrip("+"), "message": message, "from": self._sender}
        for attempt in range(2):
            token = await self._bearer(force=attempt > 0)
            if token is None:
                return False
            try:
                async with self._http() as client:
                    response = await client.post(
                        f"{self._base}/api/message/sms/send",
                        data=form,
                        headers={"Authorization": f"Bearer {token}"},
                    )
            except httpx.HTTPError as exc:
                log.warning("eskiz_send_failed", error=type(exc).__name__)
                return False
            if response.status_code == 401 and attempt == 0:
                continue
            if response.status_code not in (200, 201):
                log.warning("eskiz_send_rejected", status=response.status_code)
                return False
            return True
        return False

    async def _bearer(self, *, force: bool) -> str | None:
        async with self._lock:
            fresh = self._token is not None and time.monotonic() - self._token_at < _TOKEN_TTL_S
            if fresh and not force:
                return self._token
            try:
                async with self._http() as client:
                    response = await client.post(
                        f"{self._base}/api/auth/login",
                        data={"email": self._email or "", "password": self._password or ""},
                    )
                body: Any = response.json() if response.content else {}
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("eskiz_login_failed", error=type(exc).__name__)
                return None
            data = body.get("data") if isinstance(body, dict) else None
            token = data.get("token") if isinstance(data, dict) else None
            if response.status_code != 200 or not isinstance(token, str) or not token:
                log.warning("eskiz_login_rejected", status=response.status_code)
                return None
            self._token, self._token_at = token, time.monotonic()
            return token
