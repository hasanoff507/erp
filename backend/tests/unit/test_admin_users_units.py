"""Pure pieces of BO-11 (slice A2): cursor codec (17 §4) and request validation (07 BO-11 fields)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.db.base import uuid7
from app.core.errors import AppError
from app.modules.auth.api.admin_users import StaffCreate, StaffUpdate
from app.modules.auth.application.admin_users import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    stamp, ident = datetime(2026, 10, 16, 9, 30, 1, 123456, tzinfo=UTC), uuid7()
    assert decode_cursor(encode_cursor(stamp, ident)) == (stamp, ident)


@pytest.mark.parametrize("bad", ["%%%", "bm90LWEtY3Vyc29y", encode_cursor(datetime(2026, 1, 1), UUID(int=1))])  # noqa: DTZ001 — a naive stamp is refused
def test_bad_cursor_is_a_validation_error(bad: str) -> None:
    with pytest.raises(AppError) as exc:
        decode_cursor(bad)
    assert exc.value.code == "VALIDATION_ERROR"
    assert exc.value.details[0].field == "cursor"


def _create(**overrides: object) -> StaffCreate:
    values: dict[str, object] = {
        "phone": "+998 90 123-45-67", "name": "  Dilnoza  ", "role_ids": [str(uuid7())],
        "branch_ids": [str(uuid7())],
    }  # fmt: skip
    return StaffCreate.model_validate({**values, **overrides})


def test_staff_create_normalizes_phone_and_name() -> None:
    body = _create()
    assert body.phone == "+998901234567" and body.name == "Dilnoza"


@pytest.mark.parametrize(
    "overrides",
    [
        {"phone": "+79001234567"},
        {"phone": "998901234567"},
        {"name": "A"},
        {"name": "x" * 101},
        {"role_ids": []},
        {"branch_ids": []},
        {"password": "secret-123"},
        {"pin": "1234"},
    ],
)
def test_staff_create_rejects(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _create(**overrides)


def test_staff_update_fields() -> None:
    assert StaffUpdate.model_validate({"status": "blocked"}).status == "blocked"
    with pytest.raises(ValidationError):
        StaffUpdate.model_validate({"status": "deleted"})
    with pytest.raises(ValidationError):
        StaffUpdate.model_validate({"role_ids": []})
    with pytest.raises(ValidationError):
        StaffUpdate.model_validate({"name": "x"})
