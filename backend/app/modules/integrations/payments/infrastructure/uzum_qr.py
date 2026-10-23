"""Uzum Bank Dynamic QR client (https://developer.uzumbank.uz/en/dynamicqr/ — «QR CRM Scan Specification»).

``POST /api/dynamic-qr/merchant/payment/create`` ``{amount (tiyin), order_id, service_id}`` →
``payment_link``; ``POST /api/dynamic-qr/merchant/payment/status-by-order`` ``{order_id, service_id}`` →
``payment_id``, ``payment_status``. Header
``Authorization: <merchant_service_user_id>:sha1(timestamp + secret_key):<timestamp>`` (timestamp — UNIX ms).
Every method answers HTTP 200 with ``error_code`` (0 = success). Credentials come from the tenant's
``uzum`` secret (``dynamic_qr_service_id``, ``dynamic_qr_user_id``, ``dynamic_qr_secret_key``).
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import structlog

from app.modules.integrations.payments.application.ports import PaymentProviderUnavailableError, UzumQrOrder

log = structlog.get_logger(__name__)

CREATE_PATH = "/api/dynamic-qr/merchant/payment/create"
STATUS_PATH = "/api/dynamic-qr/merchant/payment/status-by-order"


def authorization(user_id: str, secret_key: str, timestamp_ms: int) -> str:
    digest = hashlib.sha1(f"{timestamp_ms}{secret_key}".encode(), usedforsecurity=False).hexdigest()
    return f"{user_id}:{digest}:{timestamp_ms}"


class UzumDynamicQrClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._transport = transport
        self._clock_ms = clock_ms

    async def _call(self, secret: Mapping[str, str], path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": authorization(secret["dynamic_qr_user_id"], secret["dynamic_qr_secret_key"],
                                           self._clock_ms()),
            "Content-Type": "application/json", "Accept": "application/json",
        }  # fmt: skip
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(self._base + path, json=body, headers=headers)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("uzum_qr_unreachable", path=path, error=type(exc).__name__)
            raise PaymentProviderUnavailableError("uzum dynamic QR unreachable") from exc
        if response.status_code != 200 or not isinstance(data, dict) or data.get("error_code") != 0:
            code = data.get("error_code") if isinstance(data, dict) else None
            log.warning("uzum_qr_error", path=path, status=response.status_code, error_code=code)
            raise PaymentProviderUnavailableError(f"uzum dynamic QR error {code}")
        return data

    async def create_order(self, secret: Mapping[str, str], order_id: str, amount_tiyin: int) -> str:
        data = await self._call(secret, CREATE_PATH, {
            "amount": amount_tiyin, "order_id": order_id, "service_id": int(secret["dynamic_qr_service_id"]),
        })  # fmt: skip
        link = data.get("payment_link")
        if not isinstance(link, str) or not link:
            raise PaymentProviderUnavailableError("uzum dynamic QR: no payment_link")
        return link

    async def order_status(self, secret: Mapping[str, str], order_id: str) -> UzumQrOrder:
        data = await self._call(secret, STATUS_PATH, {
            "order_id": order_id, "service_id": int(secret["dynamic_qr_service_id"]),
        })  # fmt: skip
        payment_id = data.get("payment_id")
        return UzumQrOrder(
            payment_id=str(payment_id) if payment_id else None,
            status=str(data.get("payment_status") or "CREATED"),
        )
