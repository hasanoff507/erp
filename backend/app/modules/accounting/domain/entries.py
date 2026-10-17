"""Ledger lines and VAT moves of a document posting (13 §2, §4.1, §5.2, §5.3). Pure Python.

A posting service builds :class:`LedgerLine` / :class:`VatMove` values and hands them to the
accounting poster, which validates them with :func:`checked_line` / :func:`checked_vat` and writes
``ledger_entries`` / ``vat_moves`` rows in the caller's transaction.

Rules (13 §1, §5.3, 12 ``ledger_entries``):

* both accounts are in the chart and in use; ``account_dt != account_kt``;
* the amount is quantized to tiyin (ROUND_HALF_UP); a zero amount is *skipped* (never written),
  a negative amount is a programming error;
* ``branch_id`` is mandatory analytics (13 §5.4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.core.money import money, to_decimal
from app.modules.accounting.domain.calendar import month_start
from app.modules.accounting.domain.chart_of_accounts import ACCOUNTS_BY_CODE

VatKind = Literal["input", "output"]
ZERO = Decimal("0.00")


class PostingError(ValueError):
    """A posting service built an invalid entry — a bug, never a user error."""


@dataclass(frozen=True, slots=True)
class LedgerLine:
    entry_date: date
    branch_id: UUID
    account_dt: str
    account_kt: str
    amount: Decimal
    analytics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VatMove:
    """One ``vat_moves`` row; ``period`` is derived from ``entry_date`` (first day of the month)."""

    entry_date: date
    kind: VatKind
    base_amount: Decimal
    vat_amount: Decimal
    einvoice_id: UUID | None = None

    @property
    def period(self) -> date:
        return month_start(self.entry_date)


def _account(code: str, side: str) -> None:
    account = ACCOUNTS_BY_CODE.get(code)
    if account is None:
        raise PostingError(f"{side} account {code!r} is not in the chart of accounts (13 §1)")
    if not account.in_use:
        raise PostingError(f"{side} account {code!r} is not used in the MVP (13 §1)")


def checked_line(line: LedgerLine) -> LedgerLine | None:
    """Validated copy with the amount quantized to tiyin; ``None`` for a zero amount (skip it)."""
    _account(line.account_dt, "debit")
    _account(line.account_kt, "credit")
    if line.account_dt == line.account_kt:
        raise PostingError(f"account_dt == account_kt ({line.account_dt})")
    if not isinstance(line.branch_id, UUID):
        raise PostingError("branch_id is mandatory ledger analytics (13 §5.4)")
    amount = money(to_decimal(line.amount))
    if amount < 0:
        raise PostingError(f"negative ledger amount {amount} ({line.account_dt}/{line.account_kt})")
    if amount == 0:
        return None
    return LedgerLine(
        entry_date=line.entry_date,
        branch_id=line.branch_id,
        account_dt=line.account_dt,
        account_kt=line.account_kt,
        amount=amount,
        analytics=dict(line.analytics),
    )


def checked_vat(move: VatMove) -> VatMove | None:
    """Validated copy (amounts in tiyin); ``None`` when both amounts are zero."""
    if move.kind not in ("input", "output"):
        raise PostingError(f"vat kind {move.kind!r}")
    base = money(to_decimal(move.base_amount))
    vat = money(to_decimal(move.vat_amount))
    if base == 0 and vat == 0:
        return None
    return VatMove(move.entry_date, move.kind, base, vat, move.einvoice_id)


def swapped(line: LedgerLine, entry_date: date, extra: Mapping[str, Any] | None = None) -> LedgerLine:
    """The storno twin of ``line`` (13 §5.2): Dt/Kt swapped, same positive amount."""
    return LedgerLine(
        entry_date=entry_date,
        branch_id=line.branch_id,
        account_dt=line.account_kt,
        account_kt=line.account_dt,
        amount=line.amount,
        analytics={**line.analytics, **(extra or {})},
    )
