"""Transfers between own branches (19 §13, 13 §2.9–§2.10, 16 §7). Pure Python.

* :func:`receive_pieces` — how a received quantity fills the issued pieces of a transfer line:
  pieces are filled **in allocation order**, the shortage is taken from the **tail**; a fully
  received piece carries its exact issued cost, a partly received one ``ROUND_HALF_UP(take ×
  cost / qty, 2)``. The shortage amount is always ``send cost − received cost`` (13 §2.10: the
  2970 credits equal the send debit to the tiyin).
* :func:`is_overdue` — QT-M06-05 "kechikkan" flag (``tenants.settings.transfer_overdue_hours``).
* offline sync payloads ``transfer.sent`` / ``transfer.received`` (19 §13, 16 §3 event list) —
  names and validators reserved for ``/sync/push`` (Bosqich 3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

from app.core.money import money, price, qty, to_decimal

TransportMode = Literal["vehicle", "on_foot_or_public"]
TRANSPORT_MODES: Final = ("vehicle", "on_foot_or_public")
STATUSES: Final = ("draft", "posted", "sent", "received", "discrepancy", "cancelled")
ETTN_STATUSES: Final = (
    "pending_signature",
    "sending",
    "registered",
    "received",
    "accepted",
    "rejected",
    "cancelled",
    "failed",
)
TRANSIT_ACCOUNT: Final = "2970"  # 13 §2.9 Yo'ldagi tovarlar
SHORTAGE_ACCOUNT: Final = "5910"  # 13 §2.10 kamomad
DEFAULT_OVERDUE_HOURS: Final = 48
ZERO_QTY: Final = Decimal("0.000")
ZERO_MONEY: Final = Decimal("0.00")

# offline sync event types (16 §3 "Yakuniy ro'yxat"); /sync/push wires them in Bosqich 3
EVENT_TRANSFER_SENT: Final = "transfer.sent"
EVENT_TRANSFER_RECEIVED: Final = "transfer.received"


@dataclass(frozen=True, slots=True)
class IssuedPiece:
    """One live issue move of a transfer line (sender side): ``qty > 0``, ``cost`` = its exact cost."""

    lot_id: UUID | None
    qty: Decimal
    cost: Decimal
    pending: bool


@dataclass(frozen=True, slots=True)
class ReceivedPiece:
    piece: IssuedPiece
    qty: Decimal
    amount: Decimal


@dataclass(frozen=True, slots=True)
class ReceivePlan:
    pieces: list[ReceivedPiece]
    send_cost: Decimal
    received_cost: Decimal

    @property
    def shortage_cost(self) -> Decimal:
        return money(self.send_cost - self.received_cost)


def receive_pieces(issued: Sequence[IssuedPiece], quantity: Decimal) -> ReceivePlan:
    """Fill ``quantity`` into the issued pieces in order (13 §2.10); the tail is the shortage."""
    quantity = qty(quantity)
    total_qty = sum((p.qty for p in issued), ZERO_QTY)
    if quantity < 0 or quantity > total_qty:
        raise ValueError(f"received quantity {quantity} outside 0..{total_qty}")
    send_cost = money(sum((p.cost for p in issued), ZERO_MONEY))
    need = quantity
    out: list[ReceivedPiece] = []
    for piece in issued:
        if need <= 0:
            break
        take = min(need, piece.qty)
        amount = piece.cost if take == piece.qty else money(to_decimal(piece.cost) * take / piece.qty)
        out.append(ReceivedPiece(piece, take, money(amount)))
        need -= take
    received = money(sum((r.amount for r in out), ZERO_MONEY))
    return ReceivePlan(out, send_cost, received)


def is_overdue(status: str, sent_at: datetime | None, now: datetime, hours: int) -> bool:
    """QT-M06-05: still "yo'lda" (``sent``) longer than the tenant's ``transfer_overdue_hours``."""
    return status == "sent" and sent_at is not None and now > sent_at + timedelta(hours=hours)


def overdue_hours(raw: object) -> int:
    """``tenants.settings.transfer_overdue_hours`` (1..720) with the default for missing/bad values."""
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_OVERDUE_HOURS
    return value if 1 <= value <= 720 else DEFAULT_OVERDUE_HOURS


def weighted_unit_cost(total_cost: Decimal, quantity: Decimal) -> Decimal:
    """``transfer_lines.unit_cost`` — the allocations' weighted average (4 dp)."""
    return price(total_cost / quantity) if quantity > 0 else Decimal("0.0000")


# --- offline sync payloads (19 §13 "Sync voqea payload'lari"; validators only — Bosqich 3) ---------
class EventPayloadError(ValueError):
    """An offline event payload is invalid: ``field`` + ``message_key`` → ``422 VALIDATION_ERROR``."""

    def __init__(self, field: str, message_key: str) -> None:
        super().__init__(f"{field}: {message_key}")
        self.field = field
        self.message_key = message_key


