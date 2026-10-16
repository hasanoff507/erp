"""Slice A1 unit checks: phone rule, PIN hashing, BO-01 login-page entry points."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.modules.auth.api.login_page import render_login
from app.modules.auth.application.otp import mask_phone, require_phone
from app.modules.auth.application.passwords import hash_pin

WEB = {
    "response_type": "code", "client_id": "web-bff", "redirect_uri": "https://t/auth/callback", "state": "s",
    "code_challenge": "c" * 43, "code_challenge_method": "S256",
}  # fmt: skip


def test_only_plus_998_numbers() -> None:
    assert require_phone("+998 90 123-45-67") == "+998901234567"
    for bad in ("+79161234567", "998901234567", "+99890123456", ""):
        with pytest.raises(AppError) as exc:
            require_phone(bad)
        assert exc.value.code == "VALIDATION_ERROR"
    assert mask_phone("+998901234567") == "+99890*****67"


def test_pin_is_4_to_6_digits_and_argon2id() -> None:
    assert hash_pin("1234").startswith("$argon2id$")
    for bad in ("123", "1234567", "12a4"):
        with pytest.raises(ValueError, match="pin"):
            hash_pin(bad)


def test_login_page_has_google_and_code_entry_points_uz_ru() -> None:
    uz = render_login(WEB).body.decode()
    assert 'href="/auth/google/start"' in uz and "Google bilan kirish" in uz
    assert 'href="/recover"' in uz and "Parolni unutdim?" in uz
    assert 'href="/invite"' in uz and "Taklif kodi bor" in uz
    ru = render_login({**WEB, "ui_locales": "ru"}).body.decode()
    assert "Войти через Google" in ru and "Забыли пароль?" in ru and "Есть код приглашения" in ru
    with_tenant = render_login({**WEB, "tenant_id": "0190a1b2-0000-7000-8000-000000000001"}).body.decode()
    assert "/auth/google/start?tenant_id=0190a1b2-0000-7000-8000-000000000001" in with_tenant
    android = render_login({**WEB, "client_id": "android-pos"}).body.decode()
    assert "/auth/google/start" not in android and 'href="/recover"' in android
