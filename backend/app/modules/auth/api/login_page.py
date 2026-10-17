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
    "device_id",
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
    "main{width:min(420px,calc(100vw - 32px));padding:24px 0}"
    "form{background:#FFFFFF;padding:32px;border:1px solid #E7EAEE;border-radius:16px;"
    "box-shadow:0 8px 24px rgba(15,27,45,.06)}"
    ".top{display:flex;align-items:center;gap:10px;margin:0 0 24px}"
    ".mark{width:38px;height:38px;flex-shrink:0;border-radius:11px;background:#0E7C66;color:#FFFFFF;"
    "display:flex;align-items:center;justify-content:center;font-weight:800}"
    ".brand{flex-grow:1;margin:0;font-size:16px;font-weight:800;line-height:1.2}"
    ".brand small{display:block;font-size:12px;font-weight:500;color:#5B6675}"
    "h1{font-size:28px;font-weight:800;margin:0 0 6px}"
    ".hint{margin:0 0 8px;font-size:14px;color:#5B6675}"
    ".lang{display:flex;gap:2px;padding:3px;border:1px solid #E7EAEE;border-radius:10px;font-size:12px}"
    ".lang a,.lang span{min-width:40px;padding:8px 10px;box-sizing:border-box;border-radius:8px;"
    "text-align:center;text-decoration:none;font-weight:700;color:#3D4A5C}"
    ".lang span{background:#0F1B2D;color:#FFFFFF}"
    ".lang a:hover{background:#F4F6F8;text-decoration:none}"
    ".row{display:flex;align-items:baseline;justify-content:space-between;gap:8px}"
    "label{display:block;font-size:13px;font-weight:600;color:#3D4A5C;margin:14px 0 6px}"
    "input,select{width:100%;box-sizing:border-box;height:48px;padding:0 14px;border:1px solid #DCE1E7;"
    "border-radius:12px;font:inherit;font-size:15px;color:#0F1B2D;background:#FFFFFF}"
    "input[type=tel]{font-variant-numeric:tabular-nums;font-weight:600}"
    "input[aria-invalid=true],select[aria-invalid=true]{border-color:#C8372D}"
    "input:focus,select:focus{outline:2px solid #0E7C66;outline-offset:1px;border-color:#0E7C66}"
    "button{margin-top:20px;width:100%;height:50px;border:0;border-radius:12px;"
    "background:#0E7C66;color:#FFFFFF;font:inherit;font-size:16px;font-weight:800;cursor:pointer}"
    "button:hover,button:active{background:#0A5E4D}"
    "button:focus-visible,a:focus-visible{outline:2px solid #0E7C66;outline-offset:2px}"
    ".err{background:#FBEAE8;color:#A82B22;border:1px solid #F3CFCB;padding:10px 12px;border-radius:10px;"
    "font-size:13px;font-weight:600;margin:12px 0 0}"
    ".or{display:flex;align-items:center;gap:12px;margin:20px 0 0;color:#5B6675;font-size:12px;"
    "font-weight:600}"
    ".or::before,.or::after{content:'';flex:1;border-top:1px solid #E7EAEE}"
    "a{color:#0E7C66;font-weight:700;text-decoration:none}a:hover{color:#0A5E4D;text-decoration:underline}"
    ".google{display:flex;align-items:center;justify-content:center;gap:10px;margin-top:14px;height:48px;"
    "border:1px solid #DCE1E7;border-radius:12px;color:#0F1B2D;font-size:15px}"
    ".google:hover{background:#F4F6F8;color:#0F1B2D;text-decoration:none}"
    ".google b{width:24px;height:24px;border-radius:50%;border:1.5px solid #3D4A5C;display:inline-flex;"
    "align-items:center;justify-content:center;font-size:13px;font-weight:800}"
    ".row a{font-size:13px}"
    ".links{display:flex;flex-direction:column;align-items:center;gap:8px;margin:20px 0 0;font-size:14px;"
    "color:#3D4A5C}"
)
# BO-01 entry points (07 BO-01, qaror #34): Google login (web BFF only) and the one-time-code flows
GOOGLE_START_PATH: Final = "/auth/google/start"
RECOVERY_PATH: Final = "/recover"  # SPA: OTP purpose=recovery → POST /auth/credentials
SIGNUP_PATH: Final = "/onboarding"  # SPA: BO-21 self-service signup (web only)
INVITE_PATH: Final = "/invite"  # SPA: staff invite / reset code → POST /auth/credentials
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
        "INVALID_CREDENTIALS": "Telefon yoki parol noto'g'ri. Qayta urinib ko'ring yoki parolni tiklang.",
        "ACCOUNT_LOCKED": "Hisob vaqtincha bloklangan, keyinroq urinib ko'ring",
        "RATE_LIMITED": "Juda ko'p urinish, biroz kutib qayta urinib ko'ring",
        "SUBSCRIPTION_RESTRICTED": "Obuna muddati tugagan, to'lov qiling",
        "PERMISSION_DENIED": "Bu do'konga kirish huquqingiz yo'q",
        "VALIDATION_ERROR": "Do'konni tanlang va parolni qayta kiriting",
    },
    "ru": {
        "INVALID_CREDENTIALS": "Неверный телефон или пароль. Попробуйте ещё раз или восстановите пароль.",
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
        "tagline": "Do'kon boshqaruv paneli",
        "heading": "Tizimga kirish",
        "hint": "Egasi, menejer va buxgalter uchun. Kassirlar kassadan PIN bilan kiradi.",
        "phone": "Telefon",
        "password": "Parol",
        "tenant": "Do'kon",
        "submit": "Kirish",
        "lang": "Til",
        "or": "yoki",
        "google": "Google bilan kirish",
        "forgot": "Parolni unutdim?",
        "invite": "Taklif kodi bor",
        "no_account": "Hisobingiz yo'qmi?",
        "signup": "Ro'yxatdan o'ting",
    },
    "ru": {
        "title": "Вход",
        "tagline": "Панель управления магазином",
        "heading": "Вход в систему",
        "hint": "Для владельца, менеджера и бухгалтера. Кассиры входят на кассе по PIN-коду.",
        "phone": "Телефон",
        "password": "Пароль",
        "tenant": "Магазин",
        "submit": "Войти",
        "lang": "Язык",
        "or": "или",
        "google": "Войти через Google",
        "forgot": "Забыли пароль?",
        "invite": "Есть код приглашения",
        "no_account": "Нет учётной записи?",
        "signup": "Зарегистрируйтесь",
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


def _invalid(flag: bool) -> str:
    return ' aria-invalid="true" aria-describedby="login-error"' if flag else ""


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
    # 07 BO-01 "error": which part is wrong is not revealed, so both credentials are marked
    invalid_credentials = error_code in ("INVALID_CREDENTIALS", "ACCOUNT_LOCKED")
    invalid_tenant = bool(tenants) and error_code in ("VALIDATION_ERROR", "PERMISSION_DENIED")
    tenant_field = ""
    if tenants:
        options = "".join(
            f'<option value="{escape(str(t.tenant_id))}">{escape(t.tenant_name)}</option>' for t in tenants
        )
        label = f'<label for="tenant_id">{escape(labels["tenant"])}</label>'
        tenant_field = (
            f'{label}<select id="tenant_id" name="tenant_id" required{_invalid(invalid_tenant)}>'
            f"{options}</select>"
        )
    elif params.get("tenant_id"):
        tenant_field = f'<input type="hidden" name="tenant_id" value="{escape(params["tenant_id"])}">'
    error = (
        '<p class="err" id="login-error" role="alert">'
        f"{escape(MESSAGES[locale].get(error_code, error_code))}</p>"
        if error_code
        else ""
    )
    switch = _switch(params, locale, labels["lang"])
    web = params.get("client_id") == "web-bff"
    extras = ""
    if web:
        tenant = {"tenant_id": params["tenant_id"]} if params.get("tenant_id") else {}
        google_href = GOOGLE_START_PATH + ("?" + urlencode(tenant) if tenant else "")
        extras += (
            f'<p class="or">{escape(labels["or"])}</p>'
            f'<a class="google" href="{escape(google_href)}"><b aria-hidden="true">G</b>'
            f"{escape(labels['google'])}</a>"
        )
    links = f'<a href="{INVITE_PATH}">{escape(labels["invite"])}</a>'
    if web:  # BO-21 signup is a web flow
        signup = f'<a href="{SIGNUP_PATH}">{escape(labels["signup"])}</a>'
        links += f"<span>{escape(labels['no_account'])} {signup}</span>"
    extras += f'<nav class="links">{links}</nav>'
    body = (
        f'<!doctype html><html lang="{locale}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(labels['title'])}</title>"
        f"<style>{STYLE}</style></head><body><main>"
        '<form method="post" action="/oauth/authorize" autocomplete="on" aria-labelledby="login-title">'
        '<div class="top"><span class="mark" aria-hidden="true">E</span>'
        f'<p class="brand">ERP<small>{escape(labels["tagline"])}</small></p>{switch}</div>'
        f'<h1 id="login-title">{escape(labels["heading"])}</h1><p class="hint">{escape(labels["hint"])}</p>'
        f"{error}{hidden}"
        f'<label for="phone">{escape(labels["phone"])}</label>'
        '<input id="phone" name="phone" type="tel" inputmode="tel" autocomplete="username" required '
        f'maxlength="17" placeholder="+998 90 123 45 67" value="{escape(phone)}"'
        f"{_invalid(invalid_credentials)}>"
        f'<div class="row"><label for="password">{escape(labels["password"])}</label>'
        f'<a href="{RECOVERY_PATH}">{escape(labels["forgot"])}</a></div>'
        '<input id="password" name="password" type="password" autocomplete="current-password" required '
        f'minlength="8" maxlength="128"{_invalid(invalid_credentials)}>'
        f"{tenant_field}"
        f'<button type="submit">{escape(labels["submit"])}</button>{extras}</form></main></body></html>'
    )
    return HTMLResponse(body, status_code=status_code, headers={**SECURITY_HEADERS, **(headers or {})})
