"""``bank_settlements`` / ``bank_statement_imports`` SQL and the statement file store (20 #55a–#55h, 12 §2.6).

Runs in the caller's ``tenant_transaction`` (RLS). The 5710 transit balance is read from ``ledger_entries``
(``account_dt``/``account_kt = '5710'``) per ``branch_id`` × ``analytics->>'payment_method'``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash.application.bank_settlements_ports import CardTx, SettlementFilter, SettlementRow
from app.modules.cash.domain.bank_matching import Batch

_COLUMNS = (
    "id, branch_id, number, doc_date, status, source, method, settled_from, settled_to, gross_amount, "
    "commission_amount, variance_amount, net_amount, bank_ref, attachment_id, statement_import_id, comment, "
    "created_by, created_at, posted_at, cancelled_at, cancelled_by, cancel_reason, version"
)
_TRANSIT = "(account_dt = '5710' OR account_kt = '5710')"
_SIGNED = "CASE WHEN account_dt = '5710' THEN amount ELSE -amount END"
_TX_DAY = "((COALESCE(t.tx_at, t.requested_at) AT TIME ZONE 'Asia/Tashkent')::date)"
_OPEN_TX = (
    f"SELECT t.id, t.branch_id, t.rrn, t.approved_amount, {_TX_DAY} AS business_date "  # noqa: S608
    "FROM app.card_terminal_transactions t WHERE t.kind = 'purchase' AND t.status = 'approved' "
    "AND t.rrn IS NOT NULL AND t.approved_amount IS NOT NULL AND t.doc_id IS NOT NULL "
    "AND t.bank_settlement_id IS NULL"
)


def _row(m: Any) -> SettlementRow:
    return SettlementRow(**{k: m[k] for k in SettlementRow.__slots__})


def _tx(m: Any) -> CardTx:
    return CardTx(m["id"], m["branch_id"], m["rrn"], Decimal(m["approved_amount"]), m["business_date"])


class SqlBankSettlementRepository:
    # --- tenant / references ------------------------------------------------------------------------
    async def tenant_bank(self, s: AsyncSession) -> tuple[str | None, str | None]:
        row = (
            await s.execute(
                text(
                    "SELECT settings->>'bank_account', settings->>'payment_org_commission_account' FROM "
                    "app.tenants "
                    "WHERE id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
                )
            )
        ).first()
        return (None, None) if row is None else (row[0], row[1])

    async def branch_ids(self, s: AsyncSession) -> list[UUID]:
        rows = await s.execute(text("SELECT id FROM app.branches ORDER BY is_default DESC, id"))
        return [r[0] for r in rows]

    async def attachment_exists(self, s: AsyncSession, attachment_id: UUID) -> bool:
        found = await s.execute(
            text("SELECT 1 FROM app.attachments WHERE id = :id AND kind = 'import'"), {"id": attachment_id}
        )
        return found.first() is not None

    async def terminal_identifiers(self, s: AsyncSession) -> dict[str, UUID]:
        rows = await s.execute(
            text("SELECT tid, mid, branch_id FROM app.card_terminals WHERE status <> 'archived' ORDER BY id")
        )
        out: dict[str, UUID] = {}
        for tid, mid, branch in rows:
            for ident in (tid, mid):
                if ident:
                    out[str(ident)] = branch
        return out

    async def acquirer_inns(self, s: AsyncSession) -> list[str]:
        rows = await s.execute(
            text(
                "SELECT DISTINCT c.stir FROM app.card_terminals t JOIN app.counterparties c "
                "ON c.id = t.acquirer_counterparty_id WHERE c.stir IS NOT NULL"
            )
        )
        return [r[0] for r in rows]

    async def lock_imports(self, s: AsyncSession, tenant_id: UUID) -> None:
        await s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"bank_statement_import:{tenant_id}"},
        )

    async def lock_transit(self, s: AsyncSession, branch_id: UUID, method: str) -> None:
        await s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"bank_settlement:{branch_id}:{method}"},
        )

    # --- documents ----------------------------------------------------------------------------------
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.bank_settlements (id, tenant_id, branch_id, number, doc_date, status, "
                "source, method, "
                "settled_from, settled_to, gross_amount, commission_amount, variance_amount, bank_ref, "
                "statement_import_id, attachment_id, created_by, comment) VALUES (:id, :tenant_id, "
                ":branch_id, "
                ":number, :doc_date, 'draft', :source, :method, :settled_from, :settled_to, :gross_amount, "
                ":commission_amount, :variance_amount, :bank_ref, :statement_import_id, :attachment_id, "
                ":created_by, "
                ":comment)"
            ),
            dict(row),
        )

    async def get(self, s: AsyncSession, settlement_id: UUID, *, lock: bool = False) -> SettlementRow | None:
        sql = f"SELECT {_COLUMNS} FROM app.bank_settlements WHERE id = :id" + (" FOR UPDATE" if lock else "")  # noqa: S608
        row = (await s.execute(text(sql), {"id": settlement_id})).first()
        return None if row is None else _row(row._mapping)

    async def update_draft(self, s: AsyncSession, settlement_id: UUID, values: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "UPDATE app.bank_settlements SET settled_from = :settled_from, settled_to = :settled_to, "
                "gross_amount = :gross_amount, commission_amount = :commission_amount, "
                "variance_amount = :variance_amount, bank_ref = :bank_ref, comment = :comment, "
                "version = version + 1, updated_at = now() WHERE id = :id"
            ),
            {**values, "id": settlement_id},
        )

    async def mark_posted(self, s: AsyncSession, settlement_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.bank_settlements SET status = 'posted', posted_at = now(), version = version + "
                "1, "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": settlement_id},
        )

    async def mark_cancelled(self, s: AsyncSession, settlement_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.bank_settlements SET status = 'cancelled', cancelled_at = now(), cancelled_by "
                "= :u, "
                "cancel_reason = :r, version = version + 1, updated_at = now() WHERE id = :id"
            ),
            {"id": settlement_id, "u": user_id, "r": reason},
        )

    async def list_settlements(self, s: AsyncSession, flt: SettlementFilter) -> list[SettlementRow]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": flt.limit}
        expanding = False
        if flt.branch_ids is not None:
            where.append("branch_id IN :branches")
            params["branches"] = list(flt.branch_ids)
            expanding = True
        for column, value in (("method", flt.method), ("status", flt.status), ("source", flt.source)):
            if value is not None:
                where.append(f"{column} = :{column}")
                params[column] = value
        if flt.date_from is not None:
            where.append("doc_date >= :date_from")
            params["date_from"] = flt.date_from
        if flt.date_to is not None:
            where.append("doc_date <= :date_to")
            params["date_to"] = flt.date_to
        if flt.cursor is not None:
            where.append("(doc_date, id) < (:after_date, :after_id)")
            params["after_date"], params["after_id"] = flt.cursor
        clause = ("WHERE " + " AND ".join(where) + " ") if where else ""
        stmt = text(
            f"SELECT {_COLUMNS} FROM app.bank_settlements {clause}"  # noqa: S608
            "ORDER BY doc_date DESC, id DESC LIMIT :limit"
        )
        if expanding:
            stmt = stmt.bindparams(bindparam("branches", expanding=True))
        rows = await s.execute(stmt, params)
        return [_row(r._mapping) for r in rows]

    async def ledger_rows(self, s: AsyncSession, settlement_id: UUID) -> list[dict[str, Any]]:
        rows = await s.execute(
            text(
                "SELECT id, entry_date, account_dt, account_kt, amount, analytics, reversal_of_id "
                "FROM app.ledger_entries WHERE doc_type = 'bank_settlements' AND doc_id = :id ORDER BY id"
            ),
            {"id": settlement_id},
        )
        return [
            {
                "id": str(r[0]),
                "entry_date": r[1].isoformat(),
                "account_dt": r[2],
                "account_kt": r[3],
                "amount": format(Decimal(r[4]).quantize(Decimal("0.01")), "f"),
                "analytics": r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}"),
                "reversal_of_id": None if r[6] is None else str(r[6]),
            }
            for r in rows
        ]

    async def is_duplicate(self, s: AsyncSession, bank_ref: str, doc_date: date, net: Decimal) -> bool:
        found = await s.execute(
            text(
                "SELECT 1 FROM app.bank_settlements WHERE bank_ref = :r AND doc_date = :d AND net_amount = "
                ":n "
                "AND status <> 'cancelled' LIMIT 1"
            ),
            {"r": bank_ref, "d": doc_date, "n": net},
        )
        return found.first() is not None

    # --- transit (5710) -----------------------------------------------------------------------------
    async def transit_balance(
        self, s: AsyncSession, branch_id: UUID, method: str, as_of: date | None
    ) -> Decimal:
        value = (
            await s.execute(
                text(
                    f"SELECT COALESCE(SUM({_SIGNED}), 0) FROM app.ledger_entries WHERE {_TRANSIT} "  # noqa: S608
                    "AND branch_id = :b AND analytics->>'payment_method' = :m "
                    "AND (CAST(:d AS date) IS NULL OR entry_date <= CAST(:d AS date))"
                ),
                {"b": branch_id, "m": method, "d": as_of},
            )
        ).scalar_one()
        return Decimal(value).quantize(Decimal("0.01"))

    async def transit_balances(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> list[tuple[UUID, str, Decimal]]:
        params: dict[str, Any] = {"d": as_of}
        branch_clause = ""
        if branch_ids is not None:
            branch_clause = "AND branch_id IN :branches "
            params["branches"] = list(branch_ids)
        stmt = text(
            f"SELECT branch_id, analytics->>'payment_method' AS method, SUM({_SIGNED}) "  # noqa: S608
            "FROM app.ledger_entries "
            f"WHERE {_TRANSIT} AND entry_date <= :d AND analytics->>'payment_method' IN "
            f"('card','uzqr','click','payme','uzum','collection') {branch_clause}"
            "GROUP BY branch_id, analytics->>'payment_method'"
        )
        if branch_ids is not None:
            stmt = stmt.bindparams(bindparam("branches", expanding=True))
        rows = await s.execute(stmt, params)
        return [(r[0], r[1], Decimal(r[2]).quantize(Decimal("0.01"))) for r in rows]

    async def daily_inflows(
        self, s: AsyncSession, branch_id: UUID, method: str, as_of: date
    ) -> list[tuple[date, Decimal]]:
        rows = await s.execute(
            text(
                f"SELECT entry_date, SUM({_SIGNED}) FROM app.ledger_entries WHERE {_TRANSIT} "  # noqa: S608
                "AND branch_id = :b AND analytics->>'payment_method' = :m AND entry_date <= :d "
                "AND doc_type <> 'bank_settlements' GROUP BY entry_date ORDER BY entry_date"
            ),
            {"b": branch_id, "m": method, "d": as_of},
        )
        return [(r[0], Decimal(r[1]).quantize(Decimal("0.01"))) for r in rows]

    async def holds(self, s: AsyncSession, branch_id: UUID, method: str) -> list[tuple[date, date, Decimal]]:
        rows = await s.execute(
            text(
                "SELECT settled_from, settled_to, gross_amount FROM app.bank_settlements "
                "WHERE branch_id = :b "
                "AND method = :m AND status IN ('posted', 'draft') ORDER BY settled_from, id"
            ),
            {"b": branch_id, "m": method},
        )
        return [(r[0], r[1], Decimal(r[2])) for r in rows]

    async def integrated_card(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> dict[UUID, Decimal]:
        params: dict[str, Any] = {"d": as_of}
        clause = ""
        if branch_ids is not None:
            clause = "AND branch_id IN :branches "
            params["branches"] = list(branch_ids)
        stmt = text(
            f"SELECT branch_id, SUM(v) FROM (SELECT branch_id, {_SIGNED} AS v FROM app.ledger_entries "  # noqa: S608
            f"WHERE {_TRANSIT} AND entry_date <= :d AND analytics->>'payment_method' = 'card' "
            "AND analytics->>'rrn' IS NOT NULL AND doc_type <> 'bank_settlements' "
            "UNION ALL SELECT b.branch_id, -t.approved_amount FROM app.card_terminal_transactions t "
            "JOIN app.bank_settlements b ON b.id = t.bank_settlement_id WHERE b.status = 'posted' "
            f"AND b.doc_date <= :d) x WHERE true {clause}GROUP BY branch_id"
        )
        if branch_ids is not None:
            stmt = stmt.bindparams(bindparam("branches", expanding=True))
        rows = await s.execute(stmt, params)
        return {r[0]: Decimal(r[1]).quantize(Decimal("0.01")) for r in rows}

    # --- card terminal links ------------------------------------------------------------------------
    async def card_txs_by_rrn(self, s: AsyncSession, rrns: Sequence[str]) -> list[CardTx]:
        if not rrns:
            return []
        rows = await s.execute(
            text(f"{_OPEN_TX} AND t.rrn IN :rrns ORDER BY t.id").bindparams(
                bindparam("rrns", expanding=True)
            ),
            {"rrns": list(rrns)},
        )
        return [_tx(r._mapping) for r in rows]

    async def open_card_txs(
        self, s: AsyncSession, branch_id: UUID, date_from: date, date_to: date
    ) -> list[CardTx]:
        rows = await s.execute(
            text(f"{_OPEN_TX} AND t.branch_id = :b AND {_TX_DAY} BETWEEN :f AND :t ORDER BY t.id"),
            {"b": branch_id, "f": date_from, "t": date_to},
        )
        return [_tx(r._mapping) for r in rows]

    async def link_card_txs(self, s: AsyncSession, tx_ids: Sequence[UUID], settlement_id: UUID) -> None:
        if tx_ids:
            await s.execute(
                text(
                    "UPDATE app.card_terminal_transactions SET bank_settlement_id = :sid, updated_at = now() "
                    "WHERE id IN :ids AND bank_settlement_id IS NULL"
                ).bindparams(bindparam("ids", expanding=True)),
                {"sid": settlement_id, "ids": list(tx_ids)},
            )

    async def open_terminal_batches(
        self, s: AsyncSession, branch_id: UUID, identifiers: Sequence[str], up_to: date
    ) -> list[Batch]:
        if not identifiers:
            return []
        rows = await s.execute(
            text(
                "SELECT c.id, c.business_date, c.net_total FROM app.card_terminal_settlements c "
                "JOIN app.card_terminals t ON t.id = c.card_terminal_id "
                "WHERE c.branch_id = :b AND c.bank_settlement_id IS NULL AND c.status <> 'failed' "
                "AND c.business_date <= :d AND (t.tid IN :ids OR t.mid IN :ids) "
                "AND NOT EXISTS (SELECT 1 FROM app.bank_settlements x WHERE x.branch_id = c.branch_id "
                "AND x.method = 'card' AND x.status = 'draft' "
                "AND c.business_date BETWEEN x.settled_from AND x.settled_to) "
                "ORDER BY c.business_date, c.id"
            ).bindparams(bindparam("ids", expanding=True)),
            {"b": branch_id, "d": up_to, "ids": list(identifiers)},
        )
        return [Batch(r[0], r[1], Decimal(r[2])) for r in rows]

    async def link_batches(self, s: AsyncSession, batch_ids: Sequence[UUID], settlement_id: UUID) -> None:
        if batch_ids:
            await s.execute(
                text(
                    "UPDATE app.card_terminal_settlements SET bank_settlement_id = :sid, updated_at = now() "
                    "WHERE id IN :ids AND bank_settlement_id IS NULL"
                ).bindparams(bindparam("ids", expanding=True)),
                {"sid": settlement_id, "ids": list(batch_ids)},
            )

    async def link_terminal_batches(self, s: AsyncSession, row: SettlementRow) -> int:
        """13 §2.18a: the terminal settlement batches of the RRN-linked purchases, else the branch's open
        batches of ``settled_from … settled_to``, get ``bank_settlement_id``."""
        result = await s.execute(
            text(
                "UPDATE app.card_terminal_settlements c SET bank_settlement_id = :sid, updated_at = now() "
                "WHERE c.bank_settlement_id IS NULL AND c.status <> 'failed' AND c.branch_id = :b AND ("
                " c.id IN (SELECT t.settlement_id FROM app.card_terminal_transactions t WHERE "
                "t.bank_settlement_id = :sid)"
                " OR (NOT EXISTS (SELECT 1 FROM app.card_terminal_transactions t WHERE "
                "t.bank_settlement_id = :sid)"
                "     AND NOT EXISTS (SELECT 1 FROM app.card_terminal_settlements b WHERE "
                "b.bank_settlement_id = :sid)"
                "     AND c.business_date BETWEEN :f AND :t))"
            ),
            {"sid": row.id, "b": row.branch_id, "f": row.settled_from, "t": row.settled_to},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def unlink(self, s: AsyncSession, settlement_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.card_terminal_transactions SET bank_settlement_id = NULL, updated_at = now() "
                "WHERE bank_settlement_id = :sid"
            ),
            {"sid": settlement_id},
        )
        await s.execute(
            text(
                "UPDATE app.card_terminal_settlements SET bank_settlement_id = NULL, updated_at = now() "
                "WHERE bank_settlement_id = :sid"
            ),
            {"sid": settlement_id},
        )

    # --- statement imports --------------------------------------------------------------------------
    async def import_by_sha(self, s: AsyncSession, sha256: str) -> UUID | None:
        value = (
            await s.execute(
                text("SELECT id FROM app.bank_statement_imports WHERE file_sha256 = :h"), {"h": sha256}
            )
        ).scalar_one_or_none()
        return None if value is None else UUID(str(value))

    async def insert_attachment(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.attachments (id, tenant_id, s3_key, content_type, original_name, sha256, "
                "kind, size_bytes, uploaded_by) VALUES (:id, :tenant_id, :s3_key, :content_type, "
                ":original_name, :sha256, :kind, :size_bytes, :uploaded_by)"
            ),
            dict(row),
        )

    async def insert_import(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.bank_statement_imports (id, tenant_id, branch_id, attachment_id, "
                "file_sha256, "
                "account, period_from, period_to, status, created_by) VALUES (:id, :tenant_id, :branch_id, "
                ":attachment_id, :file_sha256, :account, :period_from, :period_to, 'parsed', :created_by)"
            ),
            dict(row),
        )

    async def finish_import(self, s: AsyncSession, import_id: UUID, values: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "UPDATE app.bank_statement_imports SET rows_total = :rows_total, drafts_created = "
                ":drafts_created, "
                "duplicates = :duplicates, ignored_outgoing = :ignored_outgoing, "
                "unmatched_lines = CAST(:unmatched AS jsonb), parsed_at = now() WHERE id = :id"
            ),
            {
                "id": import_id,
                "rows_total": values["rows_total"],
                "drafts_created": values["drafts_created"],
                "duplicates": values["duplicates"],
                "ignored_outgoing": values["ignored_outgoing"],
                "unmatched": json.dumps(values["unmatched_lines"], ensure_ascii=False),
            },
        )


class BankStatementFileStore:
    """Filesystem store under ``ERP_FILE_STORAGE_DIR`` (same layout as the import-jobs store; keys never leave
    the base directory) — the S3 ``StoragePort`` of 23 §7 replaces both."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        del content_type
        path = (self._base / key).resolve()
        if not path.is_relative_to(self._base):
            raise ValueError(f"storage key escapes the base directory: {key!r}")

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(path)

        await asyncio.to_thread(write)
