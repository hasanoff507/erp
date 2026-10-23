"""``period_closings`` + month-closing readiness SQL (12 §2.7, 13 §5.1, 20 #14–#16). Caller's txn."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.application.ports import ClosingRow, DeviceOutbox
from app.modules.accounting.domain.closing import period_end
from app.modules.accounting.infrastructure.repositories import PERIOD_LOCK_KEY

# posting documents that may stay unposted in a month (13 §2.25); stock_counts use their own statuses
DRAFT_TABLES: Final = (
    "goods_receipts", "supplier_returns", "transfers", "write_offs", "stock_openings", "debt_openings",
    "debt_writeoffs", "expenses", "bank_settlements", "tax_settlements",
)  # fmt: skip


class SqlClosingRepository:
    async def lock_exclusive(self, s: AsyncSession) -> bool:
        got = (await s.execute(text(f"SELECT pg_try_advisory_xact_lock({PERIOD_LOCK_KEY})"))).scalar()
        return bool(got)

    async def last_closed(self, s: AsyncSession) -> date | None:
        value: date | None = (await s.execute(text("SELECT max(period) FROM app.period_closings"))).scalar()
        return value

    async def first_activity(self, s: AsyncSession) -> date | None:
        """Earliest accounting date: the first ledger line or ``go_live_date − 1`` (openings, 13 §5.5)."""
        value: date | None = (
            await s.execute(
                text(
                    "SELECT least((SELECT min(entry_date) FROM app.ledger_entries), "
                    "(SELECT go_live_date - 1 FROM app.tenants LIMIT 1))"
                )
            )
        ).scalar()
        return value

    async def insert(self, s: AsyncSession, tenant_id: UUID, period: date, user_id: UUID) -> ClosingRow:
        row = (
            await s.execute(
                text(
                    "INSERT INTO app.period_closings (tenant_id, period, closed_by) VALUES (:t, :p, :u) "
                    "RETURNING period, closed_at, closed_by"
                ),
                {"t": tenant_id, "p": period, "u": user_id},
            )
        ).one()
        return ClosingRow(row.period, row.closed_at, row.closed_by)

    async def page(self, s: AsyncSession, after: date | None, limit: int) -> list[ClosingRow]:
        rows = await s.execute(
            text(
                "SELECT period, closed_at, closed_by FROM app.period_closings "
                "WHERE (CAST(:after AS date) IS NULL OR period < :after) ORDER BY period DESC LIMIT :limit"
            ),
            {"after": after, "limit": limit},
        )
        return [ClosingRow(r.period, r.closed_at, r.closed_by) for r in rows]

    async def pending_recost(self, s: AsyncSession, end: date) -> int:
        value = (
            await s.execute(
                text(
                    "SELECT count(*) FROM app.recost_jobs WHERE status IN ('queued','running','failed') "
                    "AND from_date <= :e"
                ),
                {"e": end},
            )
        ).scalar()
        return int(value or 0)

    async def unsynced_devices(self, s: AsyncSession, bound: datetime) -> list[DeviceOutbox]:
        rows = await s.execute(
            text(
                "SELECT d.id, cr.name, d.outbox_pending_count, d.outbox_oldest_pending_at FROM app.devices d "
                "LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id "
                "WHERE d.kind IN ('web','android') AND d.revoked_at IS NULL AND d.outbox_pending_count > 0 "
                "AND d.outbox_oldest_pending_at < :bound ORDER BY d.id"
            ),
            {"bound": bound},
        )
        return [DeviceOutbox(r[0], r[1], int(r[2]), r[3]) for r in rows]

    async def devices_not_synced(self, s: AsyncSession, bound: datetime) -> int:
        value = (
            await s.execute(
                text(
                    "SELECT count(*) FROM app.devices WHERE kind IN ('web','android') AND revoked_at IS NULL "
                    "AND created_at < :bound AND (last_sync_at IS NULL OR last_sync_at < :bound)"
                ),
                {"bound": bound},
            )
        ).scalar()
        return int(value or 0)

    async def opening_0000_balance(self, s: AsyncSession) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(CASE WHEN account_dt = '0000' THEN amount ELSE -amount END), 0) "
                    "FROM app.ledger_entries WHERE account_dt = '0000' OR account_kt = '0000'"
                )
            )
        ).scalar()
        return Decimal(value or 0).quantize(Decimal("0.01"))

    async def open_shifts(self, s: AsyncSession, bound: datetime) -> int:
        value = (
            await s.execute(
                text("SELECT count(*) FROM app.shifts WHERE status = 'open' AND opened_at < :bound"),
                {"bound": bound},
            )
        ).scalar()
        return int(value or 0)

    async def drafts_in_period(self, s: AsyncSession, start: date, end: date) -> int:
        parts = [
            f"SELECT count(*) AS n FROM app.{t} WHERE status = 'draft' AND doc_date BETWEEN :a AND :e"  # noqa: S608
            for t in DRAFT_TABLES
        ]
        parts.append(
            "SELECT count(*) AS n FROM app.stock_counts WHERE status IN ('counting','review') "
            "AND doc_date BETWEEN :a AND :e"
        )
        sql = f"SELECT COALESCE(sum(n), 0) FROM ({' UNION ALL '.join(parts)}) x"  # noqa: S608
        value = (await s.execute(text(sql), {"a": start, "e": end})).scalar()
        return int(value or 0)

    async def ledger_stock_mismatches(self, s: AsyncSession) -> list[tuple[str, Decimal, Decimal]]:
        """ACC-09: GL balance of 2910/2920 vs Σ ``stock_balances.value`` of the warehouses booked to it."""
        rows = await s.execute(
            text(
                "WITH gl AS ("
                " SELECT a.account, COALESCE(sum(CASE WHEN le.account_dt = a.account THEN le.amount "
                "   ELSE -le.amount END), 0) AS bal"
                " FROM (VALUES ('2910'), ('2920')) a(account)"
                " LEFT JOIN app.ledger_entries le ON le.account_dt = a.account OR le.account_kt = a.account"
                " GROUP BY a.account),"
                " st AS ("
                " SELECT w.inventory_account AS account, COALESCE(sum(sb.value), 0) AS val"
                " FROM app.stock_balances sb JOIN app.warehouses w ON w.id = sb.warehouse_id"
                " GROUP BY w.inventory_account)"
                " SELECT gl.account, gl.bal, COALESCE(st.val, 0)"
                " FROM gl LEFT JOIN st ON st.account = gl.account"
                " ORDER BY gl.account"
            )
        )
        return [(r[0], Decimal(r[1]), Decimal(r[2])) for r in rows if Decimal(r[1]) != Decimal(r[2])]


class SqlFiscalReadiness:
    """Fallback of b5-fiscal ``fiscal_readiness`` (contracts/accounting.md): receipts whose document is dated
    ≤ the month end and whose status is still ``pending``/``sent``/``failed`` (13 §5.1 ``fiscal_pending``)."""

    async def __call__(self, s: AsyncSession, tenant_id: UUID, period: date) -> int:
        value = (
            await s.execute(
                text(
                    "SELECT count(*) FROM app.fiscal_receipts f "
                    "LEFT JOIN app.sales sa ON sa.id = f.sale_id "
                    "LEFT JOIN app.returns r ON r.id = f.return_id "
                    "LEFT JOIN app.debt_payments dp ON dp.id = f.debt_payment_id "
                    "LEFT JOIN app.shifts sh ON sh.id = f.shift_id "
                    "WHERE f.status IN ('pending','sent','failed') "
                    "AND COALESCE(sa.doc_date, r.doc_date, dp.doc_date, "
                    "(COALESCE(sh.closed_at, f.created_at) AT TIME ZONE 'Asia/Tashkent')::date) <= :e"
                ),
                {"e": period_end(period)},
            )
        ).scalar()
        return int(value or 0)
