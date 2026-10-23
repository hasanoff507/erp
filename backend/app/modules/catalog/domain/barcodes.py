"""Barcode rules (US-M09-05, 11 §11, 12 ``internal_barcode_seq``) — pure functions.

Internal codes are EAN-13 in the GS1 "restricted circulation" range 040–049:
``lpad(next_value, 12, '0')`` (``04`` + 10 digits) + the EAN check digit. That
range is never assigned to manufacturers (no clash with real GTINs) and does
not overlap the in-store weight prefixes 20–29 (``weight_barcode_templates``).
"""

from __future__ import annotations

import re
from typing import Final, Literal

BarcodeKind = Literal["ean", "internal", "weighed_prefix"]

INTERNAL_SEQ_MIN: Final = 40_000_000_000
INTERNAL_SEQ_MAX: Final = 49_999_999_999
INTERNAL_RE: Final = re.compile(r"^04[0-9]{11}$")
WEIGHT_PREFIXES: Final = frozenset(f"{p}" for p in range(20, 30))
MAX_BARCODE_LENGTH: Final = 64
_BARCODE_RE: Final = re.compile(r"^[0-9A-Za-z\-.$/+%]{1,64}$")


class InternalRangeExhaustedError(Exception):
    """``internal_barcode_seq`` reached 049999999999."""


def ean_check_digit(body: str) -> int:
    """GS1 mod-10 check digit for the data digits ``body`` (EAN-8/12/13/14 bodies)."""
    if not body.isdigit():
        raise ValueError("barcode body must be digits")
    total = 0
    # weights 3,1,3,1… from the rightmost data digit
    for index, char in enumerate(reversed(body)):
        total += int(char) * (3 if index % 2 == 0 else 1)
    return (10 - total % 10) % 10


def is_valid_ean13(code: str) -> bool:
    return len(code) == 13 and code.isdigit() and ean_check_digit(code[:12]) == int(code[12])


def internal_barcode(seq_value: int) -> str:
    """EAN-13 for one ``internal_barcode_seq.next_value``."""
    if not INTERNAL_SEQ_MIN <= seq_value <= INTERNAL_SEQ_MAX:
        raise InternalRangeExhaustedError(seq_value)
    body = f"{seq_value:012d}"
    return body + str(ean_check_digit(body))


def is_internal_barcode(code: str) -> bool:
    return bool(INTERNAL_RE.match(code)) and is_valid_ean13(code)


def is_weight_prefixed(code: str) -> bool:
    """13-digit code in the 20–29 in-store weight/sum range (US-M09-06)."""
    return len(code) == 13 and code.isdigit() and code[:2] in WEIGHT_PREFIXES


def barcode_format_ok(code: str, kind: BarcodeKind) -> bool:
    """Shape check for a manually entered barcode.

    ``ean`` accepts any printable scanner code (shops also carry non-GS1 codes);
    ``internal`` must be a valid 04x EAN-13 (DB CHECK + check digit).
    """
    if not _BARCODE_RE.match(code):
        return False
    if kind == "internal":
        return is_internal_barcode(code)
    return True
