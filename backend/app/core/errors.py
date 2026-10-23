"""Error envelope and exception handlers (17 §7, 32 §5.1).

Every error leaves the API as
``{"error": {code, message_key, params, details[], request_id}}``.
Endpoints raise :class:`AppError`; JSON is never assembled by hand.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import current_request_id
from app.core.error_codes import ERROR_SPECS, ErrorCode


class ErrorDetail(BaseModel):
    field: str
    message_key: str


class ErrorBody(BaseModel):
    code: ErrorCode
    message_key: str
    params: dict[str, Any] = Field(default_factory=dict)
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Business/API error carrying a catalog code (17 §15)."""

    def __init__(
        self,
        code: ErrorCode,
        *,
        params: Mapping[str, Any] | None = None,
        details: Sequence[ErrorDetail] | None = None,
        message_key: str | None = None,
        status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        spec = ERROR_SPECS[code]
        status = status_code if status_code is not None else spec.http_status
        if status is None or status < 400:
            raise ValueError(f"{code} is not an HTTP error code (17 §15)")
        super().__init__(code.value)
        self.code = code
        self.status_code = status
        self.message_key = message_key or spec.message_key
        self.params = dict(params or {})
        self.details = list(details or [])
        self.headers = dict(headers or {})


def error_body(
    code: ErrorCode,
    *,
    message_key: str | None = None,
    params: Mapping[str, Any] | None = None,
    details: Sequence[ErrorDetail] = (),
) -> dict[str, Any]:
    body = ErrorBody(
        code=code,
        message_key=message_key or ERROR_SPECS[code].message_key,
        params=dict(params or {}),
        details=list(details),
        request_id=current_request_id(),
    )
    return ErrorEnvelope(error=body).model_dump(mode="json")


def error_response(
    code: ErrorCode,
    status_code: int,
    *,
    message_key: str | None = None,
    params: Mapping[str, Any] | None = None,
    details: Sequence[ErrorDetail] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        error_body(code, message_key=message_key, params=params, details=details),
        status_code=status_code,
        headers=dict(headers or {}),
    )


_PYDANTIC_KEYS = {
    "missing": "validation.required",
    "string_too_long": "validation.max_length",
    "too_long": "validation.max_length",
}


def _field_path(loc: Sequence[Any]) -> str:
    parts = list(loc)
    if parts and parts[0] in ("body", "query", "path", "header", "cookie"):
        parts = parts[1:]
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


def validation_details(errors: Sequence[Mapping[str, Any]]) -> list[ErrorDetail]:
    return [
        ErrorDetail(
            field=_field_path(err.get("loc", ())),
            message_key=_PYDANTIC_KEYS.get(str(err.get("type")), f"validation.{err.get('type')}"),
        )
        for err in errors
    ]


_HTTP_STATUS_CODES = {
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.NOT_FOUND,
    429: ErrorCode.RATE_LIMITED,
}


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(
        exc.code,
        exc.status_code,
        message_key=exc.message_key,
        params=exc.params,
        details=exc.details,
        headers=exc.headers,
    )


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(ErrorCode.VALIDATION_ERROR, 422, details=validation_details(exc.errors()))


async def _http_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = exc.status_code
    if status in _HTTP_STATUS_CODES:
        code = _HTTP_STATUS_CODES[status]
    else:
        code = ErrorCode.INTERNAL_ERROR if status >= 500 else ErrorCode.VALIDATION_ERROR
    return error_response(code, status, headers=exc.headers)


_NUMERIC_OUT_OF_RANGE = "22003"  # PostgreSQL numeric_value_out_of_range


def _sqlstate(exc: DBAPIError) -> str | None:
    orig = exc.orig
    state = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    return str(state) if state else None


async def _db_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """A value too large for its NUMERIC column (e.g. qty × cost) is bad input, not a 500 (SEC-05)."""
    assert isinstance(exc, DBAPIError)
    if _sqlstate(exc) == _NUMERIC_OUT_OF_RANGE:
        return error_response(
            ErrorCode.VALIDATION_ERROR,
            422,
            details=[ErrorDetail(field="", message_key="validation.numeric_out_of_range")],
        )
    raise exc  # anything else stays an INTERNAL_ERROR (RequestContextMiddleware logs it)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(DBAPIError, _db_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    # unhandled exceptions become INTERNAL_ERROR in RequestContextMiddleware
