"""Placeholder of the real fiscal adapters (``partner_cloud``, ``multikassa_local``, ``fiscaldrive_local``).

The real adapters are Bosqich 5 (21 §1, after the fiscal partner's answer). Until then every call is a
``transient`` failure — server-side receipts stay ``pending`` in the outbox (nothing is lost) and an
``unknown`` device state stays ``unknown`` (= locked, 18 §4.10).
"""

from __future__ import annotations

from app.modules.integrations.fiscal.application.ports import (
    CashRegisterRef,
    FiscalDeviceStatus,
    FiscalProviderError,
    FiscalReceiptPayload,
    FiscalResult,
    RefundInfo,
)


class UnavailableFiscalAdapter:
    def __init__(self, provider: str) -> None:
        self._provider = provider

    def _error(self) -> FiscalProviderError:
        return FiscalProviderError("transient", f"fiscal provider {self._provider!r} is Bosqich 5")

    async def register_sale(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        raise self._error()

    async def register_refund(self, receipt: FiscalReceiptPayload, refund_ref: RefundInfo) -> FiscalResult:
        raise self._error()

    async def close_shift(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        raise self._error()

    async def get_device_status(self, register: CashRegisterRef) -> FiscalDeviceStatus:
        return FiscalDeviceStatus(fm_state="unknown")
