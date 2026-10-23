"""Card terminal domain rules (qaror #71; 21 §9.4, 18 §2.7/§16a, 12 ``card_terminal_*``). Pure Python.

* ``CardTxResult.status`` → ``card_terminal_transactions.status`` mapping and the forward-only state machine
  (``pending`` → ``approved``/``declined``/``unknown``; ``unknown`` → ``approved``/``declined``;
  ``approved`` purchase → ``voided``); a final state is never replaced by another final state.
* ``card_mask`` normalisation to first 4 + last 4 (the BIN is returned separately, only for the in-memory
  ``platform.card_bin_rules`` lookup — it is never stored, 15 §9.3).
* ``card_type`` source order: terminal → BIN table → ``unknown`` (source ``bin_table``).
* Settlement status: ``matched`` / ``mismatch`` / ``failed`` (18 §16a.6).
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Final, Literal

TxStatus = Literal["pending", "approved", "declined", "unknown", "voided"]
PortStatus = Literal["approved", "declined", "cancelled", "timeout", "unknown", "error"]
CardType = Literal["personal", "corporate", "social", "unknown"]
CardTypeSource = Literal["terminal", "bin_table"]
SettlementStatus = Literal["matched", "mismatch", "failed"]

CARD_SCHEMES: Final = frozenset({"uzcard", "humo", "visa", "mastercard", "unionpay", "mir", "other"})
CARD_TYPES: Final = frozenset({"personal", "corporate", "social", "unknown"})
ENTRY_MODES: Final = frozenset({"chip", "contactless", "magstripe", "fallback"})
ADAPTERS: Final = frozenset({"agent_ecr", "cloud", "android_intent", "softpos", "fake"})
CAPABILITIES: Final = (
    "refund", "void", "status_query", "last_transaction", "settlement", "contactless",
    "returns_card_type", "returns_bin",
)  # fmt: skip

FINAL: Final[frozenset[str]] = frozenset({"approved", "declined", "voided"})
UNRESOLVED: Final[frozenset[str]] = frozenset({"pending", "unknown"})
HEALTH_STATUSES: Final = frozenset({"online", "busy", "offline", "error"})  # agent card.status values
TASHKENT: Final = timezone(timedelta(hours=5))  # Asia/Tashkent, no DST
ORPHAN_AFTER_HOURS: Final = 24  # 16 §2.1: approved purchase without a document → card_orphan_transaction

MASK_RE: Final = re.compile(r"^[0-9]{4}\*+[0-9]{4}$")
RRN_RE: Final = re.compile(r"^[0-9A-Za-z]{6,32}$")
APPROVAL_CODE_RE: Final = re.compile(r"^[0-9A-Za-z]{1,12}$")
BIN_RE: Final = re.compile(r"^[0-9]{6,8}$")
_RAW_MASK_RE: Final = re.compile(r"^([0-9]{4,8})[*Xx•]+([0-9]{4})$")

# CardTxResult.status (port) → stored status (21 §9.4 "Holatlar")
_PORT_TO_TX: Final[dict[str, TxStatus]] = {
    "approved": "approved",
    "declined": "declined",
    "cancelled": "declined",
    "error": "declined",
    "timeout": "unknown",
    "unknown": "unknown",
}
# allowed forward transitions (18 §16a.3 "Holat faqat oldinga o'tadi")
_FORWARD: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"approved", "declined", "unknown"}),
    "unknown": frozenset({"approved", "declined"}),
    "approved": frozenset({"voided"}),
    "declined": frozenset(),
    "voided": frozenset(),
}


def tx_status_of(port_status: str) -> TxStatus:
    """``CardTxResult.status`` → stored status; unknown values are a programming/adapter error."""
    try:
        return _PORT_TO_TX[port_status]
    except KeyError:
        raise ValueError(f"unknown CardTxResult.status {port_status!r}") from None


def decline_code_of(port_status: str, bank_code: str | None) -> str | None:
    """``declined`` keeps the bank code; ``cancelled``/``error`` become the decline code themselves."""
    if port_status in ("cancelled", "error"):
        return port_status
    return bank_code if port_status == "declined" else None


def can_transition(current: str, new: str) -> bool:
    """Same status (a replay) is always allowed; otherwise only a forward step."""
    return current == new or new in _FORWARD.get(current, frozenset())


@dataclass(frozen=True, slots=True)
class NormalizedMask:
    mask: str  # ^[0-9]{4}\*+[0-9]{4}$
    bin: str | None  # first 6–8 digits when the terminal gave them — memory only


def normalize_mask(raw: str | None) -> NormalizedMask | None:
    """``860031******1234`` → ``8600********1234`` (+ BIN ``860031``); ``8600****1234`` stays as is.

    The length of the masked middle is preserved (total length unchanged); anything else → ``None``.
    """
    if raw is None:
        return None
    compact = raw.replace(" ", "").replace("-", "")
    found = _RAW_MASK_RE.match(compact)
    if found is None:
        return None
    head, tail = found.group(1), found.group(2)
    stars = len(compact) - 4 - len(tail)
    mask = head[:4] + "*" * stars + tail
    if not MASK_RE.match(mask):
        return None
    return NormalizedMask(mask, head if len(head) >= 6 else None)


def derive_card_type(
    terminal_card_type: str | None, bin_rule_type: str | None
) -> tuple[CardType, CardTypeSource]:
    """21 §9.4 ``card_type``: terminal value → BIN table rule → ``unknown`` (source ``bin_table``)."""
    if terminal_card_type is not None:
        if terminal_card_type not in CARD_TYPES:
            raise ValueError(f"invalid card_type {terminal_card_type!r}")
        return terminal_card_type, "terminal"  # type: ignore[return-value]
    if bin_rule_type in ("personal", "corporate", "social"):
        return bin_rule_type, "bin_table"  # type: ignore[return-value]
    return "unknown", "bin_table"


def settlement_status(
    purchase_total: Decimal, refund_total: Decimal, expected_total: Decimal, *, failed: bool
) -> SettlementStatus:
    if failed:
        return "failed"
    return "matched" if purchase_total - refund_total == expected_total else "mismatch"


def private_ipv4(host: str) -> bool:
    """RFC 1918 only (12 ``card_terminals`` CHECK; no arbitrary hosts — 15 §9.3, 21 §9.4)."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if not isinstance(address, ipaddress.IPv4Address):
        return False
    return any(
        address in ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    )


def capability_enabled(capabilities: Mapping[str, Any], family: str) -> bool:
    """34 §14.2: ``capabilities.<family>.enabled is True`` (anything else — disabled)."""
    block = capabilities.get(family)
    return isinstance(block, Mapping) and block.get("enabled") is True


def capability_devices(capabilities: Mapping[str, Any], family: str) -> list[Mapping[str, Any]]:
    block = capabilities.get(family)
    devices = block.get("devices") if isinstance(block, Mapping) else None
    return [d for d in devices if isinstance(d, Mapping)] if isinstance(devices, list) else []


def tashkent_date(moment: datetime) -> date:
    """Business date of a terminal event (Asia/Tashkent, UTC+5 all year)."""
    return moment.astimezone(TASHKENT).date()
