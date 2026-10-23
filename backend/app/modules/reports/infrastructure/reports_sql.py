"""Read-only SQL of the M12 reports over documents and registers (D4: no materialised report tables).

Runs in the caller's tenant transaction (RLS). Posted documents only (``status = 'posted'``); a cancelled
document leaves its storno in the registers, so register sums are already net of cancellations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.application.ports import (
    ApprovalPending,
    Branches,
    BranchRow,
    Counterparty,
    DiscountAgg,
    ExpenseLine,
    LedgerTotals,
    ProductSales,
    RegisterCash,
    SalesAgg,
    SalesGroup,
    StockRow,
    UnsyncedDevices,
)
from app.modules.reports.domain.debts import DebtDoc
from app.modules.reports.domain.periods import DateRange, day_bounds

ZERO = Decimal("0.00")
EXPENSE_ACCOUNTS = ("9410", "9420", "9430", "9820")
_PNL_ACCOUNTS = "('9020','9040','9050','9120','9390')"
_EXPENSE_IN = "('9410','9420','9430','9820')"
_UUID_RE = "'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'"


def _d(value: Any) -> Decimal:
    return ZERO if value is None else Decimal(value)


def _branch(column: str, branch_ids: Branches, params: dict[str, Any]) -> str:
    """`` AND <column> IN branches`` (empty string for the whole tenant)."""
    if branch_ids is None:
        return ""
    params["branches"] = [str(b) for b in branch_ids]
    return f" AND {column} = ANY(CAST(:branches AS uuid[]))"


def _like(raw: str) -> str:
    return "%" + raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


_SALE_KEYS = {
    "day": "CAST(x.doc_date AS text)",
    "branch": "CAST(x.branch_id AS text)",
    "cashier": "CAST(x.created_by AS text)",
}


class SqlReportsRepository:
    async def branches(self, s: AsyncSession, branch_ids: Branches) -> list[BranchRow]:
        params: dict[str, Any] = {}
        if branch_ids is None:
            where = "archived_at IS NULL"
        else:
            where = "id = ANY(CAST(:branches AS uuid[]))"
            params["branches"] = [str(b) for b in branch_ids]
        rows = await s.execute(
            text(f"SELECT id, name FROM app.branches WHERE {where} ORDER BY name, id"),  # noqa: S608
            params,
        )
        return [BranchRow(r.id, r.name) for r in rows]

    async def tenant_settings(self, s: AsyncSession) -> dict[str, object]:
        value = (await s.execute(text("SELECT settings FROM app.tenants LIMIT 1"))).scalar()
        return dict(value) if isinstance(value, dict) else {}

    # --- sales (20 #18)
    # --------------------------------------------------------------------------------------
    async def sales(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches, group_by: SalesGroup
    ) -> list[SalesAgg]:
        key = _SALE_KEYS[group_by]
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to}
        sales_branch = _branch("x.branch_id", branch_ids, params)
        sql = (
            "WITH sold AS ("  # noqa: S608
            f"  SELECT {key} AS k, count(*) AS n, COALESCE(sum(COALESCE(x.total_amount, "
            "    (SELECT sum(l.line_total) FROM app.sale_lines l WHERE l.sale_id = x.id))), 0) AS gross "
            "  FROM app.sales x WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b"
            f"{sales_branch} GROUP BY 1), "
            "returned AS ("
            f"  SELECT {key} AS k, COALESCE(sum(rl.line_total), 0) AS total "
            "  FROM app.returns x JOIN app.return_lines rl ON rl.return_id = x.id "
            f"  WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b{sales_branch} GROUP BY 1) "
            "SELECT COALESCE(sold.k, returned.k) AS k, COALESCE(sold.n, 0) AS n, COALESCE(sold.gross, 0) AS "
            "gross, "
            "COALESCE(returned.total, 0) AS ret FROM sold FULL JOIN returned ON returned.k = sold.k"
        )
        rows = list(await s.execute(text(sql), params))
        labels: dict[str, str] = {}
        keys = [r.k for r in rows]
        if keys and group_by == "branch":
            found = await s.execute(
                text("SELECT CAST(id AS text) AS k, name FROM app.branches WHERE CAST(id AS text) = ANY(:k)"),
                {"k": keys},
            )
            labels = {r.k: r.name for r in found}
        elif keys and group_by == "cashier":
            found = await s.execute(
                text("SELECT CAST(id AS text) AS k, name FROM app.users WHERE CAST(id AS text) = ANY(:k)"),
                {"k": keys},
            )
            labels = {r.k: r.name for r in found}
        out = [SalesAgg(r.k, labels.get(r.k), _d(r.gross), int(r.n), _d(r.ret)) for r in rows]
        if group_by == "day":
            out.sort(key=lambda a: a.group_key)
        else:
            out.sort(key=lambda a: (a.group_label or "", a.group_key))
        return out

    # --- top products (20 #19)
    # -------------------------------------------------------------------------------
    async def product_sales(
        self,
        s: AsyncSession,
        rng: DateRange,
        branch_ids: Branches,
        order: Literal["top", "bottom"],
        limit: int,
    ) -> list[ProductSales]:
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to, "lim": limit}
        branch = _branch("x.branch_id", branch_ids, params)
        direction = "DESC" if order == "top" else "ASC"
        sql = (
            "WITH sold AS ("  # noqa: S608
            "  SELECT l.product_id, sum(l.qty) AS q, sum(l.line_total) AS r FROM app.sale_lines l "
            "  JOIN app.sales x ON x.id = l.sale_id "
            f"  WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b{branch} GROUP BY 1), "
            "returned AS ("
            "  SELECT l.product_id, sum(l.qty) AS q, sum(l.line_total) AS r FROM app.return_lines l "
            "  JOIN app.returns x ON x.id = l.return_id "
            f"  WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b{branch} GROUP BY 1), "
            "net AS ("
            "  SELECT COALESCE(sold.product_id, returned.product_id) AS product_id, "
            "  COALESCE(sold.q, 0) - COALESCE(returned.q, 0) AS q, COALESCE(sold.r, 0) - "
            "COALESCE(returned.r, 0) AS r "
            "  FROM sold FULL JOIN returned ON returned.product_id = sold.product_id) "
            "SELECT p.id, p.name, p.unit_code, net.q, net.r FROM net JOIN app.products p ON p.id = "
            "net.product_id "
            f"ORDER BY net.q {direction}, net.r {direction}, p.name, p.id LIMIT :lim"
        )
        rows = await s.execute(text(sql), params)
        return [ProductSales(r.id, r.name, r.unit_code, _d(r.q), _d(r.r)) for r in rows]

    # --- P&L (20 #12)
    # ----------------------------------------------------------------------------------------
    async def ledger_totals(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> list[LedgerTotals]:
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to}
        branch = _branch("e.branch_id", branch_ids, params)

        def net(account: str, credit_side: bool) -> str:
            kt = f"COALESCE(sum(CASE WHEN e.account_kt = '{account}' THEN e.amount END), 0)"
            dt = f"COALESCE(sum(CASE WHEN e.account_dt = '{account}' THEN e.amount END), 0)"
            return f"{kt} - {dt}" if credit_side else f"{dt} - {kt}"

        sql = (
            f"SELECT e.branch_id, {net('9020', True)} AS rev, {net('9040', False)} AS ret, "  # noqa: S608
            f"{net('9050', False)} AS disc, {net('9120', False)} AS cogs, {net('9390', True)} AS other "
            "FROM app.ledger_entries e WHERE e.entry_date BETWEEN :a AND :b "
            f"AND (e.account_dt IN {_PNL_ACCOUNTS} OR e.account_kt IN {_PNL_ACCOUNTS}){branch} "
            "GROUP BY e.branch_id"
        )
        rows = await s.execute(text(sql), params)
        return [
            LedgerTotals(r.branch_id, _d(r.rev), _d(r.ret), _d(r.disc), _d(r.cogs), _d(r.other)) for r in rows
        ]

    async def expense_lines(self, s: AsyncSession, rng: DateRange, branch_ids: Branches) -> list[ExpenseLine]:
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to}
        branch = _branch("e.branch_id", branch_ids, params)
        sql = (
            "WITH lines AS ("  # noqa: S608
            "  SELECT e.branch_id, e.account_dt AS account, e.amount, e.doc_type, e.doc_id, e.analytics "
            f"  FROM app.ledger_entries e WHERE e.entry_date BETWEEN :a AND :b AND e.account_dt IN "
            f"{_EXPENSE_IN}"
            f"{branch} UNION ALL "
            "  SELECT e.branch_id, e.account_kt, -e.amount, e.doc_type, e.doc_id, e.analytics "
            f"  FROM app.ledger_entries e WHERE e.entry_date BETWEEN :a AND :b AND e.account_kt IN "
            f"{_EXPENSE_IN}"
            f"{branch}) "
            "SELECT l.branch_id, l.account, l.doc_type, c.id AS category_id, c.name AS category_name, "
            "sum(l.amount) AS amount FROM lines l "
            "LEFT JOIN app.expenses x ON l.doc_type = 'expenses' AND x.id = l.doc_id "
            "LEFT JOIN app.expense_categories c ON c.id = COALESCE(x.category_id, CASE WHEN "
            f"l.analytics->>'expense_category_id' ~ {_UUID_RE} THEN CAST(l.analytics->>'expense_category_id' "
            f"AS uuid) "
            "END) "
            "GROUP BY l.branch_id, l.account, l.doc_type, c.id, c.name"
        )
        rows = await s.execute(text(sql), params)
        return [
            ExpenseLine(r.branch_id, r.account, r.doc_type, r.category_id, r.category_name, _d(r.amount))
            for r in rows
            if _d(r.amount) != 0
        ]

    # --- discounts and margin (US-M03-03)
    # --------------------------------------------------------------------
    async def discounts(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches, group_by: str
    ) -> list[DiscountAgg]:
        keys = {
            "day": "CAST(x.doc_date AS text)",
            "branch": "CAST(x.branch_id AS text)",
            "cashier": "CAST(x.created_by AS text)",
            "product": "CAST(l.product_id AS text)",
        }
        key = keys[group_by]
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to}
        branch = _branch("x.branch_id", branch_ids, params)
        sql = (
            "WITH sold AS ("  # noqa: S608
            f"  SELECT {key} AS k, sum(l.line_total) AS total, sum(l.discount_amount) AS disc, "
            "  sum(l.discount_amount * 100 / (100 + l.vat_rate)) AS disc_net, "
            "  sum(l.line_total - l.vat_amount) AS rev, sum(l.cost_amount) AS cost "
            "  FROM app.sale_lines l JOIN app.sales x ON x.id = l.sale_id "
            f"  WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b{branch} GROUP BY 1), "
            "returned AS ("
            f"  SELECT {key} AS k, sum(l.line_total) AS total, "
            "  COALESCE(sum(sl.discount_amount * l.qty / sl.qty), 0) AS disc, "
            "  COALESCE(sum(sl.discount_amount * l.qty / sl.qty * 100 / (100 + sl.vat_rate)), 0) AS "
            "disc_net, "
            "  sum(l.line_total - l.vat_amount) AS rev, sum(l.cost_amount) AS cost "
            "  FROM app.return_lines l JOIN app.returns x ON x.id = l.return_id "
            "  LEFT JOIN app.sale_lines sl ON sl.id = l.sale_line_id "
            f"  WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b{branch} GROUP BY 1) "
            "SELECT COALESCE(sold.k, returned.k) AS k, "
            "COALESCE(sold.total, 0) - COALESCE(returned.total, 0) AS total, "
            "COALESCE(sold.disc, 0) - COALESCE(returned.disc, 0) AS disc, "
            "COALESCE(sold.disc_net, 0) - COALESCE(returned.disc_net, 0) AS disc_net, "
            "COALESCE(sold.rev, 0) - COALESCE(returned.rev, 0) AS rev, "
            "COALESCE(sold.cost, 0) - COALESCE(returned.cost, 0) AS cost "
            "FROM sold FULL JOIN returned ON returned.k = sold.k"
        )
        rows = list(await s.execute(text(sql), params))
        labels: dict[str, str] = {}
        keys_found = [r.k for r in rows]
        table = {"branch": "branches", "cashier": "users", "product": "products"}.get(group_by)
        if keys_found and table is not None:
            found = await s.execute(
                text(f"SELECT CAST(id AS text) AS k, name FROM app.{table} WHERE CAST(id AS text) = ANY(:k)"),  # noqa: S608
                {"k": keys_found},
            )
            labels = {r.k: r.name for r in found}
        out = [
            DiscountAgg(r.k, labels.get(r.k), _d(r.total), _d(r.disc), _d(r.disc_net), _d(r.rev), _d(r.cost))
            for r in rows
        ]
        if group_by == "day":
            out.sort(key=lambda a: a.group_key)
        else:
            out.sort(key=lambda a: (-a.discount_total, a.group_label or "", a.group_key))
        return out

    # --- stock (20 #20, US-M04-03, WEB-10)
    # -------------------------------------------------------------------
    async def stock(
        self,
        s: AsyncSession,
        branch_ids: Branches,
        *,
        warehouse_id: UUID | None,
        search: str | None,
        category_id: UUID | None,
    ) -> list[StockRow]:
        params: dict[str, Any] = {}
        where = [
            "NOT (p.archived_at IS NOT NULL AND b.qty = 0 AND b.value = 0)",
        ]
        branch = _branch("w.branch_id", branch_ids, params)
        if warehouse_id is not None:
            where.append("b.warehouse_id = :wh")
            params["wh"] = warehouse_id
        if category_id is not None:
            where.append("p.category_id = :cat")
            params["cat"] = category_id
        if search:
            where.append(
                "(p.name ILIKE :q OR p.name_ru ILIKE :q OR EXISTS (SELECT 1 FROM app.product_barcodes pb "
                "WHERE pb.product_id = p.id AND pb.barcode = :raw))"
            )
            params["q"] = _like(search)
            params["raw"] = search
        sql = (
            "SELECT p.id, p.name, p.name_ru, p.unit_code, p.category_id, pc.name AS "  # noqa: S608
            "category_name, "
            "(SELECT pb.barcode FROM app.product_barcodes pb WHERE pb.product_id = p.id ORDER BY "
            "CASE pb.kind WHEN 'ean' THEN 0 WHEN 'internal' THEN 1 ELSE 2 END, pb.id LIMIT 1) AS barcode, "
            "p.is_marked, p.is_weighed, p.min_stock, w.branch_id, sum(b.qty) AS qty, sum(b.value) AS value, "
            "bool_or(p.min_stock IS NOT NULL AND b.qty <= p.min_stock) AS below_min "
            "FROM app.stock_balances b JOIN app.warehouses w ON w.id = b.warehouse_id "
            "JOIN app.products p ON p.id = b.product_id "
            "LEFT JOIN app.product_categories pc ON pc.id = p.category_id "
            f"WHERE {' AND '.join(where)}{branch} "
            "GROUP BY p.id, pc.name, w.branch_id ORDER BY p.name, p.id, w.branch_id"
        )
        rows = await s.execute(text(sql), params)
        return [
            StockRow(
                product_id=r.id,
                name=r.name,
                name_ru=r.name_ru,
                unit_code=r.unit_code,
                category_id=r.category_id,
                category_name=r.category_name,
                barcode=r.barcode,
                is_marked=bool(r.is_marked),
                is_weighed=bool(r.is_weighed),
                min_stock=None if r.min_stock is None else Decimal(r.min_stock),
                branch_id=r.branch_id,
                qty=Decimal(r.qty),
                value=_d(r.value),
                below_min=bool(r.below_min),
            )
            for r in rows
        ]

    async def low_stock(self, s: AsyncSession, branch_ids: Branches) -> dict[UUID, set[UUID]]:
        params: dict[str, Any] = {}
        branch = _branch("w.branch_id", branch_ids, params)
        rows = await s.execute(
            text(
                "SELECT DISTINCT w.branch_id, b.product_id FROM app.stock_balances b "  # noqa: S608
                "JOIN app.warehouses w ON w.id = b.warehouse_id JOIN app.products p ON p.id = b.product_id "
                f"WHERE p.min_stock IS NOT NULL AND p.archived_at IS NULL AND b.qty <= p.min_stock{branch}"
            ),
            params,
        )
        out: dict[UUID, set[UUID]] = defaultdict(set)
        for r in rows:
            out[r.branch_id].add(r.product_id)
        return dict(out)

    async def stock_value(self, s: AsyncSession, branch_ids: Branches) -> tuple[Decimal, int]:
        """BO-02 «Ombor qiymati»: Σ ``stock_balances.value`` and the number of products with stock."""
        params: dict[str, Any] = {}
        branch = _branch("w.branch_id", branch_ids, params)
        row = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(b.value), 0) AS value, count(DISTINCT b.product_id) "  # noqa: S608
                    "FILTER (WHERE b.qty > 0) "
                    "AS positions FROM app.stock_balances b JOIN app.warehouses w ON w.id = b.warehouse_id "
                    f"WHERE true{branch}"
                ),
                params,
            )
        ).one()
        return _d(row.value), int(row.positions)

    async def warehouse_branch(self, s: AsyncSession, warehouse_id: UUID) -> UUID | None:
        value = (
            await s.execute(text("SELECT branch_id FROM app.warehouses WHERE id = :w"), {"w": warehouse_id})
        ).scalar()
        return value if isinstance(value, UUID) else None

    async def expiring_lots(self, s: AsyncSession, branch_ids: Branches, until: date) -> int:
        params: dict[str, Any] = {"until": until}
        branch = _branch("w.branch_id", branch_ids, params)
        value = (
            await s.execute(
                text(
                    "SELECT count(*) FROM app.stock_lots l JOIN app.warehouses w ON w.id = "  # noqa: S608
                    "l.warehouse_id "
                    "WHERE l.expiry_date IS NOT NULL AND l.expiry_date <= :until "
                    f"AND l.qty_left - l.blocked_qty > 0{branch}"
                ),
                params,
            )
        ).scalar()
        return int(value or 0)

    # --- cash (M16)
    # ------------------------------------------------------------------------------------------
    async def register_cash(self, s: AsyncSession, branch_ids: Branches, at: datetime) -> list[RegisterCash]:
        """Drawer cash at ``at``: the register's last shift opened before ``at`` — its counted cash when it
        was
        closed before ``at``, else ``opening_cash + Σ cash_moves(shift, cash)`` up to ``at`` (18 §3.2)."""
        params: dict[str, Any] = {"at": at}
        branch = _branch("cr.branch_id", branch_ids, params)
        sql = (
            "SELECT cr.id, cr.name, cr.branch_id, CASE WHEN sh.id IS NULL THEN 0 "  # noqa: S608
            "WHEN sh.status = 'closed' AND sh.closed_at < :at THEN sh.counted_cash "
            "ELSE sh.opening_cash + COALESCE((SELECT sum(cm.amount) FROM app.cash_moves cm WHERE cm.shift_id "
            "= sh.id "
            "AND cm.method = 'cash' AND cm.created_at < :at), 0) END AS cash "
            "FROM app.cash_registers cr LEFT JOIN LATERAL (SELECT x.id, x.status, x.closed_at, "
            "x.counted_cash, "
            "x.opening_cash FROM app.shifts x WHERE x.cash_register_id = cr.id AND x.opened_at < :at "
            "ORDER BY x.shift_no DESC LIMIT 1) sh ON true "
            f"WHERE cr.archived_at IS NULL{branch} ORDER BY cr.name, cr.id"
        )
        rows = await s.execute(text(sql), params)
        return [RegisterCash(r.id, r.name, r.branch_id, _d(r.cash)) for r in rows]

    # --- debts (M08)
    # -----------------------------------------------------------------------------------------
    async def new_debts(self, s: AsyncSession, rng: DateRange, branch_ids: Branches) -> dict[UUID, Decimal]:
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to}
        branch = _branch("x.branch_id", branch_ids, params)
        rows = await s.execute(
            text(
                "SELECT x.branch_id, sum(p.amount) AS amount FROM app.sale_payments p "  # noqa: S608
                "JOIN app.sales x ON x.id = p.sale_id WHERE p.method = 'debt' AND x.status = 'posted' "
                f"AND x.doc_date BETWEEN :a AND :b{branch} GROUP BY x.branch_id"
            ),
            params,
        )
        return {r.branch_id: _d(r.amount) for r in rows}

    async def debt_payments(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> dict[UUID, Decimal]:
        params: dict[str, Any] = {"a": rng.date_from, "b": rng.date_to}
        branch = _branch("x.branch_id", branch_ids, params)
        rows = await s.execute(
            text(
                "SELECT x.branch_id, sum(x.amount) AS amount FROM app.debt_payments x "  # noqa: S608
                f"WHERE x.status = 'posted' AND x.doc_date BETWEEN :a AND :b{branch} GROUP BY x.branch_id"
            ),
            params,
        )
        return {r.branch_id: _d(r.amount) for r in rows}

    async def receivables(self, s: AsyncSession) -> tuple[list[Counterparty], list[DebtDoc]]:
        cps = await s.execute(
            text(
                "SELECT c.id, c.name, c.phone, b.balance FROM app.debt_balances b "
                "JOIN app.counterparties c ON c.id = b.counterparty_id "
                "WHERE b.direction = 'receivable' AND b.balance > 0 ORDER BY c.name, c.id"
            )
        )
        counterparties = [Counterparty(r.id, r.name, r.phone, _d(r.balance)) for r in cps]
        if not counterparties:
            return [], []
        docs = await s.execute(
            text(
                "WITH cps AS (SELECT counterparty_id FROM app.debt_balances WHERE direction = 'receivable' "
                "AND balance > 0), "
                "own AS (SELECT m.doc_type, m.doc_id, m.counterparty_id, sum(m.amount) AS amount, "
                "max(m.due_date) AS due FROM app.debt_moves m WHERE m.direction = 'receivable' "
                "AND m.doc_type IN ('sales','debt_openings') AND m.counterparty_id IN (SELECT "
                "counterparty_id "
                "FROM cps) GROUP BY m.doc_type, m.doc_id, m.counterparty_id), "
                "alloc AS (SELECT a.target_doc_type, a.target_doc_id, sum(a.amount) AS amount "
                "FROM app.debt_payment_allocations a JOIN app.debt_payments p ON p.id = a.debt_payment_id "
                "WHERE p.status = 'posted' AND a.target_doc_type IN ('sales','debt_openings') "
                "GROUP BY a.target_doc_type, a.target_doc_id), "
                "ret AS (SELECT r.sale_id, sum(m.amount) AS amount FROM app.debt_moves m "
                "JOIN app.returns r ON r.id = m.doc_id WHERE m.doc_type = 'returns' AND m.direction = "
                "'receivable' "
                "AND r.sale_id IS NOT NULL GROUP BY r.sale_id) "
                "SELECT own.counterparty_id, COALESCE(x.branch_id, o.branch_id) AS branch_id, own.doc_type, "
                "own.doc_id, COALESCE(x.doc_date, o.doc_date) AS doc_date, COALESCE(own.due, o.due_date) AS "
                "due, "
                "own.amount - COALESCE(alloc.amount, 0) + COALESCE(ret.amount, 0) AS open "
                "FROM own LEFT JOIN app.sales x ON own.doc_type = 'sales' AND x.id = own.doc_id "
                "LEFT JOIN app.debt_openings o ON own.doc_type = 'debt_openings' AND o.id = own.doc_id "
                "LEFT JOIN alloc ON alloc.target_doc_type = own.doc_type AND alloc.target_doc_id = "
                "own.doc_id "
                "LEFT JOIN ret ON own.doc_type = 'sales' AND ret.sale_id = own.doc_id"
            )
        )
        out = [
            DebtDoc(r.counterparty_id, r.branch_id, r.doc_type, r.doc_id, r.doc_date, r.due, _d(r.open))
            for r in docs
            if r.branch_id is not None and r.doc_date is not None
        ]
        return counterparties, out

    # --- alerts ---------------------------------------------------------------------------------------------
    async def unsynced_devices(self, s: AsyncSession, branch_ids: Branches) -> UnsyncedDevices:
        params: dict[str, Any] = {}
        branch = _branch("cr.branch_id", branch_ids, params)
        row = (
            await s.execute(
                text(
                    "SELECT count(*) AS n, min(d.outbox_oldest_pending_at) AS oldest FROM "  # noqa: S608
                    "app.devices d "
                    "LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id "
                    "WHERE d.kind IN ('web','android') AND d.revoked_at IS NULL "
                    f"AND COALESCE(d.outbox_pending_count, 0) > 0{branch}"
                ),
                params,
            )
        ).one()
        return UnsyncedDevices(int(row.n), row.oldest)

    async def cash_variance(
        self, s: AsyncSession, rng: DateRange, branch_ids: Branches
    ) -> tuple[int, Decimal]:
        start, end = day_bounds(rng)
        params: dict[str, Any] = {"start": start, "end": end}
        branch = _branch("x.branch_id", branch_ids, params)
        row = (
            await s.execute(
                text(
                    "SELECT count(*) AS n, COALESCE(sum(abs(x.variance)), 0) AS total FROM "  # noqa: S608
                    "app.shifts x "
                    "WHERE x.status = 'closed' AND x.variance <> 0 AND x.closed_at >= :start AND x.closed_at "
                    "< :end"
                    f"{branch}"
                ),
                params,
            )
        ).one()
        return int(row.n), _d(row.total)

    async def pending_approvals(self, s: AsyncSession, branch_ids: Branches) -> list[ApprovalPending]:
        params: dict[str, Any] = {}
        branch = _branch("x.branch_id", branch_ids, params)
        rows = await s.execute(
            text(
                "SELECT x.permission_code, x.kind, x.requested_value FROM app.approval_requests "  # noqa: S608
                "x "
                f"WHERE x.status = 'pending' AND x.expires_at > now(){branch}"
            ),
            params,
        )
        return [
            ApprovalPending(
                r.permission_code, r.kind, None if r.requested_value is None else Decimal(r.requested_value)
            )
            for r in rows
        ]

    async def fiscal_unacked(self, s: AsyncSession, branch_ids: Branches, older_than: datetime) -> int:
        params: dict[str, Any] = {"older": older_than}
        branch = _branch("cr.branch_id", branch_ids, params)
        value = (
            await s.execute(
                text(
                    "SELECT count(DISTINCT f.cash_register_id) FROM app.fiscal_receipts f "  # noqa: S608
                    "JOIN app.cash_registers cr ON cr.id = f.cash_register_id "
                    "WHERE f.kind <> 'z_report' AND f.ofd_acked_at IS NULL "
                    f"AND COALESCE(f.fiscal_at, f.created_at) < :older{branch}"
                ),
                params,
            )
        ).scalar()
        return int(value or 0)

    async def tenant_counts(self, s: AsyncSession) -> dict[str, int]:
        row = (
            await s.execute(
                text(
                    "SELECT (SELECT count(*) FROM app.state_reports WHERE status = 'diff_found') AS diffs, "
                    "(SELECT count(*) FROM app.einvoices WHERE direction = 'in' AND status = 'received') AS "
                    "einv, "
                    "(SELECT count(*) FROM app.sync_exceptions WHERE reviewed_at IS NULL) AS exc"
                )
            )
        ).one()
        return {
            "state_report_diff": int(row.diffs),
            "einvoices_awaiting_signature": int(row.einv),
            "sync_exceptions": int(row.exc),
        }
