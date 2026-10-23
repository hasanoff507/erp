"""Ledger aggregates for the M11 statements (20 #11, #13) and the doc_date stock report (ACC-09)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.application.accounting_reports import StockAsOfRow

# one row per ledger side: (account, debit, credit) — the double entry unfolded
_SIDES = (
    "SELECT account_dt AS account, amount AS dt, 0::numeric AS kt, entry_date, branch_id, analytics "
    "FROM app.ledger_entries {where} UNION ALL "
    "SELECT account_kt, 0::numeric, amount, entry_date, branch_id, analytics FROM app.ledger_entries {where}"
)


def _branch_filter(branch_ids: tuple[UUID, ...] | None, params: dict[str, Any]) -> str:
    if branch_ids is None:
        return ""
    params["branches"] = [str(b) for b in branch_ids]
    return "WHERE branch_id = ANY(CAST(:branches AS uuid[]))"


class SqlAccountingReports:
    async def turnovers(
        self, s: AsyncSession, start: date, end: date, branch_ids: tuple[UUID, ...] | None
    ) -> list[tuple[str, str | None, Decimal, Decimal, Decimal]]:
        """(account, tax_type, opening, debit, credit) — opening = Σ Dt−Kt before ``start``."""
        params: dict[str, Any] = {"a": start, "e": end}
        sides = _SIDES.format(where=_branch_filter(branch_ids, params))
        rows = await s.execute(
            text(
                f"SELECT account, analytics->>'tax_type' AS tax_type, "  # noqa: S608
                "COALESCE(sum(dt - kt) FILTER (WHERE entry_date < :a), 0), "
                "COALESCE(sum(dt) FILTER (WHERE entry_date BETWEEN :a AND :e), 0), "
                "COALESCE(sum(kt) FILTER (WHERE entry_date BETWEEN :a AND :e), 0) "
                f"FROM ({sides}) x WHERE entry_date <= :e "
                "GROUP BY account, tax_type ORDER BY account, tax_type"
            ),
            params,
        )
        return [(r[0], r[1], Decimal(r[2]), Decimal(r[3]), Decimal(r[4])) for r in rows]

    async def balances(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> dict[str, Decimal]:
        params: dict[str, Any] = {"e": as_of}
        sides = _SIDES.format(where=_branch_filter(branch_ids, params))
        rows = await s.execute(
            text(
                f"SELECT account, COALESCE(sum(dt - kt), 0) FROM ({sides}) x "  # noqa: S608
                "WHERE entry_date <= :e GROUP BY account"
            ),
            params,
        )
        return {r[0]: Decimal(r[1]) for r in rows}

    async def stock_as_of(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None, warehouse_id: UUID | None
    ) -> list[StockAsOfRow]:
        """Stock by document date (ACC-09): every live or reversal ``stock_moves`` row counted on the
        ``doc_date`` of its document (reversal rows — on their own Tashkent date: a cancellation is a later
        event); transfers and documents without a ``doc_date`` — on the move's own business date."""
        params: dict[str, Any] = {"d": as_of, "wh": warehouse_id}
        branch = ""
        if branch_ids is not None:
            params["branches"] = [str(b) for b in branch_ids]
            branch = "AND w.branch_id = ANY(CAST(:branches AS uuid[])) "
        rows = await s.execute(
            text(
                "WITH docs AS ("  # noqa: S608
                " SELECT id, doc_date FROM app.sales UNION ALL SELECT id, doc_date FROM app.returns"
                " UNION ALL SELECT id, doc_date FROM app.goods_receipts"
                " UNION ALL SELECT id, doc_date FROM app.supplier_returns"
                " UNION ALL SELECT id, doc_date FROM app.stock_counts"
                " UNION ALL SELECT id, doc_date FROM app.write_offs"
                " UNION ALL SELECT id, doc_date FROM app.stock_openings) "
                "SELECT m.warehouse_id, w.branch_id, w.inventory_account, m.product_id, p.name, "
                "COALESCE(sum(m.qty), 0), COALESCE(sum(m.cost_amount), 0) "
                "FROM app.stock_moves m JOIN app.warehouses w ON w.id = m.warehouse_id "
                "JOIN app.products p ON p.id = m.product_id "
                "LEFT JOIN docs d ON d.id = m.doc_id AND m.reversal_of_id IS NULL "
                "WHERE COALESCE(d.doc_date, (m.moved_at AT TIME ZONE 'Asia/Tashkent')::date) <= :d "
                "AND (CAST(:wh AS uuid) IS NULL OR m.warehouse_id = :wh) "
                f"{branch}"
                "GROUP BY m.warehouse_id, w.branch_id, w.inventory_account, m.product_id, p.name "
                "HAVING sum(m.qty) <> 0 OR sum(m.cost_amount) <> 0 "
                "ORDER BY p.name, m.product_id, m.warehouse_id"
            ),
            params,
        )
        return [StockAsOfRow(r[0], r[1], r[2], r[3], r[4], Decimal(r[5]), Decimal(r[6])) for r in rows]

    async def stock_ledger(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> dict[str, Decimal]:
        """GL 2910/2920 balance up to ``as_of`` (ledger is dated by ``doc_date``)."""
        params: dict[str, Any] = {"e": as_of}
        sides = _SIDES.format(where=_branch_filter(branch_ids, params))
        rows = await s.execute(
            text(
                f"SELECT account, COALESCE(sum(dt - kt), 0) FROM ({sides}) x "  # noqa: S608
                "WHERE entry_date <= :e AND account IN ('2910','2920') GROUP BY account"
            ),
            params,
        )
        return {r[0]: Decimal(r[1]) for r in rows}
