"""SQL of ``stock_openings``/``opening_lines`` and of the stock read API (19 §7, §16; caller's txn, RLS)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.application.openings import Opening, OpeningLine
from app.modules.inventory.application.queries import BalanceFilter, LotFilter, MoveFilter

_HEAD = (
    "id, branch_id, warehouse_id, number, doc_date, status, comment, created_at, posted_at, cancelled_at, "
    "cancel_reason"
)


def _utc(raw: str) -> datetime:
    """A cursor timestamp (``to_char(... AT TIME ZONE 'UTC')``, microseconds) as an aware instant."""
    return datetime.fromisoformat(raw).replace(tzinfo=UTC)


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class SqlOpeningRepository:
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.stock_openings (id, tenant_id, branch_id, warehouse_id, doc_date, "
                "created_by, "
                "comment) VALUES (:id, :tenant_id, :branch_id, :warehouse_id, :doc_date, :created_by, "
                ":comment)"
            ),
            dict(head),
        )
        await s.execute(
            text(
                "INSERT INTO app.opening_lines (id, tenant_id, opening_id, line_no, product_id, qty, "
                "unit_cost, "
                "expiry_date) VALUES (:id, :tenant_id, :opening_id, :line_no, :product_id, :qty, :unit_cost, "
                ":expiry_date)"
            ),
            [dict(x) for x in lines],
        )

    async def _lines(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, list[OpeningLine]]:
        out: dict[UUID, list[OpeningLine]] = {}
        if not ids:
            return out
        rows = await s.execute(
            text(
                "SELECT opening_id, id, line_no, product_id, qty, unit_cost, expiry_date FROM "
                "app.opening_lines "
                "WHERE opening_id = ANY(CAST(:ids AS uuid[])) ORDER BY opening_id, line_no"
            ),
            {"ids": [str(i) for i in ids]},
        )
        for r in rows:
            out.setdefault(r[0], []).append(OpeningLine(r[1], r[2], r[3], r[4], r[5], r[6]))
        return out

    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Opening | None:
        sql = f"SELECT {_HEAD} FROM app.stock_openings WHERE id = :id" + (" FOR UPDATE" if lock else "")  # noqa: S608
        row = (await s.execute(text(sql), {"id": doc_id})).first()
        if row is None:
            return None
        lines = await self._lines(s, [doc_id])
        return Opening(**dict(row._mapping), lines=tuple(lines.get(doc_id, [])))

    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[Opening]:
        where: list[str] = []
        params: dict[str, Any] = {"n": limit}
        if status:
            where.append("status = :status")
            params["status"] = status
        if warehouse_id is not None:
            where.append("warehouse_id = :wh")
            params["wh"] = warehouse_id
        if branch_ids is not None:
            where.append("branch_id = ANY(CAST(:branches AS uuid[]))")
            params["branches"] = [str(b) for b in branch_ids]
        if after is not None:
            where.append("(created_at, id) < (:at, :aid)")
            params["at"], params["aid"] = after
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        rows = list(
            await s.execute(
                text(
                    f"SELECT {_HEAD} FROM app.stock_openings {clause}"  # noqa: S608
                    "ORDER BY created_at DESC, id DESC LIMIT :n"
                ),
                params,
            )
        )
        lines = await self._lines(s, [r._mapping["id"] for r in rows])
        return [Opening(**dict(r._mapping), lines=tuple(lines.get(r._mapping["id"], []))) for r in rows]

    async def mark_posted(self, s: AsyncSession, doc_id: UUID, number: str, posted_at: datetime) -> None:
        await s.execute(
            text(
                "UPDATE app.stock_openings SET status = 'posted', number = :n, posted_at = :at, updated_at = "
                "now() "
                "WHERE id = :id"
            ),
            {"n": number, "at": posted_at, "id": doc_id},
        )

    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.stock_openings SET status = 'cancelled', cancelled_at = now(), cancelled_by = "
                ":u, "
                "cancel_reason = :r, updated_at = now() WHERE id = :id"
            ),
            {"u": user_id, "r": reason, "id": doc_id},
        )


class SqlStockQueryRepository:
    async def balances(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        flt: BalanceFilter,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        where = ["b.warehouse_id = :wh"]
        params: dict[str, Any] = {"wh": warehouse_id, "n": limit}
        if flt.product_id is not None:
            where.append("b.product_id = :pid")
            params["pid"] = flt.product_id
        if flt.search:
            where.append(
                "(p.name ILIKE :like OR p.name_ru ILIKE :like OR EXISTS (SELECT 1 FROM app.product_barcodes "
                "pb "
                "WHERE pb.product_id = p.id AND pb.barcode = :search))"
            )
            params["like"], params["search"] = _like(flt.search), flt.search
        if flt.low_stock:
            where.append("p.min_stock IS NOT NULL AND b.qty <= p.min_stock")
        if after is not None:
            where.append("(p.name, b.product_id) > (:after_name, :after_id)")
            params["after_name"], params["after_id"] = after
        rows = await s.execute(
            text(
                "SELECT b.product_id, p.name AS product_name, b.warehouse_id, b.qty, b.value, "  # noqa: S608
                "p.min_stock, "
                "b.updated_at, p.name AS sort FROM app.stock_balances b JOIN app.products p ON p.id = "
                "b.product_id "
                f"WHERE {' AND '.join(where)} ORDER BY p.name, b.product_id LIMIT :n"
            ),
            params,
        )
        return [dict(r._mapping) for r in rows]

    async def lots(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        flt: LotFilter,
        expiry_until: date | None,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        where = ["l.warehouse_id = :wh"]
        params: dict[str, Any] = {"wh": warehouse_id, "n": limit}
        if not flt.include_empty:
            where.append("l.qty_left > 0")
        if flt.product_id is not None:
            where.append("l.product_id = :pid")
            params["pid"] = flt.product_id
        if expiry_until is not None:
            where.append("l.expiry_date IS NOT NULL AND l.expiry_date <= :until")
            params["until"] = expiry_until
            order, sort = "l.expiry_date, l.id", "CAST(l.expiry_date AS text)"
            if after is not None:
                where.append("(l.expiry_date, l.id) > (:after_sort, :after_id)")
        else:
            order, sort = (
                "l.received_at, l.id",
                "to_char(l.received_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US')",
            )
            if after is not None:
                where.append("(l.received_at, l.id) > (:after_sort, :after_id)")
        if after is not None:
            params["after_sort"] = (
                date.fromisoformat(after[0]) if expiry_until is not None else _utc(after[0])
            )
            params["after_id"] = after[1]
        rows = await s.execute(
            text(
                "SELECT l.id, l.product_id, p.name AS product_name, l.warehouse_id, "  # noqa: S608
                "l.received_at, l.qty_in, "
                "l.qty_left, l.blocked_qty, l.unit_cost, l.expiry_date, l.receipt_line_id, "
                "l.source_doc_type, "
                f"l.source_doc_id, {sort} AS sort FROM app.stock_lots l JOIN app.products p ON p.id = "
                "l.product_id "
                f"WHERE {' AND '.join(where)} ORDER BY {order} LIMIT :n"
            ),
            params,
        )
        return [dict(r._mapping) for r in rows]

    async def moves(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        flt: MoveFilter,
        since: datetime | None,
        until: datetime | None,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        where = ["m.warehouse_id = :wh"]
        params: dict[str, Any] = {"wh": warehouse_id, "n": limit}
        if flt.product_id is not None:
            where.append("m.product_id = :pid")
            params["pid"] = flt.product_id
        if flt.doc_type:
            where.append("m.doc_type = :dt")
            params["dt"] = flt.doc_type
        if since is not None:
            where.append("m.moved_at >= :since")
            params["since"] = since
        if until is not None:
            where.append("m.moved_at <= :until")
            params["until"] = until
        if after is not None:
            where.append("(m.moved_at, m.id) < (:after_sort, :after_id)")
            params["after_sort"], params["after_id"] = _utc(after[0]), after[1]
        rows = await s.execute(
            text(
                "SELECT m.id, m.warehouse_id, m.product_id, m.lot_id, m.qty, m.cost_amount, "  # noqa: S608
                "m.doc_type, m.doc_id, "
                "m.line_id, m.reversal_of_id, m.moved_at, "
                "to_char(m.moved_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US') AS sort "
                f"FROM app.stock_moves m WHERE {' AND '.join(where)} ORDER BY m.moved_at DESC, m.id DESC "
                "LIMIT :n"
            ),
            params,
        )
        return [dict(r._mapping) for r in rows]

    async def expiring_lots(self, s: AsyncSession, today: date, until: date) -> list[dict[str, Any]]:
        rows = await s.execute(
            text(
                "SELECT l.id, l.product_id, p.name AS product_name, l.warehouse_id, w.branch_id, l.qty_left, "
                "l.expiry_date FROM app.stock_lots l JOIN app.products p ON p.id = l.product_id "
                "JOIN app.warehouses w ON w.id = l.warehouse_id WHERE l.qty_left > 0 "
                "AND l.expiry_date BETWEEN :today AND :until ORDER BY l.expiry_date, l.id"
            ),
            {"today": today, "until": until},
        )
        return [dict(r._mapping) for r in rows]

    async def low_stock(self, s: AsyncSession) -> list[dict[str, Any]]:
        rows = await s.execute(
            text(
                "SELECT b.product_id, p.name AS product_name, b.warehouse_id, w.branch_id, b.qty, "
                "p.min_stock "
                "FROM app.stock_balances b JOIN app.products p ON p.id = b.product_id "
                "JOIN app.warehouses w ON w.id = b.warehouse_id WHERE p.min_stock IS NOT NULL "
                "AND p.archived_at IS NULL AND b.qty <= p.min_stock ORDER BY p.name, b.product_id"
            )
        )
        return [dict(r._mapping) for r in rows]

    async def current_costs(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[Decimal | None, Decimal | None, Decimal | None]]:
        rows = await s.execute(
            text(
                "SELECT i.pid, "
                "(SELECT a.avg_cost FROM app.avg_costs a WHERE a.warehouse_id = :wh AND a.product_id = "
                "i.pid), "
                "(SELECT sum(l.qty_left * l.unit_cost) / NULLIF(sum(l.qty_left), 0) FROM app.stock_lots l "
                " WHERE l.warehouse_id = :wh AND l.product_id = i.pid AND l.qty_left > 0), "
                "(SELECT l.unit_cost FROM app.stock_lots l WHERE l.product_id = i.pid "
                " AND l.source_doc_type = 'goods_receipts' "
                " AND EXISTS (SELECT 1 FROM app.stock_moves m WHERE m.lot_id = l.id AND m.qty > 0 "
                "  AND m.reversal_of_id IS NULL "
                "  AND NOT EXISTS (SELECT 1 FROM app.stock_moves r WHERE r.reversal_of_id = m.id)) "
                " ORDER BY (l.warehouse_id = :wh) DESC, l.received_at DESC, l.id DESC LIMIT 1) "
                "FROM unnest(CAST(:ids AS uuid[])) AS i(pid)"
            ),
            {"wh": warehouse_id, "ids": [str(p) for p in dict.fromkeys(product_ids)]},
        )
        return {r[0]: (r[1], r[2], r[3]) for r in rows}
