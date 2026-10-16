"""SQL of BO-11 staff administration (14 §18.2, §19).

``app.users``/``app.memberships`` are read and written under RLS (12 §4); ``auth.*`` is reached only
through the SECURITY DEFINER functions (``auth_find_user_by_phone``, ``auth_set_credentials``,
``auth_reset_credentials``, ``auth_list_user_sessions``, ``auth_revoke_session``,
``auth_revoke_user``). Every :class:`MembershipAdminRepository` method runs on the caller's session.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.application.admin_ports import (
    LockedMembership,
    RoleRef,
    StaffRow,
    UserDeviceRow,
    UserSessionRow,
)

_STAFF_COLUMNS = (
    "SELECT m.id AS membership_id, m.created_at, m.user_id, COALESCE(m.invited_name, u.name) AS name, "
    "u.phone, m.role_ids, m.branch_ids, m.status, m.invited_name IS NOT NULL AS pending_invite, "
    "(SELECT max(a.at) FROM app.audit_log a WHERE a.tenant_id = m.tenant_id "
    "AND a.user_id = m.user_id AND a.action = 'login_success') AS last_login_at "
    "FROM app.memberships m JOIN app.users u ON u.id = m.user_id WHERE m.tenant_id = :tenant_id "
)
_LIST_FIRST = text(_STAFF_COLUMNS + "ORDER BY m.created_at, m.id LIMIT :limit")
_LIST_AFTER = text(
    _STAFF_COLUMNS + "AND (m.created_at, m.id) > (CAST(:after_ts AS timestamptz), CAST(:after_id AS uuid)) "
    "ORDER BY m.created_at, m.id LIMIT :limit"
)
_GET_STAFF = text(_STAFF_COLUMNS + "AND m.user_id = :user_id")
_LOCK_MEMBERSHIP = text(
    "SELECT id, status, role_ids, branch_ids, invited_name FROM app.memberships "
    "WHERE tenant_id = :tenant_id AND user_id = :user_id FOR UPDATE"
)
_SET_STATUS = text("UPDATE app.memberships SET status = :status, version = version + 1 WHERE id = :id")
_SET_ASSIGNMENT = text(
    "UPDATE app.memberships SET role_ids = CAST(:role_ids AS uuid[]), "
    "branch_ids = CAST(:branch_ids AS uuid[]), version = version + 1 WHERE id = :id"
)
_ROLES = text(
    "SELECT id, system_code FROM app.roles WHERE tenant_id = :tenant_id "
    "AND id = ANY(CAST(:ids AS uuid[])) AND archived_at IS NULL"
)
_BRANCHES = text(
    "SELECT id FROM app.branches WHERE tenant_id = :tenant_id "
    "AND id = ANY(CAST(:ids AS uuid[])) AND archived_at IS NULL"
)
_ACTIVE_OWNERS = text(
    "SELECT DISTINCT m.user_id FROM app.memberships m JOIN app.roles r ON r.tenant_id = m.tenant_id "
    "AND r.id = ANY(m.role_ids) AND r.system_code = 'owner' AND r.archived_at IS NULL "
    "WHERE m.tenant_id = :tenant_id AND m.status = 'active'"
)
_VISIBLE_USER = text("SELECT id FROM app.users WHERE phone = :phone")
_FIND_USER = text("SELECT user_id FROM app.auth_find_user_by_phone(:phone)")
_SET_USER_CTX = text("SELECT set_config('app.user_id', :uid, true)")
_INSERT_USER = text(
    "INSERT INTO app.users (id, phone, name) VALUES (:id, :phone, :name) "
    "ON CONFLICT (phone) DO NOTHING RETURNING id"
)
# the credentials row (no hashes yet) makes the new user findable by auth_find_user_by_phone
_CREATE_CREDENTIALS = text("SELECT app.auth_set_credentials(:user_id, NULL, NULL)")
_INSERT_MEMBERSHIP = text(
    "INSERT INTO app.memberships (id, tenant_id, user_id, role_ids, branch_ids, status, invited_name) "
    "VALUES (:id, :tenant_id, :user_id, CAST(:role_ids AS uuid[]), CAST(:branch_ids AS uuid[]), "
    "CASE WHEN CAST(:invited_name AS text) IS NULL THEN 'active' ELSE 'invited' END, :invited_name)"
)
_ELSEWHERE = text("SELECT count(*) FROM app.auth_list_memberships(:user_id) WHERE tenant_id <> :tenant_id")
_RESET_CREDENTIALS = text("SELECT app.auth_reset_credentials(:user_id, :password, :pin)")
_SESSION_IDS = text("SELECT session_id FROM app.auth_list_user_sessions(:user_id, :tenant_id)")
_SESSIONS = text(
    "SELECT s.session_id, c.client_id, s.device_id, d.kind AS device_kind, s.created_at, s.last_seen_at, "
    "host(s.ip) AS ip, s.user_agent FROM app.auth_list_user_sessions(:user_id, :tenant_id) s "
    "JOIN platform.oauth_clients c ON c.id = s.client_id "
    "LEFT JOIN app.devices d ON d.id = s.device_id AND d.tenant_id = :tenant_id "
    "ORDER BY s.last_seen_at DESC, s.session_id"
)
_REVOKE_SESSION = text("SELECT app.auth_revoke_session(:sid, :reason)")
_REVOKE_USER = text("SELECT app.auth_revoke_user(:user_id, :tenant_id, :reason)")
_DEVICES = text(
    "SELECT d.id, d.kind, d.app_version, d.cash_register_id, cr.name AS cash_register_name, "
    "cr.branch_id, d.last_seen_at, d.last_sync_at, d.revoked_at "
    "FROM app.devices d LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id "
    "WHERE d.tenant_id = :tenant_id AND (d.id = ANY(CAST(:ids AS uuid[])) OR EXISTS ("
    "SELECT 1 FROM app.shifts sh WHERE sh.tenant_id = d.tenant_id AND sh.device_id = d.id "
    "AND (sh.opened_by = :user_id OR sh.closed_by = :user_id))) "
    "ORDER BY d.last_seen_at DESC NULLS LAST, d.id"
)


def _ids(values: Iterable[UUID]) -> list[str]:
    return [str(v) for v in values]


def _staff(r: Any) -> StaffRow:
    return StaffRow(
        membership_id=r.membership_id, created_at=r.created_at, user_id=r.user_id, name=r.name, phone=r.phone,
        role_ids=tuple(r.role_ids or ()), branch_ids=tuple(r.branch_ids or ()), status=r.status,
        last_login_at=r.last_login_at, pending_invite=bool(r.pending_invite),
    )  # fmt: skip


class MembershipAdminRepository:
    """Implements ``StaffRepository`` (application/admin_ports.py)."""

    async def list_staff(
        self, s: AsyncSession, tenant_id: UUID, *, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[StaffRow]:
        if after is None:
            rows = (await s.execute(_LIST_FIRST, {"tenant_id": tenant_id, "limit": limit})).all()
        else:
            params = {"tenant_id": tenant_id, "limit": limit, "after_ts": after[0], "after_id": after[1]}
            rows = (await s.execute(_LIST_AFTER, params)).all()
        return [_staff(r) for r in rows]

    async def get_staff(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> StaffRow | None:
        row = (await s.execute(_GET_STAFF, {"tenant_id": tenant_id, "user_id": user_id})).first()
        return _staff(row) if row else None

    async def lock(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> LockedMembership | None:
        row = (await s.execute(_LOCK_MEMBERSHIP, {"tenant_id": tenant_id, "user_id": user_id})).first()
        if row is None:
            return None
        return LockedMembership(
            row.id, row.status, tuple(row.role_ids or ()), tuple(row.branch_ids or ()), row.invited_name
        )

    async def set_status(self, s: AsyncSession, membership_id: UUID, status: str) -> None:
        await s.execute(_SET_STATUS, {"status": status, "id": membership_id})

    async def set_assignment(
        self, s: AsyncSession, membership_id: UUID, role_ids: Sequence[UUID], branch_ids: Sequence[UUID]
    ) -> None:
        params = {"id": membership_id, "role_ids": _ids(role_ids), "branch_ids": _ids(branch_ids)}
        await s.execute(_SET_ASSIGNMENT, params)

    async def roles(self, s: AsyncSession, tenant_id: UUID, role_ids: Sequence[UUID]) -> list[RoleRef]:
        rows = (await s.execute(_ROLES, {"tenant_id": tenant_id, "ids": _ids(role_ids)})).all()
        return [RoleRef(r.id, r.system_code) for r in rows]

    async def existing_branches(
        self, s: AsyncSession, tenant_id: UUID, branch_ids: Sequence[UUID]
    ) -> set[UUID]:
        rows = (await s.execute(_BRANCHES, {"tenant_id": tenant_id, "ids": _ids(branch_ids)})).all()
        return {r.id for r in rows}

    async def active_owner_ids(self, s: AsyncSession, tenant_id: UUID) -> set[UUID]:
        return {r.user_id for r in (await s.execute(_ACTIVE_OWNERS, {"tenant_id": tenant_id})).all()}

    async def visible_user_by_phone(self, s: AsyncSession, phone: str) -> UUID | None:
        value = (await s.execute(_VISIBLE_USER, {"phone": phone})).scalar()
        return value if isinstance(value, UUID) else None

    async def user_id_by_phone(self, s: AsyncSession, phone: str) -> UUID | None:
        value = (await s.execute(_FIND_USER, {"phone": phone})).scalar()
        return value if isinstance(value, UUID) else None

    async def insert_user(
        self, s: AsyncSession, user_id: UUID, phone: str, name: str, actor_id: UUID
    ) -> bool:
        # users RLS WITH CHECK (id = app.current_user_id()) — 12 §4: the app sets app.user_id to the new
        # id for the INSERT, then restores the actor for the rest of the transaction
        await s.execute(_SET_USER_CTX, {"uid": str(user_id)})
        try:
            inserted = (await s.execute(_INSERT_USER, {"id": user_id, "phone": phone, "name": name})).first()
        finally:
            await s.execute(_SET_USER_CTX, {"uid": str(actor_id)})
        if inserted is None:
            return False
        await s.execute(_CREATE_CREDENTIALS, {"user_id": user_id})
        return True

    async def insert_membership(
        self,
        s: AsyncSession,
        membership_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        role_ids: Sequence[UUID],
        branch_ids: Sequence[UUID],
        *,
        invited_name: str | None = None,
    ) -> None:
        params = {
            "id": membership_id, "tenant_id": tenant_id, "user_id": user_id,
            "role_ids": _ids(role_ids), "branch_ids": _ids(branch_ids), "invited_name": invited_name,
        }  # fmt: skip
        await s.execute(_INSERT_MEMBERSHIP, params)

    async def active_memberships_elsewhere(self, s: AsyncSession, user_id: UUID, tenant_id: UUID) -> int:
        params = {"user_id": user_id, "tenant_id": tenant_id}
        return int((await s.execute(_ELSEWHERE, params)).scalar_one() or 0)

    async def reset_credentials(self, s: AsyncSession, user_id: UUID, *, password: bool, pin: bool) -> None:
        await s.execute(_RESET_CREDENTIALS, {"user_id": user_id, "password": password, "pin": pin})

    async def session_ids(self, s: AsyncSession, user_id: UUID, tenant_id: UUID | None) -> list[UUID]:
        rows = (await s.execute(_SESSION_IDS, {"user_id": user_id, "tenant_id": tenant_id})).all()
        return [r.session_id for r in rows]

    async def sessions(self, s: AsyncSession, user_id: UUID, tenant_id: UUID) -> list[UserSessionRow]:
        rows = (await s.execute(_SESSIONS, {"user_id": user_id, "tenant_id": tenant_id})).all()
        return [
            UserSessionRow(
                r.session_id, r.client_id, r.device_id, r.device_kind, r.created_at, r.last_seen_at, r.ip,
                r.user_agent,
            )
            for r in rows
        ]  # fmt: skip

    async def revoke_session(self, s: AsyncSession, session_id: UUID, reason: str) -> None:
        await s.execute(_REVOKE_SESSION, {"sid": session_id, "reason": reason})

    async def revoke_user(self, s: AsyncSession, user_id: UUID, tenant_id: UUID, reason: str) -> int:
        params = {"user_id": user_id, "tenant_id": tenant_id, "reason": reason}
        return int((await s.execute(_REVOKE_USER, params)).scalar_one() or 0)

    async def devices(
        self, s: AsyncSession, tenant_id: UUID, user_id: UUID, session_device_ids: Iterable[UUID]
    ) -> list[UserDeviceRow]:
        params = {"tenant_id": tenant_id, "user_id": user_id, "ids": _ids(session_device_ids)}
        rows = (await s.execute(_DEVICES, params)).all()
        return [
            UserDeviceRow(
                r.id, r.kind, r.app_version, r.cash_register_id, r.cash_register_name, r.branch_id,
                r.last_seen_at, r.last_sync_at, r.revoked_at,
            )
            for r in rows
        ]  # fmt: skip
