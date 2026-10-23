"""JSON Canonicalization Scheme — RFC 8785 (33 §8.2, §9.4: ``payload_sha256 = SHA-256(JCS(payload))``).

Pure Python. The agent (.NET) implements the same rules; both sides are checked against
``shared/agent/jcs.json``. Source: https://www.rfc-editor.org/rfc/rfc8785

* object members sorted by their UTF-16 code units, no insignificant whitespace;
* strings as ECMAScript ``JSON.stringify`` writes them (``\\"``, ``\\\\``, ``\\b \\f \\n \\r \\t``,
  other controls ``\\u00xx``; everything else literal UTF-8); lone surrogates are not JSON text → error;
* numbers as ECMAScript ``Number.prototype.toString`` (IEEE 754 doubles); integers outside the
  double-exact range ``±(2^53 − 1)`` are rejected instead of being silently rounded.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

MAX_SAFE_INTEGER: Final = 2**53 - 1

_SHORT_ESCAPES: Final = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


class JcsError(ValueError):
    """The value has no RFC 8785 representation (NaN/Infinity, lone surrogate, unsafe integer, type)."""


def _string(value: str) -> str:
    out: list[str] = ['"']
    for ch in value:
        code = ord(ch)
        escaped = _SHORT_ESCAPES.get(ch)
        if escaped is not None:
            out.append(escaped)
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        elif 0xD800 <= code <= 0xDFFF:
            raise JcsError("lone surrogate in string")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _float(value: float) -> str:
    """ECMAScript Number::toString (ECMA-262 §6.1.6.1.20) of a finite double."""
    if math.isnan(value) or math.isinf(value):
        raise JcsError("NaN/Infinity are not JSON numbers")
    if value == 0:
        return "0"  # also -0
    sign = "-" if value < 0 else ""
    text = repr(abs(value))  # shortest round-trip digits (same digit choice as ECMAScript)
    mantissa, _, exp_text = text.partition("e")
    exponent = int(exp_text) if exp_text else 0
    int_part, _, frac_part = mantissa.partition(".")
    all_digits = int_part + frac_part
    leading = len(all_digits) - len(all_digits.lstrip("0"))
    digits = all_digits.lstrip("0").rstrip("0") or "0"
    n = len(int_part) + exponent - leading  # value = 0.<digits> × 10^n
    k = len(digits)
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        exp_sign = "+" if e >= 0 else "-"
        head = digits if k == 1 else digits[0] + "." + digits[1:]
        body = f"{head}e{exp_sign}{abs(e)}"
    return sign + body


def _utf16_key(key: str) -> bytes:
    return key.encode("utf-16-be")


def _serialize(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise JcsError("integer outside +-(2^53 - 1)")
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_float(value))
    elif isinstance(value, str):
        out.append(_string(value))
    elif isinstance(value, Mapping):
        keys = list(value.keys())
        if any(not isinstance(k, str) for k in keys):
            raise JcsError("object keys must be strings")
        for key in keys:
            _string(key)  # validates (lone surrogates) before sorting
        out.append("{")
        for index, key in enumerate(sorted(keys, key=_utf16_key)):
            if index:
                out.append(",")
            out.append(_string(key))
            out.append(":")
            _serialize(value[key], out)
        out.append("}")
    elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _serialize(item, out)
        out.append("]")
    else:
        raise JcsError(f"not a JSON value: {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """RFC 8785 canonical UTF-8 bytes of a JSON value (``dict``/``list``/``str``/``int``/``float``/…)."""
    out: list[str] = []
    _serialize(value, out)
    return "".join(out).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    """``hex(SHA-256(JCS(payload)))`` — ``onec_agent_tasks.payload_sha256`` and the JWS ``psh`` claim."""
    return hashlib.sha256(canonicalize(payload)).hexdigest()


def contains_non_integer_number(value: Any) -> bool:
    """34 §7.5 #8: task payloads carry only integers (the agent rejects any other JSON number)."""
    if isinstance(value, bool) or value is None or isinstance(value, str | int):
        return False
    if isinstance(value, float):
        return True
    if isinstance(value, Mapping):
        return any(contains_non_integer_number(v) for v in value.values())
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return any(contains_non_integer_number(v) for v in value)
    return False
