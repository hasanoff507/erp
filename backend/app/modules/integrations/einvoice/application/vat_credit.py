"""Input-VAT effects of e-invoice events (13 §2.8, §2.20; 19 §19; US-M07-03, US-M10-03, US-M07-05).

* :meth:`VatCredit.release_on_green` — ``PATCH /einvoices/{id}/risk-flag`` → ``green``: the linked
  **posted** receipt's deferred credit (``Dt 4410`` with ``vat_credit='deferred'``) not yet in
  ``vat_moves`` is written now — only ``vat_moves(kind=input, einvoice_id)``, ``doc_type='goods_receipts'``,
  dated the marking day; the ledger is not rewritten (13 §2.8). What payments / advance offsets already
  released is subtracted (``Σ vat_moves`` of the e-invoice), so nothing is credited twice.
* :meth:`VatCredit.adjust_supplier_return` — the supplier's **additional** (negative) EHF linked to a posted
  supplier return is accepted: row 2 of 13 §2.20 ``Dt 6010 / Kt 4410 = Σ return VAT`` (analytics
  ``vat_credit='deferred'`` when the original credit was deferred), ``debt_moves`` payable ``−Σ VAT`` and a
  negative ``vat_moves(kind=input)`` limited to what the original e-invoice already has in ``vat_moves``;
  all as ``doc_type='supplier_returns'`` of that return, dated the acceptance day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import money
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.entries import LedgerLine, VatMove
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.register import DebtMoveInput

ZERO: Final = Decimal("0.00")
SUPPLIERS: Final = "6010"
INPUT_VAT: Final = "4410"


@dataclass(frozen=True, slots=True)
class DeferredReceipt:
    id: UUID
    deferred_vat: Decimal  # Σ live Dt 4410 lines with vat_credit='deferred'
    base: Decimal  # Σ net of the taxed lines


@dataclass(frozen=True, slots=True)
class ReturnVat:
    id: UUID
    branch_id: UUID
    supplier_id: UUID
    status: str
    regime: str
    vat_total: Decimal
    net_total: Decimal
    original_einvoice_id: UUID | None
    original_deferred: bool
    adjusted: bool


class VatCreditRepository(Protocol):
    async def deferred_receipts(self, s: AsyncSession, einvoice_id: UUID) -> list[DeferredReceipt]: ...
    async def credited(self, s: AsyncSession, einvoice_id: UUID) -> tuple[Decimal, Decimal]: ...
    async def supplier_return(self, s: AsyncSession, return_id: UUID) -> ReturnVat | None: ...
    async def match_supplier_return(
        self, s: AsyncSession, original_einvoice_id: UUID, vat_amount: Decimal | None
    ) -> UUID | None: ...


class VatCredit:
    def __init__(self, repo: VatCreditRepository, poster: LedgerPoster, debts: DebtRegister) -> None:
        self._repo = repo
        self._poster = poster
        self._debts = debts

    @property
    def repo(self) -> VatCreditRepository:
        return self._repo

    async def release_on_green(
        self, s: AsyncSession, tenant_id: UUID, einvoice_id: UUID, day: date
    ) -> Decimal:
        """Write the not-yet-credited deferred VAT of the e-invoice's posted receipt(s); returns the VAT."""
        receipts = await self._repo.deferred_receipts(s, einvoice_id)
        deferred = money(sum((r.deferred_vat for r in receipts), ZERO))
        if deferred <= 0:
            return ZERO
        credited_vat, credited_base = await self._repo.credited(s, einvoice_id)
        released = ZERO
        remaining_vat = money(deferred - credited_vat)
        remaining_base = money(sum((r.base for r in receipts), ZERO) - credited_base)
        for r in receipts:
            if remaining_vat <= 0:
                break
            vat = min(r.deferred_vat, remaining_vat)
            base = remaining_base if vat == remaining_vat else money(r.base * vat / r.deferred_vat)
            await self._poster.post(
                s, tenant_id, "goods_receipts", r.id, [], vat=[VatMove(day, "input", base, vat, einvoice_id)]
            )
            released += vat
            remaining_vat = money(remaining_vat - vat)
            remaining_base = money(remaining_base - base)
        return money(released)

    async def adjust_supplier_return(
        self, s: AsyncSession, tenant_id: UUID, return_id: UUID, day: date
    ) -> Decimal:
        """13 §2.20 row 2 on the accepted additional EHF; returns the VAT moved (0 = nothing to do)."""
        sr = await self._repo.supplier_return(s, return_id)
        if sr is None or sr.status != "posted" or sr.regime != "vat" or sr.vat_total <= 0 or sr.adjusted:
            return ZERO
        await self._debts.lock(s, tenant_id, [(sr.supplier_id, "payable")])
        analytics = {"tax_type": "vat", "counterparty_id": str(sr.supplier_id)}
        if sr.original_einvoice_id is not None:
            analytics["einvoice_id"] = str(sr.original_einvoice_id)
        if sr.original_deferred:
            analytics["vat_credit"] = "deferred"
        vat_moves: list[VatMove] = []
        if sr.original_einvoice_id is not None:
            credited_vat, _ = await self._repo.credited(s, sr.original_einvoice_id)
            negative = min(sr.vat_total, max(credited_vat, ZERO))
        else:  # a manual receipt: its credit was taken at posting (13 §2.8)
            negative = sr.vat_total
        if negative > 0:
            base = sr.net_total if negative == sr.vat_total else money(sr.net_total * negative / sr.vat_total)
            vat_moves.append(VatMove(day, "input", -base, -negative, sr.original_einvoice_id))
        line = LedgerLine(day, sr.branch_id, SUPPLIERS, INPUT_VAT, sr.vat_total, analytics)
        await self._poster.post(s, tenant_id, "supplier_returns", sr.id, [line], vat=vat_moves)
        await self._debts.post(
            s, tenant_id, [DebtMoveInput(sr.supplier_id, "payable", -sr.vat_total, "supplier_returns", sr.id)]
        )
        return sr.vat_total
