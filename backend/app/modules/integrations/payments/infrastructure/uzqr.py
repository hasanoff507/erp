"""Dynamic bank UzQR adapters (21 §9.1, ``UzqrPort``).

The UzQR POS API specification is not public (CBU MUNIS / acquiring bank — 26 #49), so there is **no real
adapter**: :class:`UzqrStubAdapter` (default, ``ERP_UZQR_PROVIDER=stub``) refuses every dynamic checkout
(``PAYMENT_PROVIDER_ERROR`` — the cashier uses static UzQR or another method), and :class:`FakeUzqrAdapter`
(``ERP_UZQR_PROVIDER=fake``, local/test only, refused in prod) is an emulator with its **own** test protocol —
not a vendor wire format: QR ``uzqr-fake://pay?…``, webhook JSON ``{provider_tx_id, status, amount_tiyin}``
signed with ``X-Fake-Uzqr-Signature: hex(HMAC-SHA256(api_key, body))``. The contract tests
(``test_contract_uzqr_*``) run against the fake and are ready for the real adapter.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Final, Literal
from urllib.parse import urlencode
from uuid import UUID, uuid4

from app.modules.integrations.payments.application.ports import (
    PaymentProviderUnavailableError,
    UzqrCheckout,
    UzqrRefund,
    UzqrTransaction,
)

FAKE_SIGNATURE_HEADER: Final = "x-fake-uzqr-signature"


class UzqrStubAdapter:
    """Dynamic UzQR is off until the POS API arrives (26 #49)."""

    async def create_dynamic_qr(
        self, secret: Mapping[str, str], register_id: UUID, amount_tiyin: int, order_id: str
    ) -> UzqrCheckout:
        raise PaymentProviderUnavailableError("dynamic UzQR POS API is not available (26 #49)")

    async def check_transaction(self, secret: Mapping[str, str], provider_tx_id: str) -> UzqrTransaction:
        raise PaymentProviderUnavailableError("dynamic UzQR POS API is not available (26 #49)")

    async def refund(self, secret: Mapping[str, str], provider_tx_id: str, amount_tiyin: int) -> UzqrRefund:
        raise PaymentProviderUnavailableError("dynamic UzQR POS API is not available (26 #49)")

    def webhook_transaction(self, headers: Mapping[str, str], body: bytes) -> UzqrTransaction | None:
        return None

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, secret: Mapping[str, str]) -> bool:
        return False


def fake_signature(api_key: str, body: bytes) -> str:
    return hmac.new(api_key.encode("utf-8"), body, hashlib.sha256).hexdigest()


class FakeUzqrAdapter:
    """In-process emulator: deterministic per call, keeps the transactions it issued (tests, dev)."""

    def __init__(self) -> None:
        self._issued: dict[str, tuple[int, str]] = {}  # provider_tx_id → (amount_tiyin, status)

    async def create_dynamic_qr(
        self, secret: Mapping[str, str], register_id: UUID, amount_tiyin: int, order_id: str
    ) -> UzqrCheckout:
        if not secret.get("api_key"):
            raise PaymentProviderUnavailableError("no dynamic QR api_key for this register")
        tx = f"fake-uzqr-{uuid4().hex}"
        self._issued[tx] = (amount_tiyin, "pending")
        query = urlencode({"m": secret.get("merchant_id", ""), "t": secret.get("terminal_id", ""), "tx": tx,
                           "a": amount_tiyin, "o": order_id})  # fmt: skip
        return UzqrCheckout(provider_tx_id=tx, qr_payload=f"uzqr-fake://pay?{query}")

    async def check_transaction(self, secret: Mapping[str, str], provider_tx_id: str) -> UzqrTransaction:
        amount, status = self._issued.get(provider_tx_id, (None, "failed"))
        state: Literal["pending", "paid", "failed"] = (
            "paid" if status == "paid" else "pending" if amount is not None else "failed"
        )
        return UzqrTransaction(provider_tx_id, state, amount)

    async def refund(self, secret: Mapping[str, str], provider_tx_id: str, amount_tiyin: int) -> UzqrRefund:
        issued = self._issued.get(provider_tx_id)
        ok = issued is not None and issued[1] == "paid" and amount_tiyin <= issued[0]
        return UzqrRefund(provider_tx_id, "refunded" if ok else "failed")

    def mark_paid(self, provider_tx_id: str) -> None:
        amount, _ = self._issued[provider_tx_id]
        self._issued[provider_tx_id] = (amount, "paid")

    @staticmethod
    def webhook_body(provider_tx_id: str, status: str, amount_tiyin: int | None) -> bytes:
        return json.dumps(
            {"provider_tx_id": provider_tx_id, "status": status, "amount_tiyin": amount_tiyin}
        ).encode()

    def webhook_transaction(self, headers: Mapping[str, str], body: bytes) -> UzqrTransaction | None:
        try:
            raw = json.loads(body)
        except ValueError:
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("provider_tx_id"), str):
            return None
        status = raw.get("status")
        if status not in ("paid", "failed", "pending"):
            return None
        amount = raw.get("amount_tiyin")
        return UzqrTransaction(raw["provider_tx_id"], status, amount if isinstance(amount, int) else None)

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, secret: Mapping[str, str]) -> bool:
        key = secret.get("api_key")
        given = headers.get(FAKE_SIGNATURE_HEADER, "")
        return bool(key) and hmac.compare_digest(given.encode(), fake_signature(key or "", body).encode())
