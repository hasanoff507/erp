"""SQL for ``app.expense_categories`` / ``app.expenses`` / ``app.recurring_expenses`` (12 §2.6; 0018).

Runs inside the caller's ``tenant_transaction`` (RLS scopes every statement to the tenant).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.access.domain.approvals import UserGrant
from app.modules.expenses.application.ports import (
    CategoryRow,
    ExpenseFilter,
    ExpenseRow,
    GrantSource,
    RuleRow,
    ShiftRef,
)
from app.modules.expenses.domain.categories import ExpenseCategoryTemplate

_INSERT = text(
    "INSERT INTO app.expense_categories (id, tenant_id, code, name, default_account, source_ref, is_system) "
    "VALUES (:id, :tenant_id, :code, :name, :default_account, :source_ref, true) "
    "ON CONFLICT DO NOTHING"
)

_CAT_COLS = "id, code, name, default_account, source_ref, is_system, archived_at, version"

# latest approval request of the document (UUIDv7 ids are monotonic — never order by a timestamp)
_EXP_COLS = (
    "e.id, e.branch_id, e.number, e.doc_date, e.status, e.category_id, c.name, c.default_account, "
    "(SELECT l.account_dt FROM app.ledger_entries l WHERE l.doc_type = 'expenses' AND l.doc_id = e.id "
    " AND l.reversal_of_id IS NULL ORDER BY l.id LIMIT 1), "
    "e.amount, e.source, e.tax_type, e.cash_register_id, e.shift_id, e.attachment_id, e.recurring_rule_id, "
    "e.comment, e.created_by, e.created_at, e.posted_at, e.cancelled_at, e.cancel_reason, e.device_id, "
    "ar.id, CASE WHEN ar.status = 'pending' AND ar.expires_at < now() THEN 'expired' ELSE ar.status END, "
    "ar.requested_value"
)
_EXP_FROM = (
    "FROM app.expenses e JOIN app.expense_categories c ON c.id = e.category_id "
    "LEFT JOIN LATERAL (SELECT r.id, r.status, r.expires_at, r.requested_value FROM app.approval_requests r "
    " WHERE r.linked_doc_type = 'expenses' AND r.linked_doc_id = e.id ORDER BY r.id DESC LIMIT 1) ar ON true"
)
_RULE_COLS = (
    "id, branch_id, category_id, name, amount, period, day_of_month, source, cash_register_id, "
    "next_due_date, last_triggered_at, is_active, created_by, version"
)


def _category(r: Any) -> CategoryRow:
    return CategoryRow(r[0], r[1], r[2], r[3], r[4], bool(r[5]), r[6], int(r[7]))


def _expense(r: Any) -> ExpenseRow:
    return ExpenseRow(
        id=r[0],
        branch_id=r[1],
        number=r[2],
        doc_date=r[3],
        status=r[4],
        category_id=r[5],
        category_name=r[6],
        category_account=r[7],
        posted_account=r[8],
        amount=Decimal(r[9]),
        source=r[10],
        tax_type=r[11],
        cash_register_id=r[12],
        shift_id=r[13],
        attachment_id=r[14],
        recurring_rule_id=r[15],
        comment=r[16],
        created_by=r[17],
        created_at=r[18],
        posted_at=r[19],
        cancelled_at=r[20],
        cancel_reason=r[21],
        device_id=r[22],
        approval_request_id=r[23],
        approval_status=r[24],
        approval_requested_value=None if r[25] is None else Decimal(r[25]),
    )


def _rule(r: Any) -> RuleRow:
    return RuleRow(
        id=r[0],
        branch_id=r[1],
        category_id=r[2],
        name=r[3],
        amount=Decimal(r[4]),
        period=r[5],
        day_of_month=int(r[6]),
        source=r[7],
        cash_register_id=r[8],
        next_due_date=r[9],
        last_triggered_at=r[10],
        is_active=bool(r[11]),
        created_by=r[12],
        version=int(r[13]),
    )


def _filter_sql(flt: ExpenseFilter, params: dict[str, Any]) -> list[str]:
    where = ["true"]
    if flt.branch_ids is not None:
        where.append("e.branch_id = ANY(CAST(:b AS uuid[]))")
        params["b"] = [str(b) for b in flt.branch_ids]
    if flt.category_id is not None:
        where.append("e.category_id = :cat")
        params["cat"] = flt.category_id
    if flt.source is not None:
        where.append("e.source = :src")
        params["src"] = flt.source
    if flt.status is not None:
        where.append("e.status = :st")
        params["st"] = flt.status
    if flt.date_from is not None:
        where.append("e.doc_date >= :df")
        params["df"] = flt.date_from
    if flt.date_to is not None:
        where.append("e.doc_date <= :dt")
        params["dt"] = flt.date_to
    return where


class ExpenseCategoryRepository:
    async def insert_system_categories(
        self, session: AsyncSession, tenant_id: UUID, categories: Iterable[ExpenseCategoryTemplate]
    ) -> None:
        await insert_system_categories(session, tenant_id, categories)


async def insert_system_categories(
    session: AsyncSession, tenant_id: UUID, categories: Iterable[ExpenseCategoryTemplate]
) -> None:
    rows = [
        {
            "id": uuid7(),
            "tenant_id": tenant_id,
            "code": c.code,
            "name": c.name,
            "default_account": c.default_account,
            "source_ref": c.source_ref,
        }
        for c in categories
    ]
    if rows:
        await session.execute(_INSERT, rows)


class SqlExpenseRepository(ExpenseCategoryRepository):
    def __init__(self, grants: GrantSource) -> None:
        self._grants = grants  # access.wiring.permission_grants(), injected by the composition

    # --- grants / approvals ---------------------------------------------------------------------
    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant:
        return await self._grants.grant(s, user_id, code)

    async def insert_approval_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await self._grants.insert_request(s, row)

    async def approval_requester(self, s: AsyncSession, request_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text("SELECT requested_by FROM app.approval_requests WHERE id = :id"), {"id": request_id}
            )
        ).scalar()
        return value

    # --- categories -----------------------------------------------------------------------------
    async def list_categories(self, s: AsyncSession, *, include_archived: bool) -> list[CategoryRow]:
        where = "" if include_archived else "WHERE archived_at IS NULL "
        rows = await s.execute(
            text(f"SELECT {_CAT_COLS} FROM app.expense_categories {where}ORDER BY name, id")  # noqa: S608
        )
        return [_category(r) for r in rows]

    async def get_category(
        self, s: AsyncSession, category_id: UUID, *, lock: bool = False
    ) -> CategoryRow | None:
        suffix = " FOR UPDATE" if lock else ""
        sql = f"SELECT {_CAT_COLS} FROM app.expense_categories WHERE id = :id{suffix}"  # noqa: S608
        row = (await s.execute(text(sql), {"id": category_id})).first()
        return None if row is None else _category(row)

    async def category_name_taken(self, s: AsyncSession, name: str, exclude: UUID | None) -> bool:
        row = (
            await s.execute(
                text(
                    "SELECT 1 FROM app.expense_categories WHERE lower(name) = lower(:n) "
                    "AND (CAST(:x AS uuid) IS NULL OR id <> CAST(:x AS uuid))"
                ),
                {"n": name, "x": None if exclude is None else str(exclude)},
            )
        ).first()
        return row is not None

    async def insert_category(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.expense_categories (id, tenant_id, code, name, default_account, is_system) "
                "VALUES (:id, :tenant_id, NULL, :name, :default_account, false)"
            ),
            dict(row),
        )

    async def update_category(
        self, s: AsyncSession, category_id: UUID, version: int, changes: Mapping[str, Any]
    ) -> bool:
        sets: list[str] = []
        params: dict[str, Any] = {"id": category_id, "v": version}
        for key in ("name", "default_account"):
            if key in changes:
                sets.append(f"{key} = :{key}")
                params[key] = changes[key]
        if "archived" in changes:
            sets.append("archived_at = CASE WHEN :arch THEN COALESCE(archived_at, now()) ELSE NULL END")
            params["arch"] = bool(changes["archived"])
        sets.append("version = version + 1")
        result = await s.execute(
            text(
                f"UPDATE app.expense_categories SET {', '.join(sets)} WHERE id = :id AND version = :v"  # noqa: S608
            ),
            params,
        )
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    # --- references -----------------------------------------------------------------------------
    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool:
        row = (await s.execute(text("SELECT 1 FROM app.branches WHERE id = :id"), {"id": branch_id})).first()
        return row is not None

    async def register_branch(self, s: AsyncSession, register_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text("SELECT branch_id FROM app.cash_registers WHERE id = :id AND archived_at IS NULL"),
                {"id": register_id},
            )
        ).scalar()
        return value

    async def get_shift(self, s: AsyncSession, shift_id: UUID) -> ShiftRef | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, branch_id, cash_register_id, status FROM app.shifts WHERE id = :id FOR SHARE"
                ),
                {"id": shift_id},
            )
        ).first()
        return None if row is None else ShiftRef(row[0], row[1], row[2], row[3])

    async def open_shift_of_register(self, s: AsyncSession, register_id: UUID) -> ShiftRef | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, branch_id, cash_register_id, status FROM app.shifts "
                    "WHERE cash_register_id = :c AND status = 'open' ORDER BY id DESC LIMIT 1 FOR SHARE"
                ),
                {"c": register_id},
            )
        ).first()
        return None if row is None else ShiftRef(row[0], row[1], row[2], row[3])

    async def attachment_kind(self, s: AsyncSession, attachment_id: UUID) -> str | None:
        value: str | None = (
            await s.execute(text("SELECT kind FROM app.attachments WHERE id = :id"), {"id": attachment_id})
        ).scalar()
        return value

    async def last_closed_period(self, s: AsyncSession) -> date | None:
        value: date | None = (await s.execute(text("SELECT max(period) FROM app.period_closings"))).scalar()
        return value

    # --- expenses -------------------------------------------------------------------------------
    async def insert_expense(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.expenses (id, tenant_id, branch_id, doc_date, status, category_id, amount, "
                "source, tax_type, cash_register_id, shift_id, attachment_id, recurring_rule_id, created_by, "
                "client_event_id, device_id, comment) VALUES (:id, :tenant_id, :branch_id, :doc_date, "
                "'draft', "
                ":category_id, :amount, :source, :tax_type, :cash_register_id, :shift_id, :attachment_id, "
                ":recurring_rule_id, :created_by, :client_event_id, :device_id, :comment)"
            ),
            dict(row),
        )

    async def get_expense(
        self, s: AsyncSession, expense_id: UUID, *, lock: bool = False
    ) -> ExpenseRow | None:
        if lock:
            await s.execute(text("SELECT 1 FROM app.expenses WHERE id = :id FOR UPDATE"), {"id": expense_id})
        row = (
            await s.execute(text(f"SELECT {_EXP_COLS} {_EXP_FROM} WHERE e.id = :id"), {"id": expense_id})
        ).first()
        return None if row is None else _expense(row)

    async def list_expenses(self, s: AsyncSession, flt: ExpenseFilter) -> list[ExpenseRow]:
        params: dict[str, Any] = {"lim": flt.limit}
        where = _filter_sql(flt, params)
        if flt.cursor is not None:
            where.append("(e.doc_date, e.id) < (:cd, :cid)")
            params["cd"], params["cid"] = flt.cursor
        rows = await s.execute(
            text(
                f"SELECT {_EXP_COLS} {_EXP_FROM} WHERE {' AND '.join(where)} "
                "ORDER BY e.doc_date DESC, e.id DESC LIMIT :lim"
            ),
            params,
        )
        return [_expense(r) for r in rows]

    async def totals(self, s: AsyncSession, flt: ExpenseFilter) -> dict[str, Decimal]:
        params: dict[str, Any] = {}
        where = _filter_sql(flt, params)
        rows = await s.execute(
            text(
                f"SELECT e.status, COALESCE(sum(e.amount), 0) FROM app.expenses e "  # noqa: S608
                f"WHERE {' AND '.join(where)} "
                "AND e.status IN ('posted', 'draft') GROUP BY e.status"
            ),
            params,
        )
        out = {"posted": Decimal("0"), "draft": Decimal("0")}
        for status, total in rows:
            out[status] = Decimal(total)
        return out

    async def mark_posted(self, s: AsyncSession, expense_id: UUID, number: str) -> datetime:
        at: datetime = (
            await s.execute(
                text(
                    "UPDATE app.expenses SET status = 'posted', number = :n, posted_at = now() "
                    "WHERE id = :id RETURNING posted_at"
                ),
                {"id": expense_id, "n": number},
            )
        ).scalar_one()
        return at

    async def mark_cancelled(self, s: AsyncSession, expense_id: UUID, user_id: UUID, reason: str) -> datetime:
        at: datetime = (
            await s.execute(
                text(
                    "UPDATE app.expenses SET status = 'cancelled', cancelled_at = now(), cancelled_by = :u, "
                    "cancel_reason = :r WHERE id = :id RETURNING cancelled_at"
                ),
                {"id": expense_id, "u": user_id, "r": reason},
            )
        ).scalar_one()
        return at

    async def insert_cash_move(self, s: AsyncSession, row: Mapping[str, Any]) -> UUID:
        move_id = uuid7()
        await s.execute(
            text(
                "INSERT INTO app.cash_moves (id, tenant_id, cash_register_id, shift_id, amount, method, "
                "doc_type, doc_id, reversal_of_id) VALUES (:id, :tenant_id, :cash_register_id, :shift_id, "
                ":amount, 'cash', "
                "'expenses', :doc_id, :reversal_of_id)"
            ),
            {"id": move_id, "reversal_of_id": None, **dict(row)},
        )
        return move_id

    async def live_cash_moves(
        self, s: AsyncSession, doc_id: UUID
    ) -> list[tuple[UUID, Decimal, UUID | None, UUID | None, str]]:
        rows = await s.execute(
            text(
                "SELECT m.id, m.amount, m.cash_register_id, m.shift_id, m.method FROM app.cash_moves m "
                "WHERE m.doc_type = 'expenses' AND m.doc_id = :d AND m.reversal_of_id IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM app.cash_moves r WHERE r.reversal_of_id = m.id)"
            ),
            {"d": doc_id},
        )
        return [(r[0], Decimal(r[1]), r[2], r[3], r[4]) for r in rows]

    # --- recurring rules ------------------------------------------------------------------------
    async def list_rules(
        self,
        s: AsyncSession,
        branch_ids: Sequence[UUID] | None,
        is_active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[RuleRow], int]:
        where = ["true"]
        params: dict[str, Any] = {"off": offset, "lim": limit}
        if branch_ids is not None:
            where.append("branch_id = ANY(CAST(:b AS uuid[]))")
            params["b"] = [str(b) for b in branch_ids]
        if is_active is not None:
            where.append("is_active = :act")
            params["act"] = is_active
        cond = " AND ".join(where)
        count_sql = f"SELECT count(*) FROM app.recurring_expenses WHERE {cond}"  # noqa: S608
        total = int((await s.execute(text(count_sql), params)).scalar_one())
        rows = await s.execute(
            text(
                f"SELECT {_RULE_COLS} FROM app.recurring_expenses WHERE {cond} "  # noqa: S608
                "ORDER BY next_due_date, id OFFSET :off LIMIT :lim"
            ),
            params,
        )
        return [_rule(r) for r in rows], total

    async def get_rule(self, s: AsyncSession, rule_id: UUID, *, lock: bool = False) -> RuleRow | None:
        suffix = " FOR UPDATE" if lock else ""
        sql = f"SELECT {_RULE_COLS} FROM app.recurring_expenses WHERE id = :id{suffix}"  # noqa: S608
        row = (await s.execute(text(sql), {"id": rule_id})).first()
        return None if row is None else _rule(row)

    async def insert_rule(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.recurring_expenses (id, tenant_id, branch_id, category_id, name, amount, "
                "period, day_of_month, source, cash_register_id, next_due_date, created_by) VALUES (:id, "
                ":tenant_id, :branch_id, :category_id, :name, :amount, :period, :day_of_month, :source, "
                ":cash_register_id, "
                ":next_due_date, :created_by)"
            ),
            dict(row),
        )

    async def update_rule(
        self, s: AsyncSession, rule_id: UUID, version: int, changes: Mapping[str, Any]
    ) -> bool:
        sets = [f"{k} = :{k}" for k in changes]
        sets.append("version = version + 1")
        result = await s.execute(
            text(
                f"UPDATE app.recurring_expenses SET {', '.join(sets)} WHERE id = :id AND version = :v"  # noqa: S608
            ),
            {"id": rule_id, "v": version, **dict(changes)},
        )
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def due_rules(self, s: AsyncSession, today: date) -> list[RuleRow]:
        rows = await s.execute(
            text(
                f"SELECT {_RULE_COLS} FROM app.recurring_expenses "  # noqa: S608
                "WHERE is_active AND next_due_date <= :d ORDER BY next_due_date, id"
            ),
            {"d": today},
        )
        return [_rule(r) for r in rows]

    async def mark_rule_triggered(self, s: AsyncSession, rule_id: UUID) -> None:
        await s.execute(
            text("UPDATE app.recurring_expenses SET last_triggered_at = now() WHERE id = :id"),
            {"id": rule_id},
        )
