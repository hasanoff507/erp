"""SQL of ``write_offs`` / ``write_off_lines`` and their approval requests (19 §15; caller's txn, RLS)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.application.write_offs import Approval, WriteOff, WriteOffLine

_HEAD = (
    "id, branch_id, number, doc_date, status, warehouse_id, responsible_user_id, promo_order_ref, "
    "source_return_id, created_by, created_at, posted_at, cancelled_at, cancel_reason, comment"
)


class SqlWriteOffRepository:
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.write_offs (id, tenant_id, branch_id, warehouse_id, doc_date, "
                "responsible_user_id, "
                "promo_order_ref, created_by, comment) VALUES (:id, :tenant_id, :branch_id, :warehouse_id, "
                ":doc_date, "
                ":responsible_user_id, :promo_order_ref, :created_by, :comment)"
            ),
            dict(head),
        )
        await s.execute(
            text(
                "INSERT INTO app.write_off_lines (id, tenant_id, write_off_id, line_no, product_id, "
                "lot_id, qty, "
                "reason, gift_kind) VALUES (:id, :tenant_id, :write_off_id, :line_no, :product_id, "
                ":lot_id, :qty, "
                ":reason, :gift_kind)"
            ),
            [dict(x) for x in lines],
        )

    async def _lines(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, list[WriteOffLine]]:
        out: dict[UUID, list[WriteOffLine]] = {}
        if not ids:
            return out
        rows = await s.execute(
            text(
                "SELECT l.write_off_id, l.id, l.line_no, l.product_id, p.name, l.lot_id, lot.expiry_date, "
                "l.qty, "
                "l.reason, l.gift_kind, l.cost_amount FROM app.write_off_lines l "
                "JOIN app.products p ON p.id = l.product_id LEFT JOIN app.stock_lots lot ON lot.id = "
                "l.lot_id "
                "WHERE l.write_off_id = ANY(CAST(:ids AS uuid[])) ORDER BY l.write_off_id, l.line_no"
            ),
            {"ids": [str(i) for i in ids]},
        )
        for r in rows:
            out.setdefault(r[0], []).append(WriteOffLine(*r[1:]))
        return out

    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> WriteOff | None:
        sql = f"SELECT {_HEAD} FROM app.write_offs WHERE id = :id" + (" FOR UPDATE" if lock else "")  # noqa: S608
        row = (await s.execute(text(sql), {"id": doc_id})).first()
        if row is None:
            return None
        lines = await self._lines(s, [doc_id])
        return WriteOff(**dict(row._mapping), lines=tuple(lines.get(doc_id, [])))

    async def page(
        self,
        s: AsyncSession,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[WriteOff]:
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
                    f"SELECT {_HEAD} FROM app.write_offs {clause}ORDER BY created_at DESC, id DESC LIMIT :n"  # noqa: S608
                ),
                params,
            )
        )
        lines = await self._lines(s, [r._mapping["id"] for r in rows])
        return [WriteOff(**dict(r._mapping), lines=tuple(lines.get(r._mapping["id"], []))) for r in rows]

    async def mark_posted(
        self, s: AsyncSession, doc_id: UUID, number: str, at: datetime, costs: Mapping[UUID, Decimal]
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.write_offs SET status = 'posted', number = :n, posted_at = :at, updated_at = "
                "now() "
                "WHERE id = :id"
            ),
            {"n": number, "at": at, "id": doc_id},
        )
        if costs:
            await s.execute(
                text("UPDATE app.write_off_lines SET cost_amount = :c WHERE id = :id"),
                [{"id": lid, "c": cost} for lid, cost in costs.items()],
            )

    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.write_offs SET status = 'cancelled', cancelled_at = now(), cancelled_by = :u, "
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

    async def latest_approval(self, s: AsyncSession, doc_id: UUID) -> Approval | None:
        # newest = the largest application uuid7 id (creation order); requested_at is the DB now() of
        # separate transactions and does not order them reliably
        row = (
            await s.execute(
                text(
                    "SELECT id, CASE WHEN status = 'pending' AND expires_at < now() THEN 'expired' ELSE "
                    "status END, requested_value "
                    "FROM app.approval_requests WHERE linked_doc_type = 'write_offs' AND linked_doc_id = :d "
                    "AND kind = 'write_off_over_limit' ORDER BY id DESC LIMIT 1"
                ),
                {"d": doc_id},
            )
        ).first()
        return Approval(row[0], row[1], row[2]) if row else None

    async def insert_approval(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.approval_requests (id, tenant_id, branch_id, kind, permission_code, "
                "requested_value, "
                "context, linked_doc_type, linked_doc_id, requested_by, expires_at) VALUES (:id, :tenant_id, "
                ":branch_id, :kind, :permission_code, :requested_value, CAST(:context AS jsonb), "
                ":linked_doc_type, "
                ":linked_doc_id, :requested_by, :expires_at)"
            ),
            dict(row),
        )

    async def consume_approval(self, s: AsyncSession, approval_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.approval_requests SET status = 'consumed', consumed_at = now(), updated_at = "
                "now() "
                "WHERE id = :id AND status = 'approved'"
            ),
            {"id": approval_id},
        )

    async def vat_payer(self, s: AsyncSession, on: date) -> bool:
        """``tenant_tax_regimes`` in force on ``on``; no row → VAT payer (13 §4.3)."""
        regime = (
            await s.execute(
                text(
                    "SELECT regime FROM app.tenant_tax_regimes WHERE valid_from <= :d "
                    "ORDER BY valid_from DESC LIMIT 1"
                ),
                {"d": on},
            )
        ).scalar()
        return regime != "turnover"

    async def vat_rates(self, s: AsyncSession, product_ids: Sequence[UUID]) -> dict[UUID, Decimal]:
        if not product_ids:
            return {}
        rows = await s.execute(
            text("SELECT id, COALESCE(vat_rate, 0) FROM app.products WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [str(i) for i in set(product_ids)]},
        )
        return {r[0]: Decimal(r[1]) for r in rows}
