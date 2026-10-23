"""``vat_moves`` / ledger / tax settlement reads for M10 (13 §4). Runs in the caller's tenant transaction."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vat.application.vat import BranchBase, RegimeRange, VatMoveRow, split_regimes

ZERO = Decimal("0.00")
_BASE_ACCOUNTS = "('9020','9040','9050','9390','8530')"
_REVENUE_ACCOUNTS = "('9020','9040','9050')"


def _d(value: Any) -> Decimal:
    return ZERO if value is None else Decimal(value)


class SqlVatRepository:
    async def regime_on(self, s: AsyncSession, on: date) -> str:
        regime = (
            await s.execute(
                text(
                    "SELECT regime FROM app.tenant_tax_regimes WHERE valid_from <= :d ORDER BY valid_from "
                    "DESC LIMIT 1"
                ),
                {"d": on},
            )
        ).scalar()
        return "turnover" if regime == "turnover" else "vat"

    async def regime_ranges(self, s: AsyncSession, start: date, end: date) -> list[RegimeRange]:
        """``[start, end]`` split by the ``tenant_tax_regimes`` in force (ACC-06; no row → ``vat``)."""
        rows = await s.execute(
            text(
                "SELECT valid_from, regime FROM app.tenant_tax_regimes WHERE valid_from <= :e "
                "ORDER BY valid_from"
            ),
            {"e": end},
        )
        return split_regimes([(r[0], r[1]) for r in rows], start, end)

    async def legal_form(self, s: AsyncSession) -> str:
        return str((await s.execute(text("SELECT legal_form FROM app.tenants LIMIT 1"))).scalar_one())

    async def vat_totals(self, s: AsyncSession, period: date) -> tuple[Decimal, Decimal]:
        row = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(vat_amount) FILTER (WHERE kind = 'output'), 0), "
                    "COALESCE(sum(vat_amount) FILTER (WHERE kind = 'input'), 0) FROM app.vat_moves WHERE "
                    "period = :p"
                ),
                {"p": period},
            )
        ).one()
        return _d(row[0]), _d(row[1])

    async def pending_credit(self, s: AsyncSession, start: date, end: date) -> tuple[int, Decimal]:
        row = (
            await s.execute(
                text(
                    "SELECT count(*), COALESCE(sum(e.vat_amount), 0) FROM app.einvoices e "
                    "WHERE e.direction = 'in' AND e.risk_flag IN ('red','unknown') "
                    "AND e.status NOT IN ('cancelled','rejected','draft') AND COALESCE(e.vat_amount, 0) > 0 "
                    "AND e.doc_date BETWEEN :a AND :e "
                    "AND NOT EXISTS (SELECT 1 FROM app.vat_moves v WHERE v.einvoice_id = e.id AND v.kind = "
                    "'input')"
                ),
                {"a": start, "e": end},
            )
        ).one()
        return int(row[0]), _d(row[1])

    async def turnover_bases(
        self, s: AsyncSession, start: date, end: date, branch_ids: tuple[UUID, ...] | None
    ) -> list[BranchBase]:
        rows = await s.execute(
            text(
                "SELECT le.branch_id, "  # noqa: S608
                f"COALESCE(sum(CASE WHEN le.account_kt IN {_BASE_ACCOUNTS} THEN le.amount ELSE 0 END), 0) - "
                f"COALESCE(sum(CASE WHEN le.account_dt IN {_BASE_ACCOUNTS} THEN le.amount ELSE 0 END), 0), "
                "COALESCE(sum(CASE WHEN p.turnover_tax_group = 'tobacco' AND le.account_kt IN "
                f"{_REVENUE_ACCOUNTS} "
                "THEN le.amount ELSE 0 END), 0) - "
                "COALESCE(sum(CASE WHEN p.turnover_tax_group = 'tobacco' AND le.account_dt IN "
                f"{_REVENUE_ACCOUNTS} "
                "THEN le.amount ELSE 0 END), 0) "
                "FROM app.ledger_entries le "
                "LEFT JOIN app.products p ON p.id = CAST(NULLIF(le.analytics->>'product_id', '') AS uuid) "
                "WHERE le.entry_date BETWEEN :a AND :e AND le.branch_id IS NOT NULL "
                "AND (CAST(:b AS uuid[]) IS NULL OR le.branch_id = ANY(CAST(:b AS uuid[]))) "
                f"AND (le.account_kt IN {_BASE_ACCOUNTS} OR le.account_dt IN {_BASE_ACCOUNTS}) "
                "GROUP BY le.branch_id ORDER BY le.branch_id"
            ),
            {"a": start, "e": end, "b": None if branch_ids is None else [str(b) for b in branch_ids]},
        )
        return [BranchBase(r[0], _d(r[1]), _d(r[2])) for r in rows]

    async def tobacco_rate(self, s: AsyncSession, on: date) -> Decimal | None:
        value = (
            await s.execute(
                text(
                    "SELECT rate_pct FROM platform.turnover_tax_rates WHERE code = 'tobacco' AND valid_from "
                    "<= :d "
                    "ORDER BY valid_from DESC LIMIT 1"
                ),
                {"d": on},
            )
        ).scalar()
        return None if value is None else Decimal(value)

    async def settlement_id(
        self, s: AsyncSession, period: date, kind: str, branch_id: UUID | None
    ) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text(
                    "SELECT id FROM app.tax_settlements WHERE period = :p AND tax_kind = :k AND status = "
                    "'posted' "
                    "AND (CAST(:b AS uuid) IS NULL OR branch_id = :b) "
                    # ids are UUIDv7 written by the tax-settlement service (monotonic): latest first
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"p": period, "k": kind, "b": branch_id},
            )
        ).scalar()
        return value

    async def list_moves(
        self,
        s: AsyncSession,
        *,
        kind: str | None,
        period: date | None,
        doc_type: str | None,
        einvoice_id: UUID | None,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[VatMoveRow]:
        where = ["true"]
        params: dict[str, Any] = {"lim": limit}
        for col, value in (
            ("kind", kind),
            ("period", period),
            ("doc_type", doc_type),
            ("einvoice_id", einvoice_id),
        ):
            if value is not None:
                where.append(f"{col} = :{col}")
                params[col] = value
        if cursor is not None:
            where.append("(created_at, id) < (:cat, :cid)")
            params["cat"], params["cid"] = cursor
        rows = await s.execute(
            text(
                "SELECT id, kind, period, base_amount, vat_amount, doc_type, doc_id, einvoice_id, created_at "  # noqa: S608
                f"FROM app.vat_moves WHERE {' AND '.join(where)} ORDER BY created_at DESC, id DESC LIMIT :lim"
            ),
            params,
        )
        return [VatMoveRow(*r) for r in rows]
