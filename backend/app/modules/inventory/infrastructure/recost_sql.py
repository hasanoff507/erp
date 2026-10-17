"""``recost_jobs`` SQL (12 ``recost_jobs``; one queued job per (tenant, warehouse, product))."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.inventory.application.ports import Key, RecostJob

_COLS = (
    "id, warehouse_id, product_id, from_date, status, reason_doc_type, reason_doc_id, attempts, last_error, "
    "created_at, finished_at"
)


def _job(row: Row[Any]) -> RecostJob:
    return RecostJob(**dict(row._mapping))


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class SqlRecostRepository:
    async def upsert_queued(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        key: Key,
        from_date: date,
        reason_doc_type: str,
        reason_doc_id: UUID,
    ) -> UUID:
        """The queued job of ``key`` with ``from_date`` widened to the earliest (unique partial index)."""
        job_id: UUID = (
            await s.execute(
                text(
                    "INSERT INTO app.recost_jobs (id, tenant_id, warehouse_id, product_id, from_date, "
                    "status, "
                    "reason_doc_type, reason_doc_id) VALUES (:id, :t, :w, :p, :f, 'queued', :rt, :rd) "
                    "ON CONFLICT (tenant_id, warehouse_id, product_id) WHERE status = 'queued' DO UPDATE "
                    "SET from_date = LEAST(app.recost_jobs.from_date, EXCLUDED.from_date) RETURNING id"
                ),
                {
                    "id": uuid7(),
                    "t": tenant_id,
                    "w": key[0],
                    "p": key[1],
                    "f": from_date,
                    "rt": reason_doc_type,
                    "rd": reason_doc_id,
                },
            )
        ).scalar_one()
        return job_id

    async def get(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> RecostJob | None:
        sql = f"SELECT {_COLS} FROM app.recost_jobs WHERE id = :id" + (" FOR UPDATE" if lock else "")  # noqa: S608
        row = (await s.execute(text(sql), {"id": job_id})).first()
        return _job(row) if row else None

    async def queued_for(self, s: AsyncSession, key: Key) -> RecostJob | None:
        row = (
            await s.execute(
                text(
                    f"SELECT {_COLS} FROM app.recost_jobs WHERE warehouse_id = :w AND "  # noqa: S608
                    "product_id = :p "
                    "AND status = 'queued' FOR UPDATE"
                ),
                {"w": key[0], "p": key[1]},
            )
        ).first()
        return _job(row) if row else None

    async def claim(self, s: AsyncSession, job_id: UUID) -> RecostJob | None:
        row = (
            await s.execute(
                text(
                    "UPDATE app.recost_jobs SET status = 'running', attempts = attempts + 1, "  # noqa: S608
                    "last_error = NULL WHERE id = (SELECT id FROM app.recost_jobs WHERE id = :id "
                    f"AND status = 'queued' FOR UPDATE SKIP LOCKED) RETURNING {_COLS}"
                ),
                {"id": job_id},
            )
        ).first()
        return _job(row) if row else None

    async def fail(self, s: AsyncSession, job_id: UUID, error: str) -> None:
        """A run's transaction rolled back on an error: ``queued`` → ``failed``, ``attempts + 1``
        (no-op when another worker has meanwhile finished it)."""
        await s.execute(
            text(
                "UPDATE app.recost_jobs SET status = 'failed', attempts = attempts + 1, last_error = :e, "
                "finished_at = now() WHERE id = :id AND status = 'queued'"
            ),
            {"e": error, "id": job_id},
        )

    async def finish(self, s: AsyncSession, job_id: UUID, status: str, error: str | None) -> None:
        await s.execute(
            text(
                "UPDATE app.recost_jobs SET status = :s, last_error = :e, finished_at = now() WHERE id = :id"
            ),
            {"s": status, "e": error, "id": job_id},
        )

    async def requeue(self, s: AsyncSession, job_id: UUID, from_date: date) -> None:
        await s.execute(
            text(
                "UPDATE app.recost_jobs SET status = 'queued', from_date = :f, finished_at = NULL WHERE id = "
                ":id"
            ),
            {"f": from_date, "id": job_id},
        )

    async def queued_ids(self, s: AsyncSession, limit: int) -> list[UUID]:
        rows = await s.execute(
            text("SELECT id FROM app.recost_jobs WHERE status = 'queued' ORDER BY created_at, id LIMIT :n"),
            {"n": limit},
        )
        return [r[0] for r in rows]

    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_ids: Sequence[UUID] | None,
        product_id: UUID | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[RecostJob]:
        where: list[str] = []
        params: dict[str, Any] = {"n": limit}
        if status:
            where.append("status = :status")
            params["status"] = status
        if warehouse_ids is not None:
            where.append("warehouse_id = ANY(CAST(:whs AS uuid[]))")
            params["whs"] = [str(w) for w in warehouse_ids]
        if product_id is not None:
            where.append("product_id = :pid")
            params["pid"] = product_id
        if after is not None:
            where.append("(created_at, id) < (:at, :aid)")
            params["at"], params["aid"] = after
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        rows = await s.execute(
            text(f"SELECT {_COLS} FROM app.recost_jobs {clause}ORDER BY created_at DESC, id DESC LIMIT :n"),  # noqa: S608
            params,
        )
        return [_job(r) for r in rows]

    async def corrections(
        self, s: AsyncSession, job_id: UUID
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Ledger rows tagged ``analytics.recost_job_id`` + the settlement stock moves of the job's key
        written while the job was open (storno of a pending move and its replacement allocations)."""
        job = await self.get(s, job_id)
        if job is None:
            return [], []
        ledger = await s.execute(
            text(
                "SELECT id, entry_date, account_dt, account_kt, amount, branch_id, doc_type, doc_id, "
                "analytics, "
                "reversal_of_id FROM app.ledger_entries WHERE analytics @> CAST(:a AS jsonb) ORDER BY "
                "created_at, id"
            ),
            {"a": json.dumps({"recost_job_id": str(job_id)})},
        )
        ledger_items = [
            {
                "id": str(r[0]), "entry_date": r[1].isoformat(), "account_dt": r[2], "account_kt": r[3],
                "amount": format(r[4], "f"), "branch_id": str(r[5]) if r[5] else None, "doc_type": r[6],
                "doc_id": str(r[7]), "analytics": r[8], "reversal_of_id": str(r[9]) if r[9] else None,
            }
            for r in ledger
        ]  # fmt: skip
        moves = await s.execute(
            text(
                "SELECT m.id, m.lot_id, m.qty, m.cost_amount, m.doc_type, m.doc_id, m.line_id, m.moved_at, "
                "m.reversal_of_id FROM app.stock_moves m WHERE m.warehouse_id = :w AND m.product_id = :p "
                "AND m.created_at >= :c0 AND (CAST(:c1 AS timestamptz) IS NULL OR m.created_at <= :c1) "
                "AND EXISTS (SELECT 1 FROM app.stock_moves r JOIN app.stock_moves o ON o.id = "
                "r.reversal_of_id "
                "WHERE o.lot_id IS NULL AND o.qty < 0 AND r.doc_type = m.doc_type AND r.doc_id = m.doc_id "
                "AND r.line_id IS NOT DISTINCT FROM m.line_id AND r.created_at = m.created_at "
                "AND r.warehouse_id = m.warehouse_id AND r.product_id = m.product_id) "
                "ORDER BY m.moved_at, m.created_at, m.id"
            ),
            {"w": job.warehouse_id, "p": job.product_id, "c0": job.created_at, "c1": job.finished_at},
        )
        move_items = [
            {
                "id": str(r[0]), "lot_id": str(r[1]) if r[1] else None, "qty": format(r[2], "f"),
                "cost_amount": format(r[3], "f"), "doc_type": r[4], "doc_id": str(r[5]),
                "line_id": str(r[6]) if r[6] else None, "moved_at": _ts(r[7]),
                "reversal_of_id": str(r[8]) if r[8] else None,
            }
            for r in moves
        ]  # fmt: skip
        return ledger_items, move_items
