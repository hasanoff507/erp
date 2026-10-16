"""Pure auth building blocks: scopes (14 §10), envelope encryption (15 §4.2), CSRF/cookie signing (15 §1.3)."""

from __future__ import annotations

import pytest

from app.core.auth.tokens import CsrfTokens, SessionCookieSigner
from app.core.config import Settings
from app.core.db.base import uuid7
from app.core.secrets import EnvelopeCipher, SecretDecryptionError
from app.modules.auth.application.bff import safe_return_to
from app.modules.auth.application.login import normalize_phone
from app.modules.auth.application.passwords import hash_password, verify_password
from app.modules.auth.domain.models import OAuthClient
from app.modules.auth.domain.scopes import client_scope_ceiling, derive_scopes, effective_scopes

KEK = "ZGV2LW9ubHkta2VrLWRvLW5vdC11c2UtaW4tcHJvZCE="
OTHER_KEK = "b3RoZXIta2VrLW9mLWV4YWN0bHktMzItYnl0ZXMhISE="


def test_scope_is_unique_permission_prefixes() -> None:
    assert derive_scopes({"sales.create", "sales.void", "debts.payment.accept"}) == {"sales", "debts"}


def test_scope_ceiling_and_effective_scopes() -> None:
    perms = {"sales.create", "settings.users"}
    assert effective_scopes("*", perms) == {"sales", "settings"}
    assert effective_scopes("* sync pos", perms) == {"sales", "settings", "sync", "pos"}
    assert effective_scopes("sales reports", perms) == {"sales"}  # never more than the user holds
    # web-bff may not ask for the Android-only implicit scopes; android-pos may
    assert client_scope_ceiling(("*",), "sales sync") == "sales"
    assert client_scope_ceiling(("*", "sync", "pos"), "sales sync") == "sales sync"
    assert client_scope_ceiling(("platform.admin",), "sales") == ""


def _client(kind: str, secret: str | None) -> OAuthClient:
    return OAuthClient(
        uuid7(), "c", kind, "c", secret, ("https://x/cb",), ("authorization_code", "refresh_token"), ("*",)
    )


def test_client_auth_methods_and_redirects() -> None:
    public, confidential = _client("public", None), _client("confidential", "s" * 40)
    assert public.check_endpoint_auth_method("none", "token")
    assert not public.check_endpoint_auth_method("none", "introspection")
    assert not confidential.check_endpoint_auth_method("none", "token")
    assert confidential.check_client_secret("s" * 40) and not confidential.check_client_secret("s" * 39)
    assert not public.check_client_secret("")
    assert public.check_redirect_uri("https://x/cb") and not public.check_redirect_uri("https://x/cb/")
    assert public.get_default_redirect_uri() is None


def test_envelope_roundtrip_binding_and_rotation() -> None:
    v1 = EnvelopeCipher.from_settings(KEK, 1, {})
    sealed = v1.encrypt(b"private-key", b"signing_keys:a")
    assert v1.decrypt(sealed, b"signing_keys:a") == b"private-key"
    with pytest.raises(SecretDecryptionError):
        v1.decrypt(sealed, b"signing_keys:b")  # copied into another row
    tampered = sealed[:-4] + ("A" if sealed[-4] != "A" else "B") + sealed[-3:]
    with pytest.raises(SecretDecryptionError):
        v1.decrypt(tampered, b"signing_keys:a")
    v2 = EnvelopeCipher.from_settings(OTHER_KEK, 2, {1: KEK})
    assert v2.decrypt(sealed, b"signing_keys:a") == b"private-key" and v2.needs_rewrap(sealed)
    with pytest.raises(SecretDecryptionError):
        EnvelopeCipher.from_settings(OTHER_KEK, 2, {}).decrypt(sealed, b"signing_keys:a")


def test_csrf_token_is_bound_to_the_session() -> None:
    csrf = CsrfTokens("secret", 3600)
    sid, other = uuid7(), uuid7()
    token = csrf.issue(sid)
    assert csrf.verify(token, sid)
    assert not csrf.verify(token, other) and not csrf.verify(None, sid) and not csrf.verify("x", sid)
    assert not CsrfTokens("another-secret", 3600).verify(token, sid)


def test_session_cookie_is_signed() -> None:
    signer = SessionCookieSigner("secret")
    sid = uuid7()
    assert signer.unsign(signer.sign(sid)) == sid
    assert signer.unsign(str(sid)) is None and signer.unsign(signer.sign(sid) + "x") is None


def test_password_hashing_argon2id() -> None:
    hashed = hash_password("Parol-12345")
    assert hashed.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert verify_password(hashed, "Parol-12345") and not verify_password(hashed, "parol-12345")
    assert not verify_password(None, "Parol-12345")  # unknown user: still one verification, never ok
    assert not verify_password(hashed, "x" * 129)
    with pytest.raises(ValueError, match=r"8..128"):
        hash_password("short")


def test_phone_and_return_to_normalisation() -> None:
    assert normalize_phone("+998 90 123-45-67") == "+998901234567"
    assert normalize_phone("998901234567") is None and normalize_phone("+7 900 1234567") is None
    assert safe_return_to("/sales?x=1") == "/sales?x=1"
    for bad in (None, "", "https://evil.example", "//evil.example", "/\\evil", "javascript:x"):
        assert safe_return_to(bad) == "/"


def test_prod_guard_requires_auth_secrets() -> None:
    base = {"_env_file": None, "environment": "prod", "auth_secret": "x" * 40, "ai_mode": "api"}
    with pytest.raises(ValueError, match="KEK"):
        Settings(**base, public_base_url="https://app.example.uz")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="WEB_BFF"):
        Settings(**base, kek=OTHER_KEK, public_base_url="https://app.example.uz")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="https"):
        Settings(  # type: ignore[arg-type]
            **base, kek=OTHER_KEK, web_bff_client_secret="y" * 40, public_base_url="http://app.example.uz"
        )
    ok = Settings(
        **base, kek=OTHER_KEK, web_bff_client_secret="y" * 40, public_base_url="https://app.example.uz/"
    )  # type: ignore[arg-type]
    assert ok.issuer == "https://app.example.uz"
