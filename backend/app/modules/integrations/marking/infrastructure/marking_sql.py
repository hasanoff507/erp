"""SQL of the marking integration (caller's transaction, RLS: one tenant).

Reads ``tenants``, ``products``, ``platform.marking_product_groups``, ``goods_receipts``, ``fiscal_receipts``;
writes ``marking_codes`` (status moves of supplier returns / write-offs, ``verified_at``) and the four
``outbox_jobs`` marking kinds.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.integrations.marking.application.ports import NoticeJob
from app.modules.integrations.marking.application.repository import (
    CodeRow,
    JobRow,
    ProductRef,
    ReceiptCode,
)
from app.modules.integrations.marking.domain.rules import JOB_KINDS


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


def _job(row: Any) -> JobRow:
    return JobRow(row[0], row[1], row[2], row[3], _json(row[4]) or {})


_KINDS = list(JOB_KINDS)
_CODES = (
    "SELECT code, product_id, status, last_doc_id FROM app.marking_codes WHERE code = ANY(:c) ORDER BY id"
)
_CODES_LOCK = _CODES + " FOR UPDATE"
_JOB_BY_KEY = (
    "SELECT id, kind, status, attempts, payload FROM app.outbox_jobs "
    "WHERE idempotency_key = :k AND kind = ANY(:kinds)"
)
_JOB_BY_KEY_LOCK = _JOB_BY_KEY + " FOR UPDATE"


class SqlMarkingRepository:
    async def precheck_mode(self, s: AsyncSession) -> str | None:
        found = (
            await s.execute(text("SELECT settings ->> 'marking_precheck' FROM app.tenants LIMIT 1"))
        ).scalar_one_or_none()
        return None if found is None else str(found)

    async def code_taken(self, s: AsyncSession, code: str) -> bool:
        found = await s.execute(
            text(
                "SELECT 1 FROM app.marking_codes WHERE code = :c "
                "AND status IN ('sold', 'pending_verification')"
            ),
            {"c": code},
        )
        return found.first() is not None

    async def product(self, s: AsyncSession, product_id: UUID) -> ProductRef | None:
        row = (
            await s.execute(
                text("SELECT id, is_marked, name FROM app.products WHERE id = :id"), {"id": product_id}
            )
        ).first()
        return ProductRef(row[0], bool(row[1]), row[2]) if row else None

    async def receipt_codes(self, s: AsyncSession, receipt_id: UUID) -> list[ReceiptCode]:
        rows = await s.execute(
            text(
                "SELECT mc.code, mc.product_id, mg.acceptance_deadline FROM app.marking_codes mc "
                "JOIN app.products p ON p.id = mc.product_id "
                "LEFT JOIN platform.marking_product_groups mg ON mg.code = p.marking_group_code "
                "WHERE mc.last_doc_id = :id AND mc.status = 'in_stock' ORDER BY mc.id"
            ),
            {"id": receipt_id},
        )
        return [ReceiptCode(r[0], r[1], r[2]) for r in rows]

    async def codes(self, s: AsyncSession, codes: Sequence[str], *, lock: bool = False) -> dict[str, CodeRow]:
        if not codes:
            return {}
        rows = await s.execute(text(_CODES_LOCK if lock else _CODES), {"c": list(codes)})
        return {r[0]: CodeRow(r[0], r[1], r[2], r[3]) for r in rows}

    async def doc_codes(self, s: AsyncSession, doc_id: UUID, status: str) -> list[str]:
        rows = await s.execute(
            text("SELECT code FROM app.marking_codes WHERE last_doc_id = :d AND status = :st ORDER BY id"),
            {"d": doc_id, "st": status},
        )
        return [r[0] for r in rows]

    async def sale_acked(self, s: AsyncSession, sale_id: UUID) -> bool:
        found = await s.execute(
            text(
                "SELECT 1 FROM app.fiscal_receipts WHERE sale_id = :id AND kind = 'sale' "
                "AND ofd_acked_at IS NOT NULL"
            ),
            {"id": sale_id},
        )
        return found.first() is not None

    async def receipt_info(self, s: AsyncSession, receipt_id: UUID) -> Mapping[str, Any] | None:
        row = (
            await s.execute(
                text(
                    "SELECT gr.number, gr.branch_id, c.name FROM app.goods_receipts gr "
                    "LEFT JOIN app.counterparties c ON c.id = gr.supplier_id WHERE gr.id = :id"
                ),
                {"id": receipt_id},
            )
        ).first()
        return {"number": row[0], "branch_id": row[1], "supplier_name": row[2]} if row else None

    # --- outbox ------------------------------------------------------------------------------------
    async def insert_job(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], key: str
    ) -> UUID:
        new_id = uuid7()
        got = (
            await s.execute(
                text(
                    "INSERT INTO app.outbox_jobs (id, tenant_id, kind, payload, idempotency_key) "
                    "VALUES (:id, :t, :k, CAST(:p AS jsonb), :key) "
                    "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING id"
                ),
                {
                    "id": new_id,
                    "t": tenant_id,
                    "k": kind,
                    "p": json.dumps(dict(payload), default=str),
                    "key": key,
                },
            )
        ).first()
        if got is not None:
            return UUID(str(got[0]))
        existing = await self.job_by_key(s, key)
        assert existing is not None
        return existing.id

    async def job_by_key(self, s: AsyncSession, key: str, *, lock: bool = False) -> JobRow | None:
        query = _JOB_BY_KEY_LOCK if lock else _JOB_BY_KEY
        row = (await s.execute(text(query), {"k": key, "kinds": _KINDS})).first()
        return _job(row) if row else None

    async def open_jobs(self, s: AsyncSession, kind: str) -> list[JobRow]:
        rows = await s.execute(
            text(
                "SELECT id, kind, status, attempts, payload FROM app.outbox_jobs "
                "WHERE kind = :k AND status <> 'done' ORDER BY id"
            ),
            {"k": kind},
        )
        return [_job(r) for r in rows]

    async def claim(self, s: AsyncSession, job_id: UUID | None, stale_s: int) -> NoticeJob | None:
        row = (
            await s.execute(
                text(
                    "UPDATE app.outbox_jobs j SET status = 'running', attempts = j.attempts + 1, "
                    "updated_at = now() "
                    "WHERE j.id = (SELECT o.id FROM app.outbox_jobs o WHERE o.kind = ANY(:kinds) "
                    "AND (CAST(:jid AS uuid) IS NULL OR o.id = CAST(:jid AS uuid)) "
                    "AND ((o.status IN ('queued', 'retry') AND o.next_run_at <= now()) "
                    "OR (o.status = 'running' AND o.updated_at < now() - make_interval(secs => :stale))) "
                    "ORDER BY o.next_run_at, o.id LIMIT 1 FOR UPDATE SKIP LOCKED) "
                    "RETURNING j.id, j.kind, j.attempts, j.payload"
                ),
                {"jid": str(job_id) if job_id else None, "stale": stale_s, "kinds": _KINDS},
            )
        ).first()
        return NoticeJob(row[0], row[1], row[2], _json(row[3]) or {}) if row else None

    async def lock_job(self, s: AsyncSession, job_id: UUID) -> JobRow | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, kind, status, attempts, payload FROM app.outbox_jobs "
                    "WHERE id = :id AND kind = ANY(:kinds) FOR UPDATE"
                ),
                {"id": job_id, "kinds": _KINDS},
            )
        ).first()
        return _job(row) if row else None

    async def finish(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        *,
        run_after: timedelta | None = None,
        patch: Mapping[str, Any] | None = None,
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.outbox_jobs SET status = :st, last_error = :err, "
                "payload = payload || CAST(:patch AS jsonb), "
                "next_run_at = CASE WHEN CAST(:after AS double precision) IS NULL THEN next_run_at "
                "ELSE now() + make_interval(secs => CAST(:after AS double precision)) END, "
                "updated_at = now() WHERE id = :id AND kind = ANY(:kinds)"
            ),
            {
                "st": status,
                "err": last_error,
                "id": job_id,
                "kinds": _KINDS,
                "patch": json.dumps(dict(patch or {}), default=str),
                "after": run_after.total_seconds() if run_after is not None else None,
            },
        )

    # --- marking_codes -----------------------------------------------------------------------------
    async def move_codes(self, s: AsyncSession, codes: Sequence[str], status: str, doc_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.marking_codes SET status = :st, last_doc_id = :d, updated_at = now() "
                "WHERE code = ANY(:c)"
            ),
            {"st": status, "d": doc_id, "c": list(codes)},
        )

    async def restore_codes(self, s: AsyncSession, doc_id: UUID, from_status: str) -> int:
        result = await s.execute(
            text(
                "UPDATE app.marking_codes SET status = 'in_stock', updated_at = now() "
                "WHERE last_doc_id = :d AND status = :st RETURNING code"
            ),
            {"d": doc_id, "st": from_status},
        )
        return len(result.all())

    async def mark_verified(self, s: AsyncSession, codes: Sequence[str], at: Any) -> None:
        await s.execute(
            text("UPDATE app.marking_codes SET verified_at = :at, updated_at = now() WHERE code = ANY(:c)"),
            {"at": at, "c": list(codes)},
        )
