"""Tenant-scoped SQL for state-report history and attachments (0020)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.application.state_reports import StateReportRow

_GET_SQL = text(
    "SELECT id, tax_type, period, status, published_at, deadline_at, file_attachment_id, state_amount, "
    "our_amount, diff_amount, compared_at, correction_sent_at, correction_comment, correction_portal_ref, "
    "confirmed_at, confirmed_by, uploaded_by, created_at FROM app.state_reports "
    "WHERE tenant_id = :tenant_id AND id = :id"
)
_LIST_SQL = text(
    "SELECT id, tax_type, period, status, published_at, deadline_at, file_attachment_id, state_amount, "
    "our_amount, diff_amount, compared_at, correction_sent_at, correction_comment, correction_portal_ref, "
    "confirmed_at, confirmed_by, uploaded_by, created_at FROM app.state_reports "
    "WHERE tenant_id = :tenant_id AND (:tax_type IS NULL OR tax_type = :tax_type) "
    "AND (:period IS NULL OR period = :period) AND (:status IS NULL OR status = :status) "
    "AND (CAST(:after AS uuid) IS NULL OR id < :after) ORDER BY id DESC LIMIT :limit"
)


class SqlStateReportsRepository:
    async def insert(self, session: AsyncSession, values: Mapping[str, Any]) -> None:
        await session.execute(
            text(
                "INSERT INTO app.state_reports "
                "(id, tenant_id, tax_type, period, published_at, deadline_at, file_attachment_id, "
                "status, uploaded_by) "
                "VALUES (:id, :tenant_id, :tax_type, :period, :published_at, :deadline_at, "
                ":file_attachment_id, 'uploaded', :uploaded_by)"
            ),
            dict(values),
        )

    async def get(self, session: AsyncSession, tenant_id: UUID, report_id: UUID) -> StateReportRow | None:
        row = (
            await session.execute(
                _GET_SQL,
                {"tenant_id": tenant_id, "id": report_id},
            )
        ).first()
        return None if row is None else StateReportRow(*row)

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
    ) -> list[StateReportRow]:
        rows = await session.execute(
            _LIST_SQL,
            {
                "tenant_id": tenant_id,
                "tax_type": tax_type,
                "period": period,
                "status": status,
                "after": after,
                "limit": limit,
            },
        )
        return [StateReportRow(*row) for row in rows]

    async def history(self, session: AsyncSession, tenant_id: UUID, report_id: UUID) -> list[tuple[Any, ...]]:
        rows = await session.execute(
            text(
                "SELECT action, user_id, at, after FROM app.audit_log "
                "WHERE tenant_id = :tenant_id AND entity = 'state_reports' AND entity_id = :id "
                "ORDER BY at, id"
            ),
            {"tenant_id": tenant_id, "id": report_id},
        )
        return list(rows)
