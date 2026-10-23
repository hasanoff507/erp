"""SQL of goods receipts and supplier returns (12 ``goods_receipts``, ``receipt_lines``,
``supplier_returns``, ``supplier_return_lines``; reads ``stock_lots``, ``marking_codes``,
``tenant_tax_regimes``, ``ledger_entries``). Runs inside the caller's ``tenant_transaction`` (RLS)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchasing.application.ports import DocFilter, EInvoiceSource, ProductRef, ReturnedSoFar
from app.modules.purchasing.domain.receipts import ZERO, ZERO_QTY, GoodsReceipt, ReceiptLine, Regime
from app.modules.purchasing.domain.supplier_returns import ReturnLine, SupplierReturn

_GR_UPDATABLE = frozenset(
    {
        "doc_date", "supplier_id", "po_id", "warehouse_id", "branch_id", "paid_immediately", "kind", "source",
        "ettn_ref", "poa_id", "poa_number", "comment", "status", "number", "posted_at", "cancelled_at",
        "einvoice_id", "cancelled_by", "cancel_reason",
    }
)  # fmt: skip
_SR_UPDATABLE = frozenset({"status", "number", "posted_at", "cancelled_at", "cancelled_by", "cancel_reason"})

_GR_HEAD = (
    "SELECT gr.id, gr.branch_id, gr.number, gr.doc_date, gr.status, gr.supplier_id, c.name AS supplier_name, "
    "c.stir AS supplier_stir, gr.po_id, gr.warehouse_id, gr.paid_immediately, gr.kind, gr.source, "
    "gr.einvoice_id, e.risk_flag AS einvoice_risk_flag, gr.ettn_ref, gr.poa_id, gr.poa_number, gr.comment, "
    "gr.created_by, u.name AS created_by_name, gr.created_at, gr.updated_at, gr.posted_at, gr.cancelled_at, "
    "gr.cancel_reason, COALESCE(t.line_count, 0) AS line_count, COALESCE(t.net_total, 0) AS net_total, "
    "COALESCE(t.vat_total, 0) AS vat_total "
    "FROM app.goods_receipts gr "
    "LEFT JOIN app.counterparties c ON c.id = gr.supplier_id "
    "LEFT JOIN app.users u ON u.id = gr.created_by "
    "LEFT JOIN app.einvoices e ON e.id = gr.einvoice_id "
    "LEFT JOIN LATERAL (SELECT count(*) AS line_count, "
    "  sum(COALESCE(l.net_amount, round(l.qty * l.cost, 2))) AS net_total, "
    "  sum(l.vat_amount) AS vat_total FROM app.receipt_lines l WHERE l.receipt_id = gr.id) t ON true "
)

_GR_LINES = text(
    "SELECT l.id, l.line_no, l.product_id, l.qty, l.cost, l.vat_rate, l.vat_exemption_code, l.vat_amount, "
    "l.expiry_date, l.discrepancy_reason, l.net_amount, p.name AS product_name, p.unit_code, p.is_marked, "
    "p.marking_group_code, mg.acceptance_deadline AS marking_deadline, lot.id AS lot_id, "
    "lot.qty_left AS lot_qty_left, COALESCE(r.qty, 0) AS returned_qty "
    "FROM app.receipt_lines l "
    "LEFT JOIN app.products p ON p.id = l.product_id "
    "LEFT JOIN platform.marking_product_groups mg ON mg.code = p.marking_group_code "
    "LEFT JOIN LATERAL (SELECT sl.id, sl.qty_left FROM app.stock_lots sl WHERE sl.receipt_line_id = l.id "
    "  ORDER BY sl.received_at, sl.id LIMIT 1) lot ON true "
    "LEFT JOIN LATERAL (SELECT sum(srl.qty) AS qty FROM app.supplier_return_lines srl "
    "  JOIN app.supplier_returns sr ON sr.id = srl.supplier_return_id "
    "  WHERE srl.receipt_line_id = l.id AND sr.status = 'posted') r ON true "
    "WHERE l.receipt_id = :id ORDER BY l.line_no"
)

_SR_HEAD = (
    "SELECT sr.id, sr.branch_id, sr.number, sr.doc_date, sr.status, sr.supplier_id, c.name AS supplier_name, "
    "c.stir AS supplier_stir, sr.receipt_id, gr.number AS receipt_number, gr.doc_date AS receipt_doc_date, "
    "gr.warehouse_id, sr.reason, sr.comment, sr.created_by, u.name AS created_by_name, sr.created_at, "
    "sr.updated_at, sr.posted_at, sr.cancelled_at, sr.cancel_reason, "
    "COALESCE((SELECT x.regime FROM app.tenant_tax_regimes x WHERE x.valid_from <= gr.doc_date "
    "  ORDER BY x.valid_from DESC LIMIT 1), 'vat') AS receipt_regime, "
    "COALESCE(t.line_count, 0) AS line_count, COALESCE(t.net_total, 0) AS net_total, "
    "COALESCE(t.vat_total, 0) AS vat_total, "
    "EXISTS (SELECT 1 FROM app.ledger_entries le WHERE le.doc_type = 'supplier_returns' AND le.doc_id = "
    "sr.id "
    "  AND le.account_kt = '4410' AND le.reversal_of_id IS NULL) AS vat_adjusted "
    "FROM app.supplier_returns sr "
    "JOIN app.goods_receipts gr ON gr.id = sr.receipt_id "
    "LEFT JOIN app.counterparties c ON c.id = sr.supplier_id "
    "LEFT JOIN app.users u ON u.id = sr.created_by "
    "LEFT JOIN LATERAL (SELECT count(*) AS line_count, sum(round(l.qty * l.cost, 2)) AS net_total, "
    "  sum(l.vat_amount) AS vat_total FROM app.supplier_return_lines l WHERE l.supplier_return_id = sr.id) t "
    "ON true "
)

_SR_LINES = text(
    "SELECT l.id, l.line_no, l.receipt_line_id, l.lot_id, rl.product_id, l.qty, l.cost, l.vat_amount, "
    "p.name AS product_name, p.unit_code, l.marking_codes, p.is_marked "
    "FROM app.supplier_return_lines l "
    "JOIN app.receipt_lines rl ON rl.id = l.receipt_line_id "
    "LEFT JOIN app.products p ON p.id = rl.product_id "
    "WHERE l.supplier_return_id = :id ORDER BY l.line_no"
)


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _filters(
    alias: str, flt: DocFilter, after: tuple[datetime, UUID] | None
) -> tuple[str, dict[str, Any], list[str]]:
    where: list[str] = []
    params: dict[str, Any] = {}
    expanding: list[str] = []
    if flt.branch_ids is not None:
        where.append(f"{alias}.branch_id IN :branches")
        params["branches"] = list(flt.branch_ids)
        expanding.append("branches")
    if flt.supplier_id is not None:
        where.append(f"{alias}.supplier_id = :supplier_id")
        params["supplier_id"] = flt.supplier_id
    if flt.status is not None:
        where.append(f"{alias}.status = :status")
        params["status"] = flt.status
    if flt.date_from is not None:
        where.append(f"{alias}.doc_date >= :date_from")
        params["date_from"] = flt.date_from
    if flt.date_to is not None:
        where.append(f"{alias}.doc_date <= :date_to")
        params["date_to"] = flt.date_to
    if flt.po_id is not None and alias == "gr":
        where.append("gr.po_id = :po_id")
        params["po_id"] = flt.po_id
    if flt.receipt_id is not None and alias == "sr":
        where.append("sr.receipt_id = :receipt_id")
        params["receipt_id"] = flt.receipt_id
    if flt.search:
        where.append(f"({alias}.number ILIKE :q OR c.name ILIKE :q)")
        params["q"] = _like(flt.search)
    if after is not None:
        where.append(f"({alias}.created_at, {alias}.id) < (:after_at, :after_id)")
        params["after_at"], params["after_id"] = after
    clause = ("WHERE " + " AND ".join(where) + " ") if where else ""
    return clause, params, expanding


def _receipt(m: Any, lines: tuple[ReceiptLine, ...] = ()) -> GoodsReceipt:
    return GoodsReceipt(
        id=m["id"], branch_id=m["branch_id"], number=m["number"], doc_date=m["doc_date"], status=m["status"],
        supplier_id=m["supplier_id"], supplier_name=m["supplier_name"], supplier_stir=m["supplier_stir"],
        po_id=m["po_id"], warehouse_id=m["warehouse_id"], paid_immediately=bool(m["paid_immediately"]),
        kind=m["kind"], source=m["source"], einvoice_id=m["einvoice_id"],
        einvoice_risk_flag=m["einvoice_risk_flag"], ettn_ref=m["ettn_ref"], poa_id=m["poa_id"],
        poa_number=m["poa_number"], comment=m["comment"], created_by=m["created_by"],
        created_by_name=m["created_by_name"], created_at=m["created_at"], updated_at=m["updated_at"],
        posted_at=m["posted_at"], cancelled_at=m["cancelled_at"], cancel_reason=m["cancel_reason"],
        lines=lines, line_count=int(m["line_count"]), net_total=Decimal(m["net_total"]),
        vat_total=Decimal(m["vat_total"]),
    )  # fmt: skip


def _return(m: Any, lines: tuple[ReturnLine, ...] = ()) -> SupplierReturn:
    return SupplierReturn(
        id=m["id"], branch_id=m["branch_id"], number=m["number"], doc_date=m["doc_date"], status=m["status"],
        supplier_id=m["supplier_id"], supplier_name=m["supplier_name"], supplier_stir=m["supplier_stir"],
        receipt_id=m["receipt_id"], receipt_number=m["receipt_number"],
        receipt_doc_date=m["receipt_doc_date"],
        warehouse_id=m["warehouse_id"], reason=m["reason"], comment=m["comment"], created_by=m["created_by"],
        created_by_name=m["created_by_name"], created_at=m["created_at"], updated_at=m["updated_at"],
        posted_at=m["posted_at"], cancelled_at=m["cancelled_at"], cancel_reason=m["cancel_reason"],
        receipt_regime=m["receipt_regime"], vat_adjusted=bool(m["vat_adjusted"]), lines=lines,
        line_count=int(m["line_count"]),
        net_total=Decimal(m["net_total"]), vat_total=Decimal(m["vat_total"]),
    )  # fmt: skip


def _assign_codes(rows: Sequence[Any], codes: Sequence[tuple[UUID, str]]) -> list[tuple[str, ...]]:
    """Codes of the receipt (insertion order) dealt to its marked lines of the same product, in line order."""
    pool: dict[UUID, list[str]] = {}
    for product_id, code in codes:
        pool.setdefault(product_id, []).append(code)
    out: list[tuple[str, ...]] = []
    for r in rows:
        mine = pool.get(r.product_id, [])
        take = int(r.qty) if r.is_marked and r.qty == int(r.qty) else (len(mine) if r.is_marked else 0)
        out.append(tuple(mine[:take]))
        pool[r.product_id] = mine[take:]
    return out


async def advance_balance(s: AsyncSession, supplier_id: UUID) -> Decimal:
    """Debit balance of 4310 (advances paid) for the supplier: Σ Dt 4310 − Σ Kt 4310 (13 §2.16). The one
    query behind the receipt's advance offset (13 §2.6) and the supplier-payment cancel guard (ACC-03)."""
    value = (
        await s.execute(
            text(
                "SELECT COALESCE(sum(CASE WHEN account_dt = '4310' THEN amount ELSE -amount END), 0) "
                "FROM app.ledger_entries WHERE (account_dt = '4310' OR account_kt = '4310') "
                "AND analytics->>'counterparty_id' = :cp"
            ),
            {"cp": str(supplier_id)},
        )
    ).scalar_one()
    return Decimal(value) if value else ZERO


