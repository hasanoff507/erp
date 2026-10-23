from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.modules.auth.api import oauth


@pytest.mark.parametrize(
    ("environment", "origin", "fetch_site", "expected"),
    [
        ("local", "http://localhost:5173", None, True),
        ("local", "https://evil.example", "same-origin", False),
        ("test", "http://localhost:5173", None, False),
        ("prod", "http://localhost:5173", None, False),
        ("prod", "https://erp.example.uz", None, True),
        ("test", "null", "same-origin", True),
        ("test", "null", "cross-site", False),
        ("test", "null", None, False),
        ("test", None, "same-origin", True),
        ("test", None, "cross-site", False),
        ("test", "https://evil.example", "same-origin", False),
    ],
)
def test_authorize_origin_allowlist_is_environment_scoped(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    origin: str | None,
    fetch_site: str | None,
    expected: bool,
) -> None:
    headers = []
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if fetch_site is not None:
        headers.append((b"sec-fetch-site", fetch_site.encode()))
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "server": ("localhost", 8000),
            "client": ("127.0.0.1", 50000),
            "root_path": "",
            "path": "/oauth/authorize",
            "raw_path": b"/oauth/authorize",
            "query_string": b"",
            "headers": headers,
        }
    )
    module = SimpleNamespace(
        settings=SimpleNamespace(environment=environment, issuer="https://erp.example.uz")
    )
    monkeypatch.setattr(oauth, "auth_module", lambda _request: module)

    assert oauth.same_origin(request) is expected
