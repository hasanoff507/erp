"""``FakeFiscalAdapter`` — the FM emulator of ``ERP_FISCAL_PROVIDER=fake`` (21 §1, MVP code; never in prod).

``terminal_id`` = ``ZZ`` + 12 digits derived from the register id (14 characters, QR ``t=\\w{14}``),
increasing ``fm_receipt_seq`` (monotonic, seeded from the clock so a restart never repeats a number),
random 12-digit ``fiscal_sign``, a real-format ``qr_url`` and an immediate OFD ack.

Test knobs (instance attributes): ``fail`` — ``None`` | ``"transient"`` | ``"validation"`` | ``"auth"``;
``ack`` — ``False`` keeps receipts un-acknowledged (48 h scenarios); ``device_state`` — the
``get_device_status`` answer (``ok`` by default); ``calls`` — every ``(method, receipt id)``.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime
from uuid import UUID

from app.core.money import to_tiyin
from app.modules.integrations.fiscal.application.ports import (
    CashRegisterRef,
    FiscalDeviceStatus,
    FiscalProviderError,
    FiscalReceiptPayload,
    FiscalResult,
    RefundInfo,
)
from app.modules.integrations.fiscal.domain.rules import qr_url


def terminal_id_for(register_id: UUID) -> str:
    return f"ZZ{register_id.int % 10**12:012d}"


class FakeFiscalAdapter:
    _last_seq = int(time.time() * 1000)

    def __init__(self) -> None:
        self.fail: str | None = None
        self.ack = True
        self.device_state = "ok"
        self.calls: list[tuple[str, UUID]] = []

    @classmethod
    def _next_seq(cls) -> int:
        cls._last_seq = max(cls._last_seq + 1, int(time.time() * 1000))
        return cls._last_seq

    def _result(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        if self.fail is not None:
            kind = self.fail if self.fail in ("transient", "auth", "validation") else "transient"
            raise FiscalProviderError(kind, f"fake fiscal module: {self.fail}")  # type: ignore[arg-type]
        total = receipt.body.get("total")
        if total is not None:
            to_tiyin(str(total))  # the real adapters send tiyin; a malformed amount must fail here too
        now = datetime.now(UTC).replace(microsecond=0)
        terminal = terminal_id_for(receipt.register.id)
        seq = self._next_seq()
        sign = f"{secrets.randbelow(10**12):012d}"
        return FiscalResult(
            terminal, seq, now, sign, qr_url(terminal, seq, now, sign), now if self.ack else None
        )

    async def register_sale(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        self.calls.append(("register_sale", receipt.id))
        return self._result(receipt)

    async def register_refund(self, receipt: FiscalReceiptPayload, refund_ref: RefundInfo) -> FiscalResult:
        self.calls.append(("register_refund", receipt.id))
        return self._result(receipt)

    async def close_shift(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        self.calls.append(("close_shift", receipt.id))
        return self._result(receipt)

    async def get_device_status(self, register: CashRegisterRef) -> FiscalDeviceStatus:
        self.calls.append(("get_device_status", register.id))
        return FiscalDeviceStatus(fm_state=self.device_state)
