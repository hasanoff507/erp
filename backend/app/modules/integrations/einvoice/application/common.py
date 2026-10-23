"""Shared helpers of the e-documents services: JSON shapes, cursors, errors, job enqueue after commit."""

from __future__ import annotations

import base64
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final, Protocol
from uuid import UUID

import structlog

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money_str

log = structlog.get_logger(__name__)

# outbox kinds (21 §0) and their SAQ job
EINVOICE_SEND: Final = "einvoice_send"
EINVOICE_ACCEPT: Final = "einvoice_accept"
POA_SEND: Final = "poa_send"
ETTN_SEND: Final = "ettn_send"
ETTN_ACCEPT: Final = "ettn_accept"
DOC_JOB: Final = "einvoice_doc_send"  # SAQ job for einvoice_send / einvoice_accept / poa_send / ettn_accept
ETTN_JOB: Final = "einvoice_ettn_send"


class JobEnqueuer(Protocol):
    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> None: ...


@dataclass(frozen=True, slots=True)
class Enqueue:
    job: str
    job_id: UUID


async def enqueue_after_commit(queue: JobEnqueuer | None, tenant_id: UUID, items: Sequence[Enqueue]) -> None:
    """Best effort — the cron sweeper picks up queued outbox jobs whose enqueue was lost."""
    if queue is None:
        return
    for item in items:
        try:
            await queue.enqueue(item.job, tenant_id, job_id=str(item.job_id), key=f"edoc:{item.job_id}")
        except Exception:
            log.warning("edoc_enqueue_failed", job_id=str(item.job_id), exc_info=True)


def ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def m2(value: Decimal | None) -> str | None:
    return None if value is None else money_str(value)


def opt(value: Any) -> str | None:
    return None if value is None else str(value)


def not_found(resource: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": resource})


def invalid_state(actual: str, expected: str, **extra: Any) -> AppError:
    return AppError(
        ErrorCode.DOC_INVALID_STATE, params={"expected_status": expected, "actual_status": actual, **extra}
    )


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def encode_cursor(doc_id: UUID) -> str:
    return base64.urlsafe_b64encode(doc_id.bytes).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    """Keyset on the UUIDv7 id (monotonic; no ``created_at`` ordering — test-clock hygiene)."""
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        return datetime.min.replace(tzinfo=UTC), UUID(bytes=raw)
    except (ValueError, TypeError) as exc:
        raise invalid("cursor", "validation.cursor_invalid") from exc


def page_out(items: list[Any], limit: int, render: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    page = items[:limit]
    next_cursor = encode_cursor(page[-1].id) if len(items) > limit else None
    return {"items": [render(x) for x in page], "next_cursor": next_cursor}
