"""Dev gap (PLAN deferred): ``scripts/auth_ops.py configure-client`` redirect URIs — ``https://`` everywhere,
``http://localhost[:port]`` / ``http://127.0.0.1[:port]`` only in local/dev/test (RFC 8252 §7.3)."""

from __future__ import annotations

import pytest

from app.modules.auth.domain.redirects import InvalidRedirectUriError, validate_redirect_uri


@pytest.mark.parametrize(
    "uri",
    [
        "https://app.example.uz/auth/callback",
        "https://localhost/auth/callback",
    ],
)
@pytest.mark.parametrize("environment", ["local", "test", "staging", "prod"])
def test_auth_ops_https_redirect_accepted_everywhere(uri: str, environment: str) -> None:
    assert validate_redirect_uri(uri, environment) == uri


@pytest.mark.parametrize(
    "uri",
    [
        "http://localhost/auth/callback",
        "http://localhost:5173/auth/callback",
        "http://127.0.0.1:8000/auth/callback",
        "http://127.0.0.1/auth/callback",
    ],
)
@pytest.mark.parametrize("environment", ["local", "dev", "test"])
def test_auth_ops_http_loopback_allowed_in_dev(uri: str, environment: str) -> None:
    assert validate_redirect_uri(uri, environment) == uri


@pytest.mark.parametrize("environment", ["staging", "prod"])
def test_auth_ops_http_loopback_refused_in_hardened_environments(environment: str) -> None:
    with pytest.raises(InvalidRedirectUriError):
        validate_redirect_uri("http://localhost:5173/auth/callback", environment)


@pytest.mark.parametrize(
    "uri",
    [
        "http://example.uz/auth/callback",  # other http host
        "http://localhost.evil.com/auth/callback",  # loopback name as a prefix of another host
        "http://localhost@evil.com/auth/callback",  # userinfo trick: the host is evil.com
        "http://evil.com@localhost/auth/callback",  # userinfo is never allowed
        "https://user:pass@app.example.uz/cb",
        "http://127.0.0.1.nip.io/cb",
        "http://[::1]:5173/cb",  # only the two named loopback hosts
        "http://localhost:99999/cb",  # invalid port
        "https://app.example.uz/cb#frag",  # RFC 6749 §3.1.2: no fragment
        "ftp://localhost/cb",
        "localhost:5173/cb",
    ],
)
@pytest.mark.parametrize("environment", ["local", "prod"])
def test_auth_ops_rejects_unsafe_redirects(uri: str, environment: str) -> None:
    with pytest.raises(InvalidRedirectUriError):
        validate_redirect_uri(uri, environment)
