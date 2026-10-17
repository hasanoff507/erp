"""SQL of ``transfers`` / ``transfer_lines`` and the outgoing e-TTN rows (19 §13; caller's txn, RLS)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.application.transfers import EttnRef, Transfer, TransferFilter, TransferLine
from app.modules.inventory.domain.transfers import overdue_hours

_HEAD = (
    "t.id, t.branch_id, t.number, t.doc_date, t.status, t.from_branch_id, t.to_branch_id, "
    "t.from_warehouse_id, "
    "t.to_warehouse_id, t.transport_mode, t.vehicle_plate, t.driver_name, t.ettn_ref, t.sent_at, t.sent_by, "
    "t.received_at, t.received_by, t.created_by, t.created_at, t.posted_at, t.cancelled_at, t.cancel_reason, "
    "t.comment, e.id AS ettn_id, e.status AS ettn_status, e.operator_doc_id AS ettn_operator_doc_id"
)
_FROM = (
    "FROM app.transfers t LEFT JOIN LATERAL (SELECT x.id, x.status, x.operator_doc_id FROM "
    "app.ettn_documents x "
    "WHERE x.transfer_id = t.id AND x.direction = 'out' ORDER BY x.created_at DESC, x.id DESC LIMIT 1) e "
    "ON true"
)


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


def _doc(row: Mapping[str, Any], lines: Sequence[TransferLine]) -> Transfer:
    data = dict(row)
    ettn_id = data.pop("ettn_id")
    ettn_status = data.pop("ettn_status")
    ettn_op = data.pop("ettn_operator_doc_id")
    ettn = EttnRef(ettn_id, ettn_status, ettn_op) if ettn_id is not None else None
    return Transfer(**data, ettn=ettn, lines=tuple(lines))


class SqlTransferRepository:
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.transfers (id, tenant_id, branch_id, doc_date, from_branch_id, "
                "to_branch_id, "
                "from_warehouse_id, to_warehouse_id, transport_mode, vehicle_plate, driver_name, "
                "created_by, comment) "
                "VALUES (:id, :tenant_id, :branch_id, :doc_date, :from_branch_id, :to_branch_id, "
                ":from_warehouse_id, "
                ":to_warehouse_id, :transport_mode, :vehicle_plate, :driver_name, :created_by, :comment)"
            ),
            dict(head),
        )
        await s.execute(
            text(
                "INSERT INTO app.transfer_lines (id, tenant_id, transfer_id, line_no, product_id, qty_sent) "
                "VALUES (:id, :tenant_id, :transfer_id, :line_no, :product_id, :qty_sent)"
            ),
            [dict(x) for x in lines],
        )

    async def _lines(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, list[TransferLine]]:
        out: dict[UUID, list[TransferLine]] = {}
        if not ids:
            return out
        rows = await s.execute(
            text(
                "SELECT l.transfer_id, l.id, l.line_no, l.product_id, p.name, l.qty_sent, l.qty_received, "
                "l.unit_cost, l.lot_allocations FROM app.transfer_lines l JOIN app.products p ON p.id = "
                "l.product_id "
                "WHERE l.transfer_id = ANY(CAST(:ids AS uuid[])) ORDER BY l.transfer_id, l.line_no"
            ),
            {"ids": [str(i) for i in ids]},
        )
        for r in rows:
            out.setdefault(r[0], []).append(
                TransferLine(r[1], r[2], r[3], r[4], r[5], r[6], r[7], tuple(_json(r[8]) or ()))
            )
        return out

    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Transfer | None:
        sql = f"SELECT {_HEAD} {_FROM} WHERE t.id = :id" + (" FOR UPDATE OF t" if lock else "")
        row = (await s.execute(text(sql), {"id": doc_id})).first()
        if row is None:
            return None
        lines = await self._lines(s, [doc_id])
        return _doc(dict(row._mapping), lines.get(doc_id, []))

    async def page(
        self,
        s: AsyncSession,
        flt: TransferFilter,
        *,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[Transfer]:
        where: list[str] = []
        params: dict[str, Any] = {"n": limit}
        if flt.status:
            where.append("t.status = :status")
            params["status"] = flt.status
        if flt.ettn_status:
            where.append("e.status = :es")
            params["es"] = flt.ettn_status
        if flt.date_from is not None:
            where.append("t.doc_date >= :df")
            params["df"] = flt.date_from
        if flt.date_to is not None:
            where.append("t.doc_date <= :dt")
            params["dt"] = flt.date_to
        if branch_ids is not None:
            where.append(
                "(t.from_branch_id = ANY(CAST(:branches AS uuid[])) OR t.to_branch_id = ANY(CAST(:branches "
                "AS uuid[])))"
            )
            params["branches"] = [str(b) for b in branch_ids]
        if after is not None:
            where.append("(t.created_at, t.id) < (:at, :aid)")
            params["at"], params["aid"] = after
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        rows = list(
            await s.execute(
                text(f"SELECT {_HEAD} {_FROM} {clause}ORDER BY t.created_at DESC, t.id DESC LIMIT :n"),
                params,
            )
        )
        lines = await self._lines(s, [r._mapping["id"] for r in rows])
        return [_doc(dict(r._mapping), lines.get(r._mapping["id"], [])) for r in rows]

    async def mark_posted(self, s: AsyncSession, doc_id: UUID, number: str, posted_at: datetime) -> None:
        await s.execute(
            text(
                "UPDATE app.transfers SET status = 'posted', number = :n, posted_at = :at, updated_at = "
                "now() "
                "WHERE id = :id"
            ),
            {"n": number, "at": posted_at, "id": doc_id},
        )

    async def mark_sent(
        self, s: AsyncSession, doc_id: UUID, at: datetime, user_id: UUID, lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.transfers SET status = 'sent', sent_at = :at, sent_by = :u, updated_at = now() "
                "WHERE id = :id"
            ),
            {"at": at, "u": user_id, "id": doc_id},
        )
        await s.execute(
            text(
                "UPDATE app.transfer_lines SET unit_cost = :unit_cost, lot_allocations = "
                "CAST(:lot_allocations AS jsonb) "
                "WHERE id = :id"
            ),
            [dict(x) for x in lines],
        )

    async def mark_received(
        self,
        s: AsyncSession,
        doc_id: UUID,
        status: str,
        at: datetime,
        user_id: UUID,
        lines: Sequence[Mapping[str, Any]],
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.transfers SET status = :st, received_at = :at, received_by = :u, updated_at = "
                "now() "
                "WHERE id = :id"
            ),
            {"st": status, "at": at, "u": user_id, "id": doc_id},
        )
        await s.execute(
            text(
                "UPDATE app.transfer_lines SET qty_received = :qty_received, unit_cost = :unit_cost, "
                "lot_allocations = CAST(:lot_allocations AS jsonb) WHERE id = :id"
            ),
            [dict(x) for x in lines],
        )

    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.transfers SET status = 'cancelled', cancelled_at = now(), cancelled_by = :u, "
                "cancel_reason = :r, updated_at = now() WHERE id = :id"
            ),
            {"u": user_id, "r": reason, "id": doc_id},
        )

    async def insert_ettn(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.ettn_documents (id, tenant_id, transfer_id, transport_type, direction, "
                "status, "
                "doc_date, payload) VALUES (:id, :tenant_id, :transfer_id, :transport_type, :direction, "
                ":status, "
                ":doc_date, CAST(:payload AS jsonb))"
            ),
            dict(row),
        )

    async def lock_outbox(self, s: AsyncSession, idempotency_key: str) -> None:
        await s.execute(
            text(
                "SELECT id FROM app.outbox_jobs WHERE kind = 'ettn_send' AND idempotency_key = :k FOR UPDATE"
            ),
            {"k": idempotency_key},
        )

    async def lock_ettn(self, s: AsyncSession, ettn_id: UUID) -> EttnRef | None:
        row = (
            await s.execute(
                text("SELECT id, status, operator_doc_id FROM app.ettn_documents WHERE id = :id FOR UPDATE"),
                {"id": ettn_id},
            )
        ).first()
        return EttnRef(row[0], row[1], row[2]) if row else None

    async def set_ettn_status(self, s: AsyncSession, ettn_id: UUID, status: str) -> None:
        await s.execute(
            text("UPDATE app.ettn_documents SET status = :st, updated_at = now() WHERE id = :id"),
            {"st": status, "id": ettn_id},
        )

    async def insert_outbox(self, s: AsyncSession, row: Mapping[str, Any]) -> bool:
        found = await s.execute(
            text(
                "INSERT INTO app.outbox_jobs (id, tenant_id, kind, payload, idempotency_key, created_by) "
                "VALUES "
                "(:id, :tenant_id, :kind, CAST(:payload AS jsonb), :idempotency_key, :created_by) "
                "ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING id"
            ),
            dict(row),
        )
        return found.first() is not None

    async def close_outbox(self, s: AsyncSession, idempotency_key: str, note: str) -> None:
        await s.execute(
            text(
                "UPDATE app.outbox_jobs SET status = 'done', last_error = :note, updated_at = now() "
                "WHERE kind = 'ettn_send' AND idempotency_key = :k AND status IN ('queued', 'retry')"
            ),
            {"k": idempotency_key, "note": note},
        )

    async def ettn_payload_refs(
        self, s: AsyncSession, warehouse_ids: Sequence[UUID], product_ids: Sequence[UUID]
    ) -> tuple[dict[UUID, dict[str, Any]], dict[UUID, dict[str, Any]]]:
        whs = await s.execute(
            text(
                "SELECT w.id, w.name, b.id, b.code, b.name, b.address FROM app.warehouses w "
                "JOIN app.branches b ON b.id = w.branch_id WHERE w.id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [str(i) for i in warehouse_ids]},
        )
        warehouses = {
            r[0]: {
                "warehouse_id": str(r[0]),
                "warehouse_name": r[1],
                "branch_id": str(r[2]),
                "branch_code": r[3],
                "branch_name": r[4],
                "address": r[5],
            }
            for r in whs
        }
        prods = await s.execute(
            text(
                "SELECT id, name, mxik_code, package_code, unit_code, is_marked FROM app.products "
                "WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": [str(i) for i in set(product_ids)]},
        )
        products = {
            r[0]: {
                "name": r[1],
                "mxik_code": r[2],
                "package_code": r[3],
                "unit_code": r[4],
                "is_marked": bool(r[5]),
            }
            for r in prods
        }
        return warehouses, products

    async def overdue_hours(self, s: AsyncSession) -> int:
        raw = (
            await s.execute(text("SELECT settings ->> 'transfer_overdue_hours' FROM app.tenants"))
        ).scalar()
        return overdue_hours(raw)

    async def free_qty(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, Decimal]:
        rows = await s.execute(
            text(
                "SELECT product_id, COALESCE(sum(qty_left - blocked_qty), 0) FROM app.stock_lots "
                "WHERE warehouse_id = :w AND product_id = ANY(CAST(:ids AS uuid[])) AND qty_left > 0 GROUP "
                "BY product_id"
            ),
            {"w": warehouse_id, "ids": [str(i) for i in set(product_ids)]},
        )
        return {r[0]: Decimal(r[1]) for r in rows}
