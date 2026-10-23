"""Ports of the auth application layer (23 §1): rows it reads and the Protocols it depends on.

``application/*`` never imports ``infrastructure``; the SQL repositories implement these
Protocols structurally and ``wiring.py`` composes them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


# --- rows ---------------------------------------------------------------------------------------------
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
class InviteAcceptance:
    """The inviting tenant's membership after an ``invite`` code was redeemed (14 §18.2)."""

    membership_id: UUID
    status: str  # 'active' | 'blocked' — never 'invited' after a redeem
    accepted_now: bool  # this redeem moved it invited → active


@dataclass(frozen=True, slots=True)
class CodeRow:
    client_id: UUID
    user_id: UUID
    tenant_id: UUID | None
    code_challenge: str
    code_challenge_method: str
    redirect_uri: str
    scope: str
    device_id: UUID | None = None  # device-bound login (14 §7.2)


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
class DeviceBinding:
    """A device as the AS sees it when binding a login to it (14 §7.2), read under RLS."""

    device_id: UUID
    kind: str
    cash_register_id: UUID | None
    branch_id: UUID | None
    revoked: bool


@dataclass(frozen=True, slots=True)
class PinState:
    """``app.auth_pin_state`` (14 §4.3, §13) — the argon2 hash stays inside the auth module."""

    pin_hash: str | None
    pin_local_hash: str | None
    must_change_pin: bool
    pin_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class BranchRow:
    branch_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class MembershipContext:
    """The live authorization facts of a user in a tenant (read under RLS)."""

    status: str
    role_ids: tuple[UUID, ...]
    branch_ids: tuple[UUID, ...]
    role_codes: tuple[str, ...]
    permission_codes: frozenset[str]


@dataclass(frozen=True, slots=True)
class SessionProfileRow:
    """Display data of ``GET /auth/session`` (14 §20), read under RLS in one transaction."""

    full_name: str
    phone: str
    tenant_name: str
    branches: tuple[BranchRow, ...]
    membership: MembershipContext


# --- the AS/RS store ----------------------------------------------------------------------------------
class AuthStore(Protocol):
    """``auth.*`` through the SECURITY DEFINER functions (12 §4.5) + tenant facts under RLS."""

    async def list_clients(self) -> list[ClientRow]: ...
    async def list_signing_keys(self, purpose: str) -> list[SigningKeyRow]: ...
    async def find_user_by_phone(self, phone: str) -> UserCredentialRow | None: ...
    async def record_login(self, phone: str, ip: str | None, success: bool, reason: str | None) -> None: ...
    async def list_memberships(self, user_id: UUID) -> list[MembershipRow]: ...
    async def set_credentials(
        self, user_id: UUID, *, password_hash: str | None = None, pin_hash: str | None = None
    ) -> None: ...
    async def has_pin(self, user_id: UUID) -> bool: ...
    async def accept_invite(self, tenant_id: UUID, user_id: UUID) -> InviteAcceptance | None:
        """``invited`` → ``active`` in that tenant (``None`` — no membership there)."""
        ...

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
        device_id: UUID | None = None,
    ) -> None: ...
    async def consume_code(self, code_hash: str) -> CodeRow | None: ...
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
    ) -> IssuedTokens: ...
    async def lookup_refresh(self, token_hash: str) -> RefreshRow | None: ...
    async def rotate_refresh(
        self, token_hash: str, new_hash: str, new_expires_at: datetime
    ) -> RotateResult: ...
    async def revoke_refresh_family(self, token_hash: str, reason: str) -> RevokedFamily | None: ...
    async def session_by_id(self, sid: UUID) -> SessionRow | None: ...
    async def touch_session(self, sid: UUID, idle_expires_at: datetime) -> None: ...
    async def revoke_session(self, sid: UUID, reason: str) -> None: ...
    async def list_user_sessions(self, user_id: UUID, tenant_id: UUID | None) -> list[UUID]: ...
    async def revoke_user(self, user_id: UUID, tenant_id: UUID | None, reason: str) -> int: ...
    async def purge_login_attempts(self, older_than_days: int) -> int: ...
    async def membership_context(self, tenant_id: UUID, user_id: UUID) -> MembershipContext | None: ...
    async def session_profile(self, tenant_id: UUID, user_id: UUID) -> SessionProfileRow | None: ...
    async def permission_limits(self, tenant_id: UUID, user_id: UUID, code: str) -> list[Decimal | None]: ...
    async def subscription_status(self, tenant_id: UUID) -> str | None: ...
    async def device_revoked(self, tenant_id: UUID, device_id: UUID) -> bool: ...
    # --- B3 device-auth ---
    async def device_binding(self, tenant_id: UUID, device_id: UUID) -> DeviceBinding | None: ...
    async def family_revoked(self, family_id: UUID) -> bool: ...
    async def session_family(self, sid: UUID) -> UUID | None: ...
    async def pin_state(self, tenant_id: UUID, user_id: UUID) -> PinState | None:
        """Only for a member of ``tenant_id`` (SEC-12: joins the current tenant's memberships)."""
        ...

    async def set_pin_local_hash(self, user_id: UUID, pin_hash: str, pin_local_hash: str) -> bool: ...
    async def pin_reset_at(self, tenant_id: UUID, user_id: UUID) -> datetime | None: ...


