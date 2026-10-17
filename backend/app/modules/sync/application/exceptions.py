"""Sync exceptions for review — BO-14 «Sinxron istisnolari» (20 #40f/#40g, 16 §5, qaror #56).

``GET /sync-exceptions`` — cursor list (``created_at, id`` descending, newest first); ``branch_id`` is
derived (``devices.cash_register_id → cash_registers.branch_id``) and a branch-restricted user sees only
rows of their branches. ``POST /sync-exceptions/{id}/review`` — ``reviewed_at/by/review_note`` once
(``409 DOC_INVALID_STATE`` afterwards), audited; postings are never touched.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.sync.application.ports import ExceptionFilter, ExceptionRow, ExceptionStore

_MIN = datetime(2000, 1, 1, tzinfo=UTC)
_MAX = datetime(2100, 1, 1, tzinfo=UTC)


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _encode(at: datetime, row_id: UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, UUID]:
    try:
        at_raw, oid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        at = datetime.fromisoformat(at_raw)
        if at.tzinfo is None or not _MIN <= at.astimezone(UTC) < _MAX:
            raise ValueError("out of range")
        return at, UUID(oid)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def exception_json(row: ExceptionRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "device_id": str(row.device_id) if row.device_id else None,
        "branch_id": str(row.branch_id) if row.branch_id else None,
        "client_event_id": str(row.client_event_id) if row.client_event_id else None,
        "doc_type": row.doc_type,
        "doc_id": str(row.doc_id) if row.doc_id else None,
        "details": dict(row.details),
        "created_at": _ts(row.created_at),
        "reviewed_at": _ts(row.reviewed_at),
        "reviewed_by": str(row.reviewed_by) if row.reviewed_by else None,
        "review_note": row.review_note,
    }


class SyncExceptionService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], store: ExceptionStore) -> None:
        self._sf = session_factory
        self._store = store

    async def page(
        self, actor: Principal, scope: BranchScope, flt: ExceptionFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        if flt.branch_id is not None and not scope.unrestricted and flt.branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        after = _decode(cursor) if cursor else None
        branches = None if scope.unrestricted else list(scope.allowed)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._store.page(s, flt, branch_ids=branches, after=after, limit=limit + 1)
        page = rows[:limit]
        return {
            "items": [exception_json(r) for r in page],
            "next_cursor": _encode(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
        }

    async def review(
        self, actor: Principal, scope: BranchScope, exception_id: UUID, note: str, ip: str | None
    ) -> dict[str, Any]:
        note = note.strip()
        if not note:
            raise _invalid("review_note", "validation.required")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._store.get(s, exception_id, lock=True)
            visible = row is not None and (
                scope.unrestricted or (row.branch_id is not None and row.branch_id in scope.allowed)
            )
            if row is None or not visible:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "sync_exception"})
            if row.reviewed_at is not None:
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "open", "actual_status": "reviewed"},
                )
            at = await self._store.mark_reviewed(s, exception_id, actor.user_id, note)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="sync_exception.reviewed",
                entity="sync_exceptions",
                entity_id=exception_id,
                ip=ip,
                before={"reviewed_at": None},
                after={"kind": row.kind, "review_note": note},
            )
            body = {
                "id": str(exception_id),
                "reviewed_at": _ts(at),
                "reviewed_by": str(actor.user_id),
                "review_note": note,
            }
            stage_response(body, 200)
        return body
