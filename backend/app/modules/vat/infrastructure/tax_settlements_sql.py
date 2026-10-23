"""SQL of ``tax_settlements`` (12; reads ``vat_moves``, ``branches``, ``tenants.settings``). Runs inside the
caller's ``tenant_transaction`` (RLS)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vat.application.tax_settlements import SettlementFilter, SettlementRow

ZERO = Decimal("0.00")
_UPDATABLE = frozenset(
    {"status", "number", "posted_at", "cancelled_at", "cancelled_by", "cancel_reason", "base_amount", "rate",
     "amount"}
)  # fmt: skip
_COLUMNS = (
    "SELECT id, number, branch_id, doc_date, status, tax_kind, period, base_amount, rate, amount, "
    "expense_account, comment, created_by, created_at, posted_at, cancelled_at, cancel_reason "
    "FROM app.tax_settlements "
)


def _row(r: Any) -> SettlementRow:
    return SettlementRow(
        id=r.id, number=r.number, branch_id=r.branch_id, doc_date=r.doc_date, status=r.status,
        tax_kind=r.tax_kind, period=r.period, base_amount=Decimal(r.base_amount),
        rate=None if r.rate is None else Decimal(r.rate), amount=Decimal(r.amount),
        expense_account=r.expense_account, comment=r.comment, created_by=r.created_by,
        created_at=r.created_at, posted_at=r.posted_at, cancelled_at=r.cancelled_at,
        cancel_reason=r.cancel_reason,
    )  # fmt: skip


class SqlTaxSettlementRepository:
    async def vat_input(self, s: AsyncSession, period: date) -> tuple[Decimal, Decimal]:
        row = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(base_amount), 0), COALESCE(sum(vat_amount), 0) FROM app.vat_moves "
                    "WHERE period = :p AND kind = 'input'"
                ),
                {"p": period},
            )
        ).one()
        return Decimal(row[0]), Decimal(row[1])

    async def default_branch(self, s: AsyncSession) -> UUID:
        value: UUID = (
            await s.execute(text("SELECT id FROM app.branches WHERE is_default ORDER BY id LIMIT 1"))
        ).scalar_one()
        return value

    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool:
        found = (
            await s.execute(text("SELECT 1 FROM app.branches WHERE id = :id"), {"id": branch_id})
        ).first()
        return found is not None

    async def turnover_account(self, s: AsyncSession) -> str:
        value = (
            await s.execute(text("SELECT settings->>'turnover_tax_account' FROM app.tenants LIMIT 1"))
        ).scalar()
        return "9820" if value == "9820" else "9430"

    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> bool:
        """``ON CONFLICT DO NOTHING`` against the partial unique indexes (one active document per
        (tenant, period) / (branch, period)) — a concurrent duplicate waits and is refused, never a 500."""
        result = await s.execute(
            text(
                "INSERT INTO app.tax_settlements (id, tenant_id, branch_id, doc_date, tax_kind, period, "
                "base_amount, rate, amount, expense_account, created_by, comment) VALUES (:id, :tenant_id, "
                ":branch_id, :doc_date, :tax_kind, :period, :base_amount, :rate, :amount, :expense_account, "
                ":created_by, :comment) ON CONFLICT DO NOTHING RETURNING id"
            ),
            dict(row),
        )
        return result.first() is not None

    async def active_id(self, s: AsyncSession, tax_kind: str, period: date, branch_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text(
                    "SELECT id FROM app.tax_settlements WHERE tax_kind = :k AND period = :p "
                    "AND status <> 'cancelled' AND (:k = 'vat_offset' OR branch_id = :b) ORDER BY id LIMIT 1"
                ),
                {"k": tax_kind, "p": period, "b": branch_id},
            )
        ).scalar()
        return value

    async def get(self, s: AsyncSession, settlement_id: UUID, *, lock: bool = False) -> SettlementRow | None:
        suffix = " FOR UPDATE" if lock else ""
        row = (await s.execute(text(_COLUMNS + "WHERE id = :id" + suffix), {"id": settlement_id})).first()
        return None if row is None else _row(row)

    async def list_page(
        self, s: AsyncSession, flt: SettlementFilter, after: UUID | None, limit: int
    ) -> list[SettlementRow]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        expanding: list[str] = []
        if flt.branch_ids is not None:
            where.append("branch_id IN :branches")
            params["branches"] = list(flt.branch_ids)
            expanding.append("branches")
        for column, value in (("tax_kind", flt.tax_kind), ("period", flt.period), ("status", flt.status)):
            if value is not None:
                where.append(f"{column} = :{column}")
                params[column] = value
        if after is not None:
            where.append("id < :after")
            params["after"] = after
        clause = ("WHERE " + " AND ".join(where) + " ") if where else ""
        stmt = text(_COLUMNS + clause + "ORDER BY id DESC LIMIT :limit")
        if expanding:
            stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding))
        return [_row(r) for r in await s.execute(stmt, params)]

    async def update(self, s: AsyncSession, settlement_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _UPDATABLE]
        if not cols:
            return
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        await s.execute(
            text(f"UPDATE app.tax_settlements SET {assignments} WHERE id = :id"),  # noqa: S608
            {**{c: values[c] for c in cols}, "id": settlement_id},
        )
