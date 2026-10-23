"""``price_changes`` document (19 §4, qaror #25): ``draft → pending_approval (202) → posted | rejected``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

PriceChangeStatus = Literal["draft", "pending_approval", "posted", "rejected", "cancelled"]

# 26 #5 / US-M09-02: changes beyond ±10% of the catalog price need the owner's approval. Used when the
# poster holds no `prices.approve` grant of their own (a grant's limit_value — None = unlimited — wins).
DEFAULT_APPROVAL_LIMIT_PCT: Final = Decimal("10.00")
APPROVAL_TTL_MINUTES: Final = 15  # approval_requests.expires_at = requested_at + 15 min (26 #87)
MAX_LINES: Final = 1000


@dataclass(frozen=True, slots=True)
class PriceChangeLine:
    id: UUID
    line_no: int
    product_id: UUID
    branch_id: UUID | None
    old_price: Decimal
    new_price: Decimal
    valid_from: datetime | None


@dataclass(frozen=True, slots=True)
class PriceChange:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: PriceChangeStatus
    comment: str | None
    created_by: UUID
    posted_at: datetime | None
    lines: tuple[PriceChangeLine, ...]
