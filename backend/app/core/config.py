"""Application settings (23 §7.3): pydantic-settings, ``ERP_`` prefix, staging/prod guard."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT = "insecure-dev-secret-change-me"
# fixed 32-byte dev KEK (urlsafe base64) — local/test only, rejected in prod
_INSECURE_KEK = "ZGV2LW9ubHkta2VrLWRvLW5vdC11c2UtaW4tcHJvZCE="
_INSECURE_BFF_SECRET = "insecure-dev-web-bff-client-secret-change-me"  # noqa: S105

Environment = Literal["local", "test", "staging", "prod"]
AiMode = Literal["fake", "cli", "api"]
# environments that face real users/data: the production guard applies to all of them
_HARDENED_ENVIRONMENTS: frozenset[str] = frozenset({"staging", "prod"})
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ERP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # .env.example ships names with empty values (qaror #57): an empty ERP_X= means "use default"
        env_ignore_empty=True,
    )

    environment: Environment = "local"
    app_name: str = "erp-backend"
    api_prefix: str = "/api/v1"

    # erp_app — RLS-bound runtime role (12 §0); never a superuser
    database_url: SecretStr = SecretStr("postgresql+asyncpg://erp_app:erp_app_dev@localhost:5432/erp")
    # erp_migrator — owns all objects, used only by Alembic
    migrator_database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://erp_migrator:erp_migrator_dev@localhost:5432/erp"
    )
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_echo: bool = False

    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    queue_name: str = "default"
    worker_concurrency: int = Field(default=10, ge=1)

    auth_enabled: bool = True
    # itsdangerous key for the __Host-sid cookie and the CSRF synchronizer token (15 §1.3)
    auth_secret: SecretStr = SecretStr(_INSECURE_DEFAULT)

    # --- OAuth 2.0 AS/RS (14) -------------------------------------------------------------------
    # issuer (`iss`, RFC 8414) and the origin the first-party login form must be posted from
    public_base_url: str = "https://localhost:8000"
    # KEK of the envelope scheme (15 §4.2, qaror #65): urlsafe-base64 of 32 bytes; previous
    # versions stay readable during a KEK rotation
    kek: SecretStr = SecretStr(_INSECURE_KEK)
    kek_version: int = Field(default=1, ge=1)
    kek_previous: dict[int, SecretStr] = Field(default_factory=dict)
    # web-bff client secret; the in-process BFF authenticates to /oauth/token with it (14 §2.1)
    web_bff_client_secret: SecretStr = SecretStr(_INSECURE_BFF_SECRET)
    access_token_ttl_s: int = Field(default=900, ge=60)  # qaror #44
    sync_drain_token_ttl_s: int = Field(default=300, ge=60)  # 14 §16.4
    auth_code_ttl_s: int = Field(default=60, ge=10, le=600)  # 14 §3
    # refresh/session lifetimes without a device (14 §7): sliding idle 12 h, absolute 7 days
    session_idle_s: int = Field(default=12 * 3600, ge=300)
    session_absolute_s: int = Field(default=7 * 86400, ge=3600)
    # retired signing keys stay in the JWKS this long (14 §6: access max + skew ≈ 30 min)
    signing_key_overlap_s: int = Field(default=1800, ge=0)
    # sid revoke cache (14 §5: 30–60 s), BFF single-flight refresh lock (14 §7: 5 s)
    session_check_cache_s: int = Field(default=30, ge=1, le=60)
    refresh_lock_ttl_s: int = Field(default=5, ge=1)
    # brute force (14 §12, qaror #54)
    login_max_failures: int = Field(default=5, ge=1)
    login_failure_window_s: int = Field(default=900, ge=60)
    login_ip_failures_per_hour: int = Field(default=20, ge=1)
    token_requests_per_minute: int = Field(default=30, ge=1)
    # auth.login_attempts retention (14 §19, qaror #54); purge job — 23 §4
    login_attempts_retention_days: int = Field(default=90, ge=1)

    # 22 §1.1 / qaror #16
    ai_mode: AiMode = "fake"
    # qaror #61: optional EU route for PII-bearing prompts/images (bedrock_eu)
    ai_pii_route: Literal["anthropic", "bedrock_eu"] = "anthropic"

    # 21 §1 — MVP: fake
    fiscal_provider: Literal["fake", "partner_cloud", "multikassa_local", "fiscaldrive_local"] = "fake"
    # qaror #55 — used when the CBU rate cannot be fetched
    fx_usd_uzs_fallback: Decimal | None = None

    idempotency_lock_ttl_s: int = Field(default=60, ge=1)
    idempotency_retention_days: int = Field(default=30, ge=1)

    log_level: str = "INFO"
    log_json: bool = True
    cors_origins: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_production_security(self) -> Self:
        # main.py always sets allow_credentials=True: a wildcard origin is never acceptable
        if "*" in self.cors_origins:
            raise ValueError("cors_origins'da '*' ruxsat etilmaydi (credentials bilan CORS)")
        if self.environment not in _HARDENED_ENVIRONMENTS:
            return self
        env = self.environment
        secret = self.auth_secret.get_secret_value()
        if not self.auth_enabled or secret == _INSECURE_DEFAULT:
            raise ValueError(f"{env}'da auth yoqilgan va maxfiy kalit o'zgartirilgan bo'lishi shart")
        if len(secret) < _MIN_SECRET_LENGTH:
            raise ValueError(f"{env}'da auth_secret kamida {_MIN_SECRET_LENGTH} belgi bo'lishi shart")
        if self.db_echo:
            raise ValueError(f"{env}'da db_echo o'chirilgan bo'lishi shart (SQL parametrlari logga chiqadi)")
        if self.ai_mode == "cli":
            raise ValueError(f"{env}'da AI rejimi 'api' bo'lishi shart (22-ai-qatlami.md §1, qaror #16)")
        if self.kek.get_secret_value() == _INSECURE_KEK:
            raise ValueError(f"{env}'da KEK (ERP_KEK) o'rnatilgan bo'lishi shart (15 §4.2, qaror #65)")
        if self.web_bff_client_secret.get_secret_value() == _INSECURE_BFF_SECRET:
            raise ValueError(f"{env}'da ERP_WEB_BFF_CLIENT_SECRET o'zgartirilgan bo'lishi shart (14 §15)")
        if not self.public_base_url.startswith("https://"):
            raise ValueError(
                f"{env}'da public_base_url https bo'lishi shart (__Host- cookie, RFC 8414 issuer)"
            )
        return self

    @property
    def issuer(self) -> str:
        return self.public_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
