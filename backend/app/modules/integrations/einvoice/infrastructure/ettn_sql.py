"""SQL of the ``ettn_send`` outbox worker (caller's transaction, RLS: one tenant)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.einvoice.application.ettn_outbox import ClaimedJob, EttnRow

STALE_RUNNING_S = 600  # a 'running' job untouched this long lost its worker


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


class SqlEttnOutboxRepository:
    def __init__(self, stale_running_s: int = STALE_RUNNING_S) -> None:
        self._stale = stale_running_s

    async def claim(self, s: AsyncSession, job_id: UUID | None) -> ClaimedJob | None:
        row = (
            await s.execute(
                text(
                    "UPDATE app.outbox_jobs j SET status = 'running', attempts = j.attempts + 1, "
                    "updated_at = now() "
                    "WHERE j.id = (SELECT o.id FROM app.outbox_jobs o WHERE o.kind = 'ettn_send' "
                    "AND (CAST(:jid AS uuid) IS NULL OR o.id = CAST(:jid AS uuid)) "
                    "AND ((o.status IN ('queued', 'retry') AND o.next_run_at <= now()) "
                    "OR (o.status = 'running' AND o.updated_at < now() - make_interval(secs => :stale))) "
                    "ORDER BY o.next_run_at, o.id LIMIT 1 FOR UPDATE SKIP LOCKED) "
                    "RETURNING j.id, j.payload, j.attempts"
                ),
                {"jid": str(job_id) if job_id else None, "stale": self._stale},
            )
        ).first()
        return ClaimedJob(row[0], _json(row[1]) or {}, row[2]) if row else None

    async def ettn(self, s: AsyncSession, ettn_id: UUID) -> EttnRow | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, transfer_id, status, payload FROM app.ettn_documents "
                    "WHERE id = :id AND direction = 'out' FOR UPDATE"
                ),
                {"id": ettn_id},
            )
        ).first()
        return EttnRow(row[0], row[1], row[2], _json(row[3]) or {}) if row else None

    async def lock_transfer(self, s: AsyncSession, transfer_id: UUID) -> None:
        await s.execute(text("SELECT id FROM app.transfers WHERE id = :id FOR UPDATE"), {"id": transfer_id})

    async def lock_job(self, s: AsyncSession, job_id: UUID) -> None:
        await s.execute(
            text("SELECT id FROM app.outbox_jobs WHERE id = :id AND kind = 'ettn_send' FOR UPDATE"),
            {"id": job_id},
        )

    async def set_ettn(
        self,
        s: AsyncSession,
        ettn_id: UUID,
        status: str,
        *,
        operator_doc_id: str | None,
        last_error: str | None,
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.ettn_documents SET status = :st, operator_doc_id = COALESCE(:op, "
                "operator_doc_id), "
                "last_error = :err, updated_at = now() WHERE id = :id"
            ),
            {"st": status, "op": operator_doc_id, "err": last_error, "id": ettn_id},
        )

    async def set_transfer_ref(self, s: AsyncSession, transfer_id: UUID, ref: str) -> None:
        await s.execute(
            text("UPDATE app.transfers SET ettn_ref = :r, updated_at = now() WHERE id = :id"),
            {"r": ref, "id": transfer_id},
        )

    async def finish(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        run_after: timedelta | None = None,
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.outbox_jobs SET status = :st, last_error = :err, "
                "next_run_at = CASE WHEN CAST(:after AS double precision) IS NULL THEN next_run_at "
                "ELSE now() + make_interval(secs => CAST(:after AS double precision)) END, "
                "updated_at = now() WHERE id = :id AND kind = "
                "'ettn_send'"
            ),
            {
                "st": status,
                "err": last_error,
                "id": job_id,
                "after": run_after.total_seconds() if run_after is not None else None,
            },
        )
