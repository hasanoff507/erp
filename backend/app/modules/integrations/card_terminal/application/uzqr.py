"""``UzqrPort`` (21 §9.1) — dynamic bank UzQR checkout. Bosqich 3 ships only the contract and a stub
(``UzqrStubAdapter``): dynamic UzQR, ``/payments/checkouts`` and webhooks are Bosqich 5 (26 #49, PLAN D4);
static UzQR needs no port (the cashier confirms it — sales module)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    provider_tx_id: str
    qr_payload: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TransactionStatus:
    provider_tx_id: str
    status: Literal["pending", "confirmed", "failed", "expired"]
    amount: Decimal | None = None


@dataclass(frozen=True, slots=True)
class RefundResult:
    provider_tx_id: str
    status: Literal["refunded", "failed"]


class UzqrDisabledError(Exception):
    """Dynamic UzQR is not available (stub adapter) — callers offer another payment method."""


class UzqrPort(Protocol):
    async def create_dynamic_qr(
        self, register_id: UUID, amount: Decimal, order_id: str
    ) -> CheckoutResult: ...

    async def check_transaction(self, provider_tx_id: str) -> TransactionStatus: ...

    async def refund(self, provider_tx_id: str, amount: Decimal) -> RefundResult: ...
