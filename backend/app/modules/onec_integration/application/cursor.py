"""Opaque cursor ``(at, id)`` of the W-08 log feed (17 §8 cursor pagination)."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail


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
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="cursor", message_key="validation.cursor_invalid")],
        ) from exc