class SqlGoodsReceiptRepository:
    async def get(self, s: AsyncSession, receipt_id: UUID, *, lock: bool = False) -> GoodsReceipt | None:
        if lock:
            locked = await s.execute(
                text("SELECT id FROM app.goods_receipts WHERE id = :id FOR UPDATE"), {"id": receipt_id}
            )
            if locked.first() is None:
                return None
        row = (await s.execute(text(_GR_HEAD + "WHERE gr.id = :id"), {"id": receipt_id})).first()
        if row is None:
            return None
        line_rows = list(await s.execute(_GR_LINES, {"id": receipt_id}))
        code_rows = await s.execute(
            text("SELECT product_id, code FROM app.marking_codes WHERE last_doc_id = :id ORDER BY id"),
            {"id": receipt_id},
        )
        codes = _assign_codes(line_rows, [(c[0], c[1]) for c in code_rows])
        lines = tuple(
            ReceiptLine(
                id=r.id,
                line_no=r.line_no,
                product_id=r.product_id,
                qty=r.qty,
                cost=r.cost,
                vat_rate=r.vat_rate,
                vat_amount=r.vat_amount,
                vat_exemption_code=r.vat_exemption_code,
                expiry_date=r.expiry_date,
                discrepancy_reason=r.discrepancy_reason,
                product_name=r.product_name,
                unit_code=r.unit_code,
                is_marked=bool(r.is_marked),
                marking_group_code=r.marking_group_code,
                marking_deadline=r.marking_deadline,
                marking_codes=mine,
                lot_id=r.lot_id,
                lot_qty_left=r.lot_qty_left,
                returned_qty=Decimal(r.returned_qty) if r.returned_qty else ZERO_QTY,
                net_amount=r.net_amount,
            )
            for r, mine in zip(line_rows, codes, strict=True)
        )
        return _receipt(row._mapping, lines)

    async def list_page(
        self, s: AsyncSession, flt: DocFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[GoodsReceipt]:
        clause, params, expanding = _filters("gr", flt, after)
        params["limit"] = limit
        stmt = text(_GR_HEAD + clause + "ORDER BY gr.created_at DESC, gr.id DESC LIMIT :limit")
        if expanding:
            stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding))
        return [_receipt(r._mapping) for r in await s.execute(stmt, params)]

    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.goods_receipts (id, tenant_id, branch_id, doc_date, supplier_id, po_id, "
                "warehouse_id, paid_immediately, kind, source, einvoice_id, ettn_ref, poa_id, poa_number, "
                "created_by, comment) "
                "VALUES (:id, :tenant_id, :branch_id, :doc_date, :supplier_id, :po_id, :warehouse_id, "
                ":paid_immediately, :kind, :source, :einvoice_id, :ettn_ref, :poa_id, :poa_number, "
                ":created_by, "
                ":comment)"
            ),
            {"einvoice_id": None, **dict(row)},
        )

    async def update(self, s: AsyncSession, receipt_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _GR_UPDATABLE]
        if not cols:
            return
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        await s.execute(
            text(f"UPDATE app.goods_receipts SET {assignments} WHERE id = :id"),  # noqa: S608
            {**{c: values[c] for c in cols}, "id": receipt_id},
        )

    async def replace_lines(
        self, s: AsyncSession, receipt_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(text("DELETE FROM app.receipt_lines WHERE receipt_id = :id"), {"id": receipt_id})
        if rows:
            await s.execute(
                text(
                    "INSERT INTO app.receipt_lines (id, tenant_id, receipt_id, line_no, product_id, qty, "
                    "cost, vat_rate, vat_exemption_code, vat_amount, expiry_date, discrepancy_reason, "
                    "net_amount) "
                    "VALUES (:id, :tenant_id, :receipt_id, :line_no, :product_id, :qty, :cost, :vat_rate, "
                    ":vat_exemption_code, :vat_amount, :expiry_date, :discrepancy_reason, :net_amount)"
                ),
                [{"net_amount": None, **dict(r)} for r in rows],
            )

    async def products(self, s: AsyncSession, product_ids: Sequence[UUID]) -> dict[UUID, ProductRef]:
        if not product_ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT id, archived_at IS NOT NULL AS archived, vat_rate, vat_exemption_code, is_marked, "
                "marking_group_code FROM app.products WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": list(dict.fromkeys(product_ids))},
        )
        return {
            r.id: ProductRef(
                r.id,
                bool(r.archived),
                r.vat_rate,
                r.vat_exemption_code,
                bool(r.is_marked),
                r.marking_group_code,
            )
            for r in rows
        }

    async def einvoice_source(self, s: AsyncSession, einvoice_id: UUID) -> EInvoiceSource | None:
        """The incoming e-invoice a receipt is made from (19 §8 ``from-einvoice``) + its combined e-TTN."""
        row = (
            await s.execute(
                text(
                    "SELECT e.id, e.direction, e.status, e.counterparty_id, e.doc_date, e.payload, "
                    "(SELECT x.operator_doc_id FROM app.ettn_documents x WHERE x.einvoice_id = e.id "
                    "  ORDER BY x.id LIMIT 1) AS ettn_ref, "
                    "(SELECT g.id FROM app.goods_receipts g WHERE g.einvoice_id = e.id AND g.status <> "
                    "'cancelled' "
                    "  ORDER BY g.id LIMIT 1) AS receipt_id "
                    "FROM app.einvoices e WHERE e.id = :id"
                ),
                {"id": einvoice_id},
            )
        ).first()
        if row is None:
            return None
        payload = json.loads(row[5]) if isinstance(row[5], str) else (row[5] or {})
        return EInvoiceSource(row[0], row[1], row[2], row[3], row[4], payload, row[6], row[7])

    async def product_by_code(self, s: AsyncSession, *, barcode: str | None, mxik: str | None) -> UUID | None:
        """A non-archived product by barcode, else by an MXIK code only one product carries."""
        if barcode:
            found = (
                await s.execute(
                    text(
                        "SELECT b.product_id FROM app.product_barcodes b JOIN app.products p ON p.id = "
                        "b.product_id "
                        "WHERE b.barcode = :b AND p.archived_at IS NULL"
                    ),
                    {"b": barcode},
                )
            ).scalar_one_or_none()
            if found is not None:
                value: UUID = found
                return value
        if mxik:
            rows = list(
                await s.execute(
                    text("SELECT id FROM app.products WHERE mxik_code = :m AND archived_at IS NULL LIMIT 2"),
                    {"m": mxik},
                )
            )
            if len(rows) == 1:
                only: UUID = rows[0][0]
                return only
        return None

    async def shipped_on(self, s: AsyncSession, receipt_id: UUID) -> date | None:
        """Dispatch date of a from-einvoice receipt (the e-invoice date) — marking deadline start (19 §8)."""
        value: date | None = (
            await s.execute(
                text(
                    "SELECT e.doc_date FROM app.goods_receipts g JOIN app.einvoices e ON e.id = "
                    "g.einvoice_id "
                    "WHERE g.id = :id"
                ),
                {"id": receipt_id},
            )
        ).scalar_one_or_none()
        return value

    async def regime_on(self, s: AsyncSession, day: date) -> Regime:
        """``tenant_tax_regimes`` in force on ``day``; no row → VAT payer (the general regime)."""
        found = (
            await s.execute(
                text(
                    "SELECT regime FROM app.tenant_tax_regimes WHERE valid_from <= :d "
                    "ORDER BY valid_from DESC LIMIT 1"
                ),
                {"d": day},
            )
        ).scalar_one_or_none()
        return "turnover" if found == "turnover" else "vat"

    async def advance_balance(self, s: AsyncSession, supplier_id: UUID) -> Decimal:
        return await advance_balance(s, supplier_id)

    async def poa_number(self, s: AsyncSession, poa_id: UUID) -> tuple[bool, str | None]:
        row = (
            await s.execute(text("SELECT number FROM app.powers_of_attorney WHERE id = :id"), {"id": poa_id})
        ).first()
        return (False, None) if row is None else (True, row[0])

    async def foreign_codes(self, s: AsyncSession, receipt_id: UUID, codes: Sequence[str]) -> list[str]:
        """Codes already registered by another document (or not as this draft's pending codes)."""
        if not codes:
            return []
        rows = await s.execute(
            text(
                "SELECT code FROM app.marking_codes WHERE code IN :codes "
                "AND (last_doc_id IS DISTINCT FROM :id OR status <> 'pending_verification')"
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": list(codes), "id": receipt_id},
        )
        return [r[0] for r in rows]

    async def replace_codes(
        self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> list[str]:
        """Drop this draft's codes and register ``rows``; returns the codes NOT inserted because another
        document registered them meanwhile (``ON CONFLICT (tenant_id, code) DO NOTHING`` — a concurrent
        draft waits on the unique index and is refused instead of failing with a 500)."""
        await self.drop_codes(s, receipt_id)
        if not rows:
            return []
        result = await s.execute(
            text(
                "INSERT INTO app.marking_codes (id, tenant_id, code, product_id, status, last_doc_id) "
                "SELECT x.id, :tenant_id, x.code, x.product_id, 'pending_verification', :doc_id "
                "FROM unnest(CAST(:ids AS uuid[]), CAST(:codes AS text[]), CAST(:products AS uuid[])) "
                "AS x(id, code, product_id) "
                "ON CONFLICT (tenant_id, code) DO NOTHING RETURNING code"
            ),
            {
                "tenant_id": tenant_id,
                "doc_id": receipt_id,
                "ids": [r["id"] for r in rows],
                "codes": [r["code"] for r in rows],
                "products": [r["product_id"] for r in rows],
            },
        )
        inserted = {r[0] for r in result}
        return [r["code"] for r in rows if r["code"] not in inserted]

    async def set_codes_status(self, s: AsyncSession, receipt_id: UUID, status: str) -> None:
        await s.execute(
            text("UPDATE app.marking_codes SET status = :st WHERE last_doc_id = :id"),
            {"st": status, "id": receipt_id},
        )

    async def drop_codes(self, s: AsyncSession, receipt_id: UUID) -> None:
        """Codes this receipt registered and that nothing has moved since (pending or in stock)."""
        await s.execute(
            text(
                "DELETE FROM app.marking_codes WHERE last_doc_id = :id "
                "AND status IN ('pending_verification', 'in_stock')"
            ),
            {"id": receipt_id},
        )

    async def paying_supplier_payments(self, s: AsyncSession, receipt_id: UUID) -> list[UUID]:
        """Posted supplier payments allocated to the receipt (19 §8 cancel guard, 13 §2.16)."""
        rows = await s.execute(
            text(
                "SELECT DISTINCT p.id FROM app.supplier_payment_allocations a "
                "JOIN app.supplier_payments p ON p.id = a.supplier_payment_id "
                "WHERE a.target_doc_type = 'goods_receipts' AND a.target_doc_id = :id "
                "AND p.status = 'posted' "
                "ORDER BY p.id"
            ),
            {"id": receipt_id},
        )
        return [r[0] for r in rows]


class SqlSupplierReturnRepository:
    async def get(self, s: AsyncSession, return_id: UUID, *, lock: bool = False) -> SupplierReturn | None:
        if lock:
            locked = await s.execute(
                text("SELECT id FROM app.supplier_returns WHERE id = :id FOR UPDATE"), {"id": return_id}
            )
            if locked.first() is None:
                return None
        row = (await s.execute(text(_SR_HEAD + "WHERE sr.id = :id"), {"id": return_id})).first()
        if row is None:
            return None
        lines = tuple(
            ReturnLine(
                id=r.id,
                line_no=r.line_no,
                receipt_line_id=r.receipt_line_id,
                lot_id=r.lot_id,
                product_id=r.product_id,
                qty=r.qty,
                cost=r.cost,
                vat_amount=r.vat_amount,
                product_name=r.product_name,
                unit_code=r.unit_code,
                marking_codes=tuple(r.marking_codes or ()),
                is_marked=bool(r.is_marked),
            )
            for r in await s.execute(_SR_LINES, {"id": return_id})
        )
        return _return(row._mapping, lines)

    async def list_page(
        self, s: AsyncSession, flt: DocFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[SupplierReturn]:
        clause, params, expanding = _filters("sr", flt, after)
        params["limit"] = limit
        stmt = text(_SR_HEAD + clause + "ORDER BY sr.created_at DESC, sr.id DESC LIMIT :limit")
        if expanding:
            stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding))
        return [_return(r._mapping) for r in await s.execute(stmt, params)]

    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.supplier_returns (id, tenant_id, branch_id, doc_date, supplier_id, "
                "receipt_id, reason, created_by, comment) "
                "VALUES (:id, :tenant_id, :branch_id, :doc_date, :supplier_id, "
                ":receipt_id, :reason, :created_by, :comment)"
            ),
            dict(head),
        )
        await s.execute(
            text(
                "INSERT INTO app.supplier_return_lines (id, tenant_id, supplier_return_id, line_no, "
                "receipt_line_id, lot_id, qty, cost, vat_amount, marking_codes) VALUES (:id, :tenant_id, "
                ":supplier_return_id, :line_no, :receipt_line_id, :lot_id, :qty, :cost, :vat_amount, "
                "CAST(:marking_codes AS text[]))"
            ),
            [{"marking_codes": [], **dict(x)} for x in lines],
        )

    async def returned_so_far(
        self, s: AsyncSession, receipt_line_ids: Sequence[UUID], exclude_id: UUID | None
    ) -> dict[UUID, ReturnedSoFar]:
        if not receipt_line_ids:
            return {}
        rows = await s.execute(
            text(
                "SELECT l.receipt_line_id, sum(l.qty), sum(l.vat_amount) FROM app.supplier_return_lines l "
                "JOIN app.supplier_returns sr ON sr.id = l.supplier_return_id "
                "WHERE sr.status = 'posted' AND l.receipt_line_id IN :ids "
                "AND sr.id IS DISTINCT FROM :exclude GROUP BY l.receipt_line_id"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": list(dict.fromkeys(receipt_line_ids)), "exclude": exclude_id},
        )
        return {r[0]: ReturnedSoFar(Decimal(r[1]), Decimal(r[2] or ZERO)) for r in rows}

    async def set_line_vat(self, s: AsyncSession, line_id: UUID, vat_amount: Decimal) -> None:
        await s.execute(
            text("UPDATE app.supplier_return_lines SET vat_amount = :v WHERE id = :id"),
            {"v": vat_amount, "id": line_id},
        )

    async def update(self, s: AsyncSession, return_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _SR_UPDATABLE]
        if not cols:
            return
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        await s.execute(
            text(f"UPDATE app.supplier_returns SET {assignments} WHERE id = :id"),  # noqa: S608
            {**{c: values[c] for c in cols}, "id": return_id},
        )
