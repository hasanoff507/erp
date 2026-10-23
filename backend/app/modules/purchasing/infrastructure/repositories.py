"""Purchasing SQL (12 ``purchase_orders``, ``po_lines``; reads ``goods_receipts``/``receipt_lines``).

Runs inside the caller's ``tenant_transaction`` (RLS-bound).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchasing.application.ports import PoFilter, WarehouseRef
from app.modules.purchasing.domain.purchase_orders import PoLine, PurchaseOrder

_UPDATABLE = frozenset(
    {
        "doc_date",
        "comment",
        "supplier_id",
        "warehouse_id",
        "branch_id",
        "status",
        "number",
        "posted_at",
        "cancelled_at",
        "cancelled_by",
        "cancel_reason",
    }
)

_HEADER = (
    "SELECT po.id, po.branch_id, po.number, po.doc_date, po.status, po.supplier_id, "
    "c.name AS supplier_name, c.stir AS supplier_stir, po.warehouse_id, po.created_by, "
    "u.name AS created_by_name, po.created_at, po.updated_at, po.posted_at AS sent_at, po.cancelled_at, "
    "po.cancelled_by, po.cancel_reason, po.comment, t.total, COALESCE(t.line_count, 0) AS line_count "
    "FROM app.purchase_orders po "
    "LEFT JOIN app.counterparties c ON c.id = po.supplier_id "
    "LEFT JOIN app.users u ON u.id = po.created_by "
    "LEFT JOIN LATERAL (SELECT count(*) AS line_count, sum(l.qty * l.price) AS total "
    "  FROM app.po_lines l WHERE l.po_id = po.id) t ON true "
)


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _po(m: Any, lines: tuple[PoLine, ...] = ()) -> PurchaseOrder:
    total = m["total"]
    return PurchaseOrder(
        id=m["id"],
        branch_id=m["branch_id"],
        number=m["number"],
        doc_date=m["doc_date"],
        status=m["status"],
        supplier_id=m["supplier_id"],
        supplier_name=m["supplier_name"],
        supplier_stir=m["supplier_stir"],
        warehouse_id=m["warehouse_id"],
        created_by=m["created_by"],
        created_by_name=m["created_by_name"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
        sent_at=m["sent_at"],
        cancelled_at=m["cancelled_at"],
        cancelled_by=m["cancelled_by"],
        cancel_reason=m["cancel_reason"],
        comment=m["comment"],
        total=None if total is None else Decimal(total),
        line_count=int(m["line_count"]),
        lines=lines,
    )


class SqlPurchaseOrderRepository:
    async def get(self, s: AsyncSession, po_id: UUID, *, lock: bool = False) -> PurchaseOrder | None:
        if lock:
            # lock the order row itself (joins and the lateral aggregate cannot be locked)
            locked = await s.execute(
                text("SELECT id FROM app.purchase_orders WHERE id = :id FOR UPDATE"), {"id": po_id}
            )
            if locked.first() is None:
                return None
        row = (await s.execute(text(_HEADER + "WHERE po.id = :id"), {"id": po_id})).first()
        if row is None:
            return None
        line_rows = await s.execute(
            text(
                "SELECT l.id, l.line_no, l.product_id, l.qty, l.price, p.name AS product_name, p.unit_code "
                "FROM app.po_lines l LEFT JOIN app.products p ON p.id = l.product_id "
                "WHERE l.po_id = :id ORDER BY l.line_no"
            ),
            {"id": po_id},
        )
        lines = tuple(
            PoLine(
                id=r.id,
                line_no=r.line_no,
                product_id=r.product_id,
                qty=r.qty,
                price=r.price,
                product_name=r.product_name,
                unit_code=r.unit_code,
            )
            for r in line_rows
        )
        return _po(row._mapping, lines)

    async def list_page(
        self, s: AsyncSession, flt: PoFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[PurchaseOrder]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        expanding: list[str] = []
        if flt.branch_ids is not None:
            where.append("po.branch_id IN :branches")
            params["branches"] = list(flt.branch_ids)
            expanding.append("branches")
        if flt.supplier_id is not None:
            where.append("po.supplier_id = :supplier_id")
            params["supplier_id"] = flt.supplier_id
        if flt.status is not None:
            where.append("po.status = :status")
            params["status"] = flt.status
        if flt.date_from is not None:
            where.append("po.doc_date >= :date_from")
            params["date_from"] = flt.date_from
        if flt.date_to is not None:
            where.append("po.doc_date <= :date_to")
            params["date_to"] = flt.date_to
        if flt.search:
            where.append("(po.number ILIKE :q OR c.name ILIKE :q)")
            params["q"] = _like(flt.search)
        if after is not None:
            where.append("(po.created_at, po.id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        clause = ("WHERE " + " AND ".join(where) + " ") if where else ""
        stmt = text(_HEADER + clause + "ORDER BY po.created_at DESC, po.id DESC LIMIT :limit")
        if expanding:
            stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding))
        rows = await s.execute(stmt, params)
        return [_po(r._mapping) for r in rows]

    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.purchase_orders (id, tenant_id, branch_id, doc_date, supplier_id, "
                "warehouse_id, created_by, comment) "
                "VALUES (:id, :tenant_id, :branch_id, :doc_date, :supplier_id, :warehouse_id, "
                ":created_by, :comment)"
            ),
            dict(row),
        )

    async def update(self, s: AsyncSession, po_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _UPDATABLE]
        if not cols:
            return
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        await s.execute(
            text(f"UPDATE app.purchase_orders SET {assignments} WHERE id = :id"),  # noqa: S608
            {**{c: values[c] for c in cols}, "id": po_id},
        )

    async def replace_lines(
        self, s: AsyncSession, tenant_id: UUID, po_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(text("DELETE FROM app.po_lines WHERE po_id = :id"), {"id": po_id})
        if rows:
            await s.execute(
                text(
                    "INSERT INTO app.po_lines (id, tenant_id, po_id, line_no, product_id, qty, price) "
                    "VALUES (:id, :tenant_id, :po_id, :line_no, :product_id, :qty, :price)"
                ),
                [dict(r) for r in rows],
            )

    async def received_qty(self, s: AsyncSession, po_id: UUID) -> dict[UUID, Decimal]:
        rows = await s.execute(
            text(
                "SELECT rl.product_id, sum(rl.qty) FROM app.receipt_lines rl "
                "JOIN app.goods_receipts gr ON gr.id = rl.receipt_id "
                "WHERE gr.po_id = :id AND gr.status = 'posted' GROUP BY rl.product_id"
            ),
            {"id": po_id},
        )
        return {r[0]: r[1] for r in rows}

    async def warehouse(self, s: AsyncSession, warehouse_id: UUID) -> WarehouseRef | None:
        row = (
            await s.execute(
                text("SELECT id, branch_id, archived_at IS NOT NULL FROM app.warehouses WHERE id = :id"),
                {"id": warehouse_id},
            )
        ).first()
        return WarehouseRef(id=row[0], branch_id=row[1], archived=bool(row[2])) if row else None

    async def product_archived_flags(self, s: AsyncSession, product_ids: Sequence[UUID]) -> dict[UUID, bool]:
        if not product_ids:
            return {}
        rows = await s.execute(
            text("SELECT id, archived_at IS NOT NULL FROM app.products WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": list(dict.fromkeys(product_ids))},
        )
        return {r[0]: bool(r[1]) for r in rows}
