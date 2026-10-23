"""SQL of the signed e-document outbox worker (``outbox_jobs`` kinds ``einvoice_send``, ``einvoice_accept``,
``poa_send``, ``ettn_accept``; caller's transaction, RLS: one tenant)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.einvoice.application.doc_outbox import KINDS, DocJob

STALE_RUNNING_S = 600  # a 'running' job untouched this long lost its worker


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


class SqlDocJobRepository:
    def __init__(self, stale_running_s: int = STALE_RUNNING_S) -> None:
        self._stale = stale_running_s

    async def claim(self, s: AsyncSession, kinds: tuple[str, ...], job_id: UUID | None) -> DocJob | None:
        stmt = text(
            "UPDATE app.outbox_jobs j SET status = 'running', attempts = j.attempts + 1, updated_at = now() "
            "WHERE j.id = (SELECT o.id FROM app.outbox_jobs o WHERE o.kind IN :kinds "
            "AND (CAST(:jid AS uuid) IS NULL OR o.id = CAST(:jid AS uuid)) "
            "AND ((o.status IN ('queued', 'retry') AND o.next_run_at <= now()) "
            "OR (o.status = 'running' AND o.updated_at < now() - make_interval(secs => :stale))) "
            "ORDER BY o.next_run_at, o.id LIMIT 1 FOR UPDATE SKIP LOCKED) "
            "RETURNING j.id, j.kind, j.payload, j.attempts"
        ).bindparams(bindparam("kinds", expanding=True))
        row = (
            await s.execute(
                stmt, {"kinds": list(kinds), "jid": str(job_id) if job_id else None, "stale": self._stale}
            )
        ).first()
        return DocJob(row[0], row[1], _json(row[2]) or {}, row[3]) if row else None

    async def lock_job(self, s: AsyncSession, job_id: UUID) -> None:
        await s.execute(
            text("SELECT id FROM app.outbox_jobs WHERE id = :id AND kind IN :kinds FOR UPDATE").bindparams(
                bindparam("kinds", expanding=True)
            ),
            {"id": job_id, "kinds": list(KINDS)},
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
                "updated_at = now() WHERE id = :id"
            ),
            {
                "st": status,
                "err": last_error,
                "id": job_id,
                "after": run_after.total_seconds() if run_after is not None else None,
            },
        )
