"""Secret masking of agent log entries (33 §15.2 "Loglarda sir", 34 §9.2, PCI 15 §4). Pure Python.

The agent masks before sending (A-06); the server masks again — defence in depth: connection-string
passwords, bearer tokens, client assertions/JWTs, and card-number-like digit runs never reach the DB.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

MASK: Final = "***"
MAX_MESSAGE: Final = 4000
MAX_CONTEXT_DEPTH: Final = 6

_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    # 1C connection string parts and generic key=value secrets
    (re.compile(r"(?i)\b(pwd|password|passwd|parol|пароль)\s*=\s*(\"[^\"]*\"|[^;\s]*)"), rf"\1={MASK}"),
    (
        re.compile(r"(?i)\b(client_assertion|access_token|refresh_token|device_code)\s*=\s*[^&\s;]+"),
        rf"\1={MASK}",
    ),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), f"Bearer {MASK}"),
    # compact JWS/JWT
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), MASK),
    # PAN-like digit runs (13–19 digits, optional single separators) — keep the last 4 digits
    (re.compile(r"\b(?:\d[ -]?){9,15}(\d{4})\b"), rf"{MASK}\1"),
)

_SECRET_KEYS: Final = re.compile(
    r"(?i)(pass(word)?|pwd|secret|token|assertion|authorization|private|pin|cvv|cvc|track|pan|card_?number)"
)


def mask_text(value: str, *, limit: int | None = None) -> str:
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    if limit is not None and len(value) > limit:
        value = value[: limit - 1] + "…"
    return value


def mask_context(value: Any, depth: int = 0) -> Any:
    """Masked copy of a JSON context: secret-looking keys → ``***``, strings through :func:`mask_text`."""
    if depth > MAX_CONTEXT_DEPTH:
        return MASK
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:100]:
            name = str(key)[:64]
            out[name] = MASK if _SECRET_KEYS.search(name) else mask_context(item, depth + 1)
        return out
    if isinstance(value, str):
        return mask_text(value, limit=1000)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [mask_context(v, depth + 1) for v in list(value)[:100]]
    if value is None or isinstance(value, bool | int | float):
        return value
    return MASK
