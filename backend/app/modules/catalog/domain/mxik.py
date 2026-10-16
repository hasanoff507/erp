"""MXIK (IKPU) classifier values (21 §7). The catalog lives at tasnif.soliq.uz, never in tenant tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MxikSource = Literal["live", "cache", "stale_cache"]


@dataclass(frozen=True, slots=True)
class MxikCandidate:
    code: str
    name: str
    vat_hint: str | None  # "12.00" / "0.00" when the classifier says so


@dataclass(frozen=True, slots=True)
class MxikLookup:
    items: tuple[MxikCandidate, ...]
    source: MxikSource
