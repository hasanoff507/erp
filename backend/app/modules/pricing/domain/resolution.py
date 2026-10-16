"""Price resolution — pure functions (19 §4, 11 §4, US-M09-01; reused by POS in Bosqich 3).

``product_prices`` is an append-only history: a row is effective from its
``valid_from`` until the next row of the same series (same product, same
``branch_id`` — ``NULL`` = every branch). Rules:

* a row whose ``valid_from`` is in the future is not yet effective;
* a branch price overrides the global one ("``base`` = filial narxi, yo'q
  bo'lsa global narx", 19 §4);
* at equal ``valid_from`` the later-created row (UUIDv7 ``id``) wins.

A temporary promo price is two rows: the promo (``valid_from`` = start) and the
regular price again (``valid_from`` = end) — after the end the regular price
applies automatically (QT-M09-09).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final
from uuid import UUID

HUNDRED: Final = Decimal("100")
PCT_EXP: Final = Decimal("0.0001")  # approval_requests.requested_value NUMERIC(18,4)


@dataclass(frozen=True, slots=True)
class PriceRecord:
    id: UUID
    product_id: UUID
    branch_id: UUID | None
    price: Decimal
    valid_from: datetime
    set_by: UUID | None = None
    price_change_doc_id: UUID | None = None


def _key(r: PriceRecord) -> tuple[datetime, int]:
    return (r.valid_from, r.id.int)


def _latest(records: Iterable[PriceRecord], at: datetime) -> PriceRecord | None:
    effective = [r for r in records if r.valid_from <= at]
    return max(effective, key=_key) if effective else None


def effective_record(
    records: Iterable[PriceRecord], *, product_id: UUID, branch_id: UUID | None, at: datetime
) -> PriceRecord | None:
    """The price row in force for ``product_id`` in ``branch_id`` (``None`` = global only) at ``at``."""
    own = [r for r in records if r.product_id == product_id]
    if branch_id is not None:
        branch = _latest((r for r in own if r.branch_id == branch_id), at)
        if branch is not None:
            return branch
    return _latest((r for r in own if r.branch_id is None), at)


def effective_price(
    records: Iterable[PriceRecord], *, product_id: UUID, branch_id: UUID | None, at: datetime
) -> Decimal | None:
    record = effective_record(records, product_id=product_id, branch_id=branch_id, at=at)
    return record.price if record else None


def change_pct(base: Decimal | None, new: Decimal) -> Decimal | None:
    """``|new − base| / base × 100`` (19 §4); ``None`` when there is no base (no limit check)."""
    if base is None or base == 0:
        return None
    return (abs(new - base) / base * HUNDRED).quantize(PCT_EXP, rounding=ROUND_HALF_UP)


def within_limit(pct: Decimal | None, limit: Decimal | None) -> bool:
    """``limit`` ``None`` = unlimited (qaror #28)."""
    return pct is None or limit is None or pct <= limit


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    record: PriceRecord
    valid_to: datetime | None


def series_history(records: Sequence[PriceRecord]) -> list[HistoryEntry]:
    """One series (same product + branch) newest first; ``valid_to`` = next row's ``valid_from``."""
    ordered = sorted(records, key=_key)
    out: list[HistoryEntry] = []
    for index, record in enumerate(ordered):
        nxt = ordered[index + 1].valid_from if index + 1 < len(ordered) else None
        out.append(HistoryEntry(record, nxt))
    out.reverse()
    return out
