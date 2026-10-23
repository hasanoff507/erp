"""Composition of the auth module (23 §1 ``wiring.py``)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.core.auth.tokens import CsrfTokens, SessionCookieSigner
from app.core.config import Settings
from app.core.db.session import Database
from app.core.secrets import EnvelopeCipher
from app.modules.access.wiring import provision_system_roles
from app.modules.auth.application.actor import ActorBindings
from app.modules.auth.application.admin_users import AdminUsersService
from app.modules.auth.application.agent_grants import AgentGrantPolicy, AgentGrantService
from app.modules.auth.application.bff import BffService
from app.modules.auth.application.credentials import CredentialService
from app.modules.auth.application.device_cookie import DeviceCookieSigner
from app.modules.auth.application.gateway import AccessGuard, ErpAuthGateway
from app.modules.auth.application.google import GoogleSignInService
from app.modules.auth.application.keys import AccessTokenCodec, SigningKeyRing
from app.modules.auth.application.login import LoginPolicy, LoginService
from app.modules.auth.application.oauth_server import ErpAuthorizationServer
from app.modules.auth.application.otp import OtpPolicy, OtpService
from app.modules.auth.application.passwords import hash_password
from app.modules.auth.application.pin import PinPolicy, PinService
from app.modules.auth.application.ports import AuthStore, GoogleOidcPort, MessageSender, TenantProvisioning
from app.modules.auth.application.revocation import RevocationCache
from app.modules.auth.application.session_profile import SessionProfileService
from app.modules.auth.application.signup import SignupService
from app.modules.auth.application.staff_snapshot import StaffPinRow, StaffPinSnapshot
from app.modules.auth.application.subscription import SubscriptionStatusService
from app.modules.auth.application.tokens import ClientRegistry, TokenPolicy, TokenService
from app.modules.auth.domain.constants import PURPOSE_ACCESS
from app.modules.auth.infrastructure.admin_repositories import MembershipAdminRepository
from app.modules.auth.infrastructure.agent_repository import AgentAuthRepository
from app.modules.auth.infrastructure.google_oidc import GoogleOidcAdapter
from app.modules.auth.infrastructure.repositories import AuthRepository, ClientRow
from app.modules.auth.infrastructure.signup_repository import IdentityRepository, SignupRepository
from app.modules.auth.infrastructure.staff_snapshot_sql import SqlStaffSnapshotStore
from app.modules.billing.wiring import start_trial
from app.modules.branches.wiring import (
    ActivityType,
    SettlementCategory,
    ensure_default_branch,
    ensure_default_cash_register,
)
from app.modules.expenses.wiring import create_default_categories
from app.modules.integrations.otp.wiring import (
    FakeOutbox,
    FakeSender,
    build_eskiz_sender,
    build_telegram_sender,
)
from app.modules.notifications.wiring import telegram_links_revoker

__all__ = [
    "AuthModule",
    "PinVerifier",
    "StaffPinRow",
    "StaffPinSnapshot",
    "build_agent_grants",
    "build_auth_module",
    "build_auth_store",
    "build_cipher",
    "hash_password",
    "pin_verifier",
    "signing_key_ring",
    "staff_pin_snapshot",
]


def client_secret_aad(client_id: str) -> bytes:
    return f"oauth_clients:{client_id}".encode()


def build_cipher(settings: Settings) -> EnvelopeCipher:
    return EnvelopeCipher.from_settings(
        settings.kek.get_secret_value(),
        settings.kek_version,
        {v: k.get_secret_value() for v, k in settings.kek_previous.items()},
    )


@dataclass(frozen=True, slots=True)
class AuthModule:
    settings: Settings
    repo: AuthRepository
    cipher: EnvelopeCipher
    ring: SigningKeyRing
    codec: AccessTokenCodec
    clients: ClientRegistry
    revocation: RevocationCache
    subscriptions: SubscriptionStatusService
    login: LoginService
    tokens: TokenService
    server: ErpAuthorizationServer
    bff: BffService
    gateway: ErpAuthGateway
    admin_users: AdminUsersService
    cookies: SessionCookieSigner
    profiles: SessionProfileService
    otp: OtpService
    otp_dev_outbox: FakeOutbox | None  # only with ERP_OTP_DEV_FAKES (local dev)
    signup: SignupService
    credentials: CredentialService
    google: GoogleSignInService
    # --- B3 device-auth ---
    pin: PinService
    device_cookies: DeviceCookieSigner
    actors: ActorBindings
    # --- B5 agent-auth ---
    agent_grants: AgentGrantService


def build_auth_store(db: Database) -> AuthStore:
    """The auth SQL store for other callers (worker jobs, scripts) — 23 §1: never import infrastructure."""
    return AuthRepository(db.session_factory)


def outbound_http(settings: Settings) -> Callable[[], httpx.AsyncClient]:
    """Short-lived client per external call (Telegram, Eskiz, Google) — nothing to close at shutdown."""

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=settings.outbound_http_timeout_s, follow_redirects=False)

    return factory


def build_otp(
    settings: Settings, repo: AuthRepository, redis: Callable[[], Redis], audit: AuditLog
) -> tuple[OtpService, FakeOutbox | None]:
    """OTP channels (14 §4.2, qaror #34): Telegram bot → Eskiz SMS; recording fakes only in dev."""
    http = outbound_http(settings)
    outbox: FakeOutbox | None = None
    telegram: MessageSender | None = None
    sms: MessageSender
    if settings.otp_dev_fakes:
        outbox = FakeOutbox()
        telegram, sms = FakeSender("telegram", outbox), FakeSender("sms", outbox)
    else:
        if settings.telegram_bot_token is not None:
            telegram = build_telegram_sender(
                http,
                token=settings.telegram_bot_token.get_secret_value(),
                base_url=settings.telegram_api_base_url,
            )
        sms = build_eskiz_sender(
            http,
            base_url=settings.eskiz_base_url,
            email=settings.eskiz_email,
            password=settings.eskiz_password.get_secret_value() if settings.eskiz_password else None,
            sender=settings.eskiz_sender,
            test_mode=settings.eskiz_test_mode,
        )
    policy = OtpPolicy(
        ttl_s=settings.otp_ttl_s,
        verified_ttl_s=settings.otp_verified_ttl_s,
        telegram_per_phone_day=settings.otp_telegram_per_phone_day,
        telegram_per_ip_hour=settings.otp_telegram_per_ip_hour,
        sms_per_phone_day=settings.otp_sms_per_phone_day,
        sms_per_ip_hour=settings.otp_sms_per_ip_hour,
        sms_daily_budget=settings.otp_sms_daily_budget,
        verify_per_ip_hour=settings.otp_verify_per_ip_hour,
        verify_fail_per_phone_day=settings.otp_verify_fail_per_phone_day,
        recovery_min_response_s=settings.otp_recovery_min_response_ms / 1000,
        test_phones=frozenset(settings.otp_test_phones),
        test_code=settings.otp_test_code.get_secret_value() if settings.otp_test_code else None,
        brand=settings.sms_brand,
    )
    service = OtpService(
        repo,
        redis,
        audit,
        telegram=telegram,
        sms=sms,
        policy=policy,
        hash_key=settings.auth_secret.get_secret_value().encode(),
    )
    return service, outbox


async def _ensure_default_branch(
    session: AsyncSession, tenant_id: UUID, name: str, settlement: str, activity_type: str
) -> UUID:
    return await ensure_default_branch(
        session,
        tenant_id,
        name,
        cast(SettlementCategory, settlement),
        activity_type=cast(ActivityType, activity_type),
    )


async def _ensure_cash_register(session: AsyncSession, tenant_id: UUID, branch_id: UUID) -> UUID:
    return await ensure_default_cash_register(session, tenant_id, branch_id)


async def _provision_roles(session: AsyncSession, tenant_id: UUID) -> Mapping[str, UUID]:
    roles = await provision_system_roles(session, tenant_id)
    return {str(role): role_id for role, role_id in roles.items()}


TENANT_PROVISIONING = TenantProvisioning(
    provision_roles=_provision_roles,
    ensure_default_branch=_ensure_default_branch,
    ensure_default_cash_register=_ensure_cash_register,
    create_default_categories=create_default_categories,
    start_trial=start_trial,
)


def build_google_port(settings: Settings) -> GoogleOidcPort | None:
    if not settings.google_client_id:
        return None
    return GoogleOidcAdapter(
        outbound_http(settings),
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value()
        if settings.google_client_secret
        else None,
        audiences=settings.google_android_client_ids,
        issuers=settings.google_issuers,
        auth_url=settings.google_auth_url,
        token_url=settings.google_token_url,
        jwks_url=settings.google_jwks_url,
    )


def build_auth_module(settings: Settings, db: Database, redis: Callable[[], Redis]) -> AuthModule:
    repo = AuthRepository(db.session_factory)
    cipher = build_cipher(settings)
    audit = AuditLog(db.session_factory)

    def decrypt_secret(row: ClientRow) -> str | None:
        if not row.client_secret_encrypted:
            return None
        return cipher.decrypt(row.client_secret_encrypted, client_secret_aad(row.client_id)).decode()

    ring = SigningKeyRing(repo, cipher, purpose=PURPOSE_ACCESS, overlap_s=settings.signing_key_overlap_s)
    codec = AccessTokenCodec(ring, settings.issuer)
    clients = ClientRegistry(repo, decrypt_secret)
    revocation = RevocationCache(
        repo,
        redis,
        access_ttl_s=settings.access_token_ttl_s,
        session_check_cache_s=settings.session_check_cache_s,
    )
    subscriptions = SubscriptionStatusService(repo, redis)
    login = LoginService(
        repo,
        redis,
        subscriptions,
        audit,
        LoginPolicy(
            max_failures=settings.login_max_failures,
            failure_window_s=settings.login_failure_window_s,
            ip_failures_per_hour=settings.login_ip_failures_per_hour,
        ),
    )
    tokens = TokenService(
        repo,
        clients,
        codec,
        revocation,
        subscriptions,
        audit,
        redis,
        TokenPolicy(
            access_ttl_s=settings.access_token_ttl_s,
            drain_ttl_s=settings.sync_drain_token_ttl_s,
            code_ttl_s=settings.auth_code_ttl_s,
            session_idle_s=settings.session_idle_s,
            session_absolute_s=settings.session_absolute_s,
            device_idle_s=settings.device_session_idle_s,
            device_absolute_s=settings.device_session_absolute_s,
        ),
    )
    server = ErpAuthorizationServer(clients, tokens)
    bff = BffService(
        server=server,
        codec=codec,
        repo=repo,
        revocation=revocation,
        audit=audit,
        cipher=cipher,
        redis=redis,
        issuer=settings.issuer,
        client_secret=settings.web_bff_client_secret.get_secret_value(),
        session_absolute_s=settings.session_absolute_s,
        refresh_lock_ttl_s=settings.refresh_lock_ttl_s,
        device_absolute_s=settings.device_session_absolute_s,
    )
    cookies = SessionCookieSigner(settings.auth_secret.get_secret_value())
    # BO-11 / RS access guard: revoked device (16 §9) and claims stale (14 §5) — slice A2
    access_guard = AccessGuard(
        repo,
        redis,
        access_ttl_s=settings.access_token_ttl_s,
        device_check_cache_s=settings.session_check_cache_s,
    )
    actors = ActorBindings(redis, ttl_s=settings.actor_binding_ttl_s)
    gateway = ErpAuthGateway(
        codec=codec,
        revocation=revocation,
        subscriptions=subscriptions,
        repo=repo,
        bff=bff,
        cookies=cookies,
        csrf=CsrfTokens(settings.auth_secret.get_secret_value(), settings.session_absolute_s),
        guard=access_guard,
        actors=actors,
        api_prefix=settings.api_prefix,
    )
    profiles = SessionProfileService(repo, redis)
    otp, otp_outbox = build_otp(settings, repo, redis, audit)
    admin_users = AdminUsersService(
        db.session_factory,
        MembershipAdminRepository(),
        revocation,
        bff.drop,
        profiles.forget,
        access_guard,
        otp,
        on_blocked=telegram_links_revoker(),  # M18 QT-M18-05: a blocked user's Telegram link is revoked
    )
    signup = SignupService(
        db.session_factory,
        SignupRepository(),
        TENANT_PROVISIONING,
        otp,
        repo,
        redis,
        per_ip_hour=settings.signup_per_ip_hour,
    )
    credentials = CredentialService(repo, redis, revocation, audit, ttl_s=settings.credential_token_ttl_s)
    google = GoogleSignInService(
        build_google_port(settings),
        IdentityRepository(db.session_factory),
        repo,
        bff,
        tokens,
        audit,
        redis,
        issuer=settings.issuer,
    )
    pin = PinService(repo, redis, audit, pin_policy(settings))
    device_cookies = DeviceCookieSigner(settings.auth_secret.get_secret_value())
    return AuthModule(
        settings, repo, cipher, ring, codec, clients, revocation, subscriptions, login, tokens, server, bff,
        gateway, admin_users, cookies, profiles, otp, otp_outbox, signup, credentials, google, pin,
        device_cookies, actors, build_agent_grants(settings, db, codec, redis),
    )  # fmt: skip


# --- B3 device-auth ---
def pin_policy(settings: Settings) -> PinPolicy:
    return PinPolicy(
        max_failures=settings.pin_max_failures,
        failure_window_s=settings.pin_failure_window_s,
        user_failures_per_day=settings.pin_user_failures_per_day,
    )


class PinVerifier:
    """Server-side PIN check for other modules (approvals, 18 §9.4) — rules of ``POST /auth/pin/verify``.

    Runs in its own transactions: call it before your ``tenant_transaction``. ``True`` — the PIN
    matches an active member of the tenant; ``False`` — wrong PIN (counted and audited). Raises
    ``ACCOUNT_LOCKED`` (locked), ``PIN_INVALID`` ``reason=must_change_pin`` (PIN reset/not set) and
    ``RATE_LIMITED`` (Redis unavailable — fail-closed).
    """

    def __init__(self, service: PinService) -> None:
        self._service = service

    async def verify(
        self, *, tenant_id: UUID, user_id: UUID, pin: str, device_id: UUID | None, ip: str | None
    ) -> bool:
        return await self._service.check(
            tenant_id=tenant_id, user_id=user_id, pin=pin, device_id=device_id, ip=ip
        )


def pin_verifier(settings: Settings, db: Database, redis: Callable[[], Redis]) -> PinVerifier:
    repo = AuthRepository(db.session_factory)
    return PinVerifier(PinService(repo, redis, AuditLog(db.session_factory), pin_policy(settings)))


def staff_pin_snapshot() -> StaffPinSnapshot:
    """Staff + local PIN verifiers of a branch for the ``permissions`` pull scope (b3-sync, 16 §3.2)."""
    return StaffPinSnapshot(SqlStaffSnapshotStore())


# --- B5 agent-auth ---
def build_agent_grants(
    settings: Settings, db: Database, codec: AccessTokenCodec, redis: Callable[[], Redis]
) -> AgentGrantService:
    """Store-agent device grant + ``private_key_jwt`` (14 §2.3); also the reader of the signed artefacts."""
    policy = AgentGrantPolicy(
        access_ttl_s=settings.agent_access_token_ttl_s,
        device_auth_per_ip_hour=settings.agent_device_auth_per_ip_hour,
        verification_uri=settings.agent_verification_uri or f"{settings.issuer}/app/settings/onec/pair",
    )
    return AgentGrantService(
        AgentAuthRepository(db.session_factory), codec, redis, policy, issuer=settings.issuer
    )


def signing_key_ring(settings: Settings, db: Database, purpose: str) -> SigningKeyRing:
    """``platform.signing_keys`` ring of one purpose (``onec_task`` for the dispatcher, 33 §9.4)."""
    return SigningKeyRing(
        AuthRepository(db.session_factory), build_cipher(settings), purpose=purpose,
        overlap_s=settings.signing_key_overlap_s,
    )  # fmt: skip
