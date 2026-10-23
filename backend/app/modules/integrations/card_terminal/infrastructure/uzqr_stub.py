"""``UzqrStubAdapter`` (21 §9.1 "MVP — dinamik QR o'chiq"): every call raises :class:`UzqrDisabledError`."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.modules.integrations.card_terminal.application.uzqr import (
    CheckoutResult,
    RefundResult,
    TransactionStatus,
    UzqrDisabledError,
)


class UzqrStubAdapter:
    async def create_dynamic_qr(self, register_id: UUID, amount: Decimal, order_id: str) -> CheckoutResult:
        raise UzqrDisabledError("dynamic UzQR is not enabled (Bosqich 5)")

    async def check_transaction(self, provider_tx_id: str) -> TransactionStatus:
        raise UzqrDisabledError("dynamic UzQR is not enabled (Bosqich 5)")

    async def refund(self, provider_tx_id: str, amount: Decimal) -> RefundResult:
        raise UzqrDisabledError("dynamic UzQR is not enabled (Bosqich 5)")
