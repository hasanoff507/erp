"""Agent versions and update rollout (33 §9.1, §9.3 A-09, 34 §4.4). Pure Python."""

from __future__ import annotations

import hashlib
import re
from typing import Final
from uuid import UUID

_SEMVER: Final = re.compile(r"^(\d{1,6})\.(\d{1,6})\.(\d{1,6})(?:[-+][0-9A-Za-z.-]{1,64})?$")

SUPPORTED_PROTOCOLS: Final = frozenset({2})


def parse_version(value: str | None) -> tuple[int, int, int] | None:
    match = _SEMVER.fullmatch((value or "").strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def version_lt(a: str | None, b: str | None) -> bool:
    """``a < b``; an unparsable ``a`` is treated as older than anything parsable."""
    pa, pb = parse_version(a), parse_version(b)
    if pb is None:
        return False
    if pa is None:
        return True
    return pa < pb


def rollout_bucket(agent_id: UUID) -> int:
    """Stable 0..99 bucket: ``int(sha256(agent_id bytes)[0:8], 16) % 100`` (contracts/agent-wire.md §5)."""
    return int(hashlib.sha256(agent_id.bytes).hexdigest()[:8], 16) % 100


def in_rollout(agent_id: UUID, rollout_pct: int) -> bool:
    return rollout_bucket(agent_id) < max(0, min(100, rollout_pct))
