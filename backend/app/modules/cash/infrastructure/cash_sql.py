"""Shifts / cash movements / cash_moves SQL (12 ``shifts``, ``cash_movements``, ``cash_moves``).

Runs inside the caller's ``tenant_transaction`` (RLS-bound).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.access.domain.approvals import UserGrant
from app.modules.access.wiring import permission_grants
from app.modules.cash.application.ports import (
    MovementFilter,
    MovementRow,
    RegisterRow,
    ShiftFilter,
    ShiftRow,
)
from app.modules.cash.domain.shifts import ZERO, SettlementRow, ShiftTotals

_SHIFT_COLS = (
    "id, branch_id, cash_register_id, device_id, shift_no, status, opened_by, opened_at, closed_by, "
    "closed_at, "
    "opening_cash, expected_cash, counted_cash, variance, variance_note, counted_card_total, comment"
)
_MOVE_COLS = (
    "id, branch_id, number, doc_date, status, cash_register_id, shift_id, direction, amount, reason, "
    "account, "
    "counterparty_id, employee_id, comment, created_by, created_at, posted_at, cancelled_at, cancel_reason, "
    "device_id"
)


def _shift(r: Any) -> ShiftRow:
    return ShiftRow(*r)


def _move(r: Any) -> MovementRow:
    return MovementRow(*r)


def _dec(value: Any) -> Decimal:
    return ZERO if value is None else Decimal(value)


class SqlCashRepository:
    # --- shifts ---------------------------------------------------------------------------------------
    async def get_shift(self, s: AsyncSession, shift_id: UUID, *, lock: str | None = None) -> ShiftRow | None:
        suffix = {"share": " FOR SHARE", "update": " FOR UPDATE"}.get(lock or "", "")
        r = (
            await s.execute(
                text(f"SELECT {_SHIFT_COLS} FROM app.shifts WHERE id = :id{suffix}"),  # noqa: S608
                {"id": shift_id},
            )
        ).first()
        return None if r is None else _shift(r)

    async def open_shift_of_register(self, s: AsyncSession, register_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text("SELECT id FROM app.shifts WHERE cash_register_id = :c AND status = 'open'"),
                {"c": register_id},
            )
        ).scalar()
        return value

    async def shift_no_taken(self, s: AsyncSession, register_id: UUID, shift_no: int) -> bool:
        found = (
            await s.execute(
                text("SELECT 1 FROM app.shifts WHERE cash_register_id = :c AND shift_no = :n"),
                {"c": register_id, "n": shift_no},
            )
        ).first()
        return found is not None

    async def insert_shift(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.shifts (id, tenant_id, branch_id, cash_register_id, device_id, shift_no, "
                "status, "
                "opened_by, opened_at, opening_cash, comment, client_event_id) VALUES (:id, :tenant_id, "
                ":branch_id, "
                ":cash_register_id, :device_id, :shift_no, 'open', :opened_by, :opened_at, :opening_cash, "
                ":comment, "
                ":client_event_id)"
            ),
            dict(row),
        )

    async def close_shift(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "UPDATE app.shifts SET status = 'closed', closed_by = :closed_by, closed_at = :closed_at, "
                "expected_cash = :expected_cash, counted_cash = :counted_cash, variance_note = "
                ":variance_note, "
                "counted_card_total = :counted_card_total, updated_at = now() WHERE id = :id AND status = "
                "'open'"
            ),
            dict(row),
        )

    async def cash_moves_total(self, s: AsyncSession, shift_id: UUID) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(amount), 0) FROM app.cash_moves WHERE shift_id = :s AND method = "
                    "'cash'"
                ),
                {"s": shift_id},
            )
        ).scalar()
        return _dec(value)

    async def doc_cash_delta(self, s: AsyncSession, shift_id: UUID, doc_type: str, doc_id: UUID) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(amount), 0) FROM app.cash_moves "
                    "WHERE shift_id = :s AND method = 'cash' "
                    "AND doc_type = :t AND doc_id = :d"
                ),
                {"s": shift_id, "t": doc_type, "d": doc_id},
            )
        ).scalar()
        return _dec(value)

    async def adjust_expected(self, s: AsyncSession, shift_id: UUID, delta: Decimal, note: str) -> None:
        await s.execute(
            text(
                "UPDATE app.shifts SET expected_cash = expected_cash + :d, "
                "variance_note = COALESCE(variance_note, :n), updated_at = now() WHERE id = :id"
            ),
            {"id": shift_id, "d": delta, "n": note},
        )

    async def shift_totals(self, s: AsyncSession, shift_id: UUID) -> ShiftTotals:
        p = {"s": shift_id}
        methods = {
            r[0]: _dec(r[1])
            for r in await s.execute(
                text(
                    "SELECT sp.method, sum(sp.amount) FROM app.sale_payments sp JOIN app.sales sa ON sa.id "
                    "= sp.sale_id "
                    "WHERE sa.shift_id = :s AND sa.status = 'posted' GROUP BY sp.method"
                ),
                p,
            )
        }
        split = {
            r[0]: _dec(r[1])
            for r in await s.execute(
                text(
                    "SELECT sp.card_entry_mode, sum(sp.amount) FROM app.sale_payments sp "
                    "JOIN app.sales sa ON sa.id = sp.sale_id WHERE sa.shift_id = :s AND sa.status = 'posted' "
                    "AND sp.method = 'card' GROUP BY sp.card_entry_mode"
                ),
                p,
            )
        }
        sales = (
            await s.execute(
                text(
                    "SELECT (SELECT count(*) FROM app.sales WHERE shift_id = :s AND status = 'posted'), "
                    "(SELECT count(*) FROM app.audit_log WHERE action = 'sale.draft_voided' "
                    "AND after->>'shift_id' = CAST(:s AS text) AND "
                    "COALESCE((after->>'whole_receipt')::boolean, false))"
                ),
                p,
            )
        ).one()
        lines = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(sl.vat_amount), 0), COALESCE(sum(sl.discount_amount), 0) FROM "
                    "app.sale_lines sl "
                    "JOIN app.sales sa ON sa.id = sl.sale_id WHERE sa.shift_id = :s AND sa.status = 'posted'"
                ),
                p,
            )
        ).one()
        rets = (
            await s.execute(
                text(
                    "SELECT count(DISTINCT r.id), COALESCE(sum(rl.line_total), 0) FROM app.returns r "
                    "LEFT JOIN app.return_lines rl ON rl.return_id = r.id WHERE r.shift_id = :s AND "
                    "r.status = 'posted'"
                ),
                p,
            )
        ).one()
        moves = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(amount) FILTER (WHERE direction = 'in'), 0), "
                    "COALESCE(sum(amount) FILTER (WHERE direction = 'out'), 0) FROM app.cash_movements "
                    "WHERE shift_id = :s AND status = 'posted'"
                ),
                p,
            )
        ).one()
        settlements = [
            SettlementRow(r[0], _dec(r[1]), _dec(r[2]), _dec(r[3]), r[4])
            for r in await s.execute(
                text(
                    "SELECT card_terminal_id, net_total, expected_total, variance, status "
                    "FROM app.card_terminal_settlements WHERE shift_id = :s ORDER BY settled_at, id"
                ),
                p,
            )
        ]
        return ShiftTotals(
            totals_by_method=methods,
            card_integrated=split.get("integrated", ZERO),
            card_manual=split.get("manual", ZERO),
            vat_total=_dec(lines[0]),
            discount_total=_dec(lines[1]),
            returns_total=_dec(rets[1]),
            sales_count=int(sales[0]),
            returns_count=int(rets[0]),
            voided_count=int(sales[1]),
            cash_in=_dec(moves[0]),
            cash_out=_dec(moves[1]),
            cash_moves_total=await self.cash_moves_total(s, shift_id),
            settlements=tuple(settlements),
        )

    async def unresolved_card_attempts(self, s: AsyncSession, shift_id: UUID) -> int:
        value = (
            await s.execute(
                text(
                    "SELECT count(*) FROM app.card_terminal_transactions WHERE shift_id = :s "
                    "AND status IN ('pending','unknown')"
                ),
                {"s": shift_id},
            )
        ).scalar()
        return int(value or 0)

    async def list_shifts(self, s: AsyncSession, flt: ShiftFilter) -> list[ShiftRow]:
        where = ["true"]
        params: dict[str, Any] = {"lim": flt.limit}
        if flt.branch_ids is not None:
            where.append("branch_id = ANY(CAST(:b AS uuid[]))")
            params["b"] = [str(b) for b in flt.branch_ids]
        if flt.cash_register_id is not None:
            where.append("cash_register_id = :c")
            params["c"] = flt.cash_register_id
        if flt.status is not None:
            where.append("status = :st")
            params["st"] = flt.status
        if flt.cursor is not None:
            where.append("(opened_at, id) < (:cat, :cid)")
            params["cat"], params["cid"] = flt.cursor
        sql = (
            f"SELECT {_SHIFT_COLS} FROM app.shifts WHERE {' AND '.join(where)} "  # noqa: S608
            "ORDER BY opened_at DESC, id DESC LIMIT :lim"
        )
        return [_shift(r) for r in await s.execute(text(sql), params)]

    async def shifts_between(
        self, s: AsyncSession, register_id: UUID, start: datetime | None, end: datetime | None
    ) -> list[ShiftRow]:
        sql = (
            f"SELECT {_SHIFT_COLS} FROM app.shifts WHERE cash_register_id = :c "  # noqa: S608
            "AND (CAST(:a AS timestamptz) IS NULL OR opened_at >= :a) "
            "AND (CAST(:e AS timestamptz) IS NULL OR opened_at <= :e) ORDER BY opened_at, id LIMIT 1000"
        )
        return [_shift(r) for r in await s.execute(text(sql), {"c": register_id, "a": start, "e": end})]

    async def z_fiscal(self, s: AsyncSession, shift_id: UUID) -> Mapping[str, Any] | None:
        r = (
            await s.execute(
                text(
                    "SELECT id, status, fiscal_sign, qr_url, ofd_acked_at FROM app.fiscal_receipts "
                    "WHERE shift_id = :s AND kind = 'z_report'"
                ),
                {"s": shift_id},
            )
        ).first()
        if r is None:
            return None
        return {"id": r[0], "status": r[1], "fiscal_sign": r[2], "qr_url": r[3], "ofd_acked_at": r[4]}

    # --- references -----------------------------------------------------------------------------------
    async def get_register(self, s: AsyncSession, register_id: UUID) -> RegisterRow | None:
        r = (
            await s.execute(
                text("SELECT id, branch_id, archived_at IS NOT NULL FROM app.cash_registers WHERE id = :id"),
                {"id": register_id},
            )
        ).first()
        return None if r is None else RegisterRow(r[0], r[1], bool(r[2]))

    async def tenant_legal(self, s: AsyncSession) -> tuple[str, str | None]:
        r = (
            await s.execute(
                text("SELECT legal_form, settings->>'owner_withdrawal_account' FROM app.tenants LIMIT 1")
            )
        ).one()
        return str(r[0]), r[1]

    async def counterparty(self, s: AsyncSession, cp_id: UUID) -> tuple[bool, bool] | None:
        """``(is_founder, active)`` or ``None`` when unknown in the tenant."""
        r = (
            await s.execute(
                text("SELECT is_founder, archived_at IS NULL FROM app.counterparties WHERE id = :id"),
                {"id": cp_id},
            )
        ).first()
        return None if r is None else (bool(r[0]), bool(r[1]))

    async def is_member(self, s: AsyncSession, user_id: UUID) -> bool:
        found = (
            await s.execute(text("SELECT 1 FROM app.memberships WHERE user_id = :u"), {"u": user_id})
        ).first()
        return found is not None

    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant:
        return await permission_grants().grant(s, user_id, code)

    async def last_closed_period(self, s: AsyncSession) -> date | None:
        value: date | None = (await s.execute(text("SELECT max(period) FROM app.period_closings"))).scalar()
        return value

    # --- movements ------------------------------------------------------------------------------------
    async def insert_movement(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.cash_movements (id, tenant_id, branch_id, doc_date, status, "
                "cash_register_id, "
                "shift_id, direction, amount, reason, counterparty_id, account, employee_id, created_by, "
                "client_event_id, device_id, comment) VALUES (:id, :tenant_id, :branch_id, :doc_date, "
                "'draft', "
                ":cash_register_id, :shift_id, :direction, :amount, :reason, :counterparty_id, :account, "
                ":employee_id, :created_by, :client_event_id, :device_id, :comment)"
            ),
            dict(row),
        )

    async def get_movement(
        self, s: AsyncSession, movement_id: UUID, *, lock: bool = False
    ) -> MovementRow | None:
        sql = f"SELECT {_MOVE_COLS} FROM app.cash_movements WHERE id = :id" + (" FOR UPDATE" if lock else "")  # noqa: S608
        r = (await s.execute(text(sql), {"id": movement_id})).first()
        return None if r is None else _move(r)

    async def mark_posted(self, s: AsyncSession, movement_id: UUID, number: str) -> None:
        await s.execute(
            text(
                "UPDATE app.cash_movements SET status = 'posted', number = :n, posted_at = now(), "
                "updated_at = now() "
                "WHERE id = :id"
            ),
            {"id": movement_id, "n": number},
        )

    async def mark_cancelled(self, s: AsyncSession, movement_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.cash_movements SET status = 'cancelled', cancelled_at = now(), cancelled_by = "
                ":u, "
                "cancel_reason = :r, updated_at = now() WHERE id = :id"
            ),
            {"id": movement_id, "u": user_id, "r": reason},
        )

    async def insert_cash_move(self, s: AsyncSession, row: Mapping[str, Any]) -> UUID:
        move_id = uuid7()
        await s.execute(
            text(
                "INSERT INTO app.cash_moves (id, tenant_id, cash_register_id, shift_id, amount, method, "
                "doc_type, "
                "doc_id, reversal_of_id) VALUES (:id, :tenant_id, :cash_register_id, :shift_id, :amount, "
                ":method, "
                ":doc_type, :doc_id, :reversal_of_id)"
            ),
            {"id": move_id, "reversal_of_id": None, **dict(row)},
        )
        return move_id

    async def live_cash_moves(
        self, s: AsyncSession, doc_type: str, doc_id: UUID
    ) -> list[tuple[UUID, Decimal, UUID | None, UUID | None, str]]:
        rows = await s.execute(
            text(
                "SELECT m.id, m.amount, m.cash_register_id, m.shift_id, m.method FROM app.cash_moves m "
                "WHERE m.doc_type = :t AND m.doc_id = :d AND m.reversal_of_id IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM app.cash_moves r WHERE r.reversal_of_id = m.id)"
            ),
            {"t": doc_type, "d": doc_id},
        )
        return [(r[0], Decimal(r[1]), r[2], r[3], r[4]) for r in rows]

    async def list_movements(self, s: AsyncSession, flt: MovementFilter) -> list[MovementRow]:
        where = ["true"]
        params: dict[str, Any] = {"lim": flt.limit}
        if flt.branch_ids is not None:
            where.append("branch_id = ANY(CAST(:b AS uuid[]))")
            params["b"] = [str(b) for b in flt.branch_ids]
        for col in ("cash_register_id", "shift_id", "direction", "reason"):
            value = getattr(flt, col)
            if value is not None:
                where.append(f"{col} = :{col}")
                params[col] = value
        if flt.cursor is not None:
            where.append("(created_at, id) < (:cat, :cid)")
            params["cat"], params["cid"] = flt.cursor
        sql = (
            f"SELECT {_MOVE_COLS} FROM app.cash_movements WHERE {' AND '.join(where)} "  # noqa: S608
            "ORDER BY created_at DESC, id DESC LIMIT :lim"
        )
        return [_move(r) for r in await s.execute(text(sql), params)]

    async def insert_approval_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.approval_requests (id, tenant_id, branch_id, kind, permission_code, "
                "requested_value, "
                "context, linked_doc_type, linked_doc_id, device_id, requested_by, requested_at, expires_at) "
                "VALUES (:id, :tenant_id, :branch_id, :kind, :permission_code, :requested_value, "
                "CAST(:context AS jsonb), :linked_doc_type, :linked_doc_id, :device_id, :requested_by, "
                ":requested_at, :expires_at)"
            ),
            dict(row),
        )

    async def pending_request_of(self, s: AsyncSession, movement_id: UUID) -> UUID | None:
        # newest = the largest application uuid7 id (creation order), not a timestamp of another transaction
        value: UUID | None = (
            await s.execute(
                text(
                    "SELECT id FROM app.approval_requests WHERE linked_doc_type = 'cash_movements' "
                    "AND linked_doc_id = :d ORDER BY id DESC LIMIT 1"
                ),
                {"d": movement_id},
            )
        ).scalar()
        return value