@dataclass(frozen=True, slots=True)
class SentLine:
    line_id: UUID
    product_id: UUID
    qty_sent: Decimal


@dataclass(frozen=True, slots=True)
class TransferSentEvent:
    """``transfer.sent``: a new document (``id`` … ``lines``) or an existing one (``transfer_id``)."""

    transfer_id: UUID | None
    id: UUID | None = None
    temp_number: str | None = None
    doc_date: date | None = None
    from_warehouse_id: UUID | None = None
    to_warehouse_id: UUID | None = None
    transport_mode: TransportMode = "vehicle"
    vehicle_plate: str | None = None
    lines: tuple[SentLine, ...] = ()


@dataclass(frozen=True, slots=True)
class ReceivedLine:
    transfer_line_id: UUID
    qty_received: Decimal


@dataclass(frozen=True, slots=True)
class TransferReceivedEvent:
    transfer_id: UUID
    lines: tuple[ReceivedLine, ...]


def _uuid(raw: Mapping[str, Any], key: str, field: str | None = None) -> UUID:
    name = field or key
    value = raw.get(key)
    if value is None:
        raise EventPayloadError(name, "validation.required")
    try:
        return UUID(str(value))
    except ValueError:
        raise EventPayloadError(name, "validation.uuid") from None


def _qty(raw: Mapping[str, Any], key: str, field: str, *, positive: bool) -> Decimal:
    value = raw.get(key)
    if not isinstance(value, str):
        raise EventPayloadError(field, "validation.decimal_string")
    try:
        parsed = to_decimal(value)
    except ValueError:
        raise EventPayloadError(field, "validation.decimal_string") from None
    if parsed != qty(parsed) or parsed < 0 or (positive and parsed == 0):
        raise EventPayloadError(field, "validation.positive" if positive else "validation.non_negative")
    return qty(parsed)


def _lines(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    lines = raw.get("lines")
    if not isinstance(lines, list) or not lines:
        raise EventPayloadError("lines", "validation.required")
    if not all(isinstance(x, Mapping) for x in lines):
        raise EventPayloadError("lines", "validation.object")
    return lines


def parse_transfer_sent(raw: Mapping[str, Any]) -> TransferSentEvent:
    """Validate a ``transfer.sent`` payload (permission ``transfer.create``)."""
    if "transfer_id" in raw and raw.get("transfer_id") is not None:
        extra = set(raw) - {"transfer_id"}
        if extra:
            raise EventPayloadError(sorted(extra)[0], "validation.unexpected")
        return TransferSentEvent(transfer_id=_uuid(raw, "transfer_id"))
    mode = raw.get("transport_mode", "vehicle")
    if mode not in TRANSPORT_MODES:
        raise EventPayloadError("transport_mode", "validation.enum")
    plate = raw.get("vehicle_plate")
    if plate is not None and (not isinstance(plate, str) or not plate.strip() or len(plate) > 32):
        raise EventPayloadError("vehicle_plate", "validation.string")
    try:
        doc_date = date.fromisoformat(str(raw.get("doc_date")))
    except ValueError:
        raise EventPayloadError("doc_date", "validation.date") from None
    temp = raw.get("temp_number")
    if temp is not None and (not isinstance(temp, str) or len(temp) > 64):
        raise EventPayloadError("temp_number", "validation.string")
    lines = tuple(
        SentLine(
            _uuid(ln, "line_id", f"lines[{i}].line_id"),
            _uuid(ln, "product_id", f"lines[{i}].product_id"),
            _qty(ln, "qty_sent", f"lines[{i}].qty_sent", positive=True),
        )
        for i, ln in enumerate(_lines(raw))
    )
    src, dst = _uuid(raw, "from_warehouse_id"), _uuid(raw, "to_warehouse_id")
    if src == dst:
        raise EventPayloadError("to_warehouse_id", "validation.same_warehouse")
    return TransferSentEvent(
        transfer_id=None,
        id=_uuid(raw, "id"),
        temp_number=temp,
        doc_date=doc_date,
        from_warehouse_id=src,
        to_warehouse_id=dst,
        transport_mode=mode,
        vehicle_plate=plate.strip() if isinstance(plate, str) else None,
        lines=lines,
    )


def parse_transfer_received(raw: Mapping[str, Any]) -> TransferReceivedEvent:
    """Validate a ``transfer.received`` payload (permission ``transfer.receive``)."""
    lines = tuple(
        ReceivedLine(
            _uuid(ln, "transfer_line_id", f"lines[{i}].transfer_line_id"),
            _qty(ln, "qty_received", f"lines[{i}].qty_received", positive=False),
        )
        for i, ln in enumerate(_lines(raw))
    )
    if len({ln.transfer_line_id for ln in lines}) != len(lines):
        raise EventPayloadError("lines", "validation.duplicate_line")
    return TransferReceivedEvent(_uuid(raw, "transfer_id"), lines)
