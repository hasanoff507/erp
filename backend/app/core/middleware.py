"""Request context middleware: request id, structlog context, last-resort 500.

Pure ASGI so the request id survives into the error envelope of unhandled
exceptions (``X-Request-Id`` == ``error.request_id``, 17 §6).
"""

from __future__ import annotations

import re
import time

import structlog
import uuid_utils
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import request_id_var
from app.core.error_codes import ErrorCode
from app.core.errors import error_response

log = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "x-request-id"
_VALID_INCOMING_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == REQUEST_ID_HEADER.encode():
            candidate = value.decode("latin-1")
            return candidate if _VALID_INCOMING_ID.match(candidate) else None
    return None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or str(uuid_utils.uuid7())
        token = request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        response_started = False
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            log.exception("unhandled_error", exc_type=type(exc).__name__, path=scope.get("path"))
            if response_started:
                raise
            response = error_response(ErrorCode.INTERNAL_ERROR, 500)
            await response(scope, receive, send_wrapper)
        finally:
            log.info(
                "http_request",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("request_id")
            request_id_var.reset(token)
