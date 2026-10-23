"""``ledger_adjustments`` SQL (12 §2.6). Caller's tenant transaction (RLS)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.application.ports import AdjustmentFilter, AdjustmentRow

_COLS = (
    "id, number, branch_id, doc_date, status, account_dt, account_kt, amount, analytics, "
    "correction_of_period, comment, created_by, created_at, posted_at, cancelled_at, cancelled_by, "
    "cancel_reason"
)


def _row(r: Row[Any]) -> AdjustmentRow:
    m = dict(r._mapping)
    raw = m["analytics"]
    m["analytics"] = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    return AdjustmentRow(**m)


class SqlAdjustmentRepository:
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.ledger_adjustments (id, tenant_id, branch_id, number, doc_date, status, "
                "account_dt, account_kt, amount, analytics, correction_of_period, created_by, comment, "
                "posted_at) VALUES (:id, :tenant_id, :branch_id, :number, :doc_date, 'posted', :account_dt, "
                ":account_kt, :amount, CAST(:analytics AS jsonb), :correction_of_period, :created_by, "
                ":comment, now())"
            ),
            dict(row),
        )

    async def get(self, s: AsyncSession, adjustment_id: UUID, *, lock: bool = False) -> AdjustmentRow | None:
        suffix = " FOR UPDATE" if lock else ""
        found = (
            await s.execute(
                text(f"SELECT {_COLS} FROM app.ledger_adjustments WHERE id = :id{suffix}"),  # noqa: S608
                {"id": adjustment_id},
            )
        ).first()
        return None if found is None else _row(found)

    async def mark_cancelled(self, s: AsyncSession, adjustment_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.ledger_adjustments SET status = 'cancelled', cancelled_at = now(), "
                "cancelled_by = :u, cancel_reason = :r, updated_at = now() WHERE id = :id"
            ),
            {"id": adjustment_id, "u": user_id, "r": reason},
        )

    async def page(
        self, s: AsyncSession, flt: AdjustmentFilter, after: tuple[date, UUID] | None, limit: int
    ) -> list[AdjustmentRow]:
        where = ["true"]
        params: dict[str, Any] = {"limit": limit}
        if flt.doc_date_gte is not None:
            where.append("doc_date >= :gte")
            params["gte"] = flt.doc_date_gte
        if flt.doc_date_lte is not None:
            where.append("doc_date <= :lte")
            params["lte"] = flt.doc_date_lte
        if flt.status is not None:
            where.append("status = :status")
            params["status"] = flt.status
        if flt.branch_ids is not None:
            where.append("branch_id = ANY(CAST(:branches AS uuid[]))")
            params["branches"] = [str(b) for b in flt.branch_ids]
        if after is not None:
            where.append("(doc_date, id) < (:after_date, :after_id)")
            params["after_date"], params["after_id"] = after
        sql = (
            f"SELECT {_COLS} FROM app.ledger_adjustments WHERE {' AND '.join(where)} "  # noqa: S608
            "ORDER BY doc_date DESC, id DESC LIMIT :limit"
        )
        return [_row(r) for r in await s.execute(text(sql), params)]

    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool:
        found = (await s.execute(text("SELECT 1 FROM app.branches WHERE id = :b"), {"b": branch_id})).first()
        return found is not None

    async def counterparty_exists(self, s: AsyncSession, counterparty_id: UUID) -> bool:
        found = (
            await s.execute(text("SELECT 1 FROM app.counterparties WHERE id = :c"), {"c": counterparty_id})
        ).first()
        return found is not None

    async def go_live_date(self, s: AsyncSession) -> date | None:
        value: date | None = (await s.execute(text("SELECT go_live_date FROM app.tenants LIMIT 1"))).scalar()
        return value

    async def advance_6310(self, s: AsyncSession, counterparty_id: UUID) -> Decimal:
        """Customer advance = 6310 credit balance of the counterparty (``analytics.counterparty_id``)."""
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(CASE WHEN account_kt = '6310' THEN amount ELSE -amount END), 0) "
                    "FROM app.ledger_entries WHERE (account_kt = '6310' OR account_dt = '6310') "
                    "AND analytics->>'counterparty_id' = :c"
                ),
                {"c": str(counterparty_id)},
            )
        ).scalar()
        return Decimal(value or 0)
