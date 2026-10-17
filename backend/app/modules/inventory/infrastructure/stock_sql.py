"""Stock register SQL (12 ``stock_moves``, ``stock_lots``, ``avg_costs``, ``stock_balances``, …).

Runs inside the caller's ``tenant_transaction`` (RLS-bound). Row locks follow 23 §2.1: the
``stock_balances`` rows of a document are created if missing and locked ``FOR UPDATE`` in ascending
``(warehouse_id, product_id)`` order; lots/avg rows are then read and written without own locks.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.application.ports import Balance, Key, LotRow, MoveRow, TenantStock, Warehouse
from app.modules.inventory.domain.costing import AvgState
from app.modules.inventory.domain.valuation import MethodRow

_LOT_COLS = (
    "id, warehouse_id, product_id, source_doc_type, source_doc_id, source_line_id, receipt_line_id, "
    "received_at, qty_in, qty_left, blocked_qty, unit_cost, expiry_date"
)
_MOVE_COLS = (
    "m.id, m.warehouse_id, m.product_id, m.lot_id, m.qty, m.cost_amount, m.doc_type, m.doc_id, m.line_id, "
    "m.reversal_of_id, m.moved_at, m.created_at"
)
_LIVE_MOVE = (
    "m.reversal_of_id IS NULL AND NOT EXISTS (SELECT 1 FROM app.stock_moves r WHERE r.reversal_of_id = m.id)"
)
# a lot whose receipt (positive) move is still live — i.e. its source document is not cancelled
_LIVE_LOT = f"EXISTS (SELECT 1 FROM app.stock_moves m WHERE m.lot_id = l.id AND m.qty > 0 AND {_LIVE_MOVE})"  # noqa: S608
_ADVISORY = "hashtextextended('erp:valuation:' || CAST(:tenant AS text), 0)"
_SETTINGS_DEFAULTS = {
    "negative_stock_policy": "allow",
    "expiry_warning_days": 7,
    "low_stock_check_enabled": True,
}


def _lot(row: Row[Any]) -> LotRow:
    return LotRow(**dict(row._mapping))


def _move(row: Row[Any]) -> MoveRow:
    return MoveRow(**dict(row._mapping))


def _key_params(keys: Sequence[Key]) -> dict[str, Any]:
    return {"whs": [str(k[0]) for k in keys], "pids": [str(k[1]) for k in keys]}


class SqlStockRepository:
    # --- locks & tenant -------------------------------------------------------------------------
    async def advisory_lock(self, s: AsyncSession, tenant_id: UUID, *, shared: bool) -> None:
        fn = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
        await s.execute(text(f"SELECT {fn}({_ADVISORY})"), {"tenant": str(tenant_id)})

    async def lock_balances(
        self, s: AsyncSession, tenant_id: UUID, keys: Sequence[Key]
    ) -> dict[Key, Balance]:
        if not keys:
            return {}
        params = {"tenant_id": tenant_id, **_key_params(keys)}
        await s.execute(
            text(
                "INSERT INTO app.stock_balances (tenant_id, warehouse_id, product_id) "
                "SELECT :tenant_id, w, p FROM unnest(CAST(:whs AS uuid[]), CAST(:pids AS uuid[])) AS k(w, p) "
                "ORDER BY w, p ON CONFLICT (tenant_id, warehouse_id, product_id) DO NOTHING"
            ),
            params,
        )
        rows = await s.execute(
            text(
                "SELECT b.warehouse_id, b.product_id, b.qty, b.value FROM app.stock_balances b "
                "JOIN unnest(CAST(:whs AS uuid[]), CAST(:pids AS uuid[])) AS k(w, p) "
                "ON b.warehouse_id = k.w AND b.product_id = k.p "
                "ORDER BY b.warehouse_id, b.product_id FOR UPDATE OF b"
            ),
            params,
        )
        return {(r[0], r[1]): Balance(r[2], r[3]) for r in rows}

    async def tenant_stock(self, s: AsyncSession) -> TenantStock:
        row = (await s.execute(text("SELECT settings, go_live_date FROM app.tenants"))).first()
        settings: dict[str, Any] = {}
        go_live: date | None = None
        if row is not None:
            raw = row[0]
            settings = raw if isinstance(raw, dict) else json.loads(raw or "{}")
            go_live = row[1]
        merged = {**_SETTINGS_DEFAULTS, **{k: v for k, v in settings.items() if v is not None}}
        policy = "block" if merged["negative_stock_policy"] in ("block", "forbid") else "allow"
        try:
            days = max(0, int(merged["expiry_warning_days"]))
        except (TypeError, ValueError):
            days = 7
        state = settings.get("stock_valuation")
        return TenantStock(
            negative_stock_policy=policy,
            expiry_warning_days=days,
            low_stock_check_enabled=bool(merged["low_stock_check_enabled"]),
            go_live_date=go_live,
            valuation_state=state if isinstance(state, dict) else None,
        )

    async def save_valuation_state(self, s: AsyncSession, tenant_id: UUID, state: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "UPDATE app.tenants SET settings = jsonb_set(settings, '{stock_valuation}', CAST(:v AS "
                "jsonb)), "
                "version = version + 1, updated_at = now() WHERE id = :t"
            ),
            {"v": json.dumps(dict(state)), "t": tenant_id},
        )

    async def method_history(self, s: AsyncSession) -> list[MethodRow]:
        rows = await s.execute(
            text("SELECT valid_from, method FROM app.valuation_method_history ORDER BY valid_from")
        )
        return [MethodRow(r[0], r[1]) for r in rows]

    async def upsert_method(
        self, s: AsyncSession, tenant_id: UUID, valid_from: date, method: str, user_id: UUID
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.valuation_method_history (tenant_id, valid_from, method, created_by) "
                "VALUES (:t, :v, :m, :u) ON CONFLICT (tenant_id, valid_from) DO UPDATE SET method = "
                "EXCLUDED.method, "
                "created_by = EXCLUDED.created_by, created_at = now()"
            ),
            {"t": tenant_id, "v": valid_from, "m": method, "u": user_id},
        )

    async def has_moves_since(self, s: AsyncSession, since: datetime) -> bool:
        found = await s.execute(
            text("SELECT 1 FROM app.stock_moves WHERE moved_at >= :at LIMIT 1"), {"at": since}
        )
        return found.first() is not None

    # --- reference data ---------------------------------------------------------------------------
    async def warehouse(self, s: AsyncSession, warehouse_id: UUID) -> Warehouse | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, branch_id, inventory_account, archived_at IS NOT NULL FROM app.warehouses "
                    "WHERE id = :id"
                ),
                {"id": warehouse_id},
            )
        ).first()
        return Warehouse(row[0], row[1], row[2], bool(row[3])) if row else None

    async def branch_warehouse(self, s: AsyncSession, branch_id: UUID) -> Warehouse | None:
        """The branch's warehouse (MVP UI: one per branch, qaror #54) — the oldest active one."""
        row = (
            await s.execute(
                text(
                    "SELECT id, branch_id, inventory_account, false FROM app.warehouses WHERE branch_id = :b "
                    "AND archived_at IS NULL ORDER BY created_at, id LIMIT 1"
                ),
                {"b": branch_id},
            )
        ).first()
        return Warehouse(row[0], row[1], row[2], False) if row else None

    async def warehouse_ids(self, s: AsyncSession, branch_ids: Sequence[UUID]) -> list[UUID]:
        rows = await s.execute(
            text("SELECT id FROM app.warehouses WHERE branch_id = ANY(CAST(:b AS uuid[]))"),
            {"b": [str(b) for b in branch_ids]},
        )
        return [r[0] for r in rows]

    async def default_branch_id(self, s: AsyncSession) -> UUID | None:
        row = (
            await s.execute(
                text(
                    "SELECT id FROM app.branches WHERE archived_at IS NULL ORDER BY is_default DESC, code, "
                    "id LIMIT 1"
                )
            )
        ).first()
        return row[0] if row else None

    async def product_ids(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, bool]:
        """``{product_id: archived}`` for the products that exist (RLS: this tenant only)."""
        if not ids:
            return {}
        rows = await s.execute(
            text("SELECT id, archived_at IS NOT NULL FROM app.products WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [str(i) for i in set(ids)]},
        )
        return {r[0]: bool(r[1]) for r in rows}

    async def products_by_barcode(self, s: AsyncSession, barcodes: Sequence[str]) -> dict[str, UUID]:
        """``{barcode: product_id}`` of active products (RLS: this tenant's catalog)."""
        if not barcodes:
            return {}
        rows = await s.execute(
            text(
                "SELECT b.barcode, b.product_id FROM app.product_barcodes b JOIN app.products p "
                "ON p.id = b.product_id WHERE p.archived_at IS NULL AND b.barcode = ANY(CAST(:codes AS "
                "text[]))"
            ),
            {"codes": list(dict.fromkeys(barcodes))},
        )
        return {r[0]: r[1] for r in rows}

    # --- registers --------------------------------------------------------------------------------
    async def open_lots(self, s: AsyncSession, key: Key) -> list[LotRow]:
        rows = await s.execute(
            text(
                f"SELECT {_LOT_COLS} FROM app.stock_lots WHERE warehouse_id = :w AND "  # noqa: S608
                "product_id = :p "
                "AND qty_left > 0 ORDER BY received_at, id"
            ),
            {"w": key[0], "p": key[1]},
        )
        return [_lot(r) for r in rows]

    async def lot(self, s: AsyncSession, lot_id: UUID) -> LotRow | None:
        row = (
            await s.execute(text(f"SELECT {_LOT_COLS} FROM app.stock_lots WHERE id = :id"), {"id": lot_id})  # noqa: S608
        ).first()
        return _lot(row) if row else None

    async def lots_of_source(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> list[LotRow]:
        rows = await s.execute(
            text(
                f"SELECT {_LOT_COLS} FROM app.stock_lots WHERE source_doc_type = :t AND "  # noqa: S608
                "source_doc_id = :d "
                "ORDER BY received_at, id"
            ),
            {"t": doc_type, "d": doc_id},
        )
        return [_lot(r) for r in rows]

    async def insert_lot(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.stock_lots (id, tenant_id, warehouse_id, product_id, receipt_line_id, "
                "source_doc_type, source_doc_id, source_line_id, received_at, qty_in, qty_left, unit_cost, "
                "expiry_date) VALUES (:id, :tenant_id, :warehouse_id, :product_id, :receipt_line_id, "
                ":source_doc_type, :source_doc_id, :source_line_id, :received_at, :qty_in, :qty_left, "
                ":unit_cost, "
                ":expiry_date)"
            ),
            dict(row),
        )

    async def set_lot(
        self, s: AsyncSession, lot_id: UUID, *, qty_left: Decimal, blocked_qty: Decimal
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.stock_lots SET qty_left = :q, blocked_qty = :b, updated_at = now() WHERE id = :id"
            ),
            {"q": qty_left, "b": blocked_qty, "id": lot_id},
        )

    async def insert_moves(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.stock_moves (id, tenant_id, warehouse_id, product_id, lot_id, qty, "
                "cost_amount, "
                "doc_type, doc_id, line_id, reversal_of_id, moved_at) VALUES (:id, :tenant_id, "
                ":warehouse_id, "
                ":product_id, :lot_id, :qty, :cost_amount, :doc_type, :doc_id, :line_id, :reversal_of_id, "
                ":moved_at)"
            ),
            [dict(r) for r in rows],
        )

    async def add_balance(self, s: AsyncSession, key: Key, qty: Decimal, value: Decimal) -> None:
        await s.execute(
            text(
                "UPDATE app.stock_balances SET qty = qty + :q, value = value + :v, updated_at = now() "
                "WHERE warehouse_id = :w AND product_id = :p"
            ),
            {"q": qty, "v": value, "w": key[0], "p": key[1]},
        )

    async def avg_state(self, s: AsyncSession, key: Key) -> AvgState | None:
        row = (
            await s.execute(
                text(
                    "SELECT qty, avg_cost, total_value FROM app.avg_costs WHERE warehouse_id = :w AND "
                    "product_id = :p"
                ),
                {"w": key[0], "p": key[1]},
            )
        ).first()
        return AvgState(row[0], row[1], row[2]) if row else None

    async def save_avg(self, s: AsyncSession, tenant_id: UUID, key: Key, state: AvgState) -> None:
        await s.execute(
            text(
                "INSERT INTO app.avg_costs (tenant_id, warehouse_id, product_id, avg_cost, qty, total_value) "
                "VALUES (:t, :w, :p, :a, :q, :v) ON CONFLICT (tenant_id, warehouse_id, product_id) DO UPDATE "
                "SET "
                "avg_cost = EXCLUDED.avg_cost, qty = EXCLUDED.qty, total_value = EXCLUDED.total_value, "
                "updated_at = now()"
            ),
            {
                "t": tenant_id,
                "w": key[0],
                "p": key[1],
                "a": state.avg_cost,
                "q": state.qty,
                "v": state.total_value,
            },
        )

    async def pending_moves(self, s: AsyncSession, key: Key) -> list[MoveRow]:
        rows = await s.execute(
            text(
                f"SELECT {_MOVE_COLS} FROM app.stock_moves m WHERE m.warehouse_id = :w AND "  # noqa: S608
                "m.product_id = :p "
                f"AND m.lot_id IS NULL AND m.qty < 0 AND {_LIVE_MOVE} ORDER BY m.moved_at, m.created_at, m.id"
            ),
            {"w": key[0], "p": key[1]},
        )
        return [_move(r) for r in rows]

    async def doc_moves(
        self, s: AsyncSession, doc_type: str, doc_id: UUID, *, live_only: bool
    ) -> list[MoveRow]:
        live = f" AND {_LIVE_MOVE}" if live_only else ""
        rows = await s.execute(
            text(
                f"SELECT {_MOVE_COLS} FROM app.stock_moves m WHERE m.doc_type = :t AND "  # noqa: S608
                f"m.doc_id = :d{live} "
                "ORDER BY m.moved_at, m.created_at, m.id"
            ),
            {"t": doc_type, "d": doc_id},
        )
        return [_move(r) for r in rows]

    async def line_cost(
        self, s: AsyncSession, key: Key, doc_type: str, doc_id: UUID, line_id: UUID | None
    ) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(-sum(cost_amount), 0) FROM app.stock_moves WHERE warehouse_id = :w "
                    "AND product_id = :p AND doc_type = :t AND doc_id = :d AND line_id IS NOT DISTINCT FROM "
                    ":l"
                ),
                {"w": key[0], "p": key[1], "t": doc_type, "d": doc_id, "l": line_id},
            )
        ).scalar_one()
        return Decimal(value).quantize(Decimal("0.01"))

    async def pending_history_lines(
        self, s: AsyncSession, key: Key, since: datetime
    ) -> list[tuple[str, UUID, UUID | None]]:
        rows = await s.execute(
            text(
                "SELECT m.doc_type, m.doc_id, m.line_id, min(m.moved_at) AS at, min(m.created_at) AS created "
                "FROM app.stock_moves m WHERE m.warehouse_id = :w AND m.product_id = :p AND m.lot_id IS NULL "
                "AND m.qty < 0 AND m.reversal_of_id IS NULL AND m.moved_at >= :since "
                "GROUP BY m.doc_type, m.doc_id, m.line_id ORDER BY at, created, m.doc_id"
            ),
            {"w": key[0], "p": key[1], "since": since},
        )
        return [(r[0], r[1], r[2]) for r in rows]

    async def live_issues_since(
        self, s: AsyncSession, key: Key, created_at: datetime, exclude_doc: tuple[str, UUID]
    ) -> bool:
        """Is there a live issue (``qty < 0``, not reversed, not a reversal) of ``key`` written at or
        after ``created_at`` by another document (13 §3.1 AVECO receipt cancel)?"""
        found = await s.execute(
            text(
                "SELECT 1 FROM app.stock_moves m WHERE m.warehouse_id = :w AND m.product_id = :p "  # noqa: S608
                f"AND m.qty < 0 AND m.created_at >= :at AND NOT (m.doc_type = :t AND m.doc_id = :d) "
                f"AND {_LIVE_MOVE} LIMIT 1"
            ),
            {"w": key[0], "p": key[1], "at": created_at, "t": exclude_doc[0], "d": exclude_doc[1]},
        )
        return found.first() is not None

    async def lot_value(self, s: AsyncSession, lot_id: UUID) -> tuple[Decimal, int]:
        """Remaining value of a lot = Σ ``cost_amount`` of its live moves, and their count (13 §3.1)."""
        row = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(m.cost_amount), 0), count(*) FROM app.stock_moves m "  # noqa: S608
                    f"WHERE m.lot_id = :l AND {_LIVE_MOVE}"
                ),
                {"l": lot_id},
            )
        ).one()
        return Decimal(row[0]).quantize(Decimal("0.01")), int(row[1])

    async def last_lot_cost(self, s: AsyncSession, key: Key) -> Decimal | None:
        """Unit cost of the latest lot of ``key`` whose receipt move is still live (not cancelled)."""
        value: Decimal | None = (
            await s.execute(
                text(
                    "SELECT l.unit_cost FROM app.stock_lots l WHERE l.warehouse_id = :w "  # noqa: S608
                    f"AND l.product_id = :p AND {_LIVE_LOT} ORDER BY l.received_at DESC, l.id DESC LIMIT 1"
                ),
                {"w": key[0], "p": key[1]},
            )
        ).scalar()
        return value

    async def last_purchase_cost(
        self, s: AsyncSession, product_id: UUID, warehouse_id: UUID
    ) -> Decimal | None:
        """13 §2.11: the latest ``goods_receipts`` lot of a not-cancelled receipt (this warehouse first,
        then any)."""
        value: Decimal | None = (
            await s.execute(
                text(
                    "SELECT l.unit_cost FROM app.stock_lots l WHERE l.product_id = :p AND "  # noqa: S608
                    f"l.source_doc_type = 'goods_receipts' AND {_LIVE_LOT} "
                    "ORDER BY (l.warehouse_id = :w) DESC, l.received_at DESC, l.id DESC LIMIT 1"
                ),
                {"w": warehouse_id, "p": product_id},
            )
        ).scalar()
        return value

    async def insert_sync_exception(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        params = {**row, "details": json.dumps(row.get("details") or {}, default=str)}
        await s.execute(
            text(
                "INSERT INTO app.sync_exceptions (id, tenant_id, kind, doc_type, doc_id, details) "
                "VALUES (:id, :tenant_id, :kind, :doc_type, :doc_id, CAST(:details AS jsonb))"
            ),
            params,
        )

    async def cost_unknown_template(
        self, s: AsyncSession, doc_type: str, doc_id: UUID, line_id: UUID | None, product_id: UUID
    ) -> dict[str, Any] | None:
        row = (
            await s.execute(
                text(
                    "SELECT details -> 'cost_line' FROM app.sync_exceptions WHERE kind = 'cost_unknown' "
                    "AND doc_type = :t AND doc_id = :d AND details ->> 'product_id' = :p "
                    "AND details ->> 'line_id' = :l AND details ? 'cost_line' ORDER BY created_at LIMIT 1"
                ),
                {"t": doc_type, "d": doc_id, "p": str(product_id), "l": str(line_id)},
            )
        ).first()
        if row is None or row[0] is None:
            return None
        raw = row[0]
        loaded = raw if isinstance(raw, dict) else json.loads(raw)
        return loaded if isinstance(loaded, dict) else None

    # --- valuation switch -------------------------------------------------------------------------
    async def all_balances(self, s: AsyncSession) -> dict[Key, Balance]:
        rows = await s.execute(text("SELECT warehouse_id, product_id, qty, value FROM app.stock_balances"))
        return {(r[0], r[1]): Balance(r[2], r[3]) for r in rows}

    async def all_open_lots(self, s: AsyncSession) -> list[LotRow]:
        rows = await s.execute(
            text(f"SELECT {_LOT_COLS} FROM app.stock_lots WHERE qty_left > 0 ORDER BY received_at, id")  # noqa: S608
        )
        return [_lot(r) for r in rows]

    async def all_avg(self, s: AsyncSession) -> dict[Key, AvgState]:
        rows = await s.execute(
            text("SELECT warehouse_id, product_id, qty, avg_cost, total_value FROM app.avg_costs")
        )
        return {(r[0], r[1]): AvgState(r[2], r[3], r[4]) for r in rows}

    async def pending_estimates(self, s: AsyncSession) -> dict[Key, Decimal]:
        rows = await s.execute(
            text(
                "SELECT m.warehouse_id, m.product_id, -sum(m.cost_amount) FROM "  # noqa: S608
                "app.stock_moves m "
                f"WHERE m.lot_id IS NULL AND m.qty < 0 AND {_LIVE_MOVE} GROUP BY m.warehouse_id, m.product_id"
            )
        )
        return {(r[0], r[1]): r[2] for r in rows}

    async def set_lot_unit_cost(self, s: AsyncSession, lot_id: UUID, unit_cost: Decimal) -> None:
        await s.execute(
            text("UPDATE app.stock_lots SET unit_cost = :u, updated_at = now() WHERE id = :id"),
            {"u": unit_cost, "id": lot_id},
        )
