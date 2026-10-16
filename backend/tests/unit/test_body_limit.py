"""Request body cap (17 §12, SEC-13): 413 FILE_TOO_LARGE by Content-Length and by streamed bytes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI, Request

from app.core.body_limit import MULTIPART_MARGIN, BodyLimitMiddleware
from app.core.config import Settings
from app.core.errors import install_error_handlers
from app.main import create_app

LIMIT = 1000
UPLOAD_LIMIT = 5000


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/json")
    async def json_echo(payload: dict[str, Any]) -> dict[str, int]:
        return {"keys": len(payload)}

    @app.post("/raw")
    async def raw(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/upload")
    async def upload(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    app.add_middleware(BodyLimitMiddleware, default_max_bytes=LIMIT, upload_paths={"/upload": UPLOAD_LIMIT})
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app()), base_url="http://t")


def _assert_413(response: httpx.Response, limit: int) -> None:
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "FILE_TOO_LARGE"
    assert error["params"] == {"max_bytes": limit}


async def test_small_body_passes() -> None:
    async with _client() as client:
        response = await client.post("/json", json={"a": 1})
    assert response.status_code == 200
    assert response.json() == {"keys": 1}


async def test_declared_content_length_over_limit_is_refused() -> None:
    async with _client() as client:
        response = await client.post("/raw", content=b"x" * (LIMIT + 1))
    _assert_413(response, LIMIT)


async def test_upload_path_gets_its_own_limit() -> None:
    async with _client() as client:
        ok = await client.post("/upload", content=b"x" * (UPLOAD_LIMIT - 10))
        too_big = await client.post("/upload", content=b"x" * (UPLOAD_LIMIT + 1))
    assert ok.status_code == 200
    assert ok.json() == {"size": UPLOAD_LIMIT - 10}
    _assert_413(too_big, UPLOAD_LIMIT)


async def _chunks(total: int, size: int = 256) -> AsyncIterator[bytes]:
    sent = 0
    while sent < total:
        part = min(size, total - sent)
        sent += part
        yield b"x" * part


async def test_chunked_body_is_counted_while_streaming() -> None:
    async with _client() as client:
        ok = await client.post("/raw", content=_chunks(LIMIT))
        too_big = await client.post("/raw", content=_chunks(LIMIT * 3))
        json_too_big = await client.post(
            "/json", content=_chunks(LIMIT * 3), headers={"content-type": "application/json"}
        )
    assert ok.status_code == 200
    assert ok.json() == {"size": LIMIT}
    _assert_413(too_big, LIMIT)
    _assert_413(json_too_big, LIMIT)


async def test_lying_content_length_is_still_cut_off() -> None:
    """A small declared length does not let a longer stream through."""
    sent: list[dict[str, Any]] = []
    app = _app()
    body = b"x" * (LIMIT * 2)
    messages = [{"type": "http.request", "body": body[:LIMIT], "more_body": True},
                {"type": "http.request", "body": body[LIMIT:], "more_body": False}]  # fmt: skip

    async def receive() -> dict[str, Any]:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": "/raw", "raw_path": b"/raw", "query_string": b"",
        "headers": [(b"content-length", b"10"), (b"host", b"t")], "client": ("1.2.3.4", 1),
        "server": ("t", 80), "root_path": "",
    }  # fmt: skip
    await app(scope, receive, send)
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413


def test_create_app_registers_the_limit_for_import_uploads() -> None:
    settings = Settings(_env_file=None, log_json=False)
    app = create_app(settings)
    entries = [m for m in app.user_middleware if m.cls is BodyLimitMiddleware]
    assert len(entries) == 1
    kwargs = entries[0].kwargs
    assert kwargs["upload_paths"] == {
        f"{settings.api_prefix}/import-jobs": settings.import_max_bytes + MULTIPART_MARGIN
    }
