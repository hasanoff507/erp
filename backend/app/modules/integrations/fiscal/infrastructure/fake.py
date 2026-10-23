"""``FakeFiscalAdapter`` — the FM emulator behind ``ERP_FISCAL_PROVIDER=fake`` (21 §1; MVP/CI, never prod).

One :class:`~app.modules.integrations.fiscal.infrastructure.fm_emulator.FmEmulator` per cash register:
``terminal_id`` = ``ZZ`` + 12 digits derived from the register id (14 characters, QR ``t=\\w{14}``),
increasing
``fm_receipt_seq``, random 12-digit ``fiscal_sign``, a real-format ``qr_url``; the result is idempotent per
``fiscal_receipts.id`` (the provider idempotency key). The OFD ack is immediate while ``ack`` is true; with
``ack=False`` (network down) the FM still signs and the receipt waits in ``list_unsent`` until
``resend_unsent`` runs with ``ack`` true again (DoD-05).

Test knobs (instance attributes): ``fail`` — ``None`` | ``"transient"`` | ``"validation"`` | ``"auth"``;
``ack`` — the OFD link; ``device_state`` — the ``get_device_status`` answer (``ok`` by default);
``calls`` — every ``(method, receipt/register id)``.
"""

from __future__ import annotations

from uuid import UUID

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
from app.modules.integrations.fiscal.domain.boundary import BoundaryError, ResendResult, parse_acked, tiyin
from app.modules.integrations.fiscal.infrastructure.fm_emulator import FmEmulator


def terminal_id_for(register_id: UUID) -> str:
    return f"ZZ{register_id.int % 10**12:012d}"


class FakeFiscalAdapter:
    def __init__(self) -> None:
        self.fail: str | None = None
        self.ack = True
        self.device_state = "ok"
        self.calls: list[tuple[str, UUID]] = []
        self._fms: dict[UUID, FmEmulator] = {}

    def fm(self, register_id: UUID) -> FmEmulator:
        found = self._fms.get(register_id)
        if found is None:
            found = self._fms[register_id] = FmEmulator(terminal_id_for(register_id))
        found.online = self.ack
        return found

    def reset(self) -> None:
        self.fail, self.ack, self.device_state = None, True, "ok"
        self.calls.clear()
        self._fms.clear()

    def _result(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        if self.fail is not None:
            kind = self.fail if self.fail in ("transient", "auth", "validation") else "transient"
            raise FiscalProviderError(kind, f"fake fiscal module: {self.fail}")  # type: ignore[arg-type]
        try:  # the real adapters send tiyin; a malformed amount must fail here too
            amount = tiyin(receipt.body.get("total", "0"), "total")
        except BoundaryError as exc:
            raise FiscalProviderError("validation", str(exc)) from None
        try:
            signed = self.fm(receipt.register.id).sign(str(receipt.id), amount)
        except PermissionError as exc:  # the FM locked itself — retried until it is unlocked (21 §1)
            raise FiscalProviderError("transient", str(exc)) from None
        return FiscalResult(
            signed.terminal_id,
            signed.fm_receipt_seq,
            signed.fiscal_at,
            signed.fiscal_sign,
            signed.qr_url,
            signed.acked_at,
        )

    async def open_shift(self, register: CashRegisterRef) -> FiscalShiftResult:
        self.calls.append(("open_shift", register.id))
        fm = self.fm(register.id)
        return FiscalShiftResult(fm.terminal_id, fm.open_shift())

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
        status = self.fm(register.id).status()
        return FiscalDeviceStatus(
            fm_state=self.device_state,
            pending=status["pending_count"],
            oldest_unacked_at=status["oldest_unacked_at"],
        )

    async def list_unsent(self, register: CashRegisterRef) -> list[UnsentReceipt]:
        self.calls.append(("list_unsent", register.id))
        return [
            UnsentReceipt(r.fm_receipt_seq, r.fiscal_at, r.amount_tiyin)
            for r in self.fm(register.id).unsent()
        ]

    async def resend_unsent(self, register: CashRegisterRef) -> ResendResult:
        self.calls.append(("resend_unsent", register.id))
        if self.fail == "transient":
            raise FiscalProviderError("transient", "fake fiscal module: transient")
        raw = self.fm(register.id).resend()
        return ResendResult(raw["sent"], raw["failed"], parse_acked(raw["acked"]))
