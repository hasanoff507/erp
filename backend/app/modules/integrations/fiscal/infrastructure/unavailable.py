"""Server side of the local-bridge providers (``multikassa_local``, ``fiscaldrive_local``; 21 §1, §16).

In local-bridge mode the FM signs on the device (POS → Do'kon agenti → FM) and the result arrives with the POS
event (``fiscal_result``, qaror #68); the server never calls the FM itself — state and OFD acks come from the
``fiscal.*`` agent tasks. Every server-side call is therefore refused (``validation`` → a stray ``ofd_send``
job fails instead of looping) and the device state stays ``unknown`` (= locked) until the agent reports.
"""

from __future__ import annotations

from app.modules.integrations.fiscal.application.ports import (
    CashRegisterRef,
    FiscalDeviceStatus,
    FiscalProviderError,
    FiscalReceiptPayload,
    FiscalResult,
    FiscalShiftResult,
    RefundInfo,
    UnsentReceipt,
)
from app.modules.integrations.fiscal.domain.boundary import ResendResult


class LocalBridgeServerAdapter:
    def __init__(self, provider: str) -> None:
        self._provider = provider

    def _error(self) -> FiscalProviderError:
        return FiscalProviderError(
            "validation",
            f"{self._provider}: the FM signs on the device; the server only accepts fiscal_result",
        )

    async def open_shift(self, register: CashRegisterRef) -> FiscalShiftResult:
        raise self._error()

    async def register_sale(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        raise self._error()

    async def register_refund(self, receipt: FiscalReceiptPayload, refund_ref: RefundInfo) -> FiscalResult:
        raise self._error()

    async def close_shift(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        raise self._error()

    async def get_device_status(self, register: CashRegisterRef) -> FiscalDeviceStatus:
        return FiscalDeviceStatus(fm_state="unknown")

    async def list_unsent(self, register: CashRegisterRef) -> list[UnsentReceipt]:
        raise self._error()

    async def resend_unsent(self, register: CashRegisterRef) -> ResendResult:
        raise self._error()
