"""Small helpers shared by the cash services (cursor, timestamps, closed-period register date, scope)."""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.permissions import BranchScope
from app.modules.accounting.wiring import LedgerPoster, period_label


def ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def m2(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(Decimal("0.01")), "f")


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def encode_cursor(at: datetime, row_id: UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, row_id = json.loads(raw)
        return datetime.fromisoformat(at), UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise invalid("cursor", "validation.cursor_invalid") from exc


def scope_branches(scope: BranchScope) -> tuple[UUID, ...] | None:
    """``None`` = every branch; the validated ``X-Branch-Id`` narrows the view."""
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


def check_branch(scope: BranchScope, branch_id: UUID, resource: str) -> None:
    if not scope.unrestricted and branch_id not in scope.allowed:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": resource})


async def register_date(s: AsyncSession, poster: LedgerPoster, doc_date: date) -> tuple[date, str | None]:
    """POS event in a closed period (16 §3.4, 13 §5.1, qaror #69): registers go to the first open date and
    ledger analytics get ``correction_of_period``; returns ``(entry_date, correction_of_period | None)``."""
    entry = await poster.first_open_date(s, doc_date)
    return entry, (None if entry == doc_date else period_label(doc_date))
