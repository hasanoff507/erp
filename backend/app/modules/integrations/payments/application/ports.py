"""Ports of the payments slice (23 §1): checkout repository, tenant lookup for webhooks, tenant secrets,
dynamic UzQR (21 §9.1) and Uzum Dynamic QR."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class CheckoutRow:
    checkout_ref: UUID
    tenant_id: UUID
    branch_id: UUID
    cash_register_id: UUID
    provider: str
    qr_type: str | None
    amount: Decimal
    provider_tx_id: str | None
    status: str
    confirmed_at: datetime | None
    expires_at: datetime
    created_at: datetime
    provider_data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegisterRow:
    id: UUID
    branch_id: UUID
    archived: bool


class CheckoutRepository(Protocol):
    """``app.payment_checkouts`` inside the caller's tenant transaction (RLS)."""

    async def register(self, s: AsyncSession, cash_register_id: UUID) -> RegisterRow | None: ...

    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> bool: ...

    async def get(self, s: AsyncSession, ref: UUID, *, for_update: bool = False) -> CheckoutRow | None: ...

    async def by_provider_tx(
        self, s: AsyncSession, provider: str, provider_tx_id: str, *, for_update: bool = False
    ) -> CheckoutRow | None: ...

    async def update(
        self,
        s: AsyncSession,
        ref: UUID,
        *,
        status: str | None = None,
        provider_tx_id: str | None = None,
        provider_data: Mapping[str, Any] | None = None,
        confirmed_at: datetime | None = None,
    ) -> None: ...

    async def payme_statement(self, s: AsyncSession, from_ms: int, to_ms: int) -> list[CheckoutRow]: ...

    async def expire_due(self, s: AsyncSession, now: datetime, limit: int) -> list[UUID]: ...


@dataclass(frozen=True, slots=True)
class RefOwner:
    tenant_id: UUID
    provider: str


class TenantLookup(Protocol):
    """Tenant-less webhook resolution through SECURITY DEFINER functions (12 §4.5)."""

    async def by_ref(self, ref: UUID) -> RefOwner | None: ...

    async def by_provider_tx(self, provider: str, provider_tx_id: str) -> UUID | None: ...

    async def by_credential(self, kind: str, lookup_hash: bytes) -> UUID | None: ...


class SecretSource(Protocol):
    """:class:`app.modules.integrations.tenant_keys.wiring.TenantSecretReader`."""

    async def get(
        self, s: AsyncSession, tenant_id: UUID, kind: str, *, cash_register_id: UUID | None = None
    ) -> dict[str, str] | None: ...

    async def record_result(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        kind: str,
        *,
        cash_register_id: UUID | None = None,
        error: str | None = None,
    ) -> None: ...


class PaymentProviderUnavailableError(Exception):
    """The provider answered with an error / did not answer (→ ``502 PAYMENT_PROVIDER_ERROR``)."""


# --- dynamic bank UzQR (21 §9.1; real POS API ⛔ 26 #49) ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class UzqrCheckout:
    provider_tx_id: str
    qr_payload: str
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UzqrTransaction:
    provider_tx_id: str
    status: Literal["pending", "paid", "failed"]
    amount_tiyin: int | None = None


@dataclass(frozen=True, slots=True)
class UzqrRefund:
    provider_tx_id: str
    status: Literal["refunded", "failed"]


class UzqrPort(Protocol):
    """``UzqrPort`` (21 §9.1) — per cash register API key (``tenant_secrets.cash_register_id``)."""

    async def create_dynamic_qr(
        self, secret: Mapping[str, str], register_id: UUID, amount_tiyin: int, order_id: str
    ) -> UzqrCheckout: ...

    async def check_transaction(self, secret: Mapping[str, str], provider_tx_id: str) -> UzqrTransaction: ...

    async def refund(
        self, secret: Mapping[str, str], provider_tx_id: str, amount_tiyin: int
    ) -> UzqrRefund: ...

    def webhook_transaction(self, headers: Mapping[str, str], body: bytes) -> UzqrTransaction | None:
        """Unverified parse — only to find the checkout (and so the register key)."""
        ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, secret: Mapping[str, str]) -> bool: ...


# --- Uzum Bank Dynamic QR (developer.uzumbank.uz/en/dynamicqr) --------------------------------------------


@dataclass(frozen=True, slots=True)
class UzumQrOrder:
    payment_id: str | None
    status: (
        str  # CREATED | SUCCESS | FAILED | HOLD | REVERSE_PENDING | REVERSED | PARTIAL_CANCELLED | CANCELLED
    )


class UzumQrPort(Protocol):
    async def create_order(self, secret: Mapping[str, str], order_id: str, amount_tiyin: int) -> str:
        """→ ``payment_link`` (the QR content)."""
        ...

    async def order_status(self, secret: Mapping[str, str], order_id: str) -> UzumQrOrder: ...
