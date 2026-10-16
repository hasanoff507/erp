"""The authenticated caller as seen by the Resource Server (14 §5)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    client_id: str
    scopes: frozenset[str]
    # token-time snapshots — informative only; branch scope and permissions are
    # always re-read from the database (14 §5 "branch_ids/roles eskirishi")
    roles: tuple[str, ...]
    branch_ids: tuple[UUID, ...]
    sid: UUID | None
    device_id: UUID | None
    jti: str
    issued_at: int
    expires_at: int
    sub_status: str | None
    via_cookie: bool  # BFF session (CSRF applies) vs. direct Bearer (Android)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
