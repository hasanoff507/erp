"""``partner_cloud`` — FiscalPort over a fiscal partner's cloud API (21 §1 "Hamkor bulut"; qaror #21).

The partner's wire protocol is **not public** (26 #109, #89, #169): this module fixes only our side of the
boundary — :class:`PartnerCloudClient` speaks the 21 §16.1 schemas (``FiscalReceiptPayload`` in integer tiyin,
``FiscalResult``, ``FiscalDeviceStatus``, ``UnsentReceipt``, ``ResendResult``, ``ZReport``) and the vendor
mapping lives in the client. Clients:

* :class:`FakePartnerCloud` — FM emulator per register (``ERP_FISCAL_PARTNER_FAKE``, refused in prod) — the
  contract-test target until the partner answers;
* :class:`UnavailablePartnerCloud` — the real client is ⛔ 26 #109: every call is ``transient`` (receipts
  stay ``pending`` in the outbox, nothing is lost; ``unknown`` device state = locked).

:class:`PartnerCloudFiscalAdapter` converts at the boundary (decimal strings → tiyin, :func:`port_payload`),
validates the partner's answer (terminal id, 12-digit sign) and maps errors to ``FiscalProviderError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
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
from app.modules.integrations.fiscal.domain.boundary import (
    BoundaryError,
    ResendResult,
    fiscal_sign,
    fm_state_of,
    parse_acked,
    parse_ts,
    port_payload,
    terminal_id,
)
from app.modules.integrations.fiscal.domain.rules import payment_form
from app.modules.integrations.fiscal.infrastructure.fake import terminal_id_for
from app.modules.integrations.fiscal.infrastructure.fm_emulator import FmEmulator


class PartnerCloudClient(Protocol):
    """Our side of the partner boundary — bodies are the 21 §16.1 schemas; ``key`` is the idempotency key
    (``fiscal_receipts.id``): a repeated call returns the first result."""

    async def open_shift(self, register: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def sale(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def refund(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def close_shift(self, key: str, register: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def device_status(self, register: Mapping[str, Any]) -> Mapping[str, Any]: ...

    async def unsent(self, register: Mapping[str, Any]) -> list[Mapping[str, Any]]: ...

    async def resend(self, register: Mapping[str, Any]) -> Mapping[str, Any]: ...


def _ref(register: CashRegisterRef) -> dict[str, Any]:
    return {"cash_register_id": str(register.id), "local_id": register.fiscal_module_id}


def _form(body: Mapping[str, Any]) -> str | None:
    methods = [str(p.get("method")) for p in body.get("payments") or ()]
    try:
        return payment_form(methods)
    except ValueError:
        return None


def _result(raw: Mapping[str, Any]) -> FiscalResult:
    try:
        seq = int(str(raw["fm_receipt_seq"]))
        acked = raw.get("acked_at")
        return FiscalResult(
            terminal_id(raw.get("fm_terminal_id"), "fm_terminal_id"),
            seq,
            parse_ts(raw.get("fiscal_at"), "fiscal_at"),
            fiscal_sign(raw.get("fiscal_sign"), "fiscal_sign"),
            str(raw["qr_url"]),
            parse_ts(acked, "acked_at") if acked else None,
        )
    except (BoundaryError, KeyError, ValueError) as exc:
        raise FiscalProviderError("validation", f"partner answer: {exc}") from None


class PartnerCloudFiscalAdapter:
    def __init__(self, client: PartnerCloudClient) -> None:
        self._client = client

    def _payload(self, receipt: FiscalReceiptPayload, refund: RefundInfo | None = None) -> dict[str, Any]:
        info = None
        if refund is not None:
            info = {
                "fm_terminal_id": refund.terminal_id,
                "fm_receipt_seq": refund.receipt_seq,
                "fiscal_sign": refund.fiscal_sign,
            }
        try:
            return port_payload(
                kind=receipt.kind,
                cash_register_id=str(receipt.register.id),
                local_id=receipt.register.fiscal_module_id,
                receipt_seq=receipt.receipt_seq,
                body=receipt.body,
                payment_form=_form(receipt.body),
                refund_info=info,
            )
        except BoundaryError as exc:
            raise FiscalProviderError("validation", str(exc)) from None

    async def open_shift(self, register: CashRegisterRef) -> FiscalShiftResult:
        raw = await self._client.open_shift(_ref(register))
        try:
            return FiscalShiftResult(
                terminal_id(raw.get("fm_terminal_id"), "fm_terminal_id"),
                parse_ts(raw.get("opened_at"), "opened_at"),
            )
        except BoundaryError as exc:
            raise FiscalProviderError("validation", f"partner answer: {exc}") from None

    async def register_sale(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        return _result(await self._client.sale(str(receipt.id), self._payload(receipt)))

    async def register_refund(self, receipt: FiscalReceiptPayload, refund_ref: RefundInfo) -> FiscalResult:
        return _result(await self._client.refund(str(receipt.id), self._payload(receipt, refund_ref)))

    async def close_shift(self, receipt: FiscalReceiptPayload) -> FiscalResult:
        raw = await self._client.close_shift(str(receipt.id), _ref(receipt.register))
        try:
            closed = parse_ts(raw.get("closed_at"), "closed_at")
            term = terminal_id(raw.get("fm_terminal_id"), "fm_terminal_id")
            z = int(str(raw["z_number"]))
        except (BoundaryError, KeyError, ValueError) as exc:
            raise FiscalProviderError("validation", f"partner answer: {exc}") from None
        sign = str(raw.get("fiscal_sign") or f"{z:012d}")
        return FiscalResult(term, z, closed, sign, str(raw.get("qr_url") or ""), closed)

    async def get_device_status(self, register: CashRegisterRef) -> FiscalDeviceStatus:
        raw = await self._client.device_status(_ref(register))
        oldest = raw.get("oldest_unacked_at")
        return FiscalDeviceStatus(
            fm_state=fm_state_of(raw.get("fm_state")),
            pending=int(raw.get("pending_count") or 0),
            oldest_unacked_at=parse_ts(oldest, "oldest_unacked_at") if oldest else None,
        )

    async def list_unsent(self, register: CashRegisterRef) -> list[UnsentReceipt]:
        return [
            UnsentReceipt(
                int(r["fm_receipt_seq"]), parse_ts(r["fiscal_at"], "fiscal_at"), int(r["amount_tiyin"])
            )
            for r in await self._client.unsent(_ref(register))
        ]

    async def resend_unsent(self, register: CashRegisterRef) -> ResendResult:
        raw = await self._client.resend(_ref(register))
        try:
            return ResendResult(
                int(raw.get("sent", 0)), int(raw.get("failed", 0)), parse_acked(raw.get("acked"))
            )
        except (BoundaryError, ValueError) as exc:
            raise FiscalProviderError("validation", f"partner answer: {exc}") from None


class FakePartnerCloud:
    """In-memory partner cloud: one :class:`FmEmulator` per register; ``online`` — the partner ↔ OFD link;
    ``fail`` — ``None`` | ``"transient"`` | ``"auth"`` | ``"validation"``; ``payloads`` — what was
    received."""

    def __init__(self) -> None:
        self.online = True
        self.fail: str | None = None
        self.payloads: list[tuple[str, Mapping[str, Any]]] = []
        self._fms: dict[str, FmEmulator] = {}

    def fm(self, register: Mapping[str, Any]) -> FmEmulator:
        key = str(register["cash_register_id"])
        found = self._fms.get(key)
        if found is None:
            found = self._fms[key] = FmEmulator(terminal_id_for(UUID(key)))
        found.online = self.online
        return found

    def _check(self) -> None:
        if self.fail is not None:
            raise FiscalProviderError(self.fail, f"fake partner cloud: {self.fail}")  # type: ignore[arg-type]

    def _sign(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self._check()
        total = payload.get("total_tiyin")
        if not isinstance(total, int) or isinstance(total, bool):
            raise FiscalProviderError("validation", "total_tiyin must be an integer (21 §16.1)")
        self.payloads.append((key, payload))
        try:
            s = self.fm(payload["cash_register"]).sign(key, total)
        except PermissionError as exc:
            raise FiscalProviderError("transient", str(exc)) from None
        return {
            "fm_terminal_id": s.terminal_id,
            "fm_receipt_seq": s.fm_receipt_seq,
            "fiscal_sign": s.fiscal_sign,
            "qr_url": s.qr_url,
            "fiscal_at": s.fiscal_at.isoformat(),
            "acked_at": s.acked_at.isoformat() if s.acked_at else None,
        }

    async def open_shift(self, register: Mapping[str, Any]) -> Mapping[str, Any]:
        self._check()
        fm = self.fm(register)
        return {"fm_terminal_id": fm.terminal_id, "opened_at": fm.open_shift().isoformat()}

    async def sale(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._sign(key, payload)

    async def refund(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not payload.get("refund_info"):
            raise FiscalProviderError("validation", "refund_info is required for a refund (21 §1)")
        return self._sign(key, payload)

    async def close_shift(self, key: str, register: Mapping[str, Any]) -> Mapping[str, Any]:
        self._check()
        z = self.fm(register).close_shift()
        return {**z, "closed_at": z["closed_at"].isoformat()}

    async def device_status(self, register: Mapping[str, Any]) -> Mapping[str, Any]:
        self._check()
        return self.fm(register).status()

    async def unsent(self, register: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        self._check()
        return [
            {"fm_receipt_seq": r.fm_receipt_seq, "fiscal_at": r.fiscal_at, "amount_tiyin": r.amount_tiyin}
            for r in self.fm(register).unsent()
        ]

    async def resend(self, register: Mapping[str, Any]) -> Mapping[str, Any]:
        self._check()
        return self.fm(register).resend()


class UnavailablePartnerCloud:
    """The real partner client — ⛔ 26 #109 (protocol not public). Every call is ``transient``."""

    def _error(self) -> FiscalProviderError:
        return FiscalProviderError("transient", "fiscal partner cloud API is not available yet (26 #109)")

    async def open_shift(self, register: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._error()

    async def sale(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._error()

    async def refund(self, key: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._error()

    async def close_shift(self, key: str, register: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._error()

    async def device_status(self, register: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"fm_state": "unknown", "pending_count": 0, "oldest_unacked_at": None}

    async def unsent(self, register: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        raise self._error()

    async def resend(self, register: Mapping[str, Any]) -> Mapping[str, Any]:
        raise self._error()


__all__ = [
    "FakePartnerCloud",
    "PartnerCloudClient",
    "PartnerCloudFiscalAdapter",
    "UnavailablePartnerCloud",
]
