"""Composition of the auth module (23 §1 ``wiring.py``)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.audit import AuditLog
from app.core.auth.tokens import CsrfTokens, SessionCookieSigner
from app.core.config import Settings
from app.core.db.session import Database
from app.core.secrets import EnvelopeCipher
from app.modules.auth.application.admin_users import AdminUsersService
from app.modules.auth.application.bff import BffService
from app.modules.auth.application.gateway import ErpAuthGateway
from app.modules.auth.application.keys import AccessTokenCodec, SigningKeyRing
from app.modules.auth.application.login import LoginPolicy, LoginService
from app.modules.auth.application.oauth_server import ErpAuthorizationServer
from app.modules.auth.application.revocation import RevocationCache
from app.modules.auth.application.session_profile import SessionProfileService
from app.modules.auth.application.subscription import SubscriptionStatusService
from app.modules.auth.application.tokens import ClientRegistry, TokenPolicy, TokenService
from app.modules.auth.domain.constants import PURPOSE_ACCESS
from app.modules.auth.infrastructure.repositories import AuthRepository, ClientRow


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
    )
    cookies = SessionCookieSigner(settings.auth_secret.get_secret_value())
    gateway = ErpAuthGateway(
        codec=codec,
        revocation=revocation,
        subscriptions=subscriptions,
        repo=repo,
        bff=bff,
        cookies=cookies,
        csrf=CsrfTokens(settings.auth_secret.get_secret_value(), settings.session_absolute_s),
    )
    profiles = SessionProfileService(repo, redis)
    admin_users = AdminUsersService(db.session_factory, revocation, bff.drop, profiles.forget)
    return AuthModule(
        settings, repo, cipher, ring, codec, clients, revocation, subscriptions, login, tokens, server, bff,
        gateway, admin_users, cookies, profiles,
    )  # fmt: skip
