"""Task kinds of the store agent (33 §9.5, §5.15; 21 §16; 34 §14.3). Pure Python.

Bosqich 5 builds only the store-agent part: the device-service kinds (``purpose='device_service'``,
``base_id IS NULL``) and the agent-level ``collect_diagnostics`` (W-07). The 1C kinds (``probe``,
``write_object`` …) are Bosqich 7 — the dispatcher never leases them in B5.
"""

from __future__ import annotations

from typing import Final

PURPOSE_DEVICE_SERVICE: Final = "device_service"
PURPOSE_DIAGNOSTICS: Final = "diagnostics"

KIND_COLLECT_DIAGNOSTICS: Final = "collect_diagnostics"

# kind → (capability family, default timeout_s)
DEVICE_SERVICE_KINDS: Final[dict[str, tuple[str, int]]] = {
    "fiscal.status": ("fiscal", 60),
    "fiscal.resend_unsent": ("fiscal", 300),
    "fiscal.zreport": ("fiscal", 120),
    "print.raw": ("print", 60),
    "scale.plu_upload": ("scale", 300),
    "card.status": ("card_terminal", 60),
    "card.settlement": ("card_terminal", 180),
}

# agent-level kinds the B5 dispatcher leases (base_id IS NULL)
B5_LEASABLE_KINDS: Final[frozenset[str]] = frozenset({*DEVICE_SERVICE_KINDS, KIND_COLLECT_DIAGNOSTICS})

CAPABILITY_FAMILIES: Final[tuple[str, ...]] = ("onec", "fiscal", "print", "scale", "card_terminal")

TIMEOUT_MIN_S: Final = 10
TIMEOUT_MAX_S: Final = 1800
DIAGNOSTICS_TIMEOUT_S: Final = 300


def family_of(kind: str) -> str | None:
    entry = DEVICE_SERVICE_KINDS.get(kind)
    return entry[0] if entry else None


def default_timeout_s(kind: str) -> int:
    entry = DEVICE_SERVICE_KINDS.get(kind)
    if entry is not None:
        return entry[1]
    return DIAGNOSTICS_TIMEOUT_S


def clamp_timeout(timeout_s: int) -> int:
    return max(TIMEOUT_MIN_S, min(TIMEOUT_MAX_S, int(timeout_s)))
