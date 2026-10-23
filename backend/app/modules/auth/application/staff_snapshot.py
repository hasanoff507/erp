"""Staff + PIN verifiers of a branch for the ``permissions`` pull scope (16 §1, §3.2; decision D1).

Consumer: b3-sync (``/sync/pull?scope=permissions``) through ``app.modules.auth.wiring.staff_pin_snapshot()``.
It runs on the caller's session inside its ``tenant_transaction``: memberships, users and roles under RLS;
the verifiers through ``app.auth_staff_pin_states`` (SECURITY DEFINER — never the argon2 ``pin_hash``).

A member whose PIN is reset — globally (``must_change_pin``) or tenant-locally after a device revoke
(``memberships.pin_reset_at`` set, 16 §9) — or who is blocked gets ``pin_local_hash=None``:
the device must forget that user's verifier.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.application.pin import pin_reset_pending
from app.modules.auth.application.ports import PinState


@dataclass(frozen=True, slots=True)
class StaffPinRow:
    user_id: UUID
    full_name: str
    role_codes: tuple[str, ...]  # system_code or the role id (as the JWT ``roles`` claim)
    permission_codes: tuple[str, ...]  # sorted
    branch_ids: tuple[UUID, ...]  # () = every branch
    pin_local_hash: str | None
    must_change_pin: bool
    active: bool  # memberships.status == 'active'; blocked members are listed with False


@dataclass(frozen=True, slots=True)
class BranchMember:
    user_id: UUID
    full_name: str
    status: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    pin_reset_at: datetime | None


@dataclass(frozen=True, slots=True)
class RoleFacts:
    code: str  # system_code or str(role id)
    permissions: frozenset[str]


class StaffSnapshotStore(Protocol):
    async def branch_members(self, s: AsyncSession, tenant_id: UUID, branch_id: UUID) -> list[BranchMember]:
        """Active and blocked members who may work in the branch (empty ``branch_ids`` = every branch)."""
        ...

    async def roles(self, s: AsyncSession, tenant_id: UUID) -> dict[UUID, RoleFacts]: ...

    async def pin_states(self, s: AsyncSession, user_ids: Sequence[UUID]) -> dict[UUID, PinState]: ...


class StaffPinSnapshot:
    def __init__(self, store: StaffSnapshotStore) -> None:
        self._store = store

    async def for_branch(self, s: AsyncSession, tenant_id: UUID, branch_id: UUID) -> list[StaffPinRow]:
        members = await self._store.branch_members(s, tenant_id, branch_id)
        if not members:
            return []
        roles = await self._store.roles(s, tenant_id)
        states = await self._store.pin_states(s, [m.user_id for m in members])
        rows: list[StaffPinRow] = []
        for m in members:
            facts = [roles[r] for r in m.role_ids if r in roles]
            state = states.get(m.user_id)
            pending = state is None or pin_reset_pending(state, m.pin_reset_at)
            active = m.status == "active"
            rows.append(
                StaffPinRow(
                    user_id=m.user_id,
                    full_name=m.full_name,
                    role_codes=tuple(sorted({f.code for f in facts})),
                    permission_codes=tuple(sorted(set().union(*(f.permissions for f in facts)))),
                    branch_ids=m.branch_ids,
                    pin_local_hash=None if pending or not active or state is None else state.pin_local_hash,
                    must_change_pin=pending,
                    active=active,
                )
            )
        return rows
