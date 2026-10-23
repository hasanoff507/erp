"""``import_jobs`` / ``attachments`` SQL (12 §2.9, 0018/0022). Runs in the caller's ``tenant_transaction``."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.imports.application.ports import ImportJob


class SqlImportJobRepository:
    async def insert_attachment(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.attachments (id, tenant_id, s3_key, content_type, original_name, sha256, "
                "kind, size_bytes, uploaded_by) VALUES (:id, :tenant_id, :s3_key, :content_type, "
                ":original_name, :sha256, :kind, :size_bytes, :uploaded_by)"
            ),
            dict(row),
        )

    async def insert_job(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.import_jobs (id, tenant_id, kind, attachment_id, created_by) "
                "VALUES (:id, :tenant_id, :kind, :attachment_id, :created_by)"
            ),
            dict(row),
        )

    async def get_job(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> ImportJob | None:
        sql = (
            "SELECT j.id, j.kind, j.attachment_id, j.status, j.total_rows, j.ok_rows, j.errors, "
            "j.result, j.created_by, j.created_at, a.s3_key, a.content_type FROM app.import_jobs j "
            "JOIN app.attachments a ON a.id = j.attachment_id WHERE j.id = :id"
        )
        row = (await s.execute(text(sql + (" FOR UPDATE OF j" if lock else "")), {"id": job_id})).first()
        if row is None:
            return None
        m = row._mapping
        return ImportJob(
            id=m["id"],
            kind=m["kind"],
            attachment_id=m["attachment_id"],
            status=m["status"],
            total_rows=m["total_rows"],
            ok_rows=m["ok_rows"],
            errors=list(m["errors"] or []),
            result=dict(m["result"] or {}),
            created_by=m["created_by"],
            created_at=m["created_at"],
            s3_key=m["s3_key"],
            content_type=m["content_type"],
        )

    async def set_status(self, s: AsyncSession, job_id: UUID, status: str) -> None:
        await s.execute(
            text("UPDATE app.import_jobs SET status = :st WHERE id = :id"), {"id": job_id, "st": status}
        )

    async def save_validation(
        self,
        s: AsyncSession,
        job_id: UUID,
        *,
        status: str,
        total_rows: int,
        ok_rows: int,
        errors: Sequence[Mapping[str, Any]],
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.import_jobs SET status = :st, total_rows = :total, ok_rows = :ok, "
                "errors = CAST(:errors AS jsonb) WHERE id = :id"
            ),
            {
                "id": job_id,
                "st": status,
                "total": total_rows,
                "ok": ok_rows,
                "errors": json.dumps(list(errors)),
            },
        )

    async def save_commit(
        self,
        s: AsyncSession,
        job_id: UUID,
        *,
        status: str,
        ok_rows: int,
        errors: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any],
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.import_jobs SET status = :st, ok_rows = :ok, errors = CAST(:errors AS jsonb), "
                "result = CAST(:result AS jsonb) WHERE id = :id"
            ),
            {
                "id": job_id,
                "st": status,
                "ok": ok_rows,
                "errors": json.dumps(list(errors)),
                "result": json.dumps(dict(result)),
            },
        )
