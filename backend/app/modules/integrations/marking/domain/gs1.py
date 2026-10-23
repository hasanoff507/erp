"""GS1 DataMatrix element-string parser (Asl belgisi / CRPT Turon codes, 21 §4). Pure Python.

Source: GS1 General Specifications (Release 24.0, 2024) — §5.4 (GS1 DataMatrix: FNC1 in the first
position, FNC1 as the separator after a variable-length element string, transmitted as ``<GS>`` = ASCII 29),
§7.8.5 Figure 7.8.5-2 (element strings with a predefined length — the first two digits of the AI fix the
total length), §3.2 (the AI table: lengths and formats), §7.9.1 (the GS1 check digit, mod 10 with weights
3/1 from the right) and §7.11 Figure 7.11-1 (GS1 AI encodable character set 82).
https://www.gs1.org/standards/barcodes-epcrfid-id-keys/gs1-general-specifications

An Asl belgisi code (VM 833; CRPT Turon "Code structure") is ``(01)`` GTIN-14 + ``(21)`` serial + crypto
elements: ``(91)`` verification key id and ``(92)`` verification code, or ``(93)`` crypto tail — e.g.
``01 04780069000048 21 5a8pLsr>qeHnD <GS> 93 dGVz``. Optional ``(17)`` expiry, ``(10)`` batch, ``(3103)`` net
weight. The raw value (GS kept as is) is what goes into the fiscal receipt (``items[].marking_codes``,
18 §4.2);
this parser only *reads* it (the Fake CRPT adapter, ``POST /marking-codes/verify`` details).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

GS: Final = "\x1d"  # FNC1 as transmitted by a scanner (GS1 GenSpecs §5.4.3.6)
SYMBOLOGY_IDS: Final = ("]d2", "]Q3", "]C1", "]e0")  # DataMatrix / QR / GS1-128 / DataBar with FNC1 (§5.4.4)

# §7.8.5 Figure 7.8.5-2: AI prefix (first 2 digits) → TOTAL length of the element string (AI + data);
# these element strings never need a GS separator after them
PREDEFINED: Final[dict[str, int]] = {
    "00": 20,
    "01": 16,
    "02": 16,
    "03": 16,
    "04": 18,
    "11": 8,
    "12": 8,
    "13": 8,
    "14": 8,
    "15": 8,
    "16": 8,
    "17": 8,
    "18": 8,
    "19": 8,
    "20": 4,
    "31": 10,
    "32": 10,
    "33": 10,
    "34": 10,
    "35": 10,
    "36": 10,
    "41": 16,
}

# §3.2: variable-length AIs used on consumer goods → maximum data length (terminated by GS or the end)
VARIABLE: Final[dict[str, int]] = {
    "10": 20,
    "21": 20,
    "22": 20,
    "235": 28,
    "240": 30,
    "241": 30,
    "242": 6,
    "243": 20,
    "250": 30,
    "251": 30,
    "253": 30,
    "254": 20,
    "255": 25,
    "30": 8,
    "37": 8,
    "400": 30,
    "401": 30,
    "403": 30,
    "420": 20,
    "421": 12,
    "422": 3,
    "7003": 10,
    "7006": 6,
    "7240": 20,
    "8008": 12,
    "8020": 25,
    "90": 30,
    "91": 90,
    "92": 90,
    "93": 90,
    "94": 90,
    "95": 90,
    "96": 90,
    "97": 90,
    "98": 90,
    "99": 90,
}

# §7.11 Figure 7.11-1: GS1 AI encodable character set 82
CSET82: Final = frozenset(
    "!\"%&'()*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
)


class Gs1Error(ValueError):
    """The value is not a GS1 element string (``reason`` — a stable machine key)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class Gs1Code:
    raw: str
    elements: tuple[tuple[str, str], ...]  # (AI, data) in scan order

    def get(self, ai: str) -> str | None:
        return next((v for a, v in self.elements if a == ai), None)

    @property
    def gtin(self) -> str | None:
        return self.get("01")

    @property
    def serial(self) -> str | None:
        return self.get("21")

    @property
    def crypto_tail(self) -> str | None:
        return self.get("93")

    @property
    def verification_key(self) -> str | None:
        return self.get("91")

    @property
    def verification_code(self) -> str | None:
        return self.get("92")

    @property
    def expiry(self) -> date | None:
        raw = self.get("17")
        return yymmdd(raw) if raw else None

    @property
    def is_marking_code(self) -> bool:
        """An Asl belgisi unit code: GTIN + serial + crypto (``93``, or ``91`` and ``92``)."""
        crypto = self.crypto_tail is not None or (
            self.verification_key is not None and self.verification_code is not None
        )
        return self.gtin is not None and bool(self.serial) and crypto


def check_digit(digits: str) -> int:
    """GS1 mod-10 check digit of ``digits`` (the key WITHOUT its check digit; GenSpecs §7.9.1)."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10


def gtin_valid(gtin: str) -> bool:
    return len(gtin) in (8, 12, 13, 14) and gtin.isdigit() and check_digit(gtin[:-1]) == int(gtin[-1])


def yymmdd(raw: str) -> date | None:
    """GS1 date (§7.12): ``DD = 00`` means the last day of the month; century by the 50-year sliding window
    is simplified to 20YY (codes of the 1950–1999 range do not occur on marked goods)."""
    if len(raw) != 6 or not raw.isdigit():
        return None
    year, month, day = 2000 + int(raw[:2]), int(raw[2:4]), int(raw[4:])
    if not 1 <= month <= 12:
        return None
    if day == 0:
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        return date.fromordinal(nxt.toordinal() - 1)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _ai_at(text: str, pos: int) -> str:
    for size in (2, 3, 4):
        ai = text[pos : pos + size]
        if len(ai) < size or not ai.isdigit():
            break
        if ai[:2] in PREDEFINED and size == (4 if ai[:2] in {"31", "32", "33", "34", "35", "36"} else 2):
            return ai
        if ai in VARIABLE:
            return ai
    raise Gs1Error("unknown_ai", text[pos : pos + 4])


def parse(raw: str) -> Gs1Code:
    """Parse a scanned GS1 element string (symbology identifier and a leading FNC1/GS are tolerated)."""
    text = raw
    for sid in SYMBOLOGY_IDS:
        if text.startswith(sid):
            text = text[len(sid) :]
            break
    text = text.lstrip(GS)
    if not text:
        raise Gs1Error("empty")
    elements: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        if text[pos] == GS:  # a separator after a variable-length element (or a redundant one)
            pos += 1
            continue
        ai = _ai_at(text, pos)
        start = pos + len(ai)
        if ai[:2] in PREDEFINED and ai not in VARIABLE:
            end = pos + PREDEFINED[ai[:2]]
            data = text[start:end]
            if len(data) != end - start or GS in data:
                raise Gs1Error("truncated", ai)
        else:
            stop = text.find(GS, start)
            end = len(text) if stop < 0 else stop
            data = text[start:end]
            if not data or len(data) > VARIABLE[ai]:
                raise Gs1Error("bad_length", ai)
        if any(ch not in CSET82 for ch in data):
            raise Gs1Error("bad_character", ai)
        if any(a == ai for a, _ in elements):
            raise Gs1Error("repeated_ai", ai)
        elements.append((ai, data))
        pos = end
    code = Gs1Code(raw, tuple(elements))
    gtin = code.gtin
    if gtin is not None and not gtin_valid(gtin):
        raise Gs1Error("gtin_check_digit", gtin)
    if code.get("17") is not None and code.expiry is None:
        raise Gs1Error("bad_date", "17")
    return code
