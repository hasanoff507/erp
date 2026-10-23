"""The FiscalPort / agent wire boundary (21 §1, §16, §16.1; qaror #12, #26, #68). Pure Python.

* :func:`port_payload` — ``fiscal_receipts.payload`` (decimal strings) → the 21 §16.1 ``FiscalReceiptPayload``
  in **integer tiyin** (``int64``) and milli-units; the single conversion point of the server side;
* :func:`fm_state_of` — any reported state → the ``cash_registers.fm_state`` enum (partner codes are mapped
  in the agent/adapter; an unknown value is ``unknown`` = locked, 18 §4.10);
* :func:`parse_status_result` / :func:`parse_resend_result` / :func:`parse_zreport_result` — the result
  bodies of the ``fiscal.status`` / ``fiscal.resend_unsent`` / ``fiscal.zreport`` agent tasks (21 §16 table,
  34 §14.3). Malformed input raises :class:`BoundaryError` (field, message key).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Final

from app.modules.integrations.fiscal.domain.rules import payment_method_form

FM_STATES: Final = frozenset({"ok", "locked", "ack_overdue", "memory_full", "unknown"})
LOCKED_STATES: Final = frozenset({"locked", "ack_overdue", "memory_full"})
MAX_INT64: Final = 2**63 - 1
_TERMINAL: Final = re.compile(r"^[A-Za-z0-9]{1,64}$")
_SIGN: Final = re.compile(r"^\d{12}$")


class BoundaryError(ValueError):
    def __init__(self, field: str, message_key: str) -> None:
        super().__init__(f"{field}: {message_key}")
        self.field = field
        self.message_key = message_key


# --- decimal → tiyin -----------------------------------------------------------------------------------
def _dec(raw: object, field: str) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise BoundaryError(field, "validation.decimal_parsing") from None
    if not value.is_finite():
        raise BoundaryError(field, "validation.decimal_parsing")
    return value


def tiyin(raw: object, field: str = "amount") -> int:
    """``"12000.00"`` → ``1200000``; more than 2 decimals is rounded HALF_UP (prices are NUMERIC(18,4))."""
    try:
        value = int((_dec(raw, field) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        raise BoundaryError(field, "validation.int64_overflow") from None
    if abs(value) > MAX_INT64:
        raise BoundaryError(field, "validation.int64_overflow")
    return value


def milli(raw: object, field: str = "qty") -> int:
    """``"2.000"`` → ``2000`` (qty × 1000, the 21 §16.1 ``qty_milli``)."""
    try:
        return int((_dec(raw, field) * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        raise BoundaryError(field, "validation.int64_overflow") from None


def _form(method: str) -> str | None:
    return payment_method_form(method)


def port_payload(
    *,
    kind: str,
    cash_register_id: str,
    local_id: str | None,
    receipt_seq: int | None,
    body: Mapping[str, Any],
    payment_form: str | None,
    refund_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """21 §16.1 ``FiscalReceiptPayload`` — every amount an ``int`` of tiyin, qty in milli-units."""
    items = []
    for i, raw in enumerate(body.get("items") or ()):
        f = f"items[{i}]"
        amount = tiyin(raw.get("amount", "0"), f"{f}.amount")
        q = milli(raw.get("qty", "1"), f"{f}.qty")
        price_raw = raw.get("price")
        price_t = (
            tiyin(price_raw, f"{f}.price")
            if price_raw not in (None, "")
            else (amount * 1000 // q if q else amount)
        )
        items.append(
            {
                "name": raw.get("name") or "",
                "mxik": raw.get("mxik"),
                "package_code": raw.get("package_code"),
                "unit_code": raw.get("unit_code"),
                "qty_milli": q,
                "price_tiyin": price_t,
                "amount_tiyin": amount,
                "vat_rate": str(raw.get("vat_rate") or "0"),
                "vat_tiyin": tiyin(raw.get("vat_amount", "0"), f"{f}.vat_amount"),
                "marking_codes": list(raw.get("marking_codes") or []),
            }
        )
    pay: dict[str, Any] = {
        "payment_form": payment_form,
        "cash_tiyin": 0,
        "card_tiyin": 0,
        "qr_tiyin": 0,
        "card_type": None,
        "card_mask": None,
        "rrn": None,
    }
    for i, p in enumerate(body.get("payments") or ()):
        form = _form(str(p.get("method")))
        if form is None:
            continue  # debt parts are never on the receipt (18 §4.5)
        pay[f"{form}_tiyin"] += tiyin(p.get("amount", "0"), f"payments[{i}].amount")
        if form == "card" and p.get("card_entry_mode") == "integrated":
            pay.update(card_type=p.get("card_type"), card_mask=p.get("card_mask"), rrn=p.get("rrn"))
    out: dict[str, Any] = {
        "cash_register": {"cash_register_id": cash_register_id, "local_id": local_id},
        "receipt_seq": receipt_seq,
        "kind": kind,
        "items": items,
        "payments": pay,
        "total_tiyin": tiyin(body.get("total", "0"), "total"),
    }
    if refund_info is not None:
        out["refund_info"] = dict(refund_info)
    return out


# --- agent results -------------------------------------------------------------------------------------
def fm_state_of(raw: object) -> str:
    value = str(raw).strip().lower() if raw is not None else "unknown"
    return value if value in FM_STATES else "unknown"


def parse_ts(raw: object, field: str) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            raise BoundaryError(field, "validation.datetime") from None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _opt_ts(raw: object, field: str) -> datetime | None:
    return None if raw in (None, "") else parse_ts(raw, field)


def _int(raw: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(raw, bool):
        raise BoundaryError(field, "validation.int_parsing")
    try:
        value = int(str(raw))
    except ValueError:
        raise BoundaryError(field, "validation.int_parsing") from None
    if value < minimum:
        raise BoundaryError(field, "validation.greater_than_equal")
    return value


@dataclass(frozen=True, slots=True)
class Acked:
    fm_terminal_id: str
    fm_receipt_seq: int
    acked_at: datetime


@dataclass(frozen=True, slots=True)
class StatusResult:
    cash_register_id: str | None
    fm_state: str
    pending_count: int
    oldest_unacked_at: datetime | None
    acked: tuple[Acked, ...]


@dataclass(frozen=True, slots=True)
class ResendResult:
    sent: int
    failed: int
    acked: tuple[Acked, ...]


@dataclass(frozen=True, slots=True)
class ZReportResult:
    fm_terminal_id: str
    z_number: int
    totals: Mapping[str, Any]
    closed_at: datetime


def terminal_id(raw: object, field: str) -> str:
    value = str(raw or "")
    if not _TERMINAL.fullmatch(value):
        raise BoundaryError(field, "validation.fiscal_terminal_format")
    return value


def fiscal_sign(raw: object, field: str) -> str:
    value = str(raw or "")
    if not _SIGN.fullmatch(value):
        raise BoundaryError(field, "validation.fiscal_sign_format")
    return value


def parse_acked(raw: object, field: str = "acked") -> tuple[Acked, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise BoundaryError(field, "validation.list_type")
    out = []
    for i, item in enumerate(raw):
        f = f"{field}[{i}]"
        if not isinstance(item, Mapping):
            raise BoundaryError(f, "validation.dict_type")
        out.append(
            Acked(
                terminal_id(item.get("fm_terminal_id"), f"{f}.fm_terminal_id"),
                _int(item.get("fm_receipt_seq"), f"{f}.fm_receipt_seq", minimum=1),
                parse_ts(item.get("acked_at"), f"{f}.acked_at"),
            )
        )
    return tuple(out)


def parse_status_result(raw: Mapping[str, Any]) -> StatusResult:
    """``{cash_register_id, fm_state, pending_count, oldest_unacked_at, acked:[…]}`` (21 §16)."""
    pending = raw.get("pending_count")
    cr = raw.get("cash_register_id")
    return StatusResult(
        cash_register_id=None if cr in (None, "") else str(cr),
        fm_state=fm_state_of(raw.get("fm_state")),
        pending_count=0 if pending is None else _int(pending, "pending_count"),
        oldest_unacked_at=_opt_ts(raw.get("oldest_unacked_at"), "oldest_unacked_at"),
        acked=parse_acked(raw.get("acked")),
    )


def parse_resend_result(raw: Mapping[str, Any]) -> ResendResult:
    """``ResendResult {sent, failed, acked:[…]}`` (21 §16.1)."""
    return ResendResult(
        sent=_int(raw.get("sent", 0), "sent"),
        failed=_int(raw.get("failed", 0), "failed"),
        acked=parse_acked(raw.get("acked")),
    )


def parse_zreport_result(raw: Mapping[str, Any]) -> ZReportResult:
    """``ZReport {fm_terminal_id, z_number, totals:{sale, return, by_payment_form}, closed_at}``
    (21 §16.1)."""
    totals = raw.get("totals") or {}
    if not isinstance(totals, Mapping):
        raise BoundaryError("totals", "validation.dict_type")
    return ZReportResult(
        fm_terminal_id=terminal_id(raw.get("fm_terminal_id"), "fm_terminal_id"),
        z_number=_int(raw.get("z_number"), "z_number", minimum=1),
        totals=dict(totals),
        closed_at=parse_ts(raw.get("closed_at"), "closed_at"),
    )
