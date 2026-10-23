"""Debts SQL (12 ``counterparties``, ``debt_moves``, ``debt_balances``).

Runs inside the caller's ``tenant_transaction`` (RLS-bound); ``tenant_id`` is written explicitly on
INSERT and checked by the RLS ``WITH CHECK`` policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.debts.application.ports import CounterpartyFilter, CounterpartyListRow
from app.modules.debts.domain.counterparties import Counterparty
from app.modules.debts.domain.register import ZERO, BalanceKey, DebtMove, DebtMoveInput, Direction

_CP_COLS = (
    "id, kind, name, phone, stir, legal_address, bank_account, bank_mfo, vat_payer, is_customer, "
    "is_supplier, credit_limit, standing_discount_pct, notify_consent, notify_consent_at, note, "
    "archived_at, created_at, updated_at, version"
)
_UPDATABLE = frozenset(
    {
        "kind",
        "name",
        "phone",
        "stir",
        "legal_address",
        "bank_account",
        "bank_mfo",
        "vat_payer",
        "is_customer",
        "is_supplier",
        "credit_limit",
        "standing_discount_pct",
        "notify_consent",
        "notify_consent_at",
        "note",
    }
)
_INSERTABLE = ("id", "tenant_id", *sorted(_UPDATABLE))
_MOVE_COLS = (
    "id, counterparty_id, direction, amount, due_date, limit_exceeded, doc_type, doc_id, reversal_of_id, "
    "created_at"
)


_INSERT_MOVE = (
    "INSERT INTO app.debt_moves (id, tenant_id, counterparty_id, direction, amount, due_date, "  # noqa: S608
    "limit_exceeded, doc_type, doc_id, reversal_of_id) "
    "VALUES (:id, :t, :cp, :d, :amount, :due, :le, :doc_type, :doc_id, :rev) "
    f"RETURNING {_MOVE_COLS}"
)


def _counterparty(row: Row[Any]) -> Counterparty:
    m = row._mapping
    return Counterparty(**{k: m[k] for k in Counterparty.__dataclass_fields__})


def _move(row: Row[Any]) -> DebtMove:
    m = row._mapping
    return DebtMove(**{k: m[k] for k in DebtMove.__dataclass_fields__})


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class SqlCounterpartyRepository:
    async def get(self, s: AsyncSession, counterparty_id: UUID, *, lock: bool = False) -> Counterparty | None:
        sql = f"SELECT {_CP_COLS} FROM app.counterparties WHERE id = :id"  # noqa: S608
        row = (await s.execute(text(sql + (" FOR UPDATE" if lock else "")), {"id": counterparty_id})).first()
        return _counterparty(row) if row else None

    async def list_page(
        self, s: AsyncSession, flt: CounterpartyFilter, offset: int, limit: int
    ) -> tuple[list[CounterpartyListRow], int]:
        where = ["c.archived_at IS NOT NULL" if flt.archived else "c.archived_at IS NULL"]
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if flt.kind is not None:
            where.append("c.kind = :kind")
            params["kind"] = flt.kind
        if flt.is_supplier is not None:
            where.append("c.is_supplier = :is_supplier")
            params["is_supplier"] = flt.is_supplier
        if flt.is_customer is not None:
            where.append("c.is_customer = :is_customer")
            params["is_customer"] = flt.is_customer
        if flt.search:
            cond = ["c.name ILIKE :q"]
            params["q"] = _like(flt.search)
            if flt.search_digits:
                cond += ["c.phone LIKE :qd", "c.stir LIKE :qd"]
                params["qd"] = _like(flt.search_digits)
            where.append("(" + " OR ".join(cond) + ")")
        clause = " AND ".join(where)
        total = (
            await s.execute(text(f"SELECT count(*) FROM app.counterparties c WHERE {clause}"), params)  # noqa: S608
        ).scalar_one()
        cols = ", ".join(f"c.{c.strip()}" for c in _CP_COLS.split(","))
        rows = await s.execute(
            text(
                f"SELECT {cols}, "  # noqa: S608
                "COALESCE(r.balance, 0) AS receivable_balance, COALESCE(p.balance, 0) AS payable_balance "
                "FROM app.counterparties c "
                "LEFT JOIN app.debt_balances r ON r.counterparty_id = c.id AND r.direction = 'receivable' "
                "LEFT JOIN app.debt_balances p ON p.counterparty_id = c.id AND p.direction = 'payable' "
                f"WHERE {clause} ORDER BY c.name, c.id OFFSET :offset LIMIT :limit"
            ),
            params,
        )
        items = [
            CounterpartyListRow(
                counterparty=_counterparty(r),
                receivable_balance=r._mapping["receivable_balance"],
                payable_balance=r._mapping["payable_balance"],
            )
            for r in rows
        ]
        return items, int(total)

    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        cols = ", ".join(_INSERTABLE)
        values = ", ".join(f":{c}" for c in _INSERTABLE)
        await s.execute(
            text(f"INSERT INTO app.counterparties ({cols}) VALUES ({values})"),  # noqa: S608
            {c: row.get(c) for c in _INSERTABLE},
        )

    async def update(
        self, s: AsyncSession, counterparty_id: UUID, version: int, values: Mapping[str, Any]
    ) -> bool:
        cols = [k for k in values if k in _UPDATABLE]
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        result = await s.execute(
            text(
                f"UPDATE app.counterparties SET {assignments}, version = version + 1 "  # noqa: S608
                "WHERE id = :id AND version = :version RETURNING 1"
            ),
            {**{c: values[c] for c in cols}, "id": counterparty_id, "version": version},
        )
        return result.first() is not None

    async def set_archived(self, s: AsyncSession, counterparty_id: UUID, archived: bool) -> None:
        await s.execute(
            text(
                "UPDATE app.counterparties SET archived_at = CASE WHEN :a THEN now() END, "
                "version = version + 1 WHERE id = :id"
            ),
            {"a": archived, "id": counterparty_id},
        )

    async def find_by_stir(self, s: AsyncSession, stir: str) -> UUID | None:
        row = (
            await s.execute(
                text(
                    "SELECT id FROM app.counterparties WHERE stir = :stir "
                    "ORDER BY archived_at IS NOT NULL, created_at LIMIT 1"
                ),
                {"stir": stir},
            )
        ).first()
        return row[0] if row else None


class SqlDebtRegisterRepository:
    async def lock_balances(
        self, s: AsyncSession, tenant_id: UUID, keys: Sequence[BalanceKey]
    ) -> dict[BalanceKey, Decimal]:
        """23 §2.1: create missing rows, then ``FOR UPDATE`` them one by one in the given (sorted) order."""
        result: dict[BalanceKey, Decimal] = {}
        for counterparty_id, direction in keys:
            await s.execute(
                text(
                    "INSERT INTO app.debt_balances (tenant_id, counterparty_id, direction, balance) "
                    "VALUES (:t, :cp, :d, 0) ON CONFLICT (tenant_id, counterparty_id, direction) DO NOTHING"
                ),
                {"t": tenant_id, "cp": counterparty_id, "d": direction},
            )
            balance = (
                await s.execute(
                    text(
                        "SELECT balance FROM app.debt_balances "
                        "WHERE tenant_id = :t AND counterparty_id = :cp AND direction = :d FOR UPDATE"
                    ),
                    {"t": tenant_id, "cp": counterparty_id, "d": direction},
                )
            ).scalar_one()
            result[(counterparty_id, direction)] = balance
        return result

    async def insert_moves(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[tuple[UUID, DebtMoveInput, UUID | None]]
    ) -> list[DebtMove]:
        written: list[DebtMove] = []
        for move_id, move, reversal_of in rows:
            row = (
                await s.execute(
                    text(_INSERT_MOVE),
                    {
                        "id": move_id,
                        "t": tenant_id,
                        "cp": move.counterparty_id,
                        "d": move.direction,
                        "amount": move.amount,
                        "due": move.due_date,
                        "le": move.limit_exceeded,
                        "doc_type": move.doc_type,
                        "doc_id": move.doc_id,
                        "rev": reversal_of,
                    },
                )
            ).one()
            written.append(_move(row))
        return written

    async def add_to_balances(
        self, s: AsyncSession, tenant_id: UUID, deltas: Mapping[BalanceKey, Decimal]
    ) -> None:
        for (counterparty_id, direction), delta in deltas.items():
            if delta == ZERO:
                continue
            await s.execute(
                text(
                    "UPDATE app.debt_balances SET balance = balance + :delta, updated_at = now() "
                    "WHERE tenant_id = :t AND counterparty_id = :cp AND direction = :d"
                ),
                {"delta": delta, "t": tenant_id, "cp": counterparty_id, "d": direction},
            )

    async def moves_of_doc(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> list[DebtMove]:
        rows = await s.execute(
            text(
                f"SELECT {_MOVE_COLS} FROM app.debt_moves "  # noqa: S608
                "WHERE doc_type = :doc_type AND doc_id = :doc_id ORDER BY created_at, id"
            ),
            {"doc_type": doc_type, "doc_id": doc_id},
        )
        return [_move(r) for r in rows]

    async def balances(self, s: AsyncSession, counterparty_id: UUID) -> dict[Direction, Decimal]:
        rows = await s.execute(
            text("SELECT direction, balance FROM app.debt_balances WHERE counterparty_id = :cp"),
            {"cp": counterparty_id},
        )
        return {r[0]: r[1] for r in rows}
