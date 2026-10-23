"""Approval kinds and their rules (15 §2.3, 18 §2.4/§9, 12 §2.5a). Pure Python.

* ``PERMISSION_BY_KIND`` — the code the approver must hold (``approval_requests.permission_code``,
  15 §2.3 — the single source);
* ``REQUESTER_PERMISSION`` — the code the requester of ``POST /approval-requests`` must hold (18 §9.2);
  kinds not listed are created only by their document's own ``post`` (``price_change``,
  ``write_off_over_limit``, ``expense_over_limit``);
* ``KIND_MISSING_CODE`` — the error when an over-limit action arrives without an ``ApprovalRef``
  (18 §18);
* ``VALUE_KEY`` — the ``context`` key holding ``requested_value`` (percent for discounts, so'm otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

APPROVAL_TTL_MINUTES: Final = 15  # approval_requests.expires_at = requested_at + 15 min (26 #87)

KINDS: Final[tuple[str, ...]] = (
    "discount_over_limit",
    "return_over_limit",
    "return_no_receipt",
    "debt_over_limit",
    "cash_withdrawal_over_limit",
    "price_change",
    "expense_over_limit",
    "write_off_over_limit",
    "card_manual_entry",
)

PERMISSION_BY_KIND: Final[dict[str, str]] = {
    "discount_over_limit": "discount.approve",
    "return_over_limit": "returns.approve",
    "return_no_receipt": "returns.approve",
    "debt_over_limit": "debts.approve",
    "cash_withdrawal_over_limit": "cash.withdraw",
    "price_change": "prices.approve",
    "expense_over_limit": "expenses.approve",
    "write_off_over_limit": "stock.writeoff",
    "card_manual_entry": "card.manual_entry.approve",
}

REQUESTER_PERMISSION: Final[dict[str, str]] = {
    "discount_over_limit": "sales.create",
    "return_over_limit": "returns.create",
    "return_no_receipt": "returns.create",
    "debt_over_limit": "debts.create",
    "cash_withdrawal_over_limit": "cash.withdraw",
    "card_manual_entry": "sales.create",
}

KIND_MISSING_CODE: Final[dict[str, str]] = {
    "discount_over_limit": "DISCOUNT_LIMIT_EXCEEDED",
    "return_over_limit": "RETURN_LIMIT_EXCEEDED",
    "return_no_receipt": "APPROVAL_INVALID",
    "debt_over_limit": "DEBT_LIMIT_EXCEEDED",
    "cash_withdrawal_over_limit": "CASH_WITHDRAW_LIMIT_EXCEEDED",
    "price_change": "PRICE_CHANGE_LIMIT_EXCEEDED",
    "expense_over_limit": "EXPENSE_LIMIT_EXCEEDED",
    "write_off_over_limit": "WRITE_OFF_LIMIT_EXCEEDED",
    "card_manual_entry": "CARD_MANUAL_APPROVAL_REQUIRED",
}

VALUE_KEY: Final[dict[str, str]] = {
    "discount_over_limit": "requested_pct",
    "price_change": "requested_pct",
}

# card_manual_entry is limitless (15 §2.3): only holding the permission matters
UNLIMITED_KINDS: Final[frozenset[str]] = frozenset({"card_manual_entry"})


def value_key(kind: str) -> str:
    return VALUE_KEY.get(kind, "amount")


@dataclass(frozen=True, slots=True)
class UserGrant:
    """What one user holds for one permission code in a tenant (active membership only)."""

    active: bool
    owner: bool
    branch_ids: tuple[str, ...]  # empty = every branch
    limits: tuple[Decimal | None, ...]  # limit_value of every role granting the code

    @property
    def holds(self) -> bool:
        return self.active and (self.owner or bool(self.limits))

    @property
    def limit(self) -> Decimal | None:
        """Most generous limit (``None`` = unlimited); only meaningful when :attr:`holds`."""
        if self.owner or any(v is None for v in self.limits):
            return None
        return max(v for v in self.limits if v is not None)

    def covers(self, value: Decimal | None) -> bool:
        if not self.holds:
            return False
        limit = self.limit
        return limit is None or value is None or value <= limit

    def in_branch(self, branch_id: str) -> bool:
        return not self.branch_ids or branch_id in self.branch_ids
