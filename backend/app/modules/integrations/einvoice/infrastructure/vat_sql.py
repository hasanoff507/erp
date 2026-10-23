"""SQL reads of :mod:`..application.vat_credit` (``goods_receipts``, ``receipt_lines``, ``ledger_entries``,
``vat_moves``, ``supplier_returns``, ``tenant_tax_regimes``; caller's transaction, RLS)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.einvoice.application.vat_credit import DeferredReceipt, ReturnVat

ZERO = Decimal("0.00")


class SqlVatCreditRepository:
    async def deferred_receipts(self, s: AsyncSession, einvoice_id: UUID) -> list[DeferredReceipt]:
        rows = await s.execute(
            text(
                "SELECT gr.id, COALESCE(dv.amount, 0), COALESCE(nb.base, 0) FROM app.goods_receipts gr "
                "LEFT JOIN LATERAL (SELECT sum(le.amount) AS amount FROM app.ledger_entries le "
                "  WHERE le.doc_type = 'goods_receipts' AND le.doc_id = gr.id AND le.account_dt = '4410' "
                "  AND le.analytics->>'vat_credit' = 'deferred' AND le.reversal_of_id IS NULL "
                "  AND NOT EXISTS (SELECT 1 FROM app.ledger_entries r WHERE r.reversal_of_id = le.id)) dv "
                "ON true "
                "LEFT JOIN LATERAL (SELECT sum(COALESCE(l.net_amount, round(l.qty * l.cost, 2))) AS base "
                "  FROM app.receipt_lines l WHERE l.receipt_id = gr.id AND l.vat_amount > 0) nb ON true "
                "WHERE gr.einvoice_id = :e AND gr.status = 'posted' ORDER BY gr.id FOR UPDATE OF gr"
            ),
            {"e": einvoice_id},
        )
        return [DeferredReceipt(r[0], Decimal(r[1]), Decimal(r[2])) for r in rows if Decimal(r[1]) > 0]

    async def credited(self, s: AsyncSession, einvoice_id: UUID) -> tuple[Decimal, Decimal]:
        row = (
            await s.execute(
                text(
                    "SELECT COALESCE(sum(vat_amount), 0), COALESCE(sum(base_amount), 0) FROM app.vat_moves "
                    "WHERE einvoice_id = :e AND kind = 'input'"
                ),
                {"e": einvoice_id},
            )
        ).one()
        return Decimal(row[0]), Decimal(row[1])

    async def supplier_return(self, s: AsyncSession, return_id: UUID) -> ReturnVat | None:
        row = (
            await s.execute(
                text(
                    "SELECT sr.id, sr.branch_id, sr.supplier_id, sr.status, "
                    "COALESCE((SELECT x.regime FROM app.tenant_tax_regimes x WHERE x.valid_from <= "
                    "gr.doc_date "
                    "  ORDER BY x.valid_from DESC LIMIT 1), 'vat'), "
                    "COALESCE((SELECT sum(l.vat_amount) FROM app.supplier_return_lines l "
                    "  WHERE l.supplier_return_id = sr.id), 0), "
                    "COALESCE((SELECT sum(round(l.qty * l.cost, 2)) FROM app.supplier_return_lines l "
                    "  WHERE l.supplier_return_id = sr.id AND l.vat_amount > 0), 0), "
                    "gr.einvoice_id, "
                    "EXISTS (SELECT 1 FROM app.ledger_entries le WHERE le.doc_type = 'goods_receipts' "
                    "  AND le.doc_id = gr.id AND le.account_dt = '4410' AND le.analytics->>'vat_credit' = "
                    "'deferred'), "
                    "EXISTS (SELECT 1 FROM app.ledger_entries le WHERE le.doc_type = 'supplier_returns' "
                    "  AND le.doc_id = sr.id AND le.account_kt = '4410' AND le.reversal_of_id IS NULL) "
                    "FROM app.supplier_returns sr JOIN app.goods_receipts gr ON gr.id = sr.receipt_id "
                    "WHERE sr.id = :id FOR UPDATE OF sr"
                ),
                {"id": return_id},
            )
        ).first()
        if row is None:
            return None
        return ReturnVat(
            id=row[0],
            branch_id=row[1],
            supplier_id=row[2],
            status=row[3],
            regime=row[4],
            vat_total=Decimal(row[5]),
            net_total=Decimal(row[6]),
            original_einvoice_id=row[7],
            original_deferred=bool(row[8]),
            adjusted=bool(row[9]),
        )

    async def match_supplier_return(
        self, s: AsyncSession, original_einvoice_id: UUID, vat_amount: Decimal | None
    ) -> UUID | None:
        """The oldest posted, not yet adjusted / linked return of the receipt made from the original EHF,
        preferring one whose VAT equals the additional EHF's VAT."""
        got = await s.execute(
            text(
                "SELECT sr.id FROM app.supplier_returns sr JOIN app.goods_receipts gr ON gr.id = "
                "sr.receipt_id "
                "LEFT JOIN LATERAL (SELECT sum(l.vat_amount) AS vat FROM app.supplier_return_lines l "
                "  WHERE l.supplier_return_id = sr.id) v ON true "
                "WHERE gr.einvoice_id = :e AND sr.status = 'posted' "
                "AND NOT EXISTS (SELECT 1 FROM app.einvoices x WHERE x.related_doc_type = 'supplier_returns' "
                "  AND x.related_doc_id = sr.id AND x.status <> 'cancelled') "
                "ORDER BY (CAST(:v AS numeric) IS NOT NULL AND v.vat = abs(CAST(:v AS numeric))) DESC, sr.id "
                "LIMIT 1"
            ),
            {"e": original_einvoice_id, "v": vat_amount},
        )
        value: UUID | None = got.scalar_one_or_none()
        return value
