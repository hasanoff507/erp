"""BO-11 staff administration by the tenant owner (14 §18.2, US-M13-01…07, 31 QT-M13-*).

* ``POST /admin/users`` — membership + one-time invite code (``purpose=invite``, 14 §4.2) bound to
  this tenant. A new phone creates the user and an ``active`` membership (the person has no
  credentials until he redeems the code). A phone of an existing account creates an ``invited``
  membership with the inviter's ``invited_name``: it gives no access (login, tenant choice,
  switch-tenant, ``/auth/session`` ignore it) and the list shows ``invited_name``, never the global
  ``users.name``, until that person redeems the code (``/auth/otp/verify`` → ``active``). The code is
  issued inside the transaction: if no channel delivers it, nothing is created.
* ``PATCH /admin/users/{id}`` — block/unblock (immediate revoke of every session and refresh family in
  this tenant + Redis caches, QT-OAUTH-07) and role/branch assignment ("claims stale", 14 §5).
  The tenant always keeps an active owner (QT-M13-09).
* reset-password / reset-pin — the old credential is cleared first (``auth_reset_credentials``),
  sessions die on a password reset, then a one-time code is sent; a secret never leaves the server.
  The password/PIN is global, so a tenant may reset it only for a user who belongs to it alone: an
  ``invited`` (not accepted) member or one with an active membership elsewhere → ``422``
  ``validation.credential_shared_across_tenants`` (blocking / revoking this tenant's sessions stay).
* a member holding the ``owner`` role is changed/reset/revoked only by an owner (``403 OWNER_ONLY``) —
  a custom role with ``settings.users`` cannot take over the owner.
* sessions / devices — list, revoke all, revoke one (US-M13-07).

Every write is ONE tenant transaction: the change, the session revocation, the audit rows and the
Idempotency-Key journal commit together; the Redis side (sid/user revoke markers, BFF session drop,
``/auth/session`` profile cache, claims-stale watermark) follows right after the commit.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.auth.application.admin_ports import (
    ClaimsStaleMarker,
    LockedMembership,
    OtpSender,
    StaffRepository,
    StaffRow,
    UserDeviceRow,
    UserRevocation,
    UserSessionRow,
)
from app.modules.auth.application.otp import OtpIssued, OtpPurpose

MembershipStatus = Literal["active", "blocked", "invited"]
OWNER_ROLE = "owner"
MAX_PAGE = 200
REVOKE_REASON_BLOCKED = "membership_blocked"
REVOKE_REASON_ADMIN = "admin_revoke"


# --- views -------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class StaffView:
    user_id: UUID
    name: str
    phone: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    status: str
    last_login_at: datetime | None

    @classmethod
    def of(cls, row: StaffRow) -> StaffView:
        return cls(
            row.user_id, row.name, row.phone, row.role_ids, row.branch_ids, row.status, row.last_login_at
        )


@dataclass(frozen=True, slots=True)
class StaffPage:
    items: list[StaffView]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class InvitedStaff:
    user: StaffView
    channel_used: str


@dataclass(frozen=True, slots=True)
class MembershipStatusResult:
    user_id: UUID
    status: MembershipStatus
    sessions_revoked: int


@dataclass(frozen=True, slots=True)
class CredentialResetResult:
    user_id: UUID
    sessions_revoked: int
    channel_used: str


@dataclass(frozen=True, slots=True)
class SessionView:
    session_id: UUID
    client_id: str
    device_id: UUID | None
    device_kind: str | None
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


@dataclass(frozen=True, slots=True)
class SessionsRevoked:
    user_id: UUID
    sessions_revoked: int


# --- cursor (17 §4: base64 of the (created_at, id) pair) ----------------------------------------------
def encode_cursor(created_at: datetime, membership_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{membership_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, _, ident = raw.partition("|")
        created_at = datetime.fromisoformat(stamp)
        if created_at.tzinfo is None:
            raise ValueError("naive cursor timestamp")
        return created_at, UUID(ident)
    except (ValueError, UnicodeDecodeError):
        raise _invalid("cursor", "validation.invalid") from None


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _owner_only() -> AppError:
    return AppError(
        ErrorCode.OWNER_ONLY, params={"permission": "settings.users", "reason": "target_is_owner"}
    )


def _not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "users"})


def _unique(values: Sequence[UUID]) -> tuple[UUID, ...]:
    return tuple(dict.fromkeys(values))


class AdminUsersService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: StaffRepository,
        revocation: UserRevocation,
        drop_bff_session: Callable[[UUID], Awaitable[None]],
        forget_profile: Callable[[UUID, UUID], Awaitable[None]],
        claims: ClaimsStaleMarker,
        otp: OtpSender,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._revocation = revocation
        self._drop = drop_bff_session
        self._forget_profile = forget_profile
        self._claims = claims
        self._otp = otp

    # --- reads ---------------------------------------------------------------------------------
    async def list_users(self, actor: Principal, *, cursor: str | None, limit: int) -> StaffPage:
        after = decode_cursor(cursor) if cursor else None
        size = max(1, min(limit, MAX_PAGE))
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_staff(s, actor.tenant_id, after=after, limit=size + 1)
        page, more = rows[:size], len(rows) > size
        next_cursor = encode_cursor(page[-1].created_at, page[-1].membership_id) if more else None
        return StaffPage([StaffView.of(r) for r in page], next_cursor)

    async def sessions(self, actor: Principal, user_id: UUID) -> list[SessionView]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._member(s, actor.tenant_id, user_id)
            rows = await self._repo.sessions(s, user_id, actor.tenant_id)
        return [self._session_view(r, actor) for r in rows]

    async def devices(self, actor: Principal, user_id: UUID) -> list[UserDeviceRow]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._member(s, actor.tenant_id, user_id)
            sessions = await self._repo.sessions(s, user_id, actor.tenant_id)
            ids = {r.device_id for r in sessions if r.device_id is not None}
            return await self._repo.devices(s, actor.tenant_id, user_id, ids)

    # --- create (invite) ------------------------------------------------------------------------
    async def create(
        self,
        actor: Principal,
        *,
        phone: str,
        name: str,
        role_ids: Sequence[UUID],
        branch_ids: Sequence[UUID],
        ip: str | None,
    ) -> InvitedStaff:
        roles, branches = _unique(role_ids), _unique(branch_ids)
        tenant = actor.tenant_id
        async with self._sf() as s, tenant_transaction(s, tenant, user_id=actor.user_id):
            await self._validate_roles(s, tenant, roles, current=())
            await self._validate_branches(s, tenant, branches)
            user_id = await self._repo.visible_user_by_phone(s, phone)
            if user_id is not None and await self._repo.lock(s, tenant, user_id) is not None:
                raise _invalid("phone", "validation.phone_already_member")
            linked = user_id is not None
            if user_id is None:
                user_id = await self._repo.user_id_by_phone(s, phone)
                linked = user_id is not None
            if user_id is None:
                user_id = uuid7()
                if not await self._repo.insert_user(s, user_id, phone, name, actor.user_id):
                    # the phone exists but is reachable neither under RLS nor via auth_find_user_by_phone
                    raise _invalid("phone", "validation.phone_unavailable")
            # an existing account joins only when its owner redeems the code (14 §18.2)
            await self._repo.insert_membership(
                s, uuid7(), tenant, user_id, roles, branches, invited_name=name if linked else None
            )
            issued = await self._otp.issue(phone, "invite", ip=ip, tenant_id=tenant)
            await record_audit(
                s, tenant_id=tenant, user_id=actor.user_id, action="user_created", entity="users",
                entity_id=user_id, ip=ip,
                after={"role_ids": [str(r) for r in roles], "branch_ids": [str(b) for b in branches],
                       "existing_user": linked, "invite_channel": issued.channel_used},
            )  # fmt: skip
            row = await self._repo.get_staff(s, tenant, user_id)
            assert row is not None
            result = InvitedStaff(StaffView.of(row), issued.channel_used)
            stage_response(_invited_body(result), 201)
        return result

    # --- update (status, roles, branches) ---------------------------------------------------------
    async def update(
        self,
        actor: Principal,
        user_id: UUID,
        *,
        status: MembershipStatus | None,
        role_ids: Sequence[UUID] | None,
        branch_ids: Sequence[UUID] | None,
        ip: str | None,
    ) -> MembershipStatusResult:
        if status is None and role_ids is None and branch_ids is None:
            raise _invalid("status", "validation.required")
        if status == "blocked" and user_id == actor.user_id:
            raise _invalid("status", "validation.cannot_block_self")
        tenant = actor.tenant_id
        sids: list[UUID] = []
        revoked = 0
        assignment_changed = False
        async with self._sf() as s, tenant_transaction(s, tenant, user_id=actor.user_id):
            row = await self._repo.lock(s, tenant, user_id)
            if row is None:
                raise _not_found()
            await self._guard_owner_target(s, tenant, actor.user_id, row.role_ids)
            new_roles = _unique(role_ids) if role_ids is not None else row.role_ids
            new_branches = _unique(branch_ids) if branch_ids is not None else row.branch_ids
            if role_ids is not None:
                await self._validate_roles(s, tenant, new_roles, current=row.role_ids)
            if branch_ids is not None:
                await self._validate_branches(s, tenant, new_branches)
            final_status = self._next_status(row, status)
            if final_status == "blocked" and row.status != "blocked":
                await self._keep_an_owner(s, tenant, user_id)

            if (new_roles, new_branches) != (row.role_ids, row.branch_ids):
                await self._repo.set_assignment(s, row.id, new_roles, new_branches)
                assignment_changed = True
                await record_audit(
                    s, tenant_id=tenant, user_id=actor.user_id, action="membership_changed",
                    entity="memberships", entity_id=row.id, ip=ip,
                    before={"role_ids": [str(r) for r in row.role_ids],
                            "branch_ids": [str(b) for b in row.branch_ids]},
                    after={"user_id": str(user_id), "role_ids": [str(r) for r in new_roles],
                           "branch_ids": [str(b) for b in new_branches]},
                )  # fmt: skip
            if final_status != row.status:
                await self._repo.set_status(s, row.id, final_status)
                await record_audit(
                    s, tenant_id=tenant, user_id=actor.user_id, action="membership_status_changed",
                    entity="memberships", entity_id=row.id, before={"status": row.status},
                    after={"status": final_status, "user_id": str(user_id)}, ip=ip,
                )  # fmt: skip
                await record_audit(
                    s, tenant_id=tenant, user_id=actor.user_id,
                    action="user_blocked" if final_status == "blocked" else "user_unblocked",
                    entity="users", entity_id=user_id, ip=ip,
                )  # fmt: skip
            if status == "blocked":
                sids = await self._repo.session_ids(s, user_id, tenant)
                revoked = await self._repo.revoke_user(s, user_id, tenant, REVOKE_REASON_BLOCKED)
                await record_audit(
                    s, tenant_id=tenant, user_id=actor.user_id, action="all_sessions_revoked",
                    entity="users", entity_id=user_id, ip=ip,
                    after={"sessions": revoked, "reason": REVOKE_REASON_BLOCKED},
                )  # fmt: skip
            result = MembershipStatusResult(user_id, final_status, revoked)
            # Idempotency-Key journal row commits with the membership change (23 §3)
            stage_response(asdict(result))
        await self._forget_profile(tenant, user_id)  # /auth/session cache (14 §20)
        if assignment_changed:
            await self._claims.mark_claims_stale(tenant, user_id)
        if status == "blocked":
            # after commit: the RS sees the revocation on the very next request
            await self._after_revoke(sids, user_id, tenant)
        return result

    # --- credentials --------------------------------------------------------------------------------
    async def reset_password(self, actor: Principal, user_id: UUID, ip: str | None) -> CredentialResetResult:
        """Old password cleared + every session/refresh family of the user revoked, then ``admin_reset``."""
        tenant = actor.tenant_id
        async with self._sf() as s, tenant_transaction(s, tenant, user_id=actor.user_id):
            staff = await self._member(s, tenant, user_id)
            await self._guard_owner_target(s, tenant, actor.user_id, staff.role_ids)
            await self._credential_is_local(s, tenant, staff)
            # the user belongs to this tenant alone: "every tenant" (the credential is global) is this one
            sids = await self._repo.session_ids(s, user_id, None)
            await self._repo.reset_credentials(s, user_id, password=True, pin=False)
            await record_audit(
                s, tenant_id=tenant, user_id=actor.user_id, action="password_reset", entity="users",
                entity_id=user_id, ip=ip, after={"initiator": "owner"},
            )  # fmt: skip
            await record_audit(
                s, tenant_id=tenant, user_id=actor.user_id, action="all_sessions_revoked", entity="users",
                entity_id=user_id, ip=ip, after={"sessions": len(sids), "reason": "credential_reset"},
            )  # fmt: skip
            issued = await self._send_code(staff.phone, "admin_reset", ip)
            result = CredentialResetResult(user_id, len(sids), issued.channel_used)
            stage_response(asdict(result))
        await self._forget_profile(tenant, user_id)
        await self._after_revoke(sids, user_id, None)
        return result

    async def reset_pin(self, actor: Principal, user_id: UUID, ip: str | None) -> CredentialResetResult:
        """Old PIN cleared (``must_change_pin``), then ``pin_reset`` code; sessions stay (PIN is local)."""
        tenant = actor.tenant_id
        async with self._sf() as s, tenant_transaction(s, tenant, user_id=actor.user_id):
            staff = await self._member(s, tenant, user_id)
            await self._guard_owner_target(s, tenant, actor.user_id, staff.role_ids)
            await self._credential_is_local(s, tenant, staff)
            await self._repo.reset_credentials(s, user_id, password=False, pin=True)
            await record_audit(
                s, tenant_id=tenant, user_id=actor.user_id, action="pin_reset_forced", entity="users",
                entity_id=user_id, ip=ip,
            )  # fmt: skip
            issued = await self._send_code(staff.phone, "pin_reset", ip)
            result = CredentialResetResult(user_id, 0, issued.channel_used)
            stage_response(asdict(result))
        return result

    # --- sessions ------------------------------------------------------------------------------------
    async def revoke_sessions(self, actor: Principal, user_id: UUID, ip: str | None) -> SessionsRevoked:
        tenant = actor.tenant_id
        async with self._sf() as s, tenant_transaction(s, tenant, user_id=actor.user_id):
            staff = await self._member(s, tenant, user_id)
            await self._guard_owner_target(s, tenant, actor.user_id, staff.role_ids)
            sids = await self._repo.session_ids(s, user_id, tenant)
            revoked = await self._repo.revoke_user(s, user_id, tenant, REVOKE_REASON_ADMIN)
            await record_audit(
                s, tenant_id=tenant, user_id=actor.user_id, action="all_sessions_revoked", entity="users",
                entity_id=user_id, ip=ip, after={"sessions": revoked, "reason": REVOKE_REASON_ADMIN},
            )  # fmt: skip
            result = SessionsRevoked(user_id, revoked)
            stage_response(asdict(result))
        await self._after_revoke(sids, user_id, tenant)
        return result

    async def revoke_session(
        self, actor: Principal, user_id: UUID, session_id: UUID, ip: str | None
    ) -> SessionsRevoked:
        """Exactly one session (and its refresh family); the user's other sessions are untouched."""
        tenant = actor.tenant_id
        async with self._sf() as s, tenant_transaction(s, tenant, user_id=actor.user_id):
            staff = await self._member(s, tenant, user_id)
            await self._guard_owner_target(s, tenant, actor.user_id, staff.role_ids)
            if session_id not in await self._repo.session_ids(s, user_id, tenant):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "sessions"})
            await self._repo.revoke_session(s, session_id, REVOKE_REASON_ADMIN)
            await record_audit(
                s, tenant_id=tenant, user_id=actor.user_id, action="session_revoked", entity="sessions",
                entity_id=session_id, ip=ip, after={"user_id": str(user_id), "reason": REVOKE_REASON_ADMIN},
            )  # fmt: skip
            result = SessionsRevoked(user_id, 1)
            stage_response(asdict(result))
        await self._revocation.mark_sessions_revoked([session_id])
        await self._drop(session_id)
        return result

    # --- helpers -------------------------------------------------------------------------------------
    async def _member(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> StaffRow:
        row = await self._repo.get_staff(s, tenant_id, user_id)
        if row is None:
            raise _not_found()
        return row

    @staticmethod
    def _next_status(row: LockedMembership, requested: MembershipStatus | None) -> MembershipStatus:
        """``active`` never skips an invite: an unaccepted membership unblocks back to ``invited``."""
        if requested is None:
            return cast(MembershipStatus, row.status)
        if requested == "blocked":
            return "blocked"
        return "invited" if row.invited_name is not None else "active"

    async def _guard_owner_target(
        self, s: AsyncSession, tenant_id: UUID, actor_id: UUID, target_roles: tuple[UUID, ...]
    ) -> None:
        """An owner's membership is changed only by an owner (re-read from the DB, not the token)."""
        if not target_roles:
            return
        if not any(r.system_code == OWNER_ROLE for r in await self._repo.roles(s, tenant_id, target_roles)):
            return
        if actor_id not in await self._repo.active_owner_ids(s, tenant_id):
            raise _owner_only()

    async def _credential_is_local(self, s: AsyncSession, tenant_id: UUID, staff: StaffRow) -> None:
        """Password/PIN are global: never reset them for a user this tenant does not own alone."""
        if staff.pending_invite or await self._repo.active_memberships_elsewhere(s, staff.user_id, tenant_id):
            raise _invalid("user_id", "validation.credential_shared_across_tenants")

    async def _validate_roles(
        self, s: AsyncSession, tenant_id: UUID, role_ids: tuple[UUID, ...], *, current: tuple[UUID, ...]
    ) -> None:
        if not role_ids:
            raise _invalid("role_ids", "validation.required")
        found = {r.id: r for r in await self._repo.roles(s, tenant_id, role_ids)}
        if len(found) != len(role_ids):
            raise _invalid("role_ids", "validation.role_not_found")
        # the owner role is neither granted nor taken away here (07 BO-11 lists Kassir/Omborchi/
        # Menejer/Buxgalter): the tenant can never lose its owner through BO-11 (QT-M13-09)
        owner_after = {r for r, ref in found.items() if ref.system_code == OWNER_ROLE}
        owner_before = (
            {r.id for r in await self._repo.roles(s, tenant_id, current) if r.system_code == OWNER_ROLE}
            if current
            else set()
        )
        if owner_after != owner_before:
            raise _invalid("role_ids", "validation.owner_role_not_assignable")

    async def _validate_branches(
        self, s: AsyncSession, tenant_id: UUID, branch_ids: tuple[UUID, ...]
    ) -> None:
        if not branch_ids:
            raise _invalid("branch_ids", "validation.required")
        if len(await self._repo.existing_branches(s, tenant_id, branch_ids)) != len(branch_ids):
            raise _invalid("branch_ids", "validation.branch_not_found")

    async def _keep_an_owner(self, s: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        owners = await self._repo.active_owner_ids(s, tenant_id)
        if user_id in owners and not owners - {user_id}:
            raise _invalid("status", "validation.tenant_requires_active_owner")

    async def _send_code(self, phone: str, purpose: OtpPurpose, ip: str | None) -> OtpIssued:
        """Inside the transaction: if no channel delivers the code, the change is rolled back.

        ``otp_requested`` is audited by the OTP service itself (per tenant of the user).
        """
        return await self._otp.issue(phone, purpose, ip=ip)

    async def _after_revoke(self, sids: list[UUID], user_id: UUID, tenant_id: UUID | None) -> None:
        await self._revocation.mark_sessions_revoked(sids)
        await self._revocation.mark_user_revoked(user_id, tenant_id)  # sid-less (Android) tokens
        for sid in sids:
            await self._drop(sid)

    @staticmethod
    def _session_view(row: UserSessionRow, actor: Principal) -> SessionView:
        return SessionView(
            row.session_id, row.client_id, row.device_id, row.device_kind, row.created_at, row.last_seen_at,
            row.ip, row.user_agent, current=row.session_id == actor.sid,
        )  # fmt: skip


def _invited_body(result: InvitedStaff) -> dict[str, Any]:
    body = asdict(result.user)
    body["channel_used"] = result.channel_used
    return body
