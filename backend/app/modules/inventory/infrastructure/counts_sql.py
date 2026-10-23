"""SQL of ``stock_counts`` / ``count_lines`` (19 §14; caller's transaction, RLS)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.application.stock_counts import CountLine, StockCount

_HEAD = (
    "id, branch_id, number, doc_date, status, warehouse_id, started_at, responsible_user_id, created_by, "
    "created_at, posted_at, cancelled_at, cancel_reason, comment"
)


class SqlCountRepository:
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.stock_counts (id, tenant_id, branch_id, warehouse_id, doc_date, started_at, "
                "responsible_user_id, created_by, comment) VALUES (:id, :tenant_id, :branch_id, "
                ":warehouse_id, "
                ":doc_date, :started_at, :responsible_user_id, :created_by, :comment)"
            ),
            dict(head),
        )
        if lines:
            await s.execute(
                text(
                    "INSERT INTO app.count_lines (id, tenant_id, count_id, line_no, product_id, "
                    "snapshot_qty, expected) "
                    "VALUES (:id, :tenant_id, :count_id, :line_no, :product_id, :snapshot_qty, :expected)"
                ),
                [dict(x) for x in lines],
            )

    async def _lines(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, list[CountLine]]:
        out: dict[UUID, list[CountLine]] = {}
        if not ids:
            return out
        rows = await s.execute(
            text(
                "SELECT l.count_id, l.id, l.line_no, l.product_id, p.name, l.snapshot_qty, l.expected, "
                "l.counted, "
                "l.counted_at FROM app.count_lines l JOIN app.products p ON p.id = l.product_id "
                "WHERE l.count_id = ANY(CAST(:ids AS uuid[])) ORDER BY l.count_id, l.line_no"
            ),
            {"ids": [str(i) for i in ids]},
        )
        for r in rows:
            out.setdefault(r[0], []).append(CountLine(*r[1:]))
        return out

    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> StockCount | None:
        sql = f"SELECT {_HEAD} FROM app.stock_counts WHERE id = :id" + (" FOR UPDATE" if lock else "")  # noqa: S608
        row = (await s.execute(text(sql), {"id": doc_id})).first()
        if row is None:
            return None
        lines = await self._lines(s, [doc_id])
        return StockCount(**dict(row._mapping), lines=tuple(lines.get(doc_id, [])))

    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[StockCount]:
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
                    f"SELECT {_HEAD} FROM app.stock_counts {clause}ORDER BY created_at DESC, id DESC LIMIT :n"  # noqa: S608
                ),
                params,
            )
        )
        lines = await self._lines(s, [r._mapping["id"] for r in rows])
        return [StockCount(**dict(r._mapping), lines=tuple(lines.get(r._mapping["id"], []))) for r in rows]

    async def snapshot(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID] | None, at: datetime
    ) -> dict[UUID, Decimal]:
        """Balance at ``at`` = ``stock_balances.qty − Σ stock_moves.qty (moved_at > at)``; without
        ``product_ids`` — every product with a non-zero balance row in the warehouse."""
        params: dict[str, Any] = {"w": warehouse_id, "at": at}
        if product_ids is None:
            pick = "SELECT product_id FROM app.stock_balances WHERE warehouse_id = :w AND qty <> 0"
        else:
            pick = "SELECT unnest(CAST(:ids AS uuid[]))"
            params["ids"] = [str(i) for i in product_ids]
        rows = await s.execute(
            text(
                f"WITH p(product_id) AS ({pick}) SELECT p.product_id, COALESCE(b.qty, 0) - COALESCE(("  # noqa: S608
                "SELECT sum(m.qty) FROM app.stock_moves m WHERE m.warehouse_id = :w AND m.product_id = "
                "p.product_id "
                "AND m.moved_at > :at), 0) FROM p LEFT JOIN app.stock_balances b ON b.warehouse_id = :w "
                "AND b.product_id = p.product_id JOIN app.products pr ON pr.id = p.product_id ORDER BY "
                "pr.name, p.product_id"
            ),
            params,
        )
        return {r[0]: Decimal(r[1]).quantize(Decimal("0.001")) for r in rows}

    async def moves_since(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        product_ids: Sequence[UUID],
        since: datetime,
        exclude_doc: UUID,
    ) -> dict[UUID, list[tuple[datetime, Decimal]]]:
        out: dict[UUID, list[tuple[datetime, Decimal]]] = {}
        if not product_ids:
            return out
        rows = await s.execute(
            text(
                "SELECT product_id, moved_at, qty FROM app.stock_moves WHERE warehouse_id = :w "
                "AND product_id = ANY(CAST(:ids AS uuid[])) AND moved_at > :since "
                "AND NOT (doc_type = 'stock_counts' AND doc_id = :doc) ORDER BY moved_at, created_at, id"
            ),
            {
                "w": warehouse_id,
                "ids": [str(i) for i in set(product_ids)],
                "since": since,
                "doc": exclude_doc,
            },
        )
        for r in rows:
            out.setdefault(r[0], []).append((r[1], r[2]))
        return out

    async def set_counted(self, s: AsyncSession, line_id: UUID, counted: Decimal, at: datetime) -> None:
        await s.execute(
            text("UPDATE app.count_lines SET counted = :c, counted_at = :at WHERE id = :id"),
            {"c": counted, "at": at, "id": line_id},
        )

    async def add_line(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.count_lines (id, tenant_id, count_id, line_no, product_id, snapshot_qty, "
                "expected, "
                "counted, counted_at) VALUES (:id, :tenant_id, :count_id, :line_no, :product_id, "
                ":snapshot_qty, "
                ":expected, :counted, :counted_at)"
            ),
            dict(row),
        )

    async def set_status(self, s: AsyncSession, doc_id: UUID, status: str) -> None:
        await s.execute(
            text("UPDATE app.stock_counts SET status = :st, updated_at = now() WHERE id = :id"),
            {"st": status, "id": doc_id},
        )

    async def mark_posted(
        self, s: AsyncSession, doc_id: UUID, number: str, at: datetime, lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.stock_counts SET status = 'posted', number = :n, posted_at = :at, updated_at = "
                "now() "
                "WHERE id = :id"
            ),
            {"n": number, "at": at, "id": doc_id},
        )
        if lines:
            await s.execute(
                text(
                    "UPDATE app.count_lines SET expected = :expected, counted = :counted, counted_at = "
                    ":counted_at "
                    "WHERE id = :id"
                ),
                [dict(x) for x in lines],
            )

    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.stock_counts SET status = 'cancelled', cancelled_at = now(), cancelled_by = :u, "
                "cancel_reason = :r, updated_at = now() WHERE id = :id"
            ),
            {"u": user_id, "r": reason, "id": doc_id},
        )

    async def active_member(self, s: AsyncSession, user_id: UUID) -> bool:
        found = (
            await s.execute(
                text("SELECT 1 FROM app.memberships WHERE user_id = :u AND status = 'active'"), {"u": user_id}
            )
        ).first()
        return found is not None

    async def balances(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[Decimal, Decimal]]:
        if not product_ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT product_id, qty, value FROM app.stock_balances WHERE warehouse_id = :w "
                "AND product_id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"w": warehouse_id, "ids": [str(i) for i in set(product_ids)]},
        )
        return {r[0]: (r[1], r[2]) for r in rows}
