"""Debt-book documents SQL (12 ``debt_payments``, ``debt_payment_allocations``, ``debt_openings``,
``debt_writeoffs``, ``debt_writeoff_allocations``, ``debt_doubtful_flags``; read-only joins over ``sales``,
``sale_lines``, ``returns``, ``debt_moves``, ``debt_balances``, ``ledger_entries``).

Runs inside the caller's ``tenant_transaction`` (RLS-bound). Table/column names never come from the request:
``table`` arguments are checked against :data:`DOC_TABLES` / :data:`ALLOC_TABLES`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.debts.application.doc_ports import DocInfo, LedgerMove, Row, SaleLineRow, TargetDoc

DOC_TABLES: Final = frozenset({"debt_payments", "debt_openings", "debt_writeoffs"})
ALLOC_TABLES: Final = {
    "debt_payment_allocations": "debt_payment_id",
    "debt_writeoff_allocations": "debt_writeoff_id",
}
# documents that write debt_moves and carry number/doc_date/status/created_by/comment/branch_id (debt ledger
# rows)
INFO_TABLES: Final = frozenset(
    {
        "sales",
        "returns",
        "goods_receipts",
        "supplier_returns",
        "supplier_payments",
        "debt_payments",
        "debt_openings",
        "debt_writeoffs",
        "cash_movements",
    }
)
_ZERO = Decimal("0.00")

_TARGETS = """
WITH tg AS (
  SELECT dm.counterparty_id, dm.doc_type, dm.doc_id, sum(dm.amount) AS amt, max(dm.due_date) AS due,
         bool_or(dm.limit_exceeded) AS limit_exceeded
  FROM app.debt_moves dm
  WHERE dm.direction = 'receivable' AND dm.doc_type IN ('sales', 'debt_openings')
    AND dm.counterparty_id = ANY(:ids)
  GROUP BY dm.counterparty_id, dm.doc_type, dm.doc_id
), ret AS (
  SELECT r.sale_id AS doc_id, sum(dm.amount) AS amt
  FROM app.debt_moves dm JOIN app.returns r ON r.id = dm.doc_id
  WHERE dm.doc_type = 'returns' AND dm.direction = 'receivable' AND dm.counterparty_id = ANY(:ids)
    AND r.sale_id IS NOT NULL
  GROUP BY r.sale_id
), pay AS (
  SELECT a.target_doc_type, a.target_doc_id, sum(a.amount) AS amt
  FROM app.debt_payment_allocations a JOIN app.debt_payments p ON p.id = a.debt_payment_id
  WHERE p.status = 'posted' AND p.counterparty_id = ANY(:ids)
  GROUP BY a.target_doc_type, a.target_doc_id
), wo AS (
  SELECT a.target_doc_type, a.target_doc_id, sum(a.amount) AS amt
  FROM app.debt_writeoff_allocations a JOIN app.debt_writeoffs w ON w.id = a.debt_writeoff_id
  WHERE w.status = 'posted' AND w.counterparty_id = ANY(:ids)
  GROUP BY a.target_doc_type, a.target_doc_id
), docs AS (
  SELECT tg.counterparty_id, tg.doc_type, tg.doc_id,
         COALESCE(s.number, o.number) AS number, COALESCE(s.doc_date, o.doc_date) AS doc_date,
         COALESCE(o.due_date, tg.due) AS due_date, COALESCE(s.branch_id, o.branch_id) AS branch_id,
         tg.amt + COALESCE(ret.amt, 0) AS original, COALESCE(pay.amt, 0) AS paid, COALESCE(wo.amt, 0) AS
         written_off,
         tg.limit_exceeded, COALESCE(s.created_by, o.created_by) AS created_by,
         COALESCE(s.comment, o.comment) AS comment
  FROM tg
  LEFT JOIN app.sales s ON tg.doc_type = 'sales' AND s.id = tg.doc_id
  LEFT JOIN app.debt_openings o ON tg.doc_type = 'debt_openings' AND o.id = tg.doc_id
  LEFT JOIN ret ON tg.doc_type = 'sales' AND ret.doc_id = tg.doc_id
  LEFT JOIN pay ON pay.target_doc_type = tg.doc_type AND pay.target_doc_id = tg.doc_id
  LEFT JOIN wo ON wo.target_doc_type = tg.doc_type AND wo.target_doc_id = tg.doc_id
  UNION ALL
  SELECT w.counterparty_id, 'debt_writeoffs', w.id, w.number, w.doc_date, NULL, w.branch_id,
         w.amount, COALESCE(pay.amt, 0), 0, false, w.created_by, w.comment
  FROM app.debt_writeoffs w
  LEFT JOIN pay ON pay.target_doc_type = 'debt_writeoffs' AND pay.target_doc_id = w.id
  WHERE w.status = 'posted' AND w.counterparty_id = ANY(:ids)
)
SELECT *, original - paid - written_off AS open_amount FROM docs
"""


def _rows(result: Any) -> list[Row]:
    return [dict(r._mapping) for r in result]


def _check(table: str, allowed: Any) -> str:
    if table not in allowed:
        raise ValueError(f"unexpected table {table!r}")
    return table


class SqlDebtDocsRepository:
    # --- open documents ---------------------------------------------------------------------------
    async def target_docs(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID], *, only_open: bool = True
    ) -> dict[UUID, list[TargetDoc]]:
        ids = list(dict.fromkeys(counterparty_ids))
        out: dict[UUID, list[TargetDoc]] = {cid: [] for cid in ids}
        if not ids:
            return out
        where = (
            " WHERE original - paid - written_off > 0" if only_open else " WHERE original <> 0 OR paid <> 0"
        )
        sql = f"SELECT * FROM ({_TARGETS}) x{where} ORDER BY counterparty_id, doc_date, doc_id"  # noqa: S608
        rows = await s.execute(
            text(sql),
            {"ids": ids},
        )
        for r in rows:
            m = r._mapping
            out[m["counterparty_id"]].append(
                TargetDoc(
                    counterparty_id=m["counterparty_id"],
                    doc_type=m["doc_type"],
                    doc_id=m["doc_id"],
                    number=m["number"],
                    doc_date=m["doc_date"],
                    due_date=m["due_date"],
                    branch_id=m["branch_id"],
                    original=Decimal(m["original"]),
                    paid=Decimal(m["paid"]),
                    written_off=Decimal(m["written_off"]),
                    open_amount=Decimal(m["open_amount"]),
                    limit_exceeded=bool(m["limit_exceeded"]),
                    created_by=m["created_by"],
                    comment=m["comment"],
                )
            )
        return out

    async def sale_lines(
        self, s: AsyncSession, sale_ids: Sequence[UUID], *, counterparty_id: UUID | None = None
    ) -> dict[UUID, list[SaleLineRow]]:
        """Lines of the sales (+ returned qty/amount, ACC-01); ``counterparty_id`` — only that customer's
        sales (SYNC-03)."""
        ids = list(dict.fromkeys(sale_ids))
        out: dict[UUID, list[SaleLineRow]] = {sid: [] for sid in ids}
        if not ids:
            return out
        cp_filter = (
            ""
            if counterparty_id is None
            else "AND EXISTS (SELECT 1 FROM app.sales sx WHERE sx.id = sl.sale_id "
            "AND sx.counterparty_id = :cp) "
        )
        params: dict[str, Any] = {"ids": ids}
        if counterparty_id is not None:
            params["cp"] = counterparty_id
        rows = await s.execute(
            text(
                "SELECT sl.id AS sale_line_id, sl.sale_id, sl.line_no, sl.product_id, p.name, p.name_ru, "  # noqa: S608
                "p.mxik_code, p.package_code, p.unit_code, "
                "(SELECT min(b.barcode) FROM app.product_barcodes b WHERE b.product_id = p.id) AS barcode, "
                "sl.qty, sl.price, sl.line_total, sl.vat_rate, sl.vat_exemption_code, sl.settled_amount, "
                "sl.marking_code, COALESCE(rt.qty, 0) AS returned_qty, COALESCE(rt.amount, 0) AS "
                "returned_amount "
                "FROM app.sale_lines sl JOIN app.products p ON p.id = sl.product_id "
                "LEFT JOIN (SELECT rl.sale_line_id, sum(rl.qty) AS qty, sum(rl.line_total) AS amount "
                "  FROM app.return_lines rl JOIN app.returns r ON r.id = rl.return_id "
                "  WHERE r.status = 'posted' AND r.sale_id = ANY(:ids) AND rl.sale_line_id IS NOT NULL "
                "  GROUP BY rl.sale_line_id) rt ON rt.sale_line_id = sl.id "
                "WHERE sl.sale_id = ANY(:ids) " + cp_filter + "ORDER BY sl.sale_id, sl.line_no"
            ),
            params,
        )
        for r in rows:
            m = r._mapping
            out[m["sale_id"]].append(SaleLineRow(**{k: m[k] for k in SaleLineRow.__dataclass_fields__}))
        return out

    async def receivable_balances(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID]
    ) -> dict[UUID, Decimal]:
        ids = list(dict.fromkeys(counterparty_ids))
        out: dict[UUID, Decimal] = dict.fromkeys(ids, _ZERO)
        if not ids:
            return out
        rows = await s.execute(
            text(
                "SELECT counterparty_id, balance FROM app.debt_balances "
                "WHERE direction = 'receivable' AND counterparty_id = ANY(:ids)"
            ),
            {"ids": ids},
        )
        for r in rows:
            out[r[0]] = Decimal(r[1])
        return out

    async def add_settled(self, s: AsyncSession, amounts: Mapping[UUID, Decimal]) -> None:
        for line_id, amount in sorted(amounts.items(), key=lambda kv: kv[0].bytes):
            if amount == 0:
                continue
            await s.execute(
                text("UPDATE app.sale_lines SET settled_amount = settled_amount + :a WHERE id = :id"),
                {"a": amount, "id": line_id},
            )

    async def touch_balance(self, s: AsyncSession, counterparty_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.debt_balances SET updated_at = now() "
                "WHERE counterparty_id = :cp AND direction = 'receivable'"
            ),
            {"cp": counterparty_id},
        )

    async def set_due_date(self, s: AsyncSession, counterparty_id: UUID, due: date | None) -> None:
        await s.execute(
            text(
                "UPDATE app.counterparties SET debt_due_date = :d WHERE id = :id "
                "AND debt_due_date IS DISTINCT FROM :d"
            ),
            {"d": due, "id": counterparty_id},
        )

    async def counterparty_due_date(self, s: AsyncSession, counterparty_id: UUID) -> date | None:
        value: date | None = (
            await s.execute(
                text("SELECT debt_due_date FROM app.counterparties WHERE id = :id"), {"id": counterparty_id}
            )
        ).scalar_one_or_none()
        return value

    async def live_allocation_reason(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> str | None:
        sql = (
            "SELECT EXISTS (SELECT 1 FROM app.supplier_payment_allocations a JOIN app.supplier_payments p "
            "ON p.id = a.supplier_payment_id WHERE p.status = 'posted' AND a.target_doc_type = :t "
            "AND a.target_doc_id = :id), "
            "EXISTS (SELECT 1 FROM app.debt_payment_allocations a JOIN app.debt_payments p "
            "ON p.id = a.debt_payment_id WHERE p.status = 'posted' AND a.target_doc_type = :t AND "
            "a.target_doc_id = :id) "
            "OR EXISTS (SELECT 1 FROM app.debt_writeoff_allocations a JOIN app.debt_writeoffs w "
            "ON w.id = a.debt_writeoff_id WHERE w.status = 'posted' AND a.target_doc_type = :t AND "
            "a.target_doc_id = :id)"
        )
        supplier, debt = (await s.execute(text(sql), {"t": doc_type, "id": doc_id})).one()
        if supplier:
            return "supplier_payment_allocated"
        return "has_allocations" if debt else None

    # --- reference data ---------------------------------------------------------------------------
    async def go_live_date(self, s: AsyncSession) -> date | None:
        value: date | None = (
            await s.execute(text("SELECT go_live_date FROM app.tenants WHERE id = app.current_tenant_id()"))
        ).scalar_one_or_none()
        return value

    async def tenant_name(self, s: AsyncSession) -> str:
        value = (
            await s.execute(text("SELECT name FROM app.tenants WHERE id = app.current_tenant_id()"))
        ).scalar_one_or_none()
        return str(value or "")

    async def default_branch(self, s: AsyncSession) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text(
                    "SELECT id FROM app.branches WHERE archived_at IS NULL "
                    "ORDER BY is_default DESC, id LIMIT 1"
                )
            )
        ).scalar_one_or_none()
        return value

    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool:
        found = await s.execute(
            text("SELECT 1 FROM app.branches WHERE id = :id AND archived_at IS NULL"), {"id": branch_id}
        )
        return found.first() is not None

    async def user_names(self, s: AsyncSession, user_ids: Sequence[UUID]) -> dict[UUID, str]:
        ids = [u for u in dict.fromkeys(user_ids) if u is not None]
        if not ids:
            return {}
        rows = await s.execute(text("SELECT id, name FROM app.users WHERE id = ANY(:ids)"), {"ids": ids})
        return {r[0]: r[1] for r in rows}

    async def checkout(self, s: AsyncSession, checkout_ref: UUID) -> Row | None:
        row = (
            await s.execute(
                text(
                    "SELECT checkout_ref, provider, status, amount, provider_tx_id, cash_register_id "
                    "FROM app.payment_checkouts WHERE checkout_ref = :r FOR UPDATE"
                ),
                {"r": checkout_ref},
            )
        ).first()
        return dict(row._mapping) if row else None

    async def consume_checkout(self, s: AsyncSession, checkout_ref: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.payment_checkouts SET status = 'consumed', updated_at = now() WHERE "
                "checkout_ref = :r"
            ),
            {"r": checkout_ref},
        )

    async def insert_cash_moves(self, s: AsyncSession, rows: Sequence[Row]) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.cash_moves (id, tenant_id, cash_register_id, shift_id, amount, method, "
                "doc_type, "
                "doc_id) VALUES (:id, :tenant_id, :cash_register_id, :shift_id, :amount, :method, "
                ":doc_type, :doc_id)"
            ),
            [dict(r) for r in rows],
        )

    async def reserve_4910(self, s: AsyncSession, counterparty_id: UUID) -> Decimal:
        """Credit balance of 4910 (doubtful-debt reserve) for this counterparty (13 §2.15a)."""
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(CASE WHEN account_kt = '4910' THEN amount ELSE -amount END), 0) "
                    "FROM app.ledger_entries WHERE (account_kt = '4910' OR account_dt = '4910') "
                    "AND analytics->>'counterparty_id' = :cp"
                ),
                {"cp": str(counterparty_id)},
            )
        ).scalar_one()
        return Decimal(value)

    # --- documents --------------------------------------------------------------------------------
    async def insert_doc(self, s: AsyncSession, table: str, row: Row) -> None:
        _check(table, DOC_TABLES)
        cols = list(row)
        await s.execute(
            text(
                f"INSERT INTO app.{table} ({', '.join(cols)}) "  # noqa: S608
                f"VALUES ({', '.join(':' + c for c in cols)})"
            ),
            dict(row),
        )

    async def get_doc(self, s: AsyncSession, table: str, doc_id: UUID, *, lock: bool = False) -> Row | None:
        _check(table, DOC_TABLES)
        sql = (
            f"SELECT d.*, c.name AS counterparty_name, c.phone AS counterparty_phone "  # noqa: S608
            f"FROM app.{table} d JOIN app.counterparties c ON c.id = d.counterparty_id WHERE d.id = :id"
        )
        row = (await s.execute(text(sql + (" FOR UPDATE OF d" if lock else "")), {"id": doc_id})).first()
        return dict(row._mapping) if row else None

    async def update_doc(self, s: AsyncSession, table: str, doc_id: UUID, values: Row) -> None:
        _check(table, DOC_TABLES)
        sets = ", ".join(f"{c} = :{c}" for c in values)
        await s.execute(
            text(f"UPDATE app.{table} SET {sets} WHERE id = :doc_id"),  # noqa: S608
            {**values, "doc_id": doc_id},
        )

    async def docs_page(
        self,
        s: AsyncSession,
        table: str,
        *,
        filters: Row,
        branch_ids: Sequence[UUID] | None,
        after: tuple[date, UUID] | None,
        limit: int,
    ) -> list[Row]:
        _check(table, DOC_TABLES)
        where = ["true"]
        params: dict[str, Any] = {"limit": limit}
        for key in ("counterparty_id", "branch_id", "status", "method", "direction"):
            if filters.get(key) is not None:
                where.append(f"d.{key} = :{key}")
                params[key] = filters[key]
        if filters.get("doc_date__gte") is not None:
            where.append("d.doc_date >= :dfrom")
            params["dfrom"] = filters["doc_date__gte"]
        if filters.get("doc_date__lte") is not None:
            where.append("d.doc_date <= :dto")
            params["dto"] = filters["doc_date__lte"]
        if branch_ids is not None:
            where.append("d.branch_id = ANY(:branches)")
            params["branches"] = list(branch_ids)
        if after is not None:
            where.append("(d.doc_date, d.id) < (:after_date, :after_id)")
            params["after_date"], params["after_id"] = after
        rows = await s.execute(
            text(
                "SELECT d.*, c.name AS counterparty_name, c.phone AS counterparty_phone "  # noqa: S608
                f"FROM app.{table} d "
                "JOIN app.counterparties c ON c.id = d.counterparty_id "
                f"WHERE {' AND '.join(where)} ORDER BY d.doc_date DESC, d.id DESC LIMIT :limit"
            ),
            params,
        )
        return _rows(rows)

    async def insert_allocations(self, s: AsyncSession, table: str, rows: Sequence[Row]) -> None:
        fk = ALLOC_TABLES[_check(table, ALLOC_TABLES)]
        if not rows:
            return
        await s.execute(
            text(
                f"INSERT INTO app.{table} (id, tenant_id, {fk}, target_doc_type, target_doc_id, amount) "  # noqa: S608
                f"VALUES (:id, :tenant_id, :{fk}, :target_doc_type, :target_doc_id, :amount)"
            ),
            [dict(r) for r in rows],
        )

    async def allocations_of(
        self, s: AsyncSession, table: str, doc_ids: Sequence[UUID]
    ) -> dict[UUID, list[Row]]:
        fk = ALLOC_TABLES[_check(table, ALLOC_TABLES)]
        ids = list(dict.fromkeys(doc_ids))
        out: dict[UUID, list[Row]] = {i: [] for i in ids}
        if not ids:
            return out
        rows = await s.execute(
            text(
                f"SELECT a.{fk} AS doc_id, a.target_doc_type, a.target_doc_id, a.amount, "  # noqa: S608
                "COALESCE(s.number, o.number, w.number) AS target_number, "
                "COALESCE(s.doc_date, o.doc_date, w.doc_date) AS target_doc_date "
                f"FROM app.{table} a "
                "LEFT JOIN app.sales s ON a.target_doc_type = 'sales' AND s.id = a.target_doc_id "
                "LEFT JOIN app.debt_openings o ON a.target_doc_type = 'debt_openings' AND o.id = "
                "a.target_doc_id "
                "LEFT JOIN app.debt_writeoffs w ON a.target_doc_type = 'debt_writeoffs' AND w.id = "
                "a.target_doc_id "
                f"WHERE a.{fk} = ANY(:ids) ORDER BY a.id"
            ),
            {"ids": ids},
        )
        for r in rows:
            m = dict(r._mapping)
            out[m.pop("doc_id")].append(m)
        return out

    async def payment_receipts(self, s: AsyncSession, payment_ids: Sequence[UUID]) -> dict[UUID, Row]:
        ids = list(dict.fromkeys(payment_ids))
        if not ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT debt_payment_id, id, status, receipt_seq, fm_receipt_seq, fiscal_sign, qr_url, "
                "ofd_acked_at "
                "FROM app.fiscal_receipts WHERE kind = 'debt_settlement' AND debt_payment_id = ANY(:ids)"
            ),
            {"ids": ids},
        )
        return {r._mapping["debt_payment_id"]: dict(r._mapping) for r in rows}

    # --- doubtful flags ---------------------------------------------------------------------------
    async def active_flags(self, s: AsyncSession, counterparty_ids: Sequence[UUID] | None) -> dict[UUID, Row]:
        sql = (
            "SELECT DISTINCT ON (counterparty_id) id, counterparty_id, reason, flagged_by, flagged_at "
            "FROM app.debt_doubtful_flags WHERE unflagged_at IS NULL"
        )
        params: dict[str, Any] = {}
        if counterparty_ids is not None:
            sql += " AND counterparty_id = ANY(:ids)"
            params["ids"] = list(counterparty_ids)
        rows = await s.execute(text(sql + " ORDER BY counterparty_id, id DESC"), params)
        return {r._mapping["counterparty_id"]: dict(r._mapping) for r in rows}

    async def insert_flag(self, s: AsyncSession, row: Row) -> None:
        await s.execute(
            text(
                "INSERT INTO app.debt_doubtful_flags (id, tenant_id, counterparty_id, flagged_by, reason) "
                "VALUES (:id, :tenant_id, :counterparty_id, :flagged_by, :reason)"
            ),
            dict(row),
        )

    async def get_flag(self, s: AsyncSession, flag_id: UUID, *, lock: bool = False) -> Row | None:
        sql = (
            "SELECT id, counterparty_id, flagged_by, reason, flagged_at, unflagged_at, created_at "
            "FROM app.debt_doubtful_flags WHERE id = :id"
        )
        row = (await s.execute(text(sql + (" FOR UPDATE" if lock else "")), {"id": flag_id})).first()
        return dict(row._mapping) if row else None

    async def unflag(self, s: AsyncSession, flag_id: UUID) -> None:
        await s.execute(
            text("UPDATE app.debt_doubtful_flags SET unflagged_at = now() WHERE id = :id"), {"id": flag_id}
        )

    # --- ledger / aging ---------------------------------------------------------------------------
    async def ledger_moves(self, s: AsyncSession, counterparty_id: UUID, direction: str) -> list[LedgerMove]:
        rows = await s.execute(
            text(
                "SELECT doc_type, doc_id, sum(amount) AS amount, bool_or(reversal_of_id IS NOT NULL) AS "
                "reversed, "
                "max(due_date) AS due_date, (array_agg(id ORDER BY id))[1] AS first_id "
                "FROM app.debt_moves WHERE counterparty_id = :cp AND direction = :d "
                "GROUP BY doc_type, doc_id"
            ),
            {"cp": counterparty_id, "d": direction},
        )
        return [
            LedgerMove(r.doc_type, r.doc_id, Decimal(r.amount), bool(r.reversed), r.due_date, r.first_id)
            for r in rows
        ]

    async def doc_infos(
        self, s: AsyncSession, refs: Sequence[tuple[str, UUID]]
    ) -> dict[tuple[str, UUID], DocInfo]:
        by_type: dict[str, list[UUID]] = {}
        for doc_type, doc_id in refs:
            if doc_type in INFO_TABLES:
                by_type.setdefault(doc_type, []).append(doc_id)
        out: dict[tuple[str, UUID], DocInfo] = {}
        for doc_type, ids in by_type.items():
            table = _check(doc_type, INFO_TABLES)
            rows = await s.execute(
                text(
                    "SELECT d.id, d.number, d.doc_date, d.status, d.created_by, "  # noqa: S608
                    "u.name AS created_by_name, "
                    f"d.comment, d.branch_id FROM app.{table} d LEFT JOIN app.users u ON u.id = d.created_by "
                    "WHERE d.id = ANY(:ids)"
                ),
                {"ids": list(dict.fromkeys(ids))},
            )
            for r in rows:
                m = r._mapping
                out[(doc_type, m["id"])] = DocInfo(
                    doc_type,
                    m["id"],
                    m["number"],
                    m["doc_date"],
                    m["status"],
                    m["created_by"],
                    m["created_by_name"],
                    m["comment"],
                    m["branch_id"],
                )
        return out

    async def promise_dates(self, s: AsyncSession, counterparty_id: UUID) -> dict[tuple[str, UUID], date]:
        rows = await s.execute(
            text(
                "SELECT a.target_doc_type, a.target_doc_id, p.promise_date FROM "
                "app.debt_payment_allocations a "
                "JOIN app.debt_payments p ON p.id = a.debt_payment_id WHERE p.status = 'posted' "
                "AND p.counterparty_id = :cp AND p.promise_date IS NOT NULL ORDER BY p.doc_date, p.id"
            ),
            {"cp": counterparty_id},
        )
        out: dict[tuple[str, UUID], date] = {}
        for r in rows:
            out[(r[0], r[1])] = r[2]
        return out

    async def debtors(self, s: AsyncSession, direction: str) -> list[Row]:
        rows = await s.execute(
            text(
                "SELECT c.id AS counterparty_id, c.name, c.phone, c.credit_limit, c.debt_due_date, b.balance "
                "FROM app.debt_balances b JOIN app.counterparties c ON c.id = b.counterparty_id "
                "WHERE b.direction = :d AND b.balance > 0 ORDER BY b.balance DESC, c.id"
            ),
            {"d": direction},
        )
        return _rows(rows)

    async def payable_charges(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID]
    ) -> dict[UUID, list[Row]]:
        ids = list(dict.fromkeys(counterparty_ids))
        out: dict[UUID, list[Row]] = {i: [] for i in ids}
        if not ids:
            return out
        rows = await s.execute(
            text(
                "SELECT x.counterparty_id, x.doc_type, x.doc_id, x.amount, "
                "COALESCE(o.due_date, x.due) AS due_date, COALESCE(g.doc_date, o.doc_date) AS doc_date, "
                "COALESCE(g.branch_id, o.branch_id) AS branch_id, COALESCE(g.number, o.number) AS number "
                "FROM (SELECT counterparty_id, doc_type, doc_id, sum(amount) AS amount, max(due_date) AS due "
                "      FROM app.debt_moves WHERE direction = 'payable' AND counterparty_id = ANY(:ids) "
                "      AND doc_type IN ('goods_receipts', 'debt_openings') GROUP BY 1, 2, 3 "
                "      HAVING sum(amount) > 0) x "
                "LEFT JOIN app.goods_receipts g ON x.doc_type = 'goods_receipts' AND g.id = x.doc_id "
                "LEFT JOIN app.debt_openings o ON x.doc_type = 'debt_openings' AND o.id = x.doc_id "
                "ORDER BY x.counterparty_id, COALESCE(g.doc_date, o.doc_date), x.doc_id"
            ),
            {"ids": ids},
        )
        for r in rows:
            m = dict(r._mapping)
            out[m["counterparty_id"]].append(m)
        return out

    async def last_payments(self, s: AsyncSession, counterparty_ids: Sequence[UUID]) -> dict[UUID, Row]:
        ids = list(dict.fromkeys(counterparty_ids))
        if not ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT DISTINCT ON (counterparty_id) counterparty_id, amount, doc_date FROM "
                "app.debt_payments "
                "WHERE status = 'posted' AND counterparty_id = ANY(:ids) "
                "ORDER BY counterparty_id, doc_date DESC, id DESC"
            ),
            {"ids": ids},
        )
        return {r._mapping["counterparty_id"]: dict(r._mapping) for r in rows}


def json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)
