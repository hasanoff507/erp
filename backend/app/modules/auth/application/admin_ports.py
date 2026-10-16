"""Ports of BO-11 staff administration and of the RS access guard (23 §1).

The application layer (``admin_users.py``, ``gateway.py``) depends on these Protocols; the SQL lives in
``infrastructure/admin_repositories.py`` and ``wiring.py`` composes them. Methods taking an
``AsyncSession`` run inside the caller's ``tenant_transaction`` so that the change, the session
revocation, the audit row and the Idempotency-Key journal commit together.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.application.otp import OtpIssued, OtpPurpose


# --- rows ----------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LockedMembership:
    id: UUID
    status: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    invited_name: str | None = None  # NOT NULL = the invite is not accepted yet (12 memberships)


@dataclass(frozen=True, slots=True)
class StaffRow:
    """One ``GET /admin/users`` item (14 §18.2) plus the cursor key.

    ``name`` is ``memberships.invited_name`` while the invite is not accepted — the name the inviter
    typed, never the global ``users.name`` of an account that belongs to other tenants.
    """

    membership_id: UUID
    created_at: datetime
    user_id: UUID
    name: str
    phone: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    status: str
    last_login_at: datetime | None
    pending_invite: bool = False


@dataclass(frozen=True, slots=True)
class RoleRef:
    id: UUID
    system_code: str | None


@dataclass(frozen=True, slots=True)
class UserSessionRow:
    session_id: UUID
    client_id: str
    device_id: UUID | None
    device_kind: str | None
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class UserDeviceRow:
    id: UUID
    kind: str
    app_version: str | None
    cash_register_id: UUID | None
    cash_register_name: str | None
    branch_id: UUID | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    revoked_at: datetime | None


# --- ports ---------------------------------------------------------------------------------------------
class StaffRepository(Protocol):
    """SQL of BO-11 (app.users / app.memberships under RLS, auth.* only via SECURITY DEFINER functions)."""

    async def list_staff(
        self, s: AsyncSession, tenant_id: UUID, *, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[StaffRow]: ...

    async def get_staff(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> StaffRow | None: ...

    async def lock(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> LockedMembership | None: ...

    async def set_status(self, s: AsyncSession, membership_id: UUID, status: str) -> None: ...

    async def set_assignment(
        self, s: AsyncSession, membership_id: UUID, role_ids: Sequence[UUID], branch_ids: Sequence[UUID]
    ) -> None: ...

    async def roles(self, s: AsyncSession, tenant_id: UUID, role_ids: Sequence[UUID]) -> list[RoleRef]:
        """Live (not archived) roles of the tenant among ``role_ids``."""
        ...

    async def existing_branches(
        self, s: AsyncSession, tenant_id: UUID, branch_ids: Sequence[UUID]
    ) -> set[UUID]:
        """Live (not archived) branches of the tenant among ``branch_ids``."""
        ...

    async def active_owner_ids(self, s: AsyncSession, tenant_id: UUID) -> set[UUID]:
        """Users with an active membership holding the ``owner`` system role."""
        ...

    async def visible_user_by_phone(self, s: AsyncSession, phone: str) -> UUID | None:
        """A user visible under RLS (member of this tenant) — ``None`` otherwise."""
        ...

    async def user_id_by_phone(self, s: AsyncSession, phone: str) -> UUID | None:
        """Any user with this phone, across tenants (``auth_find_user_by_phone``)."""
        ...

    async def insert_user(
        self, s: AsyncSession, user_id: UUID, phone: str, name: str, actor_id: UUID
    ) -> bool:
        """``False`` when the phone already exists (unique violation, nothing inserted)."""
        ...

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
        """``invited_name`` set → ``status='invited'`` (an existing account), else ``'active'``."""
        ...

    async def active_memberships_elsewhere(self, s: AsyncSession, user_id: UUID, tenant_id: UUID) -> int:
        """Active memberships of the user in other tenants (``auth_list_memberships``)."""
        ...

    async def reset_credentials(
        self, s: AsyncSession, user_id: UUID, *, password: bool, pin: bool
    ) -> None: ...

    async def session_ids(self, s: AsyncSession, user_id: UUID, tenant_id: UUID | None) -> list[UUID]: ...

    async def sessions(self, s: AsyncSession, user_id: UUID, tenant_id: UUID) -> list[UserSessionRow]: ...

    async def revoke_session(self, s: AsyncSession, session_id: UUID, reason: str) -> None: ...

    async def revoke_user(self, s: AsyncSession, user_id: UUID, tenant_id: UUID, reason: str) -> int: ...

    async def devices(
        self, s: AsyncSession, tenant_id: UUID, user_id: UUID, session_device_ids: Iterable[UUID]
    ) -> list[UserDeviceRow]: ...


class UserRevocation(Protocol):
    """The Redis side of an immediate revocation (``RevocationCache``)."""

    async def mark_sessions_revoked(self, sids: Iterable[UUID | None]) -> None: ...

    async def mark_user_revoked(self, user_id: UUID, tenant_id: UUID | None) -> None: ...


class ClaimsStaleMarker(Protocol):
    async def mark_claims_stale(self, tenant_id: UUID, user_id: UUID) -> None: ...


class OtpSender(Protocol):
    """``AuthModule.otp`` (``OtpIssuer``, application/otp.py)."""

    async def issue(
        self, phone: str, purpose: OtpPurpose, *, ip: str | None, tenant_id: UUID | None = None
    ) -> OtpIssued: ...


class DeviceStatusReader(Protocol):
    async def device_revoked(self, tenant_id: UUID, device_id: UUID) -> bool:
        """``True`` when ``app.devices.revoked_at`` is set or the device does not exist in the tenant."""
        ...
