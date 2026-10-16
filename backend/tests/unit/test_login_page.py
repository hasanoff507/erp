"""AS login page (07 BO-01, 08): hashed inline style under CSP, uz/ru, language switch."""

from __future__ import annotations

import base64
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from app.modules.auth.api.login_page import STYLE, STYLE_HASH, pick_locale, render_login

PARAMS = {
    "response_type": "code",
    "client_id": "web-bff",
    "redirect_uri": "https://testserver/auth/callback",
    "state": "st-1",
    "code_challenge": "abc",
    "code_challenge_method": "S256",
    "tenant_id": "0190a0a0-0000-7000-8000-000000000001",
}


def _style_of(html: str) -> str:
    match = re.search(r"<style>(.*?)</style>", html, re.S)
    assert match is not None
    return match.group(1)


def test_csp_has_no_unsafe_inline_and_hash_matches_served_style() -> None:
    response = render_login(PARAMS)
    csp = response.headers["content-security-policy"]
    assert "unsafe-inline" not in csp
    served = _style_of(response.body.decode())
    expected = "sha256-" + base64.b64encode(hashlib.sha256(served.encode()).digest()).decode()
    assert served == STYLE and expected == STYLE_HASH
    assert f"style-src '{expected}'" in csp
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "<script" not in response.body.decode()


def test_brand_tokens_and_font() -> None:
    assert "#0E7C66" in STYLE and "#0A5E4D" in STYLE
    assert "font-family:Manrope,system-ui,sans-serif" in STYLE


def test_default_locale_is_uzbek() -> None:
    html = render_login(PARAMS).body.decode()
    assert 'lang="uz"' in html and "Parol" in html and ">Kirish</button>" in html


def test_ui_locales_ru_renders_russian() -> None:
    response = render_login({**PARAMS, "ui_locales": "ru"}, error_code="INVALID_CREDENTIALS")
    html = response.body.decode()
    assert '<html lang="ru">' in html
    assert "Телефон" in html and "Пароль" in html and ">Войти</button>" in html
    assert "Неверный номер телефона или пароль" in html
    assert '<input type="hidden" name="ui_locales" value="ru">' in html


def test_accept_language_fallback_and_precedence() -> None:
    assert pick_locale(None, "ru-RU,ru;q=0.9,en;q=0.8") == "ru"
    assert pick_locale(None, "en-US,uz;q=0.5,ru;q=0.9") == "ru"
    assert pick_locale(None, "en-US,en;q=0.9") == "uz"
    assert pick_locale("uz", "ru") == "uz"  # ui_locales wins
    assert pick_locale("en ru", None) == "ru"
    assert pick_locale(None, "ru;q=0") == "uz"
    html = render_login(PARAMS, accept_language="ru").body.decode()
    assert '<html lang="ru">' in html


def test_language_switch_preserves_oauth_params() -> None:
    html = render_login(PARAMS).body.decode()
    hrefs = re.findall(r'<a href="([^"]+)" hreflang="ru"', html)
    assert len(hrefs) == 1
    url = urlsplit(hrefs[0].replace("&amp;", "&"))
    assert url.path == "/oauth/authorize"
    query = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert query == {**PARAMS, "ui_locales": "ru"}


def test_values_are_escaped() -> None:
    html = render_login({**PARAMS, "state": '"><script>x</script>'}, phone='"><b>').body.decode()
    assert "<script>x" not in html and "<b>" not in html
