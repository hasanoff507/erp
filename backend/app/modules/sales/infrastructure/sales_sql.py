"""SQL of the sales module (caller's transaction; RLS — one tenant)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.domain.tenant_settings import effective_settings
from app.modules.sales.application.ports import (
    Checkout,
    CustomerInfo,
    DiscountRule,
    ProductInfo,
    SaleFilter,
    TenantPolicy,
)


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


class SqlSalesRepository:
    async def products(self, s: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, ProductInfo]:
        if not ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT p.id, p.name, p.name_ru, p.unit_code, COALESCE(u.is_fractional, false), p.is_marked, "
                "p.vat_rate, p.vat_exemption_code, p.mxik_code, p.package_code, p.archived_at "
                "FROM app.products p LEFT JOIN platform.units u ON u.code = p.unit_code WHERE p.id = "
                "ANY(:ids)"
            ),
            {"ids": list(ids)},
        )
        return {r[0]: ProductInfo(*r) for r in rows}

    async def prices_at(
        self, s: AsyncSession, ids: Sequence[UUID], branch_id: UUID, at: datetime
    ) -> dict[UUID, Decimal]:
        """SQL twin of ``pricing.domain.resolution.effective_record`` at ``at`` (branch row beats global)."""
        if not ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT DISTINCT ON (product_id) product_id, price FROM app.product_prices "
                "WHERE product_id = ANY(:ids) AND valid_from <= :at AND (branch_id IS NULL OR branch_id = "
                ":b) "
                "ORDER BY product_id, (branch_id IS NULL), valid_from DESC, id DESC"
            ),
            {"ids": list(ids), "at": at, "b": branch_id},
        )
        return {r[0]: r[1] for r in rows}

    async def sale_warehouse(self, s: AsyncSession, branch_id: UUID) -> UUID | None:
        """The branch's sales floor: oldest active ``store`` warehouse, else the oldest active one."""
        value = (
            await s.execute(
                text(
                    "SELECT id FROM app.warehouses WHERE branch_id = :b AND archived_at IS NULL "
                    "ORDER BY (type <> 'store'), created_at, id LIMIT 1"
                ),
                {"b": branch_id},
            )
        ).scalar_one_or_none()
        return value

    async def tenant_policy(self, s: AsyncSession, on: date) -> TenantPolicy:
        row = (await s.execute(text("SELECT settings, legal_form FROM app.tenants LIMIT 1"))).one()
        regime = (
            await s.execute(
                text(
                    "SELECT regime FROM app.tenant_tax_regimes WHERE valid_from <= :d "
                    "ORDER BY valid_from DESC LIMIT 1"
                ),
                {"d": on},
            )
        ).scalar_one_or_none()
        stored = _json(row[0]) or {}
        legal_form = str(row[1] or "llc")
        settings = {**stored, **effective_settings(stored, legal_form)}
        return TenantPolicy(settings=settings, legal_form=legal_form, vat_payer=regime != "turnover")

    async def customer(self, s: AsyncSession, counterparty_id: UUID) -> CustomerInfo | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, name, kind, is_customer, credit_limit, standing_discount_pct, archived_at "
                    "FROM app.counterparties WHERE id = :id"
                ),
                {"id": counterparty_id},
            )
        ).first()
        return CustomerInfo(*row) if row else None

    async def discount_rule(self, s: AsyncSession, rule_id: UUID) -> DiscountRule | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, scope, target_ids, branch_ids, valid_from, valid_to, archived_at "
                    "FROM app.discount_rules WHERE id = :id"
                ),
                {"id": rule_id},
            )
        ).first()
        if row is None:
            return None
        return DiscountRule(row[0], row[1], tuple(row[2] or ()), tuple(row[3] or ()), row[4], row[5], row[6])

    async def product_category(self, s: AsyncSession, product_id: UUID) -> UUID | None:
        value = (
            await s.execute(text("SELECT category_id FROM app.products WHERE id = :id"), {"id": product_id})
        ).scalar_one_or_none()
        return value

    async def sale_exists(self, s: AsyncSession, sale_id: UUID) -> bool:
        return (
            await s.execute(text("SELECT 1 FROM app.sales WHERE id = :id"), {"id": sale_id})
        ).first() is not None

    async def temp_number_taken(self, s: AsyncSession, table: str, device_id: UUID, temp_number: str) -> bool:
        if table not in ("sales", "returns"):
            raise ValueError(table)
        found = await s.execute(
            text(f"SELECT 1 FROM app.{table} WHERE device_id = :d AND temp_number = :n"),  # noqa: S608
            {"d": device_id, "n": temp_number},
        )
        return found.first() is not None

    async def checkout(self, s: AsyncSession, checkout_ref: UUID) -> Checkout | None:
        row = (
            await s.execute(
                text(
                    "SELECT checkout_ref, provider, status, amount, provider_tx_id, cash_register_id "
                    "FROM app.payment_checkouts WHERE checkout_ref = :r FOR UPDATE"
                ),
                {"r": checkout_ref},
            )
        ).first()
        return Checkout(*row) if row else None

    async def consume_checkout(self, s: AsyncSession, checkout_ref: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.payment_checkouts SET status = 'consumed', updated_at = now() WHERE "
                "checkout_ref = :r"
            ),
            {"r": checkout_ref},
        )

    async def take_marking_codes(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        codes: Sequence[tuple[str, UUID]],
        doc_id: UUID,
        *,
        keep_free: bool = False,
    ) -> list[str]:
        taken = [
            r[0]
            for r in await s.execute(
                text(
                    "SELECT code FROM app.marking_codes WHERE code = ANY(:codes) "
                    "AND status IN ('sold', 'pending_verification') FOR UPDATE"
                ),
                {"codes": [c for c, _ in codes]},
            )
        ]
        if taken and not keep_free:
            return taken
        for code, product_id in codes:
            if code in taken:
                continue
            got = (
                await s.execute(
                    text(
                        "INSERT INTO app.marking_codes (tenant_id, code, product_id, status, last_doc_id) "
                        "VALUES (:t, :c, :p, 'pending_verification', :d) ON CONFLICT (tenant_id, code) DO "
                        "UPDATE "
                        "SET status = 'pending_verification', last_doc_id = EXCLUDED.last_doc_id, "
                        "updated_at = now() "
                        "WHERE app.marking_codes.status NOT IN ('sold', 'pending_verification') RETURNING "
                        "code"
                    ),
                    {"t": tenant_id, "c": code, "p": product_id, "d": doc_id},
                )
            ).first()
            if got is None:  # taken by a concurrent sale between the check and the upsert
                taken.append(code)
        return taken

    async def insert_sale(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.sales (id, tenant_id, branch_id, number, temp_number, doc_date, status, "
                "shift_id, "
                "cash_register_id, counterparty_id, total_amount, is_offline, debt_limit_exceeded, "
                "created_by, "
                "posted_at, client_event_id, device_id, comment) VALUES (:id, :tenant_id, :branch_id, "
                ":number, "
                ":temp_number, :doc_date, 'posted', :shift_id, :cash_register_id, :counterparty_id, "
                ":total_amount, "
                ":is_offline, :debt_limit_exceeded, :created_by, :posted_at, :client_event_id, :device_id, "
                ":comment)"
            ),
            dict(row),
        )

    async def insert_lines(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.sale_lines (id, tenant_id, sale_id, line_no, product_id, qty, price, "
                "discount_amount, vat_rate, vat_exemption_code, discount_pct, discount_source, "
                "discount_rule_id, "
                "vat_amount, line_total, cost_amount, marking_code, lot_allocations, settled_amount) VALUES "
                "(:id, :tenant_id, :sale_id, :line_no, :product_id, :qty, :price, :discount_amount, "
                ":vat_rate, "
                ":vat_exemption_code, :discount_pct, :discount_source, :discount_rule_id, :vat_amount, "
                ":line_total, :cost_amount, :marking_code, CAST(:lot_allocations AS jsonb), :settled_amount)"
            ),
            [{**r, "lot_allocations": json.dumps(r["lot_allocations"], default=str)} for r in rows],
        )

    async def insert_payments(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.sale_payments (id, tenant_id, sale_id, method, amount, provider_tx_id, "
                "terminal_ref, card_type, card_mask, rrn, qr_type, due_date, checkout_ref, card_entry_mode, "
                "card_terminal_transaction_id, approval_code, card_scheme, card_type_source, "
                "manual_reason) VALUES "
                "(:id, :tenant_id, :sale_id, :method, :amount, :provider_tx_id, :terminal_ref, :card_type, "
                ":card_mask, :rrn, :qr_type, :due_date, :checkout_ref, :card_entry_mode, "
                ":card_terminal_transaction_id, :approval_code, :card_scheme, :card_type_source, "
                ":manual_reason)"
            ),
            [dict(r) for r in rows],
        )

    async def insert_cash_moves(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.cash_moves (id, tenant_id, cash_register_id, shift_id, amount, method, "
                "doc_type, "
                "doc_id) VALUES (:id, :tenant_id, :cash_register_id, :shift_id, :amount, :method, "
                ":doc_type, :doc_id)"
            ),
            [dict(r) for r in rows],
        )

    async def open_shift_of(self, s: AsyncSession, cash_register_id: UUID) -> UUID | None:
        value = (
            await s.execute(
                text("SELECT id FROM app.shifts WHERE cash_register_id = :c AND status = 'open'"),
                {"c": cash_register_id},
            )
        ).scalar_one_or_none()
        return value

    async def fiscal_receipt_ref(self, s: AsyncSession, receipt_id: UUID) -> tuple[UUID | None, str] | None:
        row = (
            await s.execute(
                text("SELECT sale_id, kind FROM app.fiscal_receipts WHERE id = :id"), {"id": receipt_id}
            )
        ).first()
        return (row[0], row[1]) if row else None

    # --- queries ------------------------------------------------------------------------------------
    async def page(
        self, s: AsyncSession, flt: SaleFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[dict[str, Any]]:
        where = ["TRUE"]
        params: dict[str, Any] = {"limit": limit}
        if flt.branch_ids is not None:
            where.append("s.branch_id = ANY(:branches)")
            params["branches"] = list(flt.branch_ids)
        for col, key in (("s.number", "number"), ("s.shift_id", "shift_id"), ("s.counterparty_id",
        "counterparty_id"),
                         ("s.status", "status")):  # fmt: skip
            value = getattr(flt, key)
            if value is not None:
                where.append(f"{col} = :{key}")
                params[key] = value
        if flt.date_from is not None:
            where.append("s.doc_date >= :date_from")
            params["date_from"] = flt.date_from
        if flt.date_to is not None:
            where.append("s.doc_date <= :date_to")
            params["date_to"] = flt.date_to
        if flt.fiscal_receipt_seq is not None:
            where.append(
                "EXISTS (SELECT 1 FROM app.fiscal_receipts f WHERE f.sale_id = s.id AND f.kind = 'sale' "
                "AND f.receipt_seq = :frs)"
            )
            params["frs"] = flt.fiscal_receipt_seq
        if after is not None:
            where.append("(s.created_at, s.id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        sql = (
            "SELECT s.id, s.number, s.temp_number, s.doc_date, s.total_amount, s.counterparty_id, "  # noqa: S608
            "s.is_offline, "
            "s.status, s.created_at, s.shift_id, s.cash_register_id, s.branch_id, "
            "(SELECT json_agg(json_build_object('method', p.method, 'amount', p.amount) ORDER BY "
            "p.created_at, p.id) "
            " FROM app.sale_payments p WHERE p.sale_id = s.id) AS payments, "
            "EXISTS (SELECT 1 FROM app.returns r WHERE r.sale_id = s.id AND r.status = 'posted') AS "
            "has_returns "
            f"FROM app.sales s WHERE {' AND '.join(where)} ORDER BY s.created_at DESC, s.id DESC LIMIT :limit"
        )
        return [dict(r._mapping) for r in await s.execute(text(sql), params)]

    async def get(self, s: AsyncSession, sale_id: UUID) -> dict[str, Any] | None:
        head = (
            await s.execute(
                text(
                    "SELECT id, number, temp_number, doc_date, status, branch_id, shift_id, "
                    "cash_register_id, "
                    "counterparty_id, total_amount, is_offline, debt_limit_exceeded, created_by, created_at, "
                    "posted_at, device_id, comment FROM app.sales WHERE id = :id"
                ),
                {"id": sale_id},
            )
        ).first()
        if head is None:
            return None
        out = dict(head._mapping)
        out["lines"] = [
            dict(r._mapping)
            for r in await s.execute(
                text(
                    "SELECT l.id, l.line_no, l.product_id, pr.name AS product_name, pr.unit_code, l.qty, "
                    "l.price, "
                    "l.discount_amount, l.discount_pct, l.discount_source, l.discount_rule_id, l.vat_rate, "
                    "l.vat_exemption_code, l.vat_amount, l.line_total, l.marking_code, l.settled_amount, "
                    "COALESCE((SELECT sum(rl.qty) FROM app.return_lines rl JOIN app.returns r ON r.id = "
                    "rl.return_id "
                    " WHERE rl.sale_line_id = l.id AND r.status = 'posted'), 0) AS returned_qty "
                    "FROM app.sale_lines l JOIN app.products pr ON pr.id = l.product_id "
                    "WHERE l.sale_id = :id ORDER BY l.line_no"
                ),
                {"id": sale_id},
            )
        ]
        out["payments"] = [
            dict(r._mapping)
            for r in await s.execute(
                text(
                    "SELECT id, method, amount, card_entry_mode, manual_reason, card_type, card_mask, rrn, "
                    "approval_code, card_scheme, terminal_ref, qr_type, provider_tx_id, due_date "
                    "FROM app.sale_payments WHERE sale_id = :id ORDER BY created_at, id"
                ),
                {"id": sale_id},
            )
        ]
        out["fiscal_receipts"] = [
            dict(r._mapping)
            for r in await s.execute(
                text(
                    "SELECT id, kind, status, receipt_seq, fm_receipt_seq, fiscal_sign, qr_url, "
                    "payment_form, "
                    "ofd_acked_at FROM app.fiscal_receipts WHERE sale_id = :id ORDER BY created_at, id"
                ),
                {"id": sale_id},
            )
        ]
        return out
