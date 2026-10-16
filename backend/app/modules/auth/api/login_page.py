"""First-party AS login page (14 §2.1; 07 BO-01; 08 tokens). Server-rendered, uz/ru.

No scripts, no external assets; strict CSP (the one inline ``<style>`` is
allowed by its SHA-256 hash, never ``'unsafe-inline'``), no framing, no
referrer (the URL carries ``state``/``code_challenge``).
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping, Sequence
from html import escape
from typing import Final, Literal
from urllib.parse import urlencode

from starlette.responses import HTMLResponse

from app.modules.auth.application.login import TenantChoice

OAUTH_PARAMS: Final = (
    "response_type", "client_id", "redirect_uri", "scope", "state", "code_challenge", "code_challenge_method",
)  # fmt: skip
UI_LOCALES_PARAM: Final = "ui_locales"  # OpenID Connect Core §3.1.2.1

Locale = Literal["uz", "ru"]
DEFAULT_LOCALE: Final[Locale] = "uz"

# 08-dizayn-tizimi.md §2: background #F4F6F8, card #FFFFFF, ink #0F1B2D, ink-2 #3D4A5C,
# muted #6B7686, input #DCE1E7, primary #0E7C66, primary-strong #0A5E4D, primary-soft #E3F2EE,
# destructive-strong #A82B22, destructive-soft #FBEAE8, destructive-border #F3CFCB
STYLE: Final = (
    "body{font-family:Manrope,system-ui,sans-serif;background:#F4F6F8;color:#0F1B2D;margin:0;display:flex;"
    "min-height:100vh;align-items:center;justify-content:center}"
    "main{width:min(380px,calc(100vw - 32px))}"
    "form{background:#FFFFFF;padding:32px;border:1px solid #E7EAEE;border-radius:16px;"
    "box-shadow:0 8px 24px rgba(15,27,45,.06)}"
    ".brand{font-size:24px;font-weight:800;color:#0E7C66;text-align:center;margin:0 0 4px}"
    "h1{font-size:18px;font-weight:700;margin:0 0 20px;text-align:center}"
    ".lang{display:flex;justify-content:center;gap:6px;margin:0 0 16px;font-size:13px}"
    ".lang a,.lang span{padding:4px 10px;border-radius:999px;text-decoration:none;color:#3D4A5C}"
    ".lang span{background:#E3F2EE;color:#0A5E4D;font-weight:700}"
    ".lang a:hover{background:#F4F6F8}"
    "label{display:block;font-size:14px;color:#3D4A5C;margin:12px 0 4px}"
    "input,select{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #DCE1E7;"
    "border-radius:10px;font:inherit;font-size:16px;color:#0F1B2D;background:#FFFFFF}"
    "input:focus,select:focus{outline:2px solid #0E7C66;outline-offset:1px;border-color:#0E7C66}"
    "button{margin-top:20px;width:100%;min-height:44px;padding:12px;border:0;border-radius:10px;"
    "background:#0E7C66;color:#FFFFFF;font:inherit;font-size:16px;font-weight:700;cursor:pointer}"
    "button:hover,button:active{background:#0A5E4D}"
    "button:focus-visible{outline:2px solid #0E7C66;outline-offset:2px}"
    ".err{background:#FBEAE8;color:#A82B22;border:1px solid #F3CFCB;padding:10px 12px;border-radius:10px;"
    "font-size:14px;margin:0 0 8px}"
)
STYLE_HASH: Final = "sha256-" + base64.b64encode(hashlib.sha256(STYLE.encode()).digest()).decode()

SECURITY_HEADERS: Final = {
    "Content-Security-Policy": (
        f"default-src 'none'; style-src '{STYLE_HASH}'; form-action 'self'; frame-ancestors 'none'; "
        "base-uri 'none'"
    ),
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Vary": "Accept-Language",
}

MESSAGES: Final[dict[Locale, dict[str, str]]] = {
    "uz": {
        "INVALID_CREDENTIALS": "Telefon raqami yoki parol noto'g'ri",
        "ACCOUNT_LOCKED": "Hisob vaqtincha bloklangan, keyinroq urinib ko'ring",
        "RATE_LIMITED": "Juda ko'p urinish, biroz kutib qayta urinib ko'ring",
        "SUBSCRIPTION_RESTRICTED": "Obuna muddati tugagan, to'lov qiling",
        "PERMISSION_DENIED": "Bu do'konga kirish huquqingiz yo'q",
        "VALIDATION_ERROR": "Do'konni tanlang va parolni qayta kiriting",
    },
    "ru": {
        "INVALID_CREDENTIALS": "Неверный номер телефона или пароль",
        "ACCOUNT_LOCKED": "Учётная запись временно заблокирована, попробуйте позже",
        "RATE_LIMITED": "Слишком много попыток, подождите и попробуйте снова",
        "SUBSCRIPTION_RESTRICTED": "Срок подписки истёк, оплатите подписку",
        "PERMISSION_DENIED": "У вас нет доступа к этому магазину",
        "VALIDATION_ERROR": "Выберите магазин и введите пароль ещё раз",
    },
}

LABELS: Final[dict[Locale, dict[str, str]]] = {
    "uz": {
        "title": "Kirish",
        "heading": "Tizimga kirish",
        "phone": "Telefon",
        "password": "Parol",
        "tenant": "Do'kon",
        "submit": "Kirish",
        "lang": "Til",
    },
    "ru": {
        "title": "Вход",
        "heading": "Вход в систему",
        "phone": "Телефон",
        "password": "Пароль",
        "tenant": "Магазин",
        "submit": "Войти",
        "lang": "Язык",
    },
}


def _match(tag: str) -> Locale | None:
    primary = tag.strip().split("-")[0].split("_")[0].lower()
    if primary == "uz":
        return "uz"
    if primary == "ru":
        return "ru"
    return None


def pick_locale(ui_locales: str | None, accept_language: str | None) -> Locale:
    """``ui_locales`` (space-separated, in preference order) wins; then Accept-Language by q; else uz."""
    for tag in (ui_locales or "").split():
        found = _match(tag)
        if found is not None:
            return found
    weighted: list[tuple[float, int, str]] = []
    for index, part in enumerate((accept_language or "").split(",")):
        tag, _, params = part.partition(";")
        q = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        if q > 0:
            weighted.append((-q, index, tag))
    for _, _, tag in sorted(weighted):
        found = _match(tag)
        if found is not None:
            return found
    return DEFAULT_LOCALE


def _switch(params: Mapping[str, str], current: Locale, label: str) -> str:
    """«UZ · RU» links back to ``GET /oauth/authorize`` with the same OAuth request."""
    keep = {k: params[k] for k in (*OAUTH_PARAMS, "tenant_id") if params.get(k)}
    items: list[str] = []
    for locale in ("uz", "ru"):
        text = locale.upper()
        if locale == current:
            items.append(f'<span aria-current="true">{text}</span>')
        else:
            href = "/oauth/authorize?" + urlencode({**keep, UI_LOCALES_PARAM: locale})
            items.append(f'<a href="{escape(href)}" hreflang="{locale}" lang="{locale}">{text}</a>')
    return f'<nav class="lang" aria-label="{escape(label)}">' + "".join(items) + "</nav>"


def render_login(
    params: Mapping[str, str],
    *,
    error_code: str | None = None,
    tenants: Sequence[TenantChoice] = (),
    phone: str = "",
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
    accept_language: str | None = None,
) -> HTMLResponse:
    locale = pick_locale(params.get(UI_LOCALES_PARAM), accept_language)
    labels = LABELS[locale]
    hidden = "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(params[k])}">'
        for k in OAUTH_PARAMS
        if k in params
    )
    hidden += f'<input type="hidden" name="{UI_LOCALES_PARAM}" value="{locale}">'
    tenant_field = ""
    if tenants:
        options = "".join(
            f'<option value="{escape(str(t.tenant_id))}">{escape(t.tenant_name)}</option>' for t in tenants
        )
        label = f'<label for="tenant_id">{escape(labels["tenant"])}</label>'
        tenant_field = f'{label}<select id="tenant_id" name="tenant_id">{options}</select>'
    elif params.get("tenant_id"):
        tenant_field = f'<input type="hidden" name="tenant_id" value="{escape(params["tenant_id"])}">'
    error = (
        f'<p class="err" role="alert">{escape(MESSAGES[locale].get(error_code, error_code))}</p>'
        if error_code
        else ""
    )
    switch = _switch(params, locale, labels["lang"])
    body = (
        f'<!doctype html><html lang="{locale}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(labels['title'])}</title>"
        f"<style>{STYLE}</style></head><body><main>"
        '<form method="post" action="/oauth/authorize" autocomplete="on">'
        f'<p class="brand">ERP</p><h1>{escape(labels["heading"])}</h1>{switch}'
        f"{error}{hidden}"
        f'<label for="phone">{escape(labels["phone"])}</label>'
        f'<input id="phone" name="phone" type="tel" inputmode="tel" autocomplete="username" required '
        f'placeholder="+998901234567" value="{escape(phone)}">'
        f'<label for="password">{escape(labels["password"])}</label>'
        '<input id="password" name="password" type="password" autocomplete="current-password" required '
        'minlength="8" maxlength="128">'
        f"{tenant_field}"
        f'<button type="submit">{escape(labels["submit"])}</button></form></main></body></html>'
    )
    return HTMLResponse(body, status_code=status_code, headers={**SECURITY_HEADERS, **(headers or {})})