# --- OTP (14 §4.2) ------------------------------------------------------------------------------------
OtpOutcome = Literal["ok", "invalid", "expired", "locked", "used"]


class OtpStore(Protocol):
    async def create_challenge(
        self, phone: str, purpose: str, channel: str, code_hash: str, ttl_s: int
    ) -> UUID: ...
    async def verify_challenge(self, challenge_id: UUID, code_hash: str) -> OtpOutcome: ...
    async def telegram_chat_by_phone(self, phone: str) -> str | None: ...
    async def find_user_by_phone(self, phone: str) -> UserCredentialRow | None: ...
    async def list_memberships(self, user_id: UUID) -> list[MembershipRow]: ...


class MessageSender(Protocol):
    """One OTP delivery channel (Telegram chat id or phone); ``False`` = not delivered."""

    async def send(self, destination: str, text: str) -> bool: ...


# --- signup provisioning (15 §1.5) --------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NewTenant:
    tenant_id: UUID
    user_id: UUID
    phone: str
    owner_name: str
    store_name: str
    business_type: str
    legal_form: str
    terms_version: str
    ip: str | None
    ai_cross_border_consent: bool
    password_hash: str | None
    valuation_valid_from: date
    signup_date: date  # Asia/Tashkent


class SignupStore(Protocol):
    """SQL of the one signup transaction; every call runs on the caller's session."""

    async def current_terms_version(self, session: AsyncSession, kind: str) -> str | None: ...
    async def insert_tenant(self, session: AsyncSession, t: NewTenant) -> None: ...
    async def insert_user(self, session: AsyncSession, t: NewTenant) -> bool:
        """``False`` when the phone is already taken (nothing inserted)."""
        ...

    async def insert_owner_membership(
        self, session: AsyncSession, t: NewTenant, owner_role_id: UUID
    ) -> None: ...
    async def insert_valuation_method(self, session: AsyncSession, t: NewTenant) -> None: ...
    async def insert_branch_tax_setting(
        self, session: AsyncSession, t: NewTenant, branch_id: UUID, valid_from: date, settlement_category: str
    ) -> None: ...
    async def insert_consent(
        self, session: AsyncSession, t: NewTenant, purpose: str, version: str
    ) -> None: ...
    async def set_credentials(
        self, session: AsyncSession, user_id: UUID, password_hash: str | None
    ) -> None: ...
    async def link_identity(
        self, session: AsyncSession, user_id: UUID, sub: str, email: str | None, email_verified: bool
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class TenantProvisioning:
    """Other modules' provisioning entry points (their ``wiring.py``), composed by auth wiring.

    Every callable runs on the signup session — one transaction (15 §1.5).
    """

    provision_roles: Callable[[AsyncSession, UUID], Awaitable[Mapping[str, UUID]]]
    # (session, tenant_id, name, settlement_category, activity_type)
    ensure_default_branch: Callable[[AsyncSession, UUID, str, str, str], Awaitable[UUID]]
    ensure_default_cash_register: Callable[[AsyncSession, UUID, UUID], Awaitable[UUID]]
    create_default_categories: Callable[[AsyncSession, UUID], Awaitable[None]]
    start_trial: Callable[[AsyncSession, UUID], Awaitable[datetime]]


# --- Google OIDC (14 §2.2, 21 §9.3) -------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    sub: str
    email: str | None
    email_verified: bool
    name: str | None


class GoogleAuthError(Exception):
    """Google said no, or the ID token did not verify → ``GOOGLE_AUTH_FAILED``."""


class GoogleOidcPort(Protocol):
    def build_auth_url(self, *, state: str, code_challenge: str, nonce: str, redirect_uri: str) -> str: ...
    async def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str, nonce: str
    ) -> GoogleIdentity: ...
    async def verify_id_token(self, id_token: str, *, nonce: str | None = None) -> GoogleIdentity: ...


class IdentityStore(Protocol):
    async def user_by_identity(self, provider: str, sub: str) -> UUID | None: ...
    async def user_by_verified_email(self, provider: str, email: str) -> UUID | None: ...
    async def link_identity(
        self, user_id: UUID, sub: str, email: str | None, email_verified: bool
    ) -> None: ...
