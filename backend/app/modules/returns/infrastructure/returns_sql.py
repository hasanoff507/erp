"""SQL of the returns module (caller's transaction; RLS — one tenant)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.returns.application.ports import FreeLot, ReturnFilter, SoldDoc, SoldLine

ZERO = Decimal("0.00")


class SqlReturnsRepository:
    async def return_exists(self, s: AsyncSession, return_id: UUID) -> bool:
        found = await s.execute(text("SELECT 1 FROM app.returns WHERE id = :id"), {"id": return_id})
        return found.first() is not None

    async def sale_for_return(self, s: AsyncSession, sale_id: UUID) -> SoldDoc | None:
        head = (
            await s.execute(
                text(
                    "SELECT id, branch_id, status, counterparty_id FROM app.sales WHERE id = :id FOR UPDATE"
                ),
                {"id": sale_id},
            )
        ).first()
        if head is None:
            return None
        lines = await s.execute(
            text(
                "SELECT l.id, l.product_id, l.qty, l.price, l.vat_rate, l.vat_exemption_code, l.line_total, "
                "l.marking_code, "
                "COALESCE((SELECT sum(rl.qty) FROM app.return_lines rl JOIN app.returns r ON r.id = "
                "rl.return_id "
                "  WHERE rl.sale_line_id = l.id AND r.status = 'posted'), 0), "
                "COALESCE((SELECT sum(rl.line_total) FROM app.return_lines rl JOIN app.returns r "
                "  ON r.id = rl.return_id WHERE rl.sale_line_id = l.id AND r.status = 'posted'), 0) "
                ", l.vat_amount, COALESCE((SELECT sum(rl.vat_amount) FROM app.return_lines rl JOIN "
                "app.returns r "
                "  ON r.id = rl.return_id WHERE rl.sale_line_id = l.id AND r.status = 'posted'), 0) "
                "FROM app.sale_lines l WHERE l.sale_id = :id ORDER BY l.line_no FOR UPDATE OF l"
            ),
            {"id": sale_id},
        )
        methods = await s.execute(
            text("SELECT method FROM app.sale_payments WHERE sale_id = :id"), {"id": sale_id}
        )
        return SoldDoc(
            id=head[0],
            branch_id=head[1],
            status=head[2],
            counterparty_id=head[3],
            lines={r[0]: SoldLine(*r) for r in lines},
            methods=tuple(r[0] for r in methods),
        )

    async def open_debt_of_sale(self, s: AsyncSession, sale_id: UUID) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE((SELECT sum(amount) FROM app.debt_moves WHERE direction = 'receivable' "
                    "  AND ((doc_type = 'sales' AND doc_id = :id) OR (doc_type = 'returns' AND doc_id IN "
                    "  (SELECT id FROM app.returns WHERE sale_id = :id)))), 0) "
                    "- COALESCE((SELECT sum(a.amount) FROM app.debt_payment_allocations a "
                    "  JOIN app.debt_payments p ON p.id = a.debt_payment_id "
                    "  WHERE a.target_doc_type = 'sales' AND a.target_doc_id = :id AND p.status = "
                    "'posted'), 0)"
                    # B4: a posted write-off took this part of the sale's debt (12 §2.6)
                    "- COALESCE((SELECT sum(a.amount) FROM app.debt_writeoff_allocations a "
                    "  JOIN app.debt_writeoffs w ON w.id = a.debt_writeoff_id "
                    "  WHERE a.target_doc_type = 'sales' AND a.target_doc_id = :id "
                    "  AND w.status = 'posted'), 0)"
                ),
                {"id": sale_id},
            )
        ).scalar_one()
        return Decimal(value)

    async def written_off_of_sale(self, s: AsyncSession, sale_id: UUID) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(a.amount), 0) FROM app.debt_writeoff_allocations a "
                    "JOIN app.debt_writeoffs w ON w.id = a.debt_writeoff_id "
                    "WHERE a.target_doc_type = 'sales' AND a.target_doc_id = :id AND w.status = 'posted'"
                ),
                {"id": sale_id},
            )
        ).scalar_one()
        return Decimal(value)

    async def fiscal_room(self, s: AsyncSession, sale_id: UUID) -> Decimal:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE((SELECT sum((payload->>'total')::numeric) FROM app.fiscal_receipts "
                    "  WHERE sale_id = :id AND kind = 'sale'), 0) "
                    "+ COALESCE((SELECT sum(a.amount) FROM app.debt_payment_allocations a "
                    "  WHERE a.target_doc_type = 'sales' AND a.target_doc_id = :id AND EXISTS (SELECT 1 "
                    "  FROM app.fiscal_receipts f WHERE f.debt_payment_id = a.debt_payment_id "
                    "  AND f.kind = 'debt_settlement')), 0) "
                    "- COALESCE((SELECT sum((f.payload->>'total')::numeric) FROM app.fiscal_receipts f "
                    "  JOIN app.returns r ON r.id = f.return_id WHERE r.sale_id = :id AND f.kind = "
                    "'return'), 0)"
                ),
                {"id": sale_id},
            )
        ).scalar_one()
        return Decimal(value)

    async def lot_expiry(self, s: AsyncSession, lot_ids: Sequence[UUID]) -> dict[UUID, date | None]:
        if not lot_ids:
            return {}
        rows = await s.execute(
            text("SELECT id, expiry_date FROM app.stock_lots WHERE id = ANY(:ids)"), {"ids": list(lot_ids)}
        )
        return {r[0]: r[1] for r in rows}

    async def free_lots(self, s: AsyncSession, warehouse_id: UUID, product_id: UUID) -> list[FreeLot]:
        rows = await s.execute(
            text(
                "SELECT id, qty_in - qty_left, unit_cost FROM app.stock_lots WHERE warehouse_id = :w "
                "AND product_id = :p AND qty_in > qty_left ORDER BY received_at DESC, id DESC"
            ),
            {"w": warehouse_id, "p": product_id},
        )
        return [FreeLot(r[0], r[1], r[2]) for r in rows]

    async def approver_of(self, s: AsyncSession, doc_approval_id: UUID) -> UUID | None:
        value = (
            await s.execute(
                text("SELECT approved_by FROM app.doc_approvals WHERE id = :id"), {"id": doc_approval_id}
            )
        ).scalar_one_or_none()
        return value

    async def mark_codes_returned(self, s: AsyncSession, codes: Sequence[str], return_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.marking_codes SET status = 'returned', last_doc_id = :d, updated_at = now() "
                "WHERE code = ANY(:codes)"
            ),
            {"codes": list(codes), "d": return_id},
        )

    async def insert_return(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.returns (id, tenant_id, branch_id, number, temp_number, doc_date, status, "
                "sale_id, "
                "shift_id, cash_register_id, counterparty_id, reason, refund_method, card_entry_mode, "
                "card_terminal_transaction_id, card_type, card_mask, rrn, approval_code, card_scheme, "
                "manual_reason, "
                "is_offline, approved_by, approved_at, created_by, posted_at, client_event_id, device_id, "
                "comment) "
                "VALUES (:id, :tenant_id, :branch_id, :number, :temp_number, :doc_date, 'posted', :sale_id, "
                ":shift_id, :cash_register_id, :counterparty_id, :reason, :refund_method, :card_entry_mode, "
                ":card_terminal_transaction_id, :card_type, :card_mask, :rrn, :approval_code, :card_scheme, "
                ":manual_reason, :is_offline, :approved_by, :approved_at, :created_by, :posted_at, "
                ":client_event_id, :device_id, :comment)"
            ),
            dict(row),
        )

    async def insert_lines(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.return_lines (id, tenant_id, return_id, line_no, sale_line_id, "
                "product_id, qty, "
                "price, vat_rate, vat_exemption_code, marking_code, vat_amount, cost_amount, line_total, "
                "restock) "
                "VALUES (:id, :tenant_id, :return_id, :line_no, :sale_line_id, :product_id, :qty, :price, "
                ":vat_rate, :vat_exemption_code, :marking_code, :vat_amount, :cost_amount, :line_total, "
                ":restock)"
            ),
            [dict(r) for r in rows],
        )

    async def insert_write_off(
        self, s: AsyncSession, header: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.write_offs (id, tenant_id, branch_id, doc_date, status, warehouse_id, "
                "source_return_id, created_by, comment) VALUES (:id, :tenant_id, :branch_id, :doc_date, "
                "'draft', "
                ":warehouse_id, :source_return_id, :created_by, :comment)"
            ),
            dict(header),
        )
        await s.execute(
            text(
                "INSERT INTO app.write_off_lines (id, tenant_id, write_off_id, line_no, product_id, "
                "lot_id, qty, reason, cost_amount, marking_codes) VALUES (:id, :tenant_id, :write_off_id, "
                ":line_no, :product_id, :lot_id, :qty, :reason, :cost_amount, CAST(:marking_codes AS text[]))"
            ),
            [{"marking_codes": [], **dict(r)} for r in lines],
        )

    # --- queries ------------------------------------------------------------------------------------
    async def page(
        self, s: AsyncSession, flt: ReturnFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[dict[str, Any]]:
        where = ["TRUE"]
        params: dict[str, Any] = {"limit": limit}
        if flt.branch_ids is not None:
            where.append("r.branch_id = ANY(:branches)")
            params["branches"] = list(flt.branch_ids)
        if flt.sale_id is not None:
            where.append("r.sale_id = :sale_id")
            params["sale_id"] = flt.sale_id
        if flt.shift_id is not None:
            where.append("r.shift_id = :shift_id")
            params["shift_id"] = flt.shift_id
        if flt.without_receipt is not None:
            where.append("r.sale_id IS NULL" if flt.without_receipt else "r.sale_id IS NOT NULL")
        if flt.date_from is not None:
            where.append("r.doc_date >= :df")
            params["df"] = flt.date_from
        if flt.date_to is not None:
            where.append("r.doc_date <= :dt")
            params["dt"] = flt.date_to
        if after is not None:
            where.append("(r.created_at, r.id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        sql = (
            "SELECT r.id, r.number, r.temp_number, r.doc_date, r.status, r.sale_id, r.branch_id, "  # noqa: S608
            "r.shift_id, "
            "r.cash_register_id, r.reason, r.refund_method, r.is_offline, r.created_at, (r.sale_id IS NULL) "
            "AS without_receipt, COALESCE((SELECT sum(line_total) FROM app.return_lines l WHERE "
            "l.return_id = r.id), "
            "0) AS total_amount "
            f"FROM app.returns r WHERE {' AND '.join(where)} ORDER BY r.created_at DESC, r.id DESC LIMIT "
            f":limit"
        )
        return [dict(r._mapping) for r in await s.execute(text(sql), params)]

    async def get(self, s: AsyncSession, return_id: UUID) -> dict[str, Any] | None:
        head = (
            await s.execute(
                text(
                    "SELECT id, number, temp_number, doc_date, status, sale_id, (sale_id IS NULL) AS "
                    "without_receipt, "
                    "branch_id, shift_id, cash_register_id, counterparty_id, reason, refund_method, "
                    "card_entry_mode, "
                    "card_type, card_mask, rrn, approval_code, card_scheme, manual_reason, is_offline, "
                    "approved_by, "
                    "approved_at, created_by, created_at, posted_at, device_id, comment "
                    "FROM app.returns WHERE id = :id"
                ),
                {"id": return_id},
            )
        ).first()
        if head is None:
            return None
        out = dict(head._mapping)
        out["lines"] = [
            dict(r._mapping)
            for r in await s.execute(
                text(
                    "SELECT l.id, l.line_no, l.sale_line_id, l.product_id, p.name AS product_name, l.qty, "
                    "l.price, "
                    "l.vat_rate, l.vat_exemption_code, l.vat_amount, l.line_total, l.marking_code, l.restock "
                    "FROM app.return_lines l JOIN app.products p ON p.id = l.product_id "
                    "WHERE l.return_id = :id ORDER BY l.line_no"
                ),
                {"id": return_id},
            )
        ]
        out["total_amount"] = sum((ln["line_total"] for ln in out["lines"]), ZERO)
        out["fiscal_receipts"] = [
            dict(r._mapping)
            for r in await s.execute(
                text(
                    "SELECT id, kind, status, receipt_seq, fm_receipt_seq, fiscal_sign, qr_url, "
                    "payment_form, "
                    "ofd_acked_at FROM app.fiscal_receipts WHERE return_id = :id ORDER BY created_at, id"
                ),
                {"id": return_id},
            )
        ]
        wo = (
            await s.execute(
                text("SELECT id FROM app.write_offs WHERE source_return_id = :id"), {"id": return_id}
            )
        ).scalar_one_or_none()
        out["write_off_id"] = wo
        return out
