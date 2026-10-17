"""``/sync/pull`` cursor and scopes (16 §1, §3.2). Pure Python.

One opaque cursor carries an independent position per **stream** — ``(updated_at, key)`` of the last
row delivered (16 §1: composite cursor, stable under equal timestamps) — and the digest of every
snapshot object the device already holds. A cursor issued for ``scope=all`` is therefore valid for any
single scope, and positions of scopes not requested are carried through unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

# delta scopes → their streams (rows upserted by id); order = delivery order inside one response
DELTA_SCOPES: Final[dict[str, tuple[str, ...]]] = {
    "catalog": ("catalog.units", "catalog.categories", "catalog.products"),
    "barcodes": ("barcodes",),
    "prices": ("prices",),
    "customers": ("customers",),
    "stock": ("stock",),
    "marking_codes": ("marking_codes",),
    "fiscal": ("fiscal.registers", "fiscal.receipts"),
}
# snapshot scopes → one object replacing the whole local table (null = unchanged since the cursor)
SNAPSHOT_SCOPES: Final = ("permissions", "limits", "shift", "settings")
ALL_SCOPES: Final = (*DELTA_SCOPES, *SNAPSHOT_SCOPES)
CURSOR_VERSION: Final = 1
_MIN: Final = datetime(2000, 1, 1, tzinfo=UTC)
_MAX: Final = datetime(2100, 1, 1, tzinfo=UTC)


class CursorError(ValueError):
    """Malformed/foreign cursor → ``422 validation.cursor_invalid`` (the device re-snapshots)."""


class ScopeError(ValueError):
    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


def parse_scopes(raw: str | None) -> tuple[str, ...]:
    """``scope=catalog,prices`` / ``all`` / empty (= all) → ordered tuple of known scopes."""
    if raw is None or not raw.strip():
        return ALL_SCOPES
    wanted: set[str] = set()
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        if name == "all":
            return ALL_SCOPES
        if name not in ALL_SCOPES:
            raise ScopeError(name)
        wanted.add(name)
    if not wanted:
        return ALL_SCOPES
    return tuple(s for s in ALL_SCOPES if s in wanted)


@dataclass(frozen=True, slots=True)
class Position:
    at: datetime
    key: str

    def as_json(self) -> list[str]:
        return [self.at.astimezone(UTC).isoformat(), self.key]


@dataclass(slots=True)
class PullCursor:
    positions: dict[str, Position] = field(default_factory=dict)
    digests: dict[str, str] = field(default_factory=dict)

    def encode(self) -> str:
        body = {
            "v": CURSOR_VERSION,
            "p": {k: v.as_json() for k, v in sorted(self.positions.items())},
            "d": dict(sorted(self.digests.items())),
        }
        raw = json.dumps(body, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, token: str | None) -> PullCursor:
        if token is None or not token.strip():
            return cls()
        try:
            raw = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
            if not isinstance(raw, dict) or raw.get("v") != CURSOR_VERSION:
                raise CursorError("version")
            positions: dict[str, Position] = {}
            for stream, value in dict(raw.get("p") or {}).items():
                at_raw, key = value
                at = datetime.fromisoformat(str(at_raw))
                if at.tzinfo is None or not _MIN <= at.astimezone(UTC) < _MAX or not isinstance(key, str):
                    raise CursorError("position")
                if len(key) > 200:
                    raise CursorError("key")
                positions[str(stream)] = Position(at, key)
            digests = {str(k): str(v) for k, v in dict(raw.get("d") or {}).items()}
        except CursorError:
            raise
        except (ValueError, TypeError, AttributeError) as exc:
            raise CursorError("malformed") from exc
        return cls(positions, digests)


def digest(value: Mapping[str, Any] | list[Any]) -> str:
    """Stable digest of a snapshot object (canonical JSON, sha256, 32 hex)."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
