"""SQL access for the auth module (14 §19, 12 §4.5).

``auth.*`` tables are reachable only through the SECURITY DEFINER functions;
they run in :func:`unscoped_transaction` because the tenant is not known yet
(login, code/token lookup by hash). Tenant data (memberships, roles,
subscriptions) is read inside :func:`tenant_transaction`, i.e. under RLS.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction, unscoped_transaction


@dataclass(frozen=True, slots=True)
class ClientRow:
    id: UUID
    client_id: str
    client_type: str
    name: str
    client_secret_encrypted: str | None
    redirect_uris: tuple[str, ...]
    allowed_grant_types: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class SigningKeyRow:
    kid: UUID
    algorithm: str
    purpose: str
    public_key: str
    private_key_encrypted: str
    status: str
    activated_at: datetime | None
    retired_at: datetime | None


@dataclass(frozen=True, slots=True)
class UserCredentialRow:
    user_id: UUID
    password_hash: str | None
    failed_login_count: int
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class MembershipRow:
    tenant_id: UUID
    tenant_name: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class CodeRow:
    client_id: UUID
    user_id: UUID
    tenant_id: UUID | None
    code_challenge: str
    code_challenge_method: str
    redirect_uri: str
    scope: str


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    session_id: UUID | None
    refresh_token_id: UUID
    family_id: UUID


@dataclass(frozen=True, slots=True)
class RefreshRow:
    refresh_token_id: UUID
    family_id: UUID
    client_id: UUID
    user_id: UUID
    tenant_id: UUID | None
    device_id: UUID | None
    scope: str
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    suspended_at: datetime | None
    family_issued_at: datetime
    session_id: UUID | None
    session_revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class RotateResult:
    outcome: str  # rotated | grace_replay | reuse_revoked | invalid
    refresh_token_id: UUID | None
    family_id: UUID | None
    suspended: bool


@dataclass(frozen=True, slots=True)
class SessionRow:
    session_id: UUID
    user_id: UUID
    tenant_id: UUID | None
    client_id: UUID
    device_id: UUID | None
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class RevokedFamily:
    session_id: UUID | None
    user_id: UUID
    tenant_id: UUID | None


@dataclass(frozen=True, slots=True)
class BranchRow:
    branch_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class SessionProfileRow:
    """Display data of ``GET /auth/session`` (14 §20), read under RLS in one transaction."""

    full_name: str
    phone: str
    tenant_name: str
    branches: tuple[BranchRow, ...]
    membership: MembershipContext


@dataclass(frozen=True, slots=True)
class MembershipContext:
    """The live authorization facts of a user in a tenant (read under RLS)."""

    status: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    role_codes: tuple[str, ...]
    permission_codes: frozenset[str]


_CLIENTS = text(
    "SELECT id, client_id, client_type, name, client_secret_encrypted, redirect_uris, allowed_grant_types, "
    "allowed_scopes, status FROM platform.oauth_clients"
)
_KEYS = text(
    "SELECT kid, algorithm, purpose, public_key, private_key_encrypted, status, activated_at, retired_at "
    "FROM platform.signing_keys WHERE purpose = :purpose AND status IN ('active', 'retired', 'next') "
    "ORDER BY created_at"
)
_FIND_USER = text(
    "SELECT user_id, password_hash, failed_login_count, locked_until FROM app.auth_find_user_by_phone(:phone)"
)
_RECORD_LOGIN = text(
    "SELECT failed_login_count, locked_until FROM "
    "app.auth_record_login(:phone, CAST(:ip AS inet), :success, :reason)"
)
_MEMBERSHIPS = text(
    "SELECT tenant_id, tenant_name, role_ids, branch_ids FROM app.auth_list_memberships(:user_id) "
    "ORDER BY tenant_name, tenant_id"
)
_ISSUE_CODE = text(
    "SELECT app.auth_issue_code(:code_hash, :client_id, :user_id, :tenant_id, :challenge, :redirect_uri, "
    ":scope, :ttl)"
)
_CONSUME_CODE = text(
    "SELECT client_id, user_id, tenant_id, code_challenge, code_challenge_method, redirect_uri, scope "
    "FROM app.auth_consume_code(:code_hash)"
)
_ISSUE_TOKENS = text(
    "SELECT session_id, refresh_token_id, family_id FROM app.auth_issue_tokens("
    ":user_id, :tenant_id, :client_id, :device_id, :rt_hash, :rt_expires_at, :scope, :with_session, "
    ":idle_expires_at, :absolute_expires_at, CAST(:ip AS inet), :user_agent)"
)
_LOOKUP_REFRESH = text("SELECT * FROM app.auth_lookup_refresh(:token_hash)")
_ROTATE = text(
    "SELECT outcome, refresh_token_id, family_id, suspended "
    "FROM app.auth_rotate_refresh(:token_hash, :new_hash, :new_expires_at)"
)
_REVOKE_FAMILY = text(
    "SELECT session_id, user_id, tenant_id FROM app.auth_revoke_refresh_family(:token_hash, :reason)"
)
_SESSION = text(
    "SELECT session_id, user_id, tenant_id, client_id, device_id, idle_expires_at, absolute_expires_at, "
    "revoked_at FROM app.auth_session_by_id(:sid)"
)
_TOUCH = text("SELECT app.auth_touch_session(:sid, :idle_expires_at)")
_REVOKE_SESSION = text("SELECT app.auth_revoke_session(:sid, :reason)")
_REVOKE_USER = text("SELECT app.auth_revoke_user(:user_id, :tenant_id, :reason)")
_USER_SESSIONS = text("SELECT session_id FROM app.auth_list_user_sessions(:user_id, :tenant_id)")
_SET_CREDENTIALS = text("SELECT app.auth_set_credentials(:user_id, :password_hash, :pin_hash)")
_PURGE_LOGIN_ATTEMPTS = text("SELECT app.auth_purge_login_attempts(make_interval(days => :days))")

_MEMBERSHIP = text(
    "SELECT status, role_ids, branch_ids FROM app.memberships "
    "WHERE tenant_id = :tenant_id AND user_id = :user_id"
)
_ROLE_FACTS = text(
    "SELECT r.id, r.system_code, rp.permission_code FROM app.roles r "
    "LEFT JOIN app.role_permissions rp ON rp.role_id = r.id AND rp.tenant_id = r.tenant_id "
    "WHERE r.tenant_id = :tenant_id AND r.id = ANY(CAST(:role_ids AS uuid[])) AND r.archived_at IS NULL"
)
_PERMISSION_LIMITS = text(
    "SELECT rp.limit_value FROM app.memberships m "
    "JOIN app.roles r ON r.tenant_id = m.tenant_id AND r.id = ANY(m.role_ids) AND r.archived_at IS NULL "
    "JOIN app.role_permissions rp ON rp.tenant_id = m.tenant_id AND rp.role_id = r.id "
    "WHERE m.tenant_id = :tenant_id AND m.user_id = :user_id AND m.status = 'active' "
    "AND rp.permission_code = :code"
)
_SUBSCRIPTION = text("SELECT status FROM app.subscriptions WHERE tenant_id = :tenant_id")
_PROFILE_USER = text("SELECT name, phone FROM app.users WHERE id = :user_id")
_PROFILE_TENANT = text("SELECT name FROM app.tenants WHERE id = :tenant_id")
_PROFILE_BRANCHES = text(
    "SELECT id, name FROM app.branches WHERE tenant_id = :tenant_id AND archived_at IS NULL "
    "AND (cardinality(CAST(:ids AS uuid[])) = 0 OR id = ANY(CAST(:ids AS uuid[]))) ORDER BY name, id"
)


def _tuple(value: Any) -> tuple[Any, ...]:
    return tuple(value or ())


class AuthRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # --- global reference data ----------------------------------------------------------------
    async def list_clients(self) -> list[ClientRow]:
        async with self._sf() as s, unscoped_transaction(s):
            rows = (await s.execute(_CLIENTS)).all()
        return [
            ClientRow(
                r.id, r.client_id, r.client_type, r.name, r.client_secret_encrypted,
                _tuple(r.redirect_uris), _tuple(r.allowed_grant_types), _tuple(r.allowed_scopes), r.status,
            )
            for r in rows
        ]  # fmt: skip

    async def list_signing_keys(self, purpose: str) -> list[SigningKeyRow]:
        async with self._sf() as s, unscoped_transaction(s):
            rows = (await s.execute(_KEYS, {"purpose": purpose})).all()
        return [SigningKeyRow(*r) for r in rows]

    # --- login -----------------------------------------------------------------------------------
    async def find_user_by_phone(self, phone: str) -> UserCredentialRow | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_FIND_USER, {"phone": phone})).first()
        return UserCredentialRow(*row) if row else None

    async def record_login(self, phone: str, ip: str | None, success: bool, reason: str | None) -> None:
        async with self._sf() as s, unscoped_transaction(s):
            await s.execute(_RECORD_LOGIN, {"phone": phone, "ip": ip, "success": success, "reason": reason})

    async def list_memberships(self, user_id: UUID) -> list[MembershipRow]:
        async with self._sf() as s, unscoped_transaction(s):
            rows = (await s.execute(_MEMBERSHIPS, {"user_id": user_id})).all()
        return [
            MembershipRow(r.tenant_id, r.tenant_name, _tuple(r.role_ids), _tuple(r.branch_ids)) for r in rows
        ]

    async def set_credentials(
        self, user_id: UUID, *, password_hash: str | None = None, pin_hash: str | None = None
    ) -> None:
        async with self._sf() as s, unscoped_transaction(s):
            await s.execute(
                _SET_CREDENTIALS, {"user_id": user_id, "password_hash": password_hash, "pin_hash": pin_hash}
            )

    # --- authorization codes ---------------------------------------------------------------------
    async def issue_code(
        self,
        *,
        code_hash: str,
        client_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        code_challenge: str,
        redirect_uri: str,
        scope: str,
        ttl_s: int,
    ) -> None:
        params = {
            "code_hash": code_hash, "client_id": client_id, "user_id": user_id, "tenant_id": tenant_id,
            "challenge": code_challenge, "redirect_uri": redirect_uri, "scope": scope, "ttl": ttl_s,
        }  # fmt: skip
        async with self._sf() as s, unscoped_transaction(s):
            await s.execute(_ISSUE_CODE, params)

    async def consume_code(self, code_hash: str) -> CodeRow | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_CONSUME_CODE, {"code_hash": code_hash})).first()
        return CodeRow(*row) if row else None

    # --- tokens and sessions ---------------------------------------------------------------------
    async def issue_tokens(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        client_id: UUID,
        device_id: UUID | None,
        refresh_hash: str,
        refresh_expires_at: datetime,
        scope: str,
        with_session: bool,
        idle_expires_at: datetime | None,
        absolute_expires_at: datetime | None,
        ip: str | None,
        user_agent: str | None,
    ) -> IssuedTokens:
        params = {
            "user_id": user_id, "tenant_id": tenant_id, "client_id": client_id, "device_id": device_id,
            "rt_hash": refresh_hash, "rt_expires_at": refresh_expires_at, "scope": scope,
            "with_session": with_session, "idle_expires_at": idle_expires_at,
            "absolute_expires_at": absolute_expires_at, "ip": ip, "user_agent": user_agent,
        }  # fmt: skip
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_ISSUE_TOKENS, params)).one()
        return IssuedTokens(row.session_id, row.refresh_token_id, row.family_id)

    async def lookup_refresh(self, token_hash: str) -> RefreshRow | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_LOOKUP_REFRESH, {"token_hash": token_hash})).first()
        return RefreshRow(*row) if row else None

    async def rotate_refresh(self, token_hash: str, new_hash: str, new_expires_at: datetime) -> RotateResult:
        params = {"token_hash": token_hash, "new_hash": new_hash, "new_expires_at": new_expires_at}
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_ROTATE, params)).one()
        return RotateResult(row.outcome, row.refresh_token_id, row.family_id, bool(row.suspended))

    async def revoke_refresh_family(self, token_hash: str, reason: str) -> RevokedFamily | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_REVOKE_FAMILY, {"token_hash": token_hash, "reason": reason})).first()
        return RevokedFamily(*row) if row else None

    async def session_by_id(self, sid: UUID) -> SessionRow | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_SESSION, {"sid": sid})).first()
        return SessionRow(*row) if row else None

    async def touch_session(self, sid: UUID, idle_expires_at: datetime) -> None:
        async with self._sf() as s, unscoped_transaction(s):
            await s.execute(_TOUCH, {"sid": sid, "idle_expires_at": idle_expires_at})

    async def revoke_session(self, sid: UUID, reason: str) -> None:
        async with self._sf() as s, unscoped_transaction(s):
            await s.execute(_REVOKE_SESSION, {"sid": sid, "reason": reason})

    async def list_user_sessions(self, user_id: UUID, tenant_id: UUID | None) -> list[UUID]:
        async with self._sf() as s, unscoped_transaction(s):
            rows = (await s.execute(_USER_SESSIONS, {"user_id": user_id, "tenant_id": tenant_id})).all()
        return [r.session_id for r in rows]

    async def revoke_user(self, user_id: UUID, tenant_id: UUID | None, reason: str) -> int:
        async with self._sf() as s, unscoped_transaction(s):
            count = (
                await s.execute(_REVOKE_USER, {"user_id": user_id, "tenant_id": tenant_id, "reason": reason})
            ).scalar_one()
        return int(count or 0)

    async def purge_login_attempts(self, older_than_days: int) -> int:
        """``login_attempts`` retention (14 §19): only the SECURITY DEFINER purge may delete (12 §3)."""
        async with self._sf() as s, unscoped_transaction(s):
            deleted = (await s.execute(_PURGE_LOGIN_ATTEMPTS, {"days": older_than_days})).scalar_one()
        return int(deleted or 0)

    # --- tenant facts (RLS) ----------------------------------------------------------------------
    async def membership_context(self, tenant_id: UUID, user_id: UUID) -> MembershipContext | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            return await self._membership_context(s, tenant_id, user_id)

    async def session_profile(self, tenant_id: UUID, user_id: UUID) -> SessionProfileRow | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            membership = await self._membership_context(s, tenant_id, user_id)
            user = (await s.execute(_PROFILE_USER, {"user_id": user_id})).first()
            tenant_name = (await s.execute(_PROFILE_TENANT, {"tenant_id": tenant_id})).scalar()
            if membership is None or user is None or tenant_name is None:
                return None
            ids = [str(b) for b in membership.branch_ids]
            rows = (await s.execute(_PROFILE_BRANCHES, {"tenant_id": tenant_id, "ids": ids})).all()
        return SessionProfileRow(
            full_name=user.name,
            phone=user.phone,
            tenant_name=str(tenant_name),
            branches=tuple(BranchRow(r.id, r.name) for r in rows),
            membership=membership,
        )

    @staticmethod
    async def _membership_context(
        s: AsyncSession, tenant_id: UUID, user_id: UUID
    ) -> MembershipContext | None:
        m = (await s.execute(_MEMBERSHIP, {"tenant_id": tenant_id, "user_id": user_id})).first()
        if m is None:
            return None
        role_ids = _tuple(m.role_ids)
        facts: Sequence[Any] = (
            await s.execute(_ROLE_FACTS, {"tenant_id": tenant_id, "role_ids": [str(r) for r in role_ids]})
        ).all()
        role_codes: dict[UUID, str] = {}
        permissions: set[str] = set()
        for role_id, system_code, permission_code in facts:
            role_codes[role_id] = system_code or str(role_id)
            if permission_code:
                permissions.add(permission_code)
        return MembershipContext(
            status=m.status,
            role_ids=role_ids,
            branch_ids=_tuple(m.branch_ids),
            role_codes=tuple(sorted(set(role_codes.values()))),
            permission_codes=frozenset(permissions),
        )

    async def permission_limits(self, tenant_id: UUID, user_id: UUID, code: str) -> list[Decimal | None]:
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            rows = (
                await s.execute(
                    _PERMISSION_LIMITS, {"tenant_id": tenant_id, "user_id": user_id, "code": code}
                )
            ).all()
        return [r.limit_value for r in rows]

    async def subscription_status(self, tenant_id: UUID) -> str | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            value = (await s.execute(_SUBSCRIPTION, {"tenant_id": tenant_id})).scalar()
        return str(value) if value is not None else None


@dataclass(frozen=True, slots=True)
class LockedMembership:
    id: UUID
    status: str


_LOCK_MEMBERSHIP = text(
    "SELECT id, status FROM app.memberships WHERE tenant_id = :tenant_id AND user_id = :user_id FOR UPDATE"
)
_SET_MEMBERSHIP_STATUS = text(
    "UPDATE app.memberships SET status = :status, version = version + 1 WHERE id = :id"
)


class MembershipAdminRepository:
    """SQL of the owner's block/unblock (14 §18.2).

    Every method runs on the caller's session: the status change, the session
    revocation, the audit row and the Idempotency-Key journal commit together.
    """

    @staticmethod
    async def lock(s: AsyncSession, tenant_id: UUID, user_id: UUID) -> LockedMembership | None:
        row = (await s.execute(_LOCK_MEMBERSHIP, {"tenant_id": tenant_id, "user_id": user_id})).first()
        return LockedMembership(row.id, row.status) if row else None

    @staticmethod
    async def set_status(s: AsyncSession, membership_id: UUID, status: str) -> None:
        await s.execute(_SET_MEMBERSHIP_STATUS, {"status": status, "id": membership_id})

    @staticmethod
    async def session_ids(s: AsyncSession, user_id: UUID, tenant_id: UUID) -> list[UUID]:
        rows = (await s.execute(_USER_SESSIONS, {"user_id": user_id, "tenant_id": tenant_id})).all()
        return [r.session_id for r in rows]

    @staticmethod
    async def revoke_user(s: AsyncSession, user_id: UUID, tenant_id: UUID, reason: str) -> int:
        params = {"user_id": user_id, "tenant_id": tenant_id, "reason": reason}
        return int((await s.execute(_REVOKE_USER, params)).scalar_one() or 0)
