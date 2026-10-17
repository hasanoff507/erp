"""Read-only SQL of ``/sync/pull`` over the owning modules' tables (catalog, pricing, debts, inventory,
access, branches) — like a reports module, never writes them. Caller's ``tenant_transaction`` (RLS)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import money_str, percent_str, price_str, qty_str
from app.modules.debts.wiring import open_debt_docs
from app.modules.sync.application.ports import PullContext, StreamRow
from app.modules.sync.domain.cursor import Position

FISCAL_SNAPSHOT_DAYS: Final = 7
_SNAPSHOT_MARKING: Final = ("sold", "pending_verification")


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _d(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _u(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _opt(fmt: Callable[[Decimal], str], value: Decimal | None) -> str | None:
    return None if value is None else fmt(value)


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


def _window(ts: str, key: str, after: Position | None, params: dict[str, Any]) -> str:
    """Settled rows after the stream position, ordered by ``(ts, key)``."""
    clause = f"{ts} <= :settle"
    if after is not None:
        clause += f" AND ({ts}, {key}) > (:after_at, :after_key)"
        params["after_at"], params["after_key"] = after.at, after.key
    return clause


class SqlPullReader:
    async def stream(
        self, s: AsyncSession, stream: str, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        reader = _STREAMS[stream]
        rows: list[StreamRow] = await reader(self, s, ctx, after, limit)
        return rows

    # --- catalog ----------------------------------------------------------------------------------
    async def _units(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit}
        where = _window("created_at", "code", after, params)
        rows = await s.execute(
            text(
                f"SELECT code, is_fractional, created_at FROM platform.units WHERE {where} "  # noqa: S608
                "ORDER BY created_at, code LIMIT :limit"
            ),
            params,
        )
        return [
            StreamRow(
                {
                    "entity": "unit",
                    "id": r.code,
                    "code": r.code,
                    "is_fractional": r.is_fractional,
                    "deleted": False,
                },
                Position(r.created_at, r.code),
            )
            for r in rows
        ]

    async def _categories(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit}
        where = _window("updated_at", "id::text", after, params)
        if after is None:
            where += " AND archived_at IS NULL"
        rows = await s.execute(
            text(
                "SELECT id, parent_id, name, archived_at, updated_at, version FROM "  # noqa: S608
                "app.product_categories "
                f"WHERE {where} ORDER BY updated_at, id::text LIMIT :limit"
            ),
            params,
        )
        return [
            StreamRow(
                {
                    "entity": "category",
                    "id": str(r.id),
                    "parent_id": _u(r.parent_id),
                    "name": r.name,
                    "archived_at": _ts(r.archived_at),
                    "updated_at": _ts(r.updated_at),
                    "version": r.version,
                    "deleted": r.archived_at is not None,
                },
                Position(r.updated_at, str(r.id)),
            )
            for r in rows
        ]

    async def _products(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit}
        where = _window("updated_at", "id::text", after, params)
        if after is None:
            where += " AND archived_at IS NULL"
        rows = await s.execute(
            text(
                "SELECT id, name, name_ru, category_id, unit_code, mxik_code, package_code, "  # noqa: S608
                "vat_rate, "
                "vat_exemption_code, is_marked, marking_group_code, is_weighed, turnover_tax_group, "
                "archived_at, "
                f"updated_at, version FROM app.products WHERE {where} ORDER BY updated_at, id::text LIMIT "
                ":limit"
            ),
            params,
        )
        return [
            StreamRow(
                {
                    "entity": "product",
                    "id": str(r.id),
                    "name": r.name,
                    "name_ru": r.name_ru,
                    "category_id": _u(r.category_id),
                    "unit_code": r.unit_code,
                    "mxik_code": r.mxik_code,
                    "package_code": r.package_code,
                    "vat_rate": _opt(percent_str, r.vat_rate),
                    "vat_exemption_code": r.vat_exemption_code,
                    "is_marked": r.is_marked,
                    "marking_group_code": r.marking_group_code,
                    "is_weighed": r.is_weighed,
                    "turnover_tax_group": r.turnover_tax_group,
                    "archived_at": _ts(r.archived_at),
                    "updated_at": _ts(r.updated_at),
                    "version": r.version,
                    "deleted": r.archived_at is not None,
                },
                Position(r.updated_at, str(r.id)),
            )
            for r in rows
        ]

    async def _barcodes(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit}
        where = _window("p.updated_at", "p.id::text", after, params)
        if after is None:
            where += " AND p.archived_at IS NULL"
        rows = await s.execute(
            text(
                "SELECT p.id, p.updated_at, p.archived_at, COALESCE((SELECT "  # noqa: S608
                "json_agg(json_build_object("
                "'barcode', b.barcode, 'kind', b.kind, 'units_per_barcode', b.units_per_barcode) "
                "ORDER BY b.barcode) FROM app.product_barcodes b WHERE b.product_id = p.id), '[]') AS "
                "barcodes "
                f"FROM app.products p WHERE {where} ORDER BY p.updated_at, p.id::text LIMIT :limit"
            ),
            params,
        )
        out: list[StreamRow] = []
        for r in rows:
            codes = [
                {
                    "barcode": b["barcode"],
                    "kind": b["kind"],
                    "units_per_barcode": qty_str(Decimal(str(b["units_per_barcode"]))),
                }
                for b in _json(r.barcodes)
            ]
            out.append(
                StreamRow(
                    {
                        "id": str(r.id),
                        "product_id": str(r.id),
                        "barcodes": codes,
                        "updated_at": _ts(r.updated_at),
                        "deleted": r.archived_at is not None,
                    },
                    Position(r.updated_at, str(r.id)),
                )
            )
        return out

    # --- prices -----------------------------------------------------------------------------------
    async def _prices(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit, "branch": ctx.branch_id}
        where = _window("g.ts", "g.product_id::text", after, params)
        groups = (
            await s.execute(
                text(
                    "WITH g AS (SELECT product_id, max(created_at) AS ts FROM "  # noqa: S608
                    "app.product_prices "
                    "WHERE branch_id IS NULL OR branch_id = :branch GROUP BY product_id) "
                    f"SELECT g.product_id, g.ts FROM g WHERE {where} ORDER BY g.ts, g.product_id::text "
                    "LIMIT :limit"
                ),
                params,
            )
        ).all()
        if not groups:
            return []
        ids = [g.product_id for g in groups]
        entries: dict[UUID, list[Any]] = {}
        for r in await s.execute(
            text(
                "SELECT id, product_id, branch_id, price, valid_from, created_at FROM app.product_prices "
                "WHERE product_id = ANY(CAST(:ids AS uuid[])) AND (branch_id IS NULL OR branch_id = :branch) "
                "ORDER BY product_id, valid_from, created_at, id"
            ),
            {"ids": ids, "branch": ctx.branch_id},
        ):
            entries.setdefault(r.product_id, []).append(r)
        out: list[StreamRow] = []
        for g in groups:
            out.append(
                StreamRow(
                    {
                        "id": str(g.product_id),
                        "product_id": str(g.product_id),
                        "prices": _relevant_prices(entries.get(g.product_id, []), ctx.now),
                        "updated_at": _ts(g.ts),
                        "deleted": False,
                    },
                    Position(g.ts, str(g.product_id)),
                )
            )
        return out

    # --- customers --------------------------------------------------------------------------------
    async def _customers(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit}
        where = _window("x.ts", "x.id::text", after, params)
        if after is None:
            where += " AND x.is_customer AND x.archived_at IS NULL"
        rows = await s.execute(
            text(
                "SELECT * FROM (SELECT c.id, c.kind, c.name, c.phone, c.stir, c.credit_limit, "  # noqa: S608
                "c.standing_discount_pct, c.debt_due_date, c.archived_at, c.is_customer, c.version, "
                "COALESCE(db.balance, 0) AS receivable, "
                "GREATEST(c.updated_at, COALESCE(db.updated_at, c.updated_at)) AS ts "
                "FROM app.counterparties c LEFT JOIN app.debt_balances db ON db.counterparty_id = c.id "
                "AND db.direction = 'receivable') x "
                f"WHERE {where} ORDER BY x.ts, x.id::text LIMIT :limit"
            ),
            params,
        )
        found = list(rows)
        # 16 §1 open_debt_docs[] (B4, b4-debts): customers with an open debt document (receivable_balance > 0
        # or an open written-off debt) — the same documents the server re-allocates on debt_payment.created
        live = [r.id for r in found if r.archived_at is None and r.is_customer]
        docs = await open_debt_docs(s, live) if live else {}
        return [
            StreamRow(
                {
                    "id": str(r.id),
                    "kind": r.kind,
                    "name": r.name,
                    "phone": r.phone,
                    "stir": r.stir,
                    "credit_limit": _opt(money_str, r.credit_limit),
                    "standing_discount_pct": _opt(percent_str, r.standing_discount_pct),
                    "receivable_balance": money_str(r.receivable),
                    "debt_due_date": _d(r.debt_due_date),
                    "archived_at": _ts(r.archived_at),
                    "version": r.version,
                    "updated_at": _ts(r.ts),
                    "open_debt_docs": docs.get(r.id, []),
                    "deleted": r.archived_at is not None or not r.is_customer,
                },
                Position(r.ts, str(r.id)),
            )
            for r in found
        ]

    # --- stock ------------------------------------------------------------------------------------
    async def _stock(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit, "branch": ctx.branch_id}
        key = "(sb.warehouse_id::text || ':' || sb.product_id::text)"
        where = _window("sb.updated_at", key, after, params)
        rows = await s.execute(
            text(
                "SELECT sb.warehouse_id, sb.product_id, sb.qty, sb.updated_at FROM "  # noqa: S608
                "app.stock_balances sb "
                "JOIN app.warehouses w ON w.id = sb.warehouse_id AND w.branch_id = :branch "
                f"WHERE {where} ORDER BY sb.updated_at, {key} LIMIT :limit"
            ),
            params,
        )
        out: list[StreamRow] = []
        for r in rows:
            row_id = f"{r.warehouse_id}:{r.product_id}"
            out.append(
                StreamRow(
                    {
                        "id": row_id,
                        "warehouse_id": str(r.warehouse_id),
                        "product_id": str(r.product_id),
                        "qty": qty_str(r.qty),
                        "updated_at": _ts(r.updated_at),
                        "deleted": False,
                    },
                    Position(r.updated_at, row_id),
                )
            )
        return out

    # --- marking codes ----------------------------------------------------------------------------
    async def _marking(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit}
        where = _window("updated_at", "id::text", after, params)
        if after is None:
            where += " AND status IN ('sold', 'pending_verification')"
        rows = await s.execute(
            text(
                "SELECT id, code, product_id, status, updated_at FROM app.marking_codes "  # noqa: S608
                f"WHERE {where} "
                "ORDER BY updated_at, id::text LIMIT :limit"
            ),
            params,
        )
        return [
            StreamRow(
                {
                    "id": str(r.id),
                    "code": r.code,
                    "product_id": str(r.product_id),
                    "status": r.status,
                    "updated_at": _ts(r.updated_at),
                    "deleted": r.status not in _SNAPSHOT_MARKING,
                },
                Position(r.updated_at, str(r.id)),
            )
            for r in rows
        ]

    # --- fiscal -----------------------------------------------------------------------------------
    async def _registers(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        if ctx.cash_register_id is None:
            return []
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit, "cr": ctx.cash_register_id}
        where = _window("updated_at", "id::text", after, params)
        rows = await s.execute(
            text(
                "SELECT id, fm_state, last_unacked_receipt_at, fm_receipts_pending, updated_at "  # noqa: S608
                f"FROM app.cash_registers WHERE id = :cr AND {where} ORDER BY updated_at, id::text LIMIT "
                ":limit"
            ),
            params,
        )
        return [
            StreamRow(
                {
                    "entity": "cash_register",
                    "id": str(r.id),
                    "fm_state": r.fm_state,
                    "last_unacked_receipt_at": _ts(r.last_unacked_receipt_at),
                    "fm_receipts_pending": r.fm_receipts_pending,
                    "updated_at": _ts(r.updated_at),
                    "deleted": False,
                },
                Position(r.updated_at, str(r.id)),
            )
            for r in rows
        ]

    async def _receipts(
        self, s: AsyncSession, ctx: PullContext, after: Position | None, limit: int
    ) -> list[StreamRow]:
        if ctx.cash_register_id is None:
            return []
        params: dict[str, Any] = {"settle": ctx.settle_before, "limit": limit, "cr": ctx.cash_register_id}
        where = _window("f.updated_at", "f.id::text", after, params)
        if after is None:
            where += " AND (f.ofd_acked_at IS NULL OR f.created_at >= :recent)"
            params["recent"] = ctx.now - timedelta(days=FISCAL_SNAPSHOT_DAYS)
        rows = await s.execute(
            text(
                "SELECT f.id, f.kind, COALESCE(sa.client_event_id, re.client_event_id, "  # noqa: S608
                "dp.client_event_id) AS cid, "
                "COALESCE(f.sale_id, f.return_id, f.debt_payment_id) AS doc_id, f.cash_register_id, "
                "f.shift_id, "
                "f.receipt_seq, f.fm_receipt_seq, f.status, f.fiscal_sign, f.qr_url, f.fiscal_at, "
                "f.ofd_acked_at, "
                "f.created_at, f.updated_at FROM app.fiscal_receipts f "
                "LEFT JOIN app.sales sa ON sa.id = f.sale_id LEFT JOIN app.returns re ON re.id = f.return_id "
                "LEFT JOIN app.debt_payments dp ON dp.id = f.debt_payment_id "
                f"WHERE f.cash_register_id = :cr AND {where} ORDER BY f.updated_at, f.id::text LIMIT :limit"
            ),
            params,
        )
        return [
            StreamRow(
                {
                    "entity": "receipt",
                    "id": str(r.id),
                    "kind": r.kind,
                    "client_event_id": _u(r.cid),
                    "doc_id": _u(r.doc_id),
                    "cash_register_id": _u(r.cash_register_id),
                    "shift_id": _u(r.shift_id),
                    "receipt_seq": r.receipt_seq,
                    "fm_receipt_seq": r.fm_receipt_seq,
                    "status": r.status,
                    "fiscal_sign": r.fiscal_sign,
                    "qr_url": r.qr_url,
                    "fiscal_at": _ts(r.fiscal_at),
                    "ofd_acked_at": _ts(r.ofd_acked_at),
                    "created_at": _ts(r.created_at),
                    "updated_at": _ts(r.updated_at),
                    "deleted": False,
                },
                Position(r.updated_at, str(r.id)),
            )
            for r in rows
        ]

    # --- snapshot objects -------------------------------------------------------------------------
    async def staff(self, s: AsyncSession, ctx: PullContext) -> list[dict[str, Any]]:
        roles = {
            r.id: r
            for r in await s.execute(
                text("SELECT id, name, system_code FROM app.roles WHERE archived_at IS NULL")
            )
        }
        grants: dict[UUID, list[tuple[str, Decimal | None]]] = {}
        for r in await s.execute(
            text("SELECT role_id, permission_code, limit_value FROM app.role_permissions")
        ):
            grants.setdefault(r.role_id, []).append((r.permission_code, r.limit_value))
        members = await s.execute(
            text(
                "SELECT m.user_id, m.status, m.role_ids, m.branch_ids, COALESCE(m.invited_name, u.name) AS "
                "name "
                "FROM app.memberships m JOIN app.users u ON u.id = m.user_id "
                "WHERE m.status IN ('active', 'blocked') "
                "AND (cardinality(m.branch_ids) = 0 OR CAST(:branch AS uuid) = ANY(m.branch_ids)) ORDER BY "
                "m.user_id"
            ),
            {"branch": ctx.branch_id},
        )
        out: list[dict[str, Any]] = []
        for m in members:
            live = [rid for rid in (m.role_ids or ()) if rid in roles]
            merged: dict[str, Decimal | None] = {}
            unlimited: set[str] = set()
            for rid in live:
                for code, limit in grants.get(rid, ()):
                    if limit is None:
                        unlimited.add(code)
                    elif code not in merged or (merged[code] is not None and limit > (merged[code] or 0)):
                        merged[code] = limit
            for code in unlimited:
                merged[code] = None
            out.append(
                {
                    "user_id": str(m.user_id),
                    "full_name": m.name,
                    "status": m.status,
                    "role_ids": [str(r) for r in live],
                    "role_codes": sorted({roles[r].system_code for r in live if roles[r].system_code}),
                    "branch_ids": [str(b) for b in (m.branch_ids or ())],
                    "permissions": [
                        {"code": code, "limit_value": _opt(price_str, merged[code])}
                        for code in sorted(merged)
                    ],
                }
            )
        return out

    async def shift(self, s: AsyncSession, ctx: PullContext) -> dict[str, Any]:
        if ctx.cash_register_id is None:
            return {"cash_register_id": None, "open_shift": None, "last_shift_no": None}
        row = (
            await s.execute(
                text(
                    "SELECT id, shift_no, status, device_id, opened_by, opened_at, opening_cash FROM "
                    "app.shifts "
                    "WHERE cash_register_id = :cr AND status = 'open' ORDER BY opened_at DESC, id DESC "
                    "LIMIT 1"
                ),
                {"cr": ctx.cash_register_id},
            )
        ).first()
        last = (
            await s.execute(
                text("SELECT max(shift_no) FROM app.shifts WHERE cash_register_id = :cr"),
                {"cr": ctx.cash_register_id},
            )
        ).scalar()
        return {
            "cash_register_id": str(ctx.cash_register_id),
            "open_shift": None
            if row is None
            else {
                "id": str(row.id),
                "shift_no": row.shift_no,
                "status": row.status,
                "device_id": str(row.device_id),
                "opened_by": str(row.opened_by),
                "opened_at": _ts(row.opened_at),
                "opening_cash": money_str(row.opening_cash),
            },
            "last_shift_no": last,
        }

    async def settings(self, s: AsyncSession, ctx: PullContext) -> dict[str, Any]:
        tenant = (
            await s.execute(
                text("SELECT name, legal_form, stir, settings FROM app.tenants WHERE id = :t"),
                {"t": ctx.tenant_id},
            )
        ).one()
        sub = (
            await s.execute(text("SELECT status, current_period_end, grace_ends_at FROM app.subscriptions"))
        ).first()
        branch = (
            await s.execute(
                text("SELECT id, code, name FROM app.branches WHERE id = :b"), {"b": ctx.branch_id}
            )
        ).one()
        register = None
        if ctx.cash_register_id is not None:
            register = (
                await s.execute(
                    text("SELECT id, name, kind FROM app.cash_registers WHERE id = :cr"),
                    {"cr": ctx.cash_register_id},
                )
            ).first()
        rules = await s.execute(
            text(
                "SELECT id, name, scope, target_ids, kind, value, branch_ids, valid_from, valid_to, "
                "priority, version "
                "FROM app.discount_rules WHERE archived_at IS NULL "
                "AND valid_from <= (now() AT TIME ZONE 'Asia/Tashkent')::date "
                "AND (valid_to IS NULL OR valid_to >= (now() AT TIME ZONE 'Asia/Tashkent')::date) "
                "AND (cardinality(branch_ids) = 0 OR CAST(:b AS uuid) = ANY(branch_ids)) "
                "ORDER BY priority DESC, id"
            ),
            {"b": ctx.branch_id},
        )
        terminals = await s.execute(
            text(
                "SELECT id, name, vendor, model, adapter, driver, cash_register_id, agent_id, local_id, "
                "host::text AS host, port, tid, mid, is_default, status, capabilities, health_status "
                "FROM app.card_terminals WHERE branch_id = :b AND status = 'active' ORDER BY name, id"
            ),
            {"b": ctx.branch_id},
        )
        bins = await s.execute(
            text(
                "SELECT bin_prefix, card_type, card_scheme, valid_from, valid_to FROM "
                "platform.card_bin_rules "
                "WHERE valid_from <= (now() AT TIME ZONE 'Asia/Tashkent')::date AND (valid_to IS NULL "
                "OR valid_to >= (now() AT TIME ZONE 'Asia/Tashkent')::date) ORDER BY bin_prefix, valid_from"
            )
        )
        return {
            "card_bin_rules": [
                {
                    "bin_prefix": b.bin_prefix,
                    "card_type": b.card_type,
                    "card_scheme": b.card_scheme,
                    "valid_from": _d(b.valid_from),
                    "valid_to": _d(b.valid_to),
                }
                for b in bins
            ],
            "tenant": {"name": tenant.name, "legal_form": tenant.legal_form, "stir": tenant.stir},
            "tenant_settings": _json(tenant.settings) or {},
            "subscription": None
            if sub is None
            else {
                "status": sub.status,
                "current_period_end": _ts(sub.current_period_end),
                "grace_ends_at": _ts(sub.grace_ends_at),
            },
            "branch": {"id": str(branch.id), "code": branch.code, "name": branch.name},
            "cash_register": None
            if register is None
            else {"id": str(register.id), "name": register.name, "kind": register.kind},
            "discount_rules": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "scope": r.scope,
                    "target_ids": [str(x) for x in r.target_ids],
                    "kind": r.kind,
                    "value": price_str(r.value),
                    "branch_ids": [str(x) for x in r.branch_ids],
                    "valid_from": _d(r.valid_from),
                    "valid_to": _d(r.valid_to),
                    "priority": r.priority,
                    "version": r.version,
                }
                for r in rules
            ],
            "card_terminals": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "vendor": t.vendor,
                    "model": t.model,
                    "adapter": t.adapter,
                    "driver": t.driver,
                    "cash_register_id": _u(t.cash_register_id),
                    "agent_id": _u(t.agent_id),
                    "local_id": t.local_id,
                    "host": t.host.split("/")[0] if t.host else None,
                    "port": t.port,
                    "tid": t.tid,
                    "mid": t.mid,
                    "is_default": t.is_default,
                    "status": t.status,
                    "capabilities": _json(t.capabilities) or {},
                    "health_status": t.health_status,
                }
                for t in terminals
            ],
        }


def _relevant_prices(rows: Sequence[Any], now: datetime) -> list[dict[str, Any]]:
    """Per branch key (this branch / all branches): the effective entry + every future-dated one."""
    out: list[dict[str, Any]] = []
    by_branch: dict[UUID | None, list[Any]] = {}
    for r in rows:
        by_branch.setdefault(r.branch_id, []).append(r)
    for branch_id in sorted(by_branch, key=lambda b: str(b or "")):
        items = by_branch[branch_id]
        current = [r for r in items if r.valid_from <= now]
        chosen = (
            [max(current, key=lambda r: (r.valid_from, r.created_at, str(r.id)))] if current else []
        ) + [r for r in items if r.valid_from > now]
        out.extend(
            {
                "price_id": str(r.id),
                "branch_id": _u(r.branch_id),
                "price": price_str(r.price),
                "valid_from": _ts(r.valid_from),
            }
            for r in chosen
        )
    return out


_STREAMS: Final[Mapping[str, Any]] = {
    "catalog.units": SqlPullReader._units,
    "catalog.categories": SqlPullReader._categories,
    "catalog.products": SqlPullReader._products,
    "barcodes": SqlPullReader._barcodes,
    "prices": SqlPullReader._prices,
    "customers": SqlPullReader._customers,
    "stock": SqlPullReader._stock,
    "marking_codes": SqlPullReader._marking,
    "fiscal.registers": SqlPullReader._registers,
    "fiscal.receipts": SqlPullReader._receipts,
}
