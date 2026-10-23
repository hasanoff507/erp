from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.modules.auth.api import oauth


@pytest.mark.parametrize(
    ("environment", "origin", "expected"),
    [
        ("local", "http://localhost:5173", True),
        ("local", "https://evil.example", False),
        ("test", "http://localhost:5173", False),
        ("prod", "http://localhost:5173", False),
        ("prod", "https://erp.example.uz", True),
    ],
)
def test_authorize_origin_allowlist_is_environment_scoped(
    monkeypatch: pytest.MonkeyPatch, environment: str, origin: str, expected: bool
) -> None:
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
            "headers": [(b"origin", origin.encode())],
        }
    )
    module = SimpleNamespace(
        settings=SimpleNamespace(environment=environment, issuer="https://erp.example.uz")
    )
    monkeypatch.setattr(oauth, "auth_module", lambda _request: module)

    assert oauth.same_origin(request) is expected
