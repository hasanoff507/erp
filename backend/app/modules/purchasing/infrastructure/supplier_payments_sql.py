"""SQL of supplier payments (12 ``supplier_payments``, ``supplier_payment_allocations``; writes
``cash_moves``; reads ``goods_receipts``, ``debt_openings``, ``supplier_returns``, ``debt_moves``,
``ledger_entries``, ``vat_moves``, ``einvoices``, ``shifts``, ``tenants.settings``). Runs inside the caller's
``tenant_transaction``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.purchasing.application.supplier_payments_ports import (
    AllocationRow,
    PaymentFilter,
    PaymentRow,
    ShiftRef,
)
from app.modules.purchasing.domain.supplier_payments import ZERO, OpenDoc
from app.modules.purchasing.infrastructure.receipts_sql import advance_balance

_HEAD = (
    "SELECT p.id, p.number, p.status, p.doc_date, p.branch_id, p.supplier_id, c.name AS supplier_name, "
    "c.stir AS supplier_stir, p.method, p.amount, p.cash_register_id, p.shift_id, p.comment, p.created_by, "
    "u.name AS created_by_name, p.created_at, p.posted_at, p.cancelled_at, p.cancel_reason "
    "FROM app.supplier_payments p "
    "LEFT JOIN app.counterparties c ON c.id = p.supplier_id "
    "LEFT JOIN app.users u ON u.id = p.created_by "
)

_ALLOCATIONS = text(
    "SELECT a.supplier_payment_id, a.target_doc_type, a.target_doc_id, a.amount, "
    "COALESCE(gr.number, o.number) AS target_number, COALESCE(gr.doc_date, o.doc_date) AS target_doc_date, "
    "gr.einvoice_id AS target_einvoice_id "
    "FROM app.supplier_payment_allocations a "
    "LEFT JOIN app.goods_receipts gr ON a.target_doc_type = 'goods_receipts' AND gr.id = a.target_doc_id "
    "LEFT JOIN app.debt_openings o ON a.target_doc_type = 'debt_openings' AND o.id = a.target_doc_id "
    "WHERE a.supplier_payment_id IN :ids ORDER BY a.supplier_payment_id, a.id"
).bindparams(bindparam("ids", expanding=True))

_VAT = text(
    "SELECT doc_id, einvoice_id, vat_amount FROM app.vat_moves "
    "WHERE doc_type = 'supplier_payments' AND doc_id IN :ids AND reversal_of_id IS NULL AND kind = 'input' "
    "ORDER BY doc_id, id"
).bindparams(bindparam("ids", expanding=True))

# Open payable documents of a supplier (13 §2.16): posted credit receipts and payable debt openings.
# outstanding = payable at posting + supplier returns (negative debt moves) − advance offset (Dt 6010 /
# Kt 4310 of the receipt, 13 §2.6) − allocations of posted supplier payments.
_OPEN_DOCS = text(
    "WITH alloc AS ("
    " SELECT a.target_doc_type, a.target_doc_id, sum(a.amount) AS paid"
    " FROM app.supplier_payment_allocations a JOIN app.supplier_payments p ON p.id = a.supplier_payment_id"
    " WHERE p.status = 'posted' AND p.supplier_id = :sup GROUP BY a.target_doc_type, a.target_doc_id) "
    "SELECT 'goods_receipts' AS doc_type, gr.id, gr.number, gr.doc_date, CAST(NULL AS date) AS due_date, "
    " COALESCE(dm.total, 0) AS total, "
    " COALESCE(dm.total, 0) + COALESCE(rt.amount, 0) - COALESCE(adv.amount, 0) - COALESCE(al.paid, 0) "
    "  AS outstanding, "
    " gr.einvoice_id, e.risk_flag, COALESCE(dv.amount, 0) AS deferred_vat, "
    " COALESCE(nb.base, 0) AS deferred_base, COALESCE(rv.vat, 0) AS released_vat, "
    " COALESCE(rv.base, 0) AS released_base "
    "FROM app.goods_receipts gr "
    "LEFT JOIN app.einvoices e ON e.id = gr.einvoice_id "
    "LEFT JOIN LATERAL (SELECT sum(m.amount) AS total FROM app.debt_moves m "
    "  WHERE m.doc_type = 'goods_receipts' AND m.doc_id = gr.id AND m.direction = 'payable' "
    "  AND m.reversal_of_id IS NULL) dm ON true "
    "LEFT JOIN LATERAL (SELECT sum(m.amount) AS amount FROM app.debt_moves m "
    "  JOIN app.supplier_returns sr ON sr.id = m.doc_id "
    "  WHERE m.doc_type = 'supplier_returns' AND m.direction = 'payable' AND sr.receipt_id = gr.id) rt "
    "  ON true "
    "LEFT JOIN LATERAL (SELECT sum(le.amount) AS amount FROM app.ledger_entries le "
    "  WHERE le.doc_type = 'goods_receipts' AND le.doc_id = gr.id AND le.account_dt = '6010' "
    "  AND le.account_kt = '4310' AND le.reversal_of_id IS NULL) adv ON true "
    "LEFT JOIN LATERAL (SELECT sum(le.amount) AS amount FROM app.ledger_entries le "
    "  WHERE le.doc_type = 'goods_receipts' AND le.doc_id = gr.id AND le.account_dt = '4410' "
    "  AND le.analytics->>'vat_credit' = 'deferred' AND le.reversal_of_id IS NULL) dv ON true "
    "LEFT JOIN LATERAL (SELECT sum(round(l.qty * l.cost, 2)) AS base FROM app.receipt_lines l "
    "  WHERE l.receipt_id = gr.id AND l.vat_amount > 0) nb ON true "
    "LEFT JOIN LATERAL (SELECT sum(v.vat_amount) AS vat, sum(v.base_amount) AS base FROM app.vat_moves v "
    "  WHERE gr.einvoice_id IS NOT NULL AND v.einvoice_id = gr.einvoice_id AND v.kind = 'input') rv ON true "
    "LEFT JOIN alloc al ON al.target_doc_type = 'goods_receipts' AND al.target_doc_id = gr.id "
    "WHERE gr.supplier_id = :sup AND gr.status = 'posted' "
    "UNION ALL "
    "SELECT 'debt_openings', o.id, o.number, o.doc_date, o.due_date, o.amount, "
    " o.amount - COALESCE(al.paid, 0), NULL, NULL, 0, 0, 0, 0 "
    "FROM app.debt_openings o "
    "LEFT JOIN alloc al ON al.target_doc_type = 'debt_openings' AND al.target_doc_id = o.id "
    "WHERE o.counterparty_id = :sup AND o.status = 'posted' AND o.direction = 'payable'"
)


def _d(value: Any) -> Decimal:
    return ZERO if value is None else Decimal(value)


def _payment(
    m: Any, allocations: tuple[AllocationRow, ...], vat: tuple[tuple[UUID | None, Decimal], ...]
) -> PaymentRow:
    return PaymentRow(
        id=m["id"], number=m["number"], status=m["status"], doc_date=m["doc_date"], branch_id=m["branch_id"],
        supplier_id=m["supplier_id"], supplier_name=m["supplier_name"], supplier_stir=m["supplier_stir"],
        method=m["method"], amount=Decimal(m["amount"]), cash_register_id=m["cash_register_id"],
        shift_id=m["shift_id"], comment=m["comment"], created_by=m["created_by"],
        created_by_name=m["created_by_name"], created_at=m["created_at"], posted_at=m["posted_at"],
        cancelled_at=m["cancelled_at"], cancel_reason=m["cancel_reason"], allocations=allocations,
        vat_unlocked=vat,
    )  # fmt: skip


class SqlSupplierPaymentRepository:
    async def shift(self, s: AsyncSession, shift_id: UUID) -> ShiftRef | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, branch_id, cash_register_id, status FROM app.shifts WHERE id = :id FOR SHARE"
                ),
                {"id": shift_id},
            )
        ).first()
        return None if row is None else ShiftRef(row[0], row[1], row[2], row[3])

    async def default_branch(self, s: AsyncSession) -> UUID:
        value: UUID = (
            await s.execute(text("SELECT id FROM app.branches WHERE is_default ORDER BY id LIMIT 1"))
        ).scalar_one()
        return value

    async def advance_balance(self, s: AsyncSession, supplier_id: UUID) -> Decimal:
        """4310 debit balance of the supplier — the same query as the receipt's advance offset."""
        return await advance_balance(s, supplier_id)

    async def overpay_policy(self, s: AsyncSession) -> str:
        value = (
            await s.execute(text("SELECT settings->>'supplier_overpay_policy' FROM app.tenants LIMIT 1"))
        ).scalar()
        return "block" if value == "block" else "warn"  # qaror #47: default 'warn'

    async def open_docs(self, s: AsyncSession, supplier_id: UUID) -> list[OpenDoc]:
        rows = await s.execute(_OPEN_DOCS, {"sup": supplier_id})
        return [
            OpenDoc(
                target_doc_type=r[0],
                target_doc_id=r[1],
                number=r[2],
                doc_date=r[3],
                due_date=r[4],
                total=_d(r[5]),
                outstanding=max(_d(r[6]), ZERO),
                einvoice_id=r[7],
                risk_flag=r[8],
                deferred_vat=_d(r[9]),
                deferred_base=_d(r[10]),
                released_vat=_d(r[11]),
                released_base=_d(r[12]),
            )
            for r in rows
        ]

    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], allocations: Sequence[Mapping[str, Any]]
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.supplier_payments (id, tenant_id, branch_id, number, doc_date, status, "
                "supplier_id, method, amount, cash_register_id, shift_id, created_by, posted_at, comment) "
                "VALUES (:id, :tenant_id, :branch_id, :number, :doc_date, 'posted', :supplier_id, :method, "
                ":amount, :cash_register_id, :shift_id, :created_by, now(), :comment)"
            ),
            dict(head),
        )
        if allocations:
            await s.execute(
                text(
                    "INSERT INTO app.supplier_payment_allocations (id, tenant_id, supplier_payment_id, "
                    "target_doc_type, target_doc_id, amount) VALUES (:id, :tenant_id, :supplier_payment_id, "
                    ":target_doc_type, :target_doc_id, :amount)"
                ),
                [dict(a) for a in allocations],
            )

    async def _hydrate(self, s: AsyncSession, heads: Sequence[Any]) -> list[PaymentRow]:
        if not heads:
            return []
        ids = [h.id for h in heads]
        allocs: dict[UUID, list[AllocationRow]] = {}
        for r in await s.execute(_ALLOCATIONS, {"ids": ids}):
            allocs.setdefault(r.supplier_payment_id, []).append(
                AllocationRow(
                    r.target_doc_type,
                    r.target_doc_id,
                    r.target_number,
                    r.target_doc_date,
                    r.target_einvoice_id,
                    Decimal(r.amount),
                )
            )
        vats: dict[UUID, list[tuple[UUID | None, Decimal]]] = {}
        for r in await s.execute(_VAT, {"ids": ids}):
            vats.setdefault(r.doc_id, []).append((r.einvoice_id, Decimal(r.vat_amount)))
        return [_payment(h._mapping, tuple(allocs.get(h.id, ())), tuple(vats.get(h.id, ()))) for h in heads]

    async def get(self, s: AsyncSession, payment_id: UUID, *, lock: bool = False) -> PaymentRow | None:
        if lock:
            locked = await s.execute(
                text("SELECT id FROM app.supplier_payments WHERE id = :id FOR UPDATE"), {"id": payment_id}
            )
            if locked.first() is None:
                return None
        head = (await s.execute(text(_HEAD + "WHERE p.id = :id"), {"id": payment_id})).first()
        if head is None:
            return None
        return (await self._hydrate(s, [head]))[0]

    async def list_page(
        self, s: AsyncSession, flt: PaymentFilter, after: UUID | None, limit: int
    ) -> list[PaymentRow]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        expanding: list[str] = []
        if flt.branch_ids is not None:
            where.append("p.branch_id IN :branches")
            params["branches"] = list(flt.branch_ids)
            expanding.append("branches")
        for column, value in (
            ("supplier_id", flt.supplier_id),
            ("status", flt.status),
            ("method", flt.method),
        ):
            if value is not None:
                where.append(f"p.{column} = :{column}")
                params[column] = value
        if flt.date_from is not None:
            where.append("p.doc_date >= :date_from")
            params["date_from"] = flt.date_from
        if flt.date_to is not None:
            where.append("p.doc_date <= :date_to")
            params["date_to"] = flt.date_to
        if after is not None:
            where.append("p.id < :after")
            params["after"] = after
        clause = ("WHERE " + " AND ".join(where) + " ") if where else ""
        stmt = text(_HEAD + clause + "ORDER BY p.id DESC LIMIT :limit")
        if expanding:
            stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding))
        heads = list(await s.execute(stmt, params))
        return await self._hydrate(s, heads)

    async def mark_cancelled(self, s: AsyncSession, payment_id: UUID, user_id: UUID, reason: str) -> None:
        await s.execute(
            text(
                "UPDATE app.supplier_payments SET status = 'cancelled', cancelled_at = now(), "
                "cancelled_by = :u, cancel_reason = :r WHERE id = :id"
            ),
            {"u": user_id, "r": reason, "id": payment_id},
        )

    async def insert_cash_move(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.cash_moves (id, tenant_id, cash_register_id, shift_id, amount, method, "
                "doc_type, doc_id, reversal_of_id) VALUES (:id, :tenant_id, :cash_register_id, :shift_id, "
                ":amount, :method, :doc_type, :doc_id, :reversal_of_id)"
            ),
            dict(row),
        )

    async def live_cash_moves(
        self, s: AsyncSession, payment_id: UUID
    ) -> list[tuple[UUID, Decimal, UUID | None, UUID | None, str]]:
        rows = await s.execute(
            text(
                "SELECT m.id, m.amount, m.cash_register_id, m.shift_id, m.method FROM app.cash_moves m "
                "WHERE m.doc_type = 'supplier_payments' AND m.doc_id = :d AND m.reversal_of_id IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM app.cash_moves r WHERE r.reversal_of_id = m.id) ORDER BY m.id"
            ),
            {"d": payment_id},
        )
        return [(r[0], Decimal(r[1]), r[2], r[3], r[4]) for r in rows]
