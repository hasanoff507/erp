"""SEC-05: a value too large for its NUMERIC column (qty × cost) is a 422, not a 500."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.exc import DBAPIError
from starlette.requests import Request

from app.core.errors import _db_error_handler


class _OrigError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("db error")
        self.sqlstate = sqlstate


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


async def test_numeric_out_of_range_maps_to_422() -> None:
    exc = DBAPIError("INSERT …", {}, _OrigError("22003"))
    response = await _db_error_handler(_request(), exc)
    assert response.status_code == 422
    body = json.loads(bytes(response.body))
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == [{"field": "", "message_key": "validation.numeric_out_of_range"}]


async def test_other_database_errors_stay_unhandled() -> None:
    exc = DBAPIError("INSERT …", {}, _OrigError("23505"))
    with pytest.raises(DBAPIError):
        await _db_error_handler(_request(), exc)
