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

    # --- Bosqich 1 settings: auth/signup slice (OTP, Telegram, Eskiz, Google) ---
    # OTP (14 §4.2, §12; qaror #34, #54): TTL 5 min; per-channel send limits
    otp_ttl_s: int = Field(default=300, ge=60, le=900)
    otp_telegram_per_phone_day: int = Field(default=10, ge=1)
    otp_telegram_per_ip_hour: int = Field(default=20, ge=1)
    otp_sms_per_phone_day: int = Field(default=5, ge=1)
    otp_sms_per_ip_hour: int = Field(default=20, ge=1)
    otp_sms_daily_budget: int = Field(default=2000, ge=1)  # global SMS/day (toll-fraud guard, alert)
    otp_verified_ttl_s: int = Field(default=900, ge=60)  # verified signup/export ticket lifetime
    otp_recovery_min_response_ms: int = Field(default=1500, ge=0, le=5000)  # timing oracle guard (14 §12)
    otp_verify_per_ip_hour: int = Field(default=60, ge=1)  # /auth/otp/verify attempts per IP (14 §12)
    otp_verify_fail_per_phone_day: int = Field(default=10, ge=1)  # wrong codes / phone / day, all challenges
    # dev/test only (qaror #34) — both refused in staging/prod by the validator below
    otp_dev_fakes: bool = False  # ERP_OTP_DEV_FAKES: recording Telegram/SMS fakes instead of real senders
    otp_test_phones: list[str] = Field(default_factory=list)  # ERP_OTP_TEST_PHONES: test-number path
    otp_test_code: SecretStr | None = None  # ERP_OTP_TEST_CODE: fixed 6-digit code of the test numbers
    # credential-set session after an invite/reset/recovery code (14 §4.2, §18.2)
    credential_token_ttl_s: int = Field(default=600, ge=60, le=3600)
    signup_per_ip_hour: int = Field(default=10, ge=1)
    # Telegram Bot API (21 §11, §11.1)
    telegram_bot_token: SecretStr | None = None
    telegram_api_base_url: str = "https://api.telegram.org"
    # Eskiz SMS — fallback channel only (21 §10, 26 #45); test mode sends only the allowed test text
    eskiz_test_mode: bool = True  # ERP_ESKIZ_TEST_MODE
    eskiz_base_url: str = "https://notify.eskiz.uz"
    eskiz_email: str | None = None
    eskiz_password: SecretStr | None = None
    eskiz_sender: str = "4546"
    sms_brand: str = "ERP"
    outbound_http_timeout_s: float = Field(default=10.0, gt=0, le=60)
    # Google OIDC (14 §2.2, 21 §9.3)
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_android_client_ids: list[str] = Field(default_factory=list)  # extra `aud` of native ID tokens
    google_auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"  # noqa: S105 — URL, not a secret
    google_jwks_url: str = "https://www.googleapis.com/oauth2/v3/certs"
    google_issuers: list[str] = Field(
        default_factory=lambda: ["https://accounts.google.com", "accounts.google.com"]
    )

    @model_validator(mode="after")
    def _guard_otp_dev_paths(self) -> Self:
        """qaror #34: fakes and the test-number path never run where real users are (staging/prod)."""
        if self.otp_test_phones:
            code = self.otp_test_code.get_secret_value() if self.otp_test_code else ""
            if not (len(code) == 6 and code.isdigit()):
                raise ValueError("ERP_OTP_TEST_PHONES uchun ERP_OTP_TEST_CODE (6 raqam) shart")
        if self.environment in _HARDENED_ENVIRONMENTS and (self.otp_dev_fakes or self.otp_test_phones):
            raise ValueError(
                f"{self.environment}'da ERP_OTP_DEV_FAKES va ERP_OTP_TEST_PHONES ruxsat etilmaydi (qaror #34)"
            )
        return self

    # --- Bosqich 1 settings: access/branches/tenant-settings slice ---
    # --- Bosqich 1 settings: catalog/pricing/import slice ---
    # MXIK classifier (21 §7): tasnif.soliq.uz; "fake" only for local/test (qaror #34)
    mxik_provider: Literal["tasnif", "fake"] = "tasnif"
    mxik_base_url: str = "https://tasnif.soliq.uz/api/cls-api"
    mxik_timeout_s: float = Field(default=5.0, gt=0)
    # 21 §7 retry: base=5s, cap=30s, max_attempts=3, then the last known cache entry
    mxik_retry_base_s: float = Field(default=5.0, ge=0)
    mxik_retry_cap_s: float = Field(default=30.0, ge=0)
    mxik_max_attempts: int = Field(default=3, ge=1)
    mxik_cache_fresh_s: int = Field(default=86_400, ge=0)
    mxik_cache_ttl_s: int = Field(default=30 * 86_400, ge=60)
    # import-jobs (17 §12, 19 §6; qaror #54 defaults): ≤ 10 MB, ≤ 20 000 rows
    import_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    import_max_rows: int = Field(default=20_000, ge=1)
    # uploaded files (attachments.s3_key) until the S3 StoragePort lands (23 §7 "Fayl ombori")
    file_storage_dir: str = "./var/files"

    # --- Bosqich 2 settings: purchasing/debts slice ---
    # e-invoice operator (21 §2, EInvoicePort): "fake" — local/test/staging only (27 Bosqich 2), refused in
    # prod; "faktura_uz" — real adapter in Bosqich 5 (until then it answers EINVOICE_PROVIDER_UNAVAILABLE)
    einvoice_provider: Literal["fake", "faktura_uz"] = "faktura_uz"

    @model_validator(mode="after")
    def _guard_einvoice_fake(self) -> Self:
        """27 Bosqich 2: the fake operator registers e-TTN instantly — never where documents are real."""
        if self.environment == "prod" and self.einvoice_provider == "fake":
            raise ValueError("prod'da ERP_EINVOICE_PROVIDER=fake ruxsat etilmaydi (27 Bosqich 2)")
        return self

    log_level: str = "INFO"
    log_json: bool = True
    cors_origins: list[str] = Field(default_factory=list)

    # --- Bosqich 3 settings: device-auth slice ---
    device_session_idle_s: int = Field(default=14 * 86400, ge=3600)  # 14 §7 sliding (26 #73)
    device_session_absolute_s: int = Field(default=180 * 86400, ge=86400)  # 14 §7 absolute
    device_cookie_max_age_s: int = Field(default=400 * 86400, ge=86400)  # __Host-erp_device (14 §7.2)
    pin_max_failures: int = Field(default=5, ge=1)  # per (tenant, user, device) — qaror #54, 14 §12
    pin_failure_window_s: int = Field(default=900, ge=60)
    pin_user_failures_per_day: int = Field(default=20, ge=5)  # per (tenant, user) across devices
    pin_revoke_lookback_days: int = Field(default=30, ge=1)  # 16 §9 PIN_REVOKE_LOOKBACK_DAYS
    actor_binding_ttl_s: int = Field(default=12 * 3600, ge=300)  # PIN actor on device sessions (14 §4.3)
    # --- Bosqich 3 settings: sales/fiscal slice ---
    # ERP_FISCAL_PROVIDER (21 §1) is declared above; "fake" — the FM emulator, refused in prod by
    # integrations.fiscal.wiring.fiscal_port (the app does not start with it in prod)
    # --- Bosqich 3 settings: cash slice ---
    approval_ttl_minutes: int = Field(default=15, ge=1, le=1440)  # approval_requests.expires_at (18 §9.1)
    # --- Bosqich 3 settings: card slice ---
    # ERP_CARD_FAKE_TERMINALS: card_terminals.adapter='fake' (FakeCardTerminalAdapter) may be registered —
    # dev/test/staging only (21 §9.4, qaror #34); refused in prod
    card_fake_terminals: bool = False

    @model_validator(mode="after")
    def _guard_card_fake(self) -> Self:
        if self.environment == "prod" and self.card_fake_terminals:
            raise ValueError("prod'da ERP_CARD_FAKE_TERMINALS ruxsat etilmaydi (21 §9.4, qaror #71)")
        return self

    # --- Bosqich 3 settings: sync slice ---
    # 16 §3.1/§8, qaror #54 defaults: batch ≤ 100, 5 req/s per device, 4 concurrent pushes per tenant
    sync_push_max_events: int = Field(default=100, ge=1, le=1000)
    sync_push_rate_per_s: int = Field(default=5, ge=1)
    sync_push_tenant_concurrency: int = Field(default=4, ge=1)
    sync_push_lock_ttl_s: int = Field(default=120, ge=5)  # single flight per device (crash safety net)
    sync_clock_skew_warn_s: int = Field(default=300, ge=0)  # CLOCK_SKEW_WARN_S
    sync_offline_clamp_window_s: int = Field(default=7 * 86400, ge=3600)  # OFFLINE_CLAMP_WINDOW
    sync_pull_page_size: int = Field(default=500, ge=1)
    sync_pull_max_page_size: int = Field(default=1000, ge=1)
    # pull waits this long for a row's transaction to settle (late commits never skip a cursor position)
    sync_pull_settle_s: float = Field(default=2.0, ge=0, le=60)
    # --- Bosqich 3 settings: print slice ---
    # --- telemetry (23 §8, 25 §5; app/core/telemetry.py) — all off by default ---
    metrics_enabled: bool = False  # GET /metrics + HTTP metrics middleware
    # Prometheus scrape bearer token; mandatory in staging/prod when metrics are on
    metrics_token: SecretStr | None = None
    # SAQ worker/scheduler /metrics listener (None = off); same bearer token
    worker_metrics_port: int | None = Field(default=None, ge=1, le=65535)
    worker_metrics_host: str = "0.0.0.0"  # noqa: S104 — container-internal listener
    # OpenTelemetry traces → OTLP/HTTP → self-hosted Grafana Tempo (26 #53)
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    sentry_dsn: SecretStr | None = None

    @model_validator(mode="after")
    def _guard_metrics_token(self) -> Self:
        """/metrics never open to the network where real data lives (staging/prod)."""
        exposed = self.metrics_enabled or self.worker_metrics_port is not None
        if exposed and self.environment in _HARDENED_ENVIRONMENTS:
            token = self.metrics_token.get_secret_value() if self.metrics_token else ""
            if len(token) < _MIN_SECRET_LENGTH:
                raise ValueError(
                    f"{self.environment}'da /metrics uchun ERP_METRICS_TOKEN "
                    f"(kamida {_MIN_SECRET_LENGTH} belgi) shart (23 §8)"
                )
        return self

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
