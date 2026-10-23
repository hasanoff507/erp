"""The posting toolkit every document posting service uses (13 §2, §5.1–§5.3; 23 §2.1, §2.3).

All methods run inside the caller's ``tenant_transaction`` — the document status, the registers
and the ledger commit or roll back together (23 §2.1). Usage::

    poster = ledger_poster()                                   # accounting.wiring
    await poster.post(s, tenant_id, "write_offs", doc.id, [
        LedgerLine(doc.doc_date, doc.branch_id, "9430", "2910", cost, analytics),
    ])
    ...
    await poster.reverse_document(s, tenant_id, "write_offs", doc.id)   # cancel = storno

* :meth:`LedgerPoster.post` refuses any line or VAT move dated in a closed period
  (``409 PERIOD_CLOSED``, ``params.period = "YYYY-MM"``); zero lines are skipped.
* :meth:`LedgerPoster.reverse_document` adds, for every *live* original row of the document (not
  itself a reversal and not yet reversed), a reversal row — ledger: Dt/Kt swapped, same amount;
  VAT: negated amounts — with ``reversal_of_id``, dated the cancellation date (today in Tashkent)
  or, if that period is closed, the first open date. A document from a closed period may be
  cancelled: the storno lands in the open period (13 §5.2).
* :meth:`LedgerPoster.reverse_entries` reverses specific rows (recost, 13 §3.3).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.accounting.application.ports import LedgerRepository, StoredEntry, StoredVat
from app.modules.accounting.domain.calendar import (
    business_today,
    first_open_date,
    is_closed,
    month_start,
    period_label,
)
from app.modules.accounting.domain.entries import (
    LedgerLine,
    VatKind,
    VatMove,
    checked_line,
    checked_vat,
    swapped,
)


@dataclass(frozen=True, slots=True)
class Posted:
    ledger_ids: list[UUID]
    vat_ids: list[UUID]
    entry_date: date | None = None


def period_closed_error(day: date) -> AppError:
    return AppError(ErrorCode.PERIOD_CLOSED, params={"period": period_label(day)})


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), default=str, ensure_ascii=False, sort_keys=True)


class LedgerPoster:
    def __init__(self, repo: LedgerRepository) -> None:
        self._repo = repo

    # --- periods ----------------------------------------------------------------------------------
    async def last_closed_period(self, s: AsyncSession) -> date | None:
        return await self._repo.last_closed_period(s)

    async def is_closed(self, s: AsyncSession, day: date) -> bool:
        return is_closed(day, await self._repo.last_closed_period(s))

    async def assert_period_open(self, s: AsyncSession, day: date) -> None:
        """``409 PERIOD_CLOSED`` when ``day`` falls in a closed month (closing is oldest-first, 13 §5.1)."""
        if await self.is_closed(s, day):
            raise period_closed_error(day)

    async def first_open_date(self, s: AsyncSession, day: date | None = None) -> date:
        """``day`` (default: today in Tashkent) or the 1st day of the first open period."""
        return first_open_date(day or business_today(), await self._repo.last_closed_period(s))

    # --- writing ----------------------------------------------------------------------------------
    async def post(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        doc_type: str,
        doc_id: UUID,
        lines: Iterable[LedgerLine],
        vat: Iterable[VatMove] = (),
    ) -> Posted:
        """Write the document's ledger lines and VAT moves (zero lines skipped)."""
        ledger = [c for c in (checked_line(line) for line in lines) if c is not None]
        vats = [c for c in (checked_vat(v) for v in vat) if c is not None]
        last_closed = await self._repo.last_closed_period(s)
        for day in sorted({x.entry_date for x in ledger} | {v.entry_date for v in vats}):
            if is_closed(day, last_closed):
                raise period_closed_error(day)
        ids = await self._insert_entries(s, tenant_id, doc_type, doc_id, [(x, None) for x in ledger])
        vat_ids = await self._insert_vat(s, tenant_id, doc_type, doc_id, [(v, None) for v in vats])
        return Posted(ids, vat_ids)

    async def reverse_document(
        self, s: AsyncSession, tenant_id: UUID, doc_type: str, doc_id: UUID, *, on: date | None = None
    ) -> Posted:
        """Storno every live ledger row and VAT move of ``(doc_type, doc_id)`` (13 §5.2, 23 §2.3)."""
        entry_date = await self.first_open_date(s, on)
        entries = await self._repo.doc_entries(s, doc_type, doc_id, live_only=True)
        vats = await self._repo.live_vat(s, doc_type, doc_id)
        ids = await self._insert_entries(
            s, tenant_id, doc_type, doc_id, [(swapped(_line(e), entry_date), e.id) for e in entries]
        )
        vat_ids = await self._insert_vat(
            s, tenant_id, doc_type, doc_id, [(_negated(v, entry_date), v.id) for v in vats]
        )
        return Posted(ids, vat_ids, entry_date)

    async def reverse_entries(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        entries: Sequence[StoredEntry],
        *,
        on: date,
        extra_analytics: Mapping[str, Any] | None = None,
    ) -> list[UUID]:
        """Storno specific rows of ONE document (recost, 13 §3.3) dated ``on`` (must be open)."""
        if not entries:
            return []
        if len({(e.doc_type, e.doc_id) for e in entries}) != 1:
            raise ValueError("reverse_entries() takes rows of one document")
        if any(e.reversal_of_id is not None for e in entries):
            raise ValueError("a reversal row is never reversed again")
        await self.assert_period_open(s, on)
        return await self._insert_entries(
            s,
            tenant_id,
            entries[0].doc_type,
            entries[0].doc_id,
            [(swapped(_line(e), on, extra_analytics), e.id) for e in entries],
        )

    # --- reading ----------------------------------------------------------------------------------
    async def doc_entries(
        self,
        s: AsyncSession,
        doc_type: str,
        doc_id: UUID,
        *,
        analytics: Mapping[str, Any] | None = None,
        live_only: bool = False,
    ) -> list[StoredEntry]:
        """Rows of a document; ``analytics`` = JSON containment filter; ``live_only`` = originals not
        reversed yet (what a storno would reverse)."""
        return await self._repo.doc_entries(s, doc_type, doc_id, analytics=analytics, live_only=live_only)

    # --- helpers ----------------------------------------------------------------------------------
    async def _insert_entries(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        doc_type: str,
        doc_id: UUID,
        rows: Sequence[tuple[LedgerLine, UUID | None]],
    ) -> list[UUID]:
        ids = [uuid7() for _ in rows]
        if rows:
            await self._repo.insert_entries(
                s,
                [
                    {
                        "id": lid, "tenant_id": tenant_id, "entry_date": line.entry_date,
                        "branch_id": line.branch_id, "account_dt": line.account_dt,
                        "account_kt": line.account_kt, "amount": line.amount, "doc_type": doc_type,
                        "doc_id": doc_id, "analytics": _json(line.analytics), "reversal_of_id": orig,
                    }
                    for lid, (line, orig) in zip(ids, rows, strict=True)
                ],
            )  # fmt: skip
        return ids

    async def _insert_vat(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        doc_type: str,
        doc_id: UUID,
        rows: Sequence[tuple[VatMove, UUID | None]],
    ) -> list[UUID]:
        ids = [uuid7() for _ in rows]
        if rows:
            await self._repo.insert_vat(
                s,
                [
                    {
                        "id": vid, "tenant_id": tenant_id, "period": month_start(v.entry_date),
                        "kind": v.kind, "base_amount": v.base_amount, "vat_amount": v.vat_amount,
                        "doc_type": doc_type, "doc_id": doc_id, "einvoice_id": v.einvoice_id,
                        "reversal_of_id": orig,
                    }
                    for vid, (v, orig) in zip(ids, rows, strict=True)
                ],
            )  # fmt: skip
        return ids


def _line(entry: StoredEntry) -> LedgerLine:
    if entry.branch_id is None:
        raise ValueError(f"ledger entry {entry.id} has no branch_id")
    return LedgerLine(
        entry_date=entry.entry_date,
        branch_id=entry.branch_id,
        account_dt=entry.account_dt,
        account_kt=entry.account_kt,
        amount=entry.amount,
        analytics=dict(entry.analytics),
    )


def _negated(v: StoredVat, entry_date: date) -> VatMove:
    kind: VatKind = "input" if v.kind == "input" else "output"
    return VatMove(entry_date, kind, -v.base_amount, -v.vat_amount, v.einvoice_id)
