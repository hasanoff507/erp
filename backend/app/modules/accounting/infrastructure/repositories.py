"""Accounting SQL (12 ``ledger_entries``, ``vat_moves``, ``period_closings``). Caller's transaction (RLS)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.doc_numbers import DOC_TYPE_CODES
from app.modules.accounting.application.ports import JournalFilter, StoredEntry, StoredVat

_ENTRY_COLS = (
    "e.id, e.entry_date, e.branch_id, e.account_dt, e.account_kt, e.amount, e.doc_type, e.doc_id, "
    "e.analytics, e.reversal_of_id, e.created_at"
)
_LIVE = (
    "e.reversal_of_id IS NULL AND NOT EXISTS "
    "(SELECT 1 FROM app.ledger_entries r WHERE r.reversal_of_id = e.id)"
)
_INSERT_ENTRY = text(
    "INSERT INTO app.ledger_entries (id, tenant_id, entry_date, branch_id, account_dt, account_kt, amount, "
    "doc_type, doc_id, analytics, reversal_of_id) VALUES (:id, :tenant_id, :entry_date, :branch_id, "
    ":account_dt, :account_kt, :amount, :doc_type, :doc_id, CAST(:analytics AS jsonb), :reversal_of_id)"
)
_INSERT_VAT = text(
    "INSERT INTO app.vat_moves (id, tenant_id, period, kind, base_amount, vat_amount, doc_type, doc_id, "
    "einvoice_id, reversal_of_id) VALUES (:id, :tenant_id, :period, :kind, :base_amount, :vat_amount, "
    ":doc_type, :doc_id, :einvoice_id, :reversal_of_id)"
)


def _analytics(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _entry(row: Row[Any]) -> StoredEntry:
    m = row._mapping
    return StoredEntry(
        id=m["id"],
        entry_date=m["entry_date"],
        branch_id=m["branch_id"],
        account_dt=m["account_dt"],
        account_kt=m["account_kt"],
        amount=m["amount"],
        doc_type=m["doc_type"],
        doc_id=m["doc_id"],
        analytics=_analytics(m["analytics"]),
        reversal_of_id=m["reversal_of_id"],
        created_at=m["created_at"],
    )


# One advisory lock per tenant guards month closing (20 #15): every posting holds it SHARED from its first
# period check to COMMIT, ``POST /period-closings`` takes it EXCLUSIVE (try-lock, never queued).
PERIOD_LOCK_KEY = "hashtextextended('erp.period_close:' || current_setting('app.tenant_id'), 0)"
_LOCK_SHARED = text(f"SELECT pg_advisory_xact_lock_shared({PERIOD_LOCK_KEY})")


class SqlLedgerRepository:
    async def last_closed_period(self, s: AsyncSession) -> date | None:
        await s.execute(_LOCK_SHARED)
        value: date | None = (await s.execute(text("SELECT max(period) FROM app.period_closings"))).scalar()
        return value

    async def insert_entries(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        await s.execute(_INSERT_ENTRY, [dict(r) for r in rows])

    async def insert_vat(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        await s.execute(_INSERT_VAT, [dict(r) for r in rows])

    async def doc_entries(
        self,
        s: AsyncSession,
        doc_type: str,
        doc_id: UUID,
        *,
        analytics: Mapping[str, Any] | None = None,
        live_only: bool = False,
    ) -> list[StoredEntry]:
        where = ["e.doc_type = :doc_type", "e.doc_id = :doc_id"]
        params: dict[str, Any] = {"doc_type": doc_type, "doc_id": doc_id}
        if analytics:
            where.append("e.analytics @> CAST(:analytics AS jsonb)")
            params["analytics"] = json.dumps(dict(analytics), default=str)
        if live_only:
            where.append(_LIVE)
        sql = f"SELECT {_ENTRY_COLS} FROM app.ledger_entries e WHERE {' AND '.join(where)} "  # noqa: S608
        rows = await s.execute(text(sql + "ORDER BY e.created_at, e.id"), params)
        return [_entry(r) for r in rows]

    async def live_vat(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> list[StoredVat]:
        rows = await s.execute(
            text(
                "SELECT v.id, v.period, v.kind, v.base_amount, v.vat_amount, v.doc_type, v.doc_id, "
                "v.einvoice_id, v.reversal_of_id FROM app.vat_moves v "
                "WHERE v.doc_type = :doc_type AND v.doc_id = :doc_id AND v.reversal_of_id IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM app.vat_moves r WHERE r.reversal_of_id = v.id) "
                "ORDER BY v.created_at, v.id"
            ),
            {"doc_type": doc_type, "doc_id": doc_id},
        )
        return [StoredVat(**dict(r._mapping)) for r in rows]

    async def journal(
        self, s: AsyncSession, flt: JournalFilter, after: tuple[date, UUID] | None, limit: int
    ) -> list[StoredEntry]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if flt.entry_date_gte is not None:
            where.append("e.entry_date >= :gte")
            params["gte"] = flt.entry_date_gte
        if flt.entry_date_lte is not None:
            where.append("e.entry_date <= :lte")
            params["lte"] = flt.entry_date_lte
        if flt.account_dt:
            where.append("e.account_dt = :account_dt")
            params["account_dt"] = flt.account_dt
        if flt.account_kt:
            where.append("e.account_kt = :account_kt")
            params["account_kt"] = flt.account_kt
        if flt.doc_type:
            where.append("e.doc_type = :doc_type")
            params["doc_type"] = flt.doc_type
        if flt.doc_id:
            where.append("e.doc_id = :doc_id")
            params["doc_id"] = flt.doc_id
        if flt.branch_ids is not None:
            where.append("e.branch_id = ANY(CAST(:branches AS uuid[]))")
            params["branches"] = [str(b) for b in flt.branch_ids]
        if after is not None:
            where.append("(e.entry_date, e.id) < (:after_date, :after_id)")
            params["after_date"], params["after_id"] = after
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        sql = f"SELECT {_ENTRY_COLS} FROM app.ledger_entries e {clause}"  # noqa: S608
        rows = await s.execute(text(sql + "ORDER BY e.entry_date DESC, e.id DESC LIMIT :limit"), params)
        return [_entry(r) for r in rows]

    async def doc_numbers(self, s: AsyncSession, refs: Mapping[str, Sequence[UUID]]) -> dict[UUID, str]:
        """``number`` of the referenced documents — only 12 §2.9 document tables (allow-list)."""
        out: dict[UUID, str] = {}
        for doc_type, ids in refs.items():
            if doc_type not in DOC_TYPE_CODES or not ids:
                continue
            rows = await s.execute(
                text(f"SELECT id, number FROM app.{doc_type} WHERE id = ANY(CAST(:ids AS uuid[]))"),  # noqa: S608
                {"ids": [str(i) for i in set(ids)]},
            )
            out.update({r[0]: r[1] for r in rows if r[1] is not None})
        return out
