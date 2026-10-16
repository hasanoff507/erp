"""Settings guard, log redaction, spec drift and liveness."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import _INSECURE_KEK, Settings
from app.core.logging import REDACTED, redact_pii
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[2]
SPEC = BACKEND.parent / "spec" / "kod-uchun"


def test_prod_guard_rejects_insecure_settings() -> None:
    with pytest.raises(ValidationError, match="auth"):
        Settings(environment="prod", ai_mode="api", _env_file=None)
    with pytest.raises(ValidationError, match="AI"):
        Settings(environment="prod", ai_mode="cli", auth_secret=SecretStr("s" * 40), _env_file=None)
    ok = Settings(
        environment="prod",
        ai_mode="api",
        auth_secret=SecretStr("s" * 40),
        kek=SecretStr("b3RoZXIta2VrLW9mLWV4YWN0bHktMzItYnl0ZXMhISE="),
        web_bff_client_secret=SecretStr("w" * 40),
        public_base_url="https://app.example.uz",
        _env_file=None,
    )
    assert ok.environment == "prod"


_HARDENED = {
    "ai_mode": "api",
    "auth_secret": SecretStr("s" * 40),
    "kek": SecretStr("b3RoZXIta2VrLW9mLWV4YWN0bHktMzItYnl0ZXMhISE="),
    "web_bff_client_secret": SecretStr("w" * 40),
    "public_base_url": "https://app.example.uz",
}


@pytest.mark.parametrize("environment", ["staging", "prod"])
def test_staging_is_guarded_like_prod(environment: str) -> None:
    assert Settings(environment=environment, **_HARDENED, _env_file=None).environment == environment
    with pytest.raises(ValidationError, match="auth"):
        Settings(environment=environment, ai_mode="api", _env_file=None)
    with pytest.raises(ValidationError, match="KEK"):
        Settings(environment=environment, **{**_HARDENED, "kek": SecretStr(_INSECURE_KEK)}, _env_file=None)
    with pytest.raises(ValidationError, match="32"):
        Settings(environment=environment, **{**_HARDENED, "auth_secret": SecretStr("s" * 31)}, _env_file=None)
    with pytest.raises(ValidationError, match="db_echo"):
        Settings(environment=environment, **_HARDENED, db_echo=True, _env_file=None)
    with pytest.raises(ValidationError, match="https"):
        Settings(environment=environment, **{**_HARDENED, "public_base_url": "http://x.uz"}, _env_file=None)


@pytest.mark.parametrize("environment", ["local", "test"])
def test_dev_environments_keep_insecure_defaults(environment: str) -> None:
    s = Settings(environment=environment, db_echo=True, _env_file=None)
    assert s.auth_secret.get_secret_value() == "insecure-dev-secret-change-me"


@pytest.mark.parametrize("environment", ["local", "test", "staging", "prod"])
def test_wildcard_cors_origin_is_rejected_everywhere(environment: str) -> None:
    with pytest.raises(ValidationError, match="cors_origins"):
        Settings(
            environment=environment,
            **_HARDENED,
            cors_origins=["https://app.example.uz", "*"],
            _env_file=None,
        )


def test_settings_load_from_env_example_with_empty_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("ERP_"):
            monkeypatch.delenv(name)
    s = Settings(_env_file=BACKEND / ".env.example")
    assert s == Settings(_env_file=None)
    assert s.environment == "local"


def test_log_redaction() -> None:
    event = redact_pii(
        None,
        "info",
        {
            "event": "login +998 90 123 45 67 card 8600123456789012",
            "phone": "+998901234567",
            "password": "x",
            "user": {"stir": "301234567", "card_mask": "8600****9012"},
            "tenant_id": "t",
            "amount": "120000.00",
        },
    )
    assert "123 45 67" not in event["event"] and "8600123456789012" not in event["event"]
    assert event["phone"] == event["password"] == REDACTED
    assert event["user"]["stir"] == REDACTED
    assert event["user"]["card_mask"] == "8600****9012"
    assert event["tenant_id"] == "t" and event["amount"] == "120000.00"


@pytest.mark.parametrize("script", ["gen_error_codes.py", "gen_migration_sql.py"])
def test_generated_code_matches_spec(script: str) -> None:
    if not SPEC.exists():
        pytest.skip("spec/ not available")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(BACKEND / "scripts" / script), "--check"],
        capture_output=True,
        text=True,
        cwd=BACKEND,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_health_liveness_without_dependencies() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        for path in ("/health", "/health/live"):
            r = client.get(path)
            assert r.status_code == 200
            assert r.json() == {"status": "ok", "checks": {}}
            assert r.headers["x-request-id"]


def test_env_example_lists_every_setting() -> None:
    example = BACKEND / ".env.example"
    names = {line.split("=", 1)[0].strip() for line in example.read_text().splitlines() if "=" in line}
    expected = {f"ERP_{name.upper()}" for name in Settings.model_fields}
    assert expected <= names, expected - names
    values = [line.split("=", 1)[1] for line in example.read_text().splitlines() if line.startswith("ERP_")]
    assert all(v == "" for v in values)  # qaror #57: names only, no values
