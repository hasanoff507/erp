"""BO-10 state-report upload, list and detail/history (20 #3, #5–#6; 11 §9)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.attachments.application.service import AttachmentService
from app.modules.reports.domain.state_reports import parse_report_period, state_report_deadline


@dataclass(frozen=True, slots=True)
class StateReportRow:
    id: UUID
    tax_type: str
    period: date
    status: str
    published_at: datetime | None
    deadline_at: datetime | None
    file_attachment_id: UUID | None
    state_amount: Any
    our_amount: Any
    diff_amount: Any
    compared_at: datetime | None
    correction_sent_at: datetime | None
    correction_comment: str | None
    correction_portal_ref: str | None
    confirmed_at: datetime | None
    confirmed_by: UUID | None
    uploaded_by: UUID
    created_at: datetime


class StateReportsRepository(Protocol):
    async def insert(self, session: AsyncSession, values: Mapping[str, Any]) -> None: ...

    async def get(self, session: AsyncSession, tenant_id: UUID, report_id: UUID) -> StateReportRow | None: ...

    async def list_page(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        tax_type: str | None,
        period: date | None,
        status: str | None,
        after: UUID | None,
        limit: int,
    ) -> list[StateReportRow]: ...

    async def history(
        self, session: AsyncSession, tenant_id: UUID, report_id: UUID
    ) -> list[tuple[Any, ...]]: ...


def _invalid(field: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        params=params or None,
        details=[ErrorDetail(field=field, message_key=key)],
    )


def _timestamp(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _amount(value: Any) -> str | None:
    return None if value is None else format(value, ".2f")


def report_summary(row: StateReportRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tax_type": row.tax_type,
        "period": row.period.strftime("%Y-%m"),
        "status": row.status,
        "deadline_at": _timestamp(row.deadline_at),
        "diff_amount": _amount(row.diff_amount),
    }


class StateReportsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: StateReportsRepository,
        attachments: AttachmentService,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._attachments = attachments

    async def upload(
        self,
        actor: Principal,
        *,
        tax_type: str,
        period_label: str,
        published_at: datetime,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        ip: str | None,
    ) -> dict[str, Any]:
        period = parse_report_period(period_label)
        if period is None:
            raise _invalid("period", "validation.period_format")
        if tax_type not in {"vat", "turnover"}:
            raise _invalid("tax_type", "validation.invalid_choice")
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise _invalid("published_at", "validation.datetime_timezone")
        deadline_at = state_report_deadline(tax_type, period, published_at)
        report_id = uuid7()
        async with self._sf() as session, tenant_transaction(session, actor.tenant_id, user_id=actor.user_id):
            attachment = await self._attachments.upload_in_transaction(
                session,
                actor,
                "state_report",
                filename,
                content_type,
                content,
                ip,
            )
            await self._repo.insert(
                session,
                {
                    "id": report_id,
                    "tenant_id": actor.tenant_id,
                    "tax_type": tax_type,
                    "period": period,
                    "published_at": published_at,
                    "deadline_at": deadline_at,
                    "file_attachment_id": attachment["id"],
                    "uploaded_by": actor.user_id,
                },
            )
            await record_audit(
                session,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="state_report.uploaded",
                entity="state_reports",
                entity_id=report_id,
                ip=ip,
                device_id=actor.device_id,
                after={
                    "status": "uploaded",
                    "tax_type": tax_type,
                    "period": period_label,
                    "published_at": published_at,
                    "deadline_at": deadline_at,
                    "file_attachment_id": attachment["id"],
                },
            )
            body = {
                "id": str(report_id),
                "tax_type": tax_type,
                "period": period_label,
                "status": "uploaded",
                "deadline_at": _timestamp(deadline_at),
            }
            stage_response(body, 201)
        return body

    async def list_page(
        self,
        actor: Principal,
        *,
        tax_type: str | None,
        period_label: str | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        period = None
        if period_label is not None:
            period = parse_report_period(period_label)
            if period is None:
                raise _invalid("period", "validation.period_format")
        after = None
        if cursor:
            try:
                after = UUID(cursor)
            except ValueError:
                raise _invalid("cursor", "validation.cursor_invalid") from None
        async with self._sf() as session, tenant_transaction(session, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_page(
                session,
                actor.tenant_id,
                tax_type=tax_type,
                period=period,
                status=status,
                after=after,
                limit=limit + 1,
            )
        page = rows[:limit]
        return {
            "items": [report_summary(row) for row in page],
            "next_cursor": str(page[-1].id) if len(rows) > limit else None,
        }

    async def get(
        self, actor: Principal, report_id: UUID, *, include_file_url: bool
    ) -> dict[str, Any]:
        async with self._sf() as session, tenant_transaction(session, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get(session, actor.tenant_id, report_id)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "state_report"})
            events = await self._repo.history(session, actor.tenant_id, report_id)
        return {
            **report_summary(row),
            "published_at": _timestamp(row.published_at),
            "state_amount": _amount(row.state_amount),
            "our_amount": _amount(row.our_amount),
            "diff_amount": _amount(row.diff_amount),
            "file_url": (
                self._attachments.signed_url(actor.tenant_id, row.file_attachment_id)
                if include_file_url and row.file_attachment_id is not None
                else None
            ),
            "correction_sent_at": _timestamp(row.correction_sent_at),
            "correction_comment": row.correction_comment,
            "correction_portal_ref": row.correction_portal_ref,
            "confirmed_at": _timestamp(row.confirmed_at),
            "confirmed_by": None if row.confirmed_by is None else str(row.confirmed_by),
            "history": [
                {
                    "action": event[0],
                    "changed_by": None if event[1] is None else str(event[1]),
                    "changed_at": _timestamp(event[2]),
                    "status": (event[3] or {}).get("status"),
                }
                for event in events
            ],
        }
