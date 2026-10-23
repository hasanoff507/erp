"""Error envelope and the generated catalog (17 §7, §15)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.error_codes import ERROR_SPECS, ErrorCode
from app.core.errors import AppError, install_error_handlers
from app.core.middleware import RequestContextMiddleware


def test_catalog_has_207_codes_with_errors_keys() -> None:
    assert len(ErrorCode) == 207  # 17 §15: 126 general + 81 ONEC_*
    assert sum(1 for c in ErrorCode if c.startswith("ONEC_")) == 81
    for code, spec in ERROR_SPECS.items():
        assert spec.message_key.startswith(("errors.", "warnings.")), code


def test_app_error_refuses_codes_that_are_not_http_errors() -> None:
    with pytest.raises(ValueError, match="not an HTTP error"):
        AppError(ErrorCode.TELEGRAM_NOT_LINKED)  # 200, informational


class Body(BaseModel):
    qty: str = Field(max_length=5)
    comment: str


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.post("/limit")
    async def limit() -> None:
        raise AppError(ErrorCode.DEBT_LIMIT_EXCEEDED, params={"limit": "500000.00", "requested": "569000.00"})

    @app.post("/validate")
    async def validate(body: Body) -> Body:
        return body

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail must not leak")

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_app_error_envelope(client: TestClient) -> None:
    r = client.post("/limit")
    assert r.status_code == ERROR_SPECS[ErrorCode.DEBT_LIMIT_EXCEEDED].http_status
    err = r.json()["error"]
    assert err["code"] == "DEBT_LIMIT_EXCEEDED"
    assert err["message_key"] == "errors.debt_limit_exceeded"
    assert err["params"] == {"limit": "500000.00", "requested": "569000.00"}
    assert err["details"] == []
    assert err["request_id"] == r.headers["x-request-id"]


def test_validation_details_are_field_level(client: TestClient) -> None:
    r = client.post("/validate", json={"qty": "1234567"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert {"field": "qty", "message_key": "validation.max_length"} in err["details"]
    assert {"field": "comment", "message_key": "validation.required"} in err["details"]


def test_unknown_route_is_not_found(client: TestClient) -> None:
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_unhandled_exception_is_internal_error_without_details(client: TestClient) -> None:
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in r.text
    assert body["error"]["request_id"] == r.headers["x-request-id"]


def test_incoming_request_id_is_kept(client: TestClient) -> None:
    r = client.post("/limit", headers={"X-Request-Id": "req-12345678"})
    assert r.headers["x-request-id"] == "req-12345678"
    assert r.json()["error"]["request_id"] == "req-12345678"
