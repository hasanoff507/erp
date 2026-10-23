"""Small helpers shared by the stock document services (transfers, stock counts, write-offs)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money, price, qty
from app.core.permissions import BranchScope
from app.modules.accounting.domain.calendar import business_today

CURSOR_MIN = datetime(2000, 1, 1, tzinfo=UTC)
CURSOR_MAX = datetime(2100, 1, 1, tzinfo=UTC)


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def q3(value: Decimal | None) -> str | None:
    return None if value is None else format(qty(value), "f")


def m2(value: Decimal | None) -> str | None:
    return None if value is None else format(money(value), "f")


def p4(value: Decimal | None) -> str | None:
    return None if value is None else format(price(value), "f")


def encode_cursor(at: datetime, doc_id: UUID) -> str:
    raw = json.dumps([at.isoformat(), str(doc_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """``(created_at, id)`` of a list cursor; anything else → ``422 validation.cursor_invalid``.

    The instant must be tz-aware and inside ``[2000-01-01, 2100-01-01)`` UTC — an extreme value
    (``9999-12-31T23:59:59+14:00``) would overflow in the driver instead of failing as a 422.
    """
    try:
        raw, oid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        at = datetime.fromisoformat(raw)
        if at.tzinfo is None or not CURSOR_MIN <= at.astimezone(UTC) < CURSOR_MAX:
            raise ValueError("cursor instant out of range")
        return at, UUID(oid)
    except (ValueError, TypeError, OverflowError) as exc:
        raise invalid("cursor", "validation.cursor_invalid") from exc


def check_doc_date(doc_date: date) -> None:
    """``doc_date`` after the business day → ``422 validation.doc_date_in_future`` (13 §5.2, 19 §0)."""
    if doc_date > business_today():
        raise invalid("doc_date", "validation.doc_date_in_future")


def in_scope(scope: BranchScope, branch_id: UUID) -> bool:
    return scope.unrestricted or branch_id in scope.allowed


def require_scope(scope: BranchScope, branch_id: UUID) -> None:
    if not in_scope(scope, branch_id):
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)


def invalid_state(expected: str, actual: str) -> AppError:
    return AppError(
        ErrorCode.DOC_INVALID_STATE, params={"expected_status": expected, "actual_status": actual}
    )


def scoped_branches(scope: BranchScope) -> list[UUID] | None:
    """Branch filter of a list query: ``None`` = every branch."""
    return None if scope.unrestricted else list(scope.allowed)
