"""SQL of the staff/PIN snapshot (``application/staff_snapshot.py``) on the caller's tenant transaction."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.application.ports import PinState
from app.modules.auth.application.staff_snapshot import BranchMember, RoleFacts

_MEMBERS: Final = text(
    "SELECT m.user_id, u.name, m.status, m.role_ids, m.branch_ids, m.pin_reset_at "
    "FROM app.memberships m JOIN app.users u ON u.id = m.user_id "
    "WHERE m.tenant_id = :tenant_id AND m.status IN ('active', 'blocked') "
    "AND (cardinality(m.branch_ids) = 0 OR CAST(:branch_id AS uuid) = ANY (m.branch_ids)) "
    "ORDER BY u.name, m.user_id"
)
_ROLES: Final = text(
    "SELECT r.id, r.system_code, rp.permission_code FROM app.roles r "
    "LEFT JOIN app.role_permissions rp ON rp.role_id = r.id AND rp.tenant_id = r.tenant_id "
    "WHERE r.tenant_id = :tenant_id AND r.archived_at IS NULL"
)
_PIN_STATES: Final = text(
    "SELECT user_id, pin_set, pin_local_hash, must_change_pin, pin_updated_at "
    "FROM app.auth_staff_pin_states(CAST(:ids AS uuid[]))"
)


class SqlStaffSnapshotStore:
    async def branch_members(self, s: AsyncSession, tenant_id: UUID, branch_id: UUID) -> list[BranchMember]:
        rows = (await s.execute(_MEMBERS, {"tenant_id": tenant_id, "branch_id": branch_id})).all()
        return [
            BranchMember(
                r.user_id,
                r.name,
                r.status,
                tuple(r.role_ids or ()),
                tuple(r.branch_ids or ()),
                r.pin_reset_at,
            )
            for r in rows
        ]

    async def roles(self, s: AsyncSession, tenant_id: UUID) -> dict[UUID, RoleFacts]:
        codes: dict[UUID, str] = {}
        perms: dict[UUID, set[str]] = {}
        for role_id, system_code, permission in (await s.execute(_ROLES, {"tenant_id": tenant_id})).all():
            codes[role_id] = system_code or str(role_id)
            bucket = perms.setdefault(role_id, set())
            if permission:
                bucket.add(permission)
        return {r: RoleFacts(codes[r], frozenset(perms[r])) for r in codes}

    async def pin_states(self, s: AsyncSession, user_ids: Sequence[UUID]) -> dict[UUID, PinState]:
        rows = (await s.execute(_PIN_STATES, {"ids": [str(u) for u in user_ids]})).all()
        # the argon2 pin_hash never leaves the function — only whether a PIN is set
        return {
            r.user_id: PinState(
                pin_hash="set" if r.pin_set else None,
                pin_local_hash=r.pin_local_hash,
                must_change_pin=bool(r.must_change_pin),
                pin_updated_at=r.pin_updated_at,
            )
            for r in rows
        }
