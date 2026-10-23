"""Request body size limit (17 §12, SEC-13): ``413 FILE_TOO_LARGE`` before the body is buffered.

Pure ASGI, route-aware: the import upload (``POST {api_prefix}/import-jobs``) may carry the
import file limit plus a multipart margin, every other request the JSON default. A declared
``Content-Length`` over the limit is refused without reading the body; chunked (or lying)
bodies are counted as they stream and cut off at the limit — the app's partial response is
replaced by the 413 envelope as long as nothing was sent yet.
"""

from __future__ import annotations

from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.error_codes import ErrorCode
from app.core.errors import error_response

DEFAULT_MAX_BYTES: Final = 1024 * 1024  # JSON bodies (largest Bosqich 1 body is far below)
MULTIPART_MARGIN: Final = 64 * 1024  # multipart boundaries + the small form fields


class BodyTooLargeError(Exception):
    """Raised from ``receive`` once the streamed body passes the limit."""


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        default_max_bytes: int = DEFAULT_MAX_BYTES,
        upload_paths: dict[str, int] | None = None,
    ) -> None:
        self.app = app
        self.default_max_bytes = default_max_bytes
        # exact path → limit (POST/PUT/PATCH only; the paths have no path parameters)
        self.upload_paths = {p.rstrip("/"): n for p, n in (upload_paths or {}).items()}

    def limit_for(self, scope: Scope) -> int:
        path = str(scope.get("path", "")).rstrip("/")
        return self.upload_paths.get(path, self.default_max_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope)
        declared = _content_length(scope)
        if declared is not None and declared > limit:
            await self._reject(scope, receive, send, limit)
            return

        received = 0
        exceeded = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise BodyTooLargeError
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if exceeded:
                return  # the app turned the cut-off into its own error; the 413 replaces it
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:  # BodyTooLargeError (or whatever the app wrapped it in) is answered below
                raise
        if exceeded and not started:
            await self._reject(scope, receive, send, limit)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, limit: int) -> None:
        response = error_response(
            ErrorCode.FILE_TOO_LARGE, 413, params={"max_bytes": limit}, headers={"Connection": "close"}
        )
        await response(scope, receive, send)
