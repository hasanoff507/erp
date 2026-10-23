"""Bank settlements — 5710 (money in transit) → 5110 (bank) + commission (13 §2.18a, qaror #42). Pure Python.

* validation of a draft (20 #55c/#55h): ``settled_from ≤ settled_to ≤ doc_date``; ``gross > 0``;
  ``0 ≤ commission < gross``; ``variance ≠ 0`` only for ``collection``;
  ``net = gross − commission + variance > 0``;
* :func:`posting_lines` — the 13 §2.18a rows: ``Dt 5110 / Kt 5710 = net``; commission ``Dt acct / Kt 5710``
  (card/uzqr 9430; click/payme/uzum ``payment_org_commission_account`` (default 9430); collection 9410);
  collection shortage ``Dt 5910 / Kt 5710``; collection surplus ``Dt 5710 / Kt 9390``.
  Net ``Kt 5710`` = gross;
* :func:`fifo_remaining` / :func:`oldest_unsettled` — the daily transit inflows after the already settled
  amount is consumed oldest day first (BO-24 ``oldest_unsettled_date``, 55g matching);
* :func:`match_days` — the 55g rule: from the oldest remaining day take the smallest ``n`` days with
  ``Σ ≥ credit`` and ``(Σ − credit) / Σ ≤ 5%``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final, Literal

Method = Literal["card", "uzqr", "click", "payme", "uzum", "collection"]
METHODS: Final[tuple[str, ...]] = ("card", "uzqr", "click", "payme", "uzum", "collection")
PROVIDERS: Final = frozenset({"click", "payme", "uzum"})
TRANSIT: Final = "5710"
BANK: Final = "5110"
SHORTAGE: Final = "5910"
SURPLUS: Final = "9390"
BANK_COMMISSION: Final = "9430"
COLLECTION_COMMISSION: Final = "9410"
PROVIDER_COMMISSION_ACCOUNTS: Final = frozenset({"9430", "9410"})
MATCH_TOLERANCE: Final = Decimal("0.05")  # (Σ − credit) / Σ ≤ 5% (20 #55g)
ZERO: Final = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class Violation:
    field: str
    message_key: str


@dataclass(frozen=True, slots=True)
class Amounts:
    method: str
    doc_date: date
    settled_from: date
    settled_to: date
    gross: Decimal
    commission: Decimal
    variance: Decimal

    @property
    def net(self) -> Decimal:
        return self.gross - self.commission + self.variance


def validate(a: Amounts) -> list[Violation]:
    out: list[Violation] = []
    if a.method not in METHODS:
        out.append(Violation("method", "validation.enum"))
    if a.settled_from > a.settled_to:
        out.append(Violation("settled_from", "validation.date_range"))
    if a.settled_to > a.doc_date:
        out.append(Violation("settled_to", "validation.date_range"))
    if a.gross <= 0:
        out.append(Violation("gross_amount", "validation.must_be_positive"))
    if a.commission < 0:
        out.append(Violation("commission_amount", "validation.non_negative"))
    elif a.gross > 0 and a.commission >= a.gross:
        out.append(Violation("commission_amount", "validation.bank_commission_ge_gross"))
    if a.method != "collection" and a.variance != 0:
        out.append(Violation("variance_amount", "validation.not_allowed"))
    elif a.gross > 0 and a.commission < a.gross and a.net <= 0:
        out.append(Violation("variance_amount", "validation.must_be_positive"))
    return out


def commission_account(method: str, provider_account: str | None) -> str:
    if method == "collection":
        return COLLECTION_COMMISSION
    if method in PROVIDERS:
        return provider_account if provider_account in PROVIDER_COMMISSION_ACCOUNTS else BANK_COMMISSION
    return BANK_COMMISSION


@dataclass(frozen=True, slots=True)
class Line:
    account_dt: str
    account_kt: str
    amount: Decimal
    analytics: dict[str, Any]


def posting_lines(a: Amounts, *, provider_account: str | None, analytics: Mapping[str, Any]) -> list[Line]:
    """13 §2.18a rows (zero rows omitted); ``Σ Kt 5710 − Σ Dt 5710 = gross``."""
    base = {"payment_method": a.method, **analytics}
    out = [Line(BANK, TRANSIT, a.net, dict(base))]
    if a.commission > 0:
        out.append(Line(commission_account(a.method, provider_account), TRANSIT, a.commission, dict(base)))
    if a.variance < 0:
        out.append(Line(SHORTAGE, TRANSIT, -a.variance, dict(base)))
    elif a.variance > 0:
        out.append(Line(TRANSIT, SURPLUS, a.variance, dict(base)))
    return out


def fifo_remaining(inflows: Sequence[tuple[date, Decimal]], consumed: Decimal) -> list[tuple[date, Decimal]]:
    """Daily transit inflows (oldest first; days with net ≤ 0 are dropped) minus ``consumed``, oldest
    day first. Returns the days that still hold an unsettled amount."""
    left = consumed
    out: list[tuple[date, Decimal]] = []
    for day, amount in sorted(inflows):
        if amount <= 0:
            continue
        take = min(amount, max(left, ZERO))
        left -= take
        rest = amount - take
        if rest > 0:
            out.append((day, rest))
    return out


def remaining_after(
    inflows: Sequence[tuple[date, Decimal]], holds: Sequence[tuple[date, date, Decimal]]
) -> list[tuple[date, Decimal]]:
    """Daily inflows minus the settlements that already hold them (``(settled_from, settled_to, gross)``,
    posted or draft): each settlement takes from the days of its own range first (oldest first), what is left
    of it from the oldest remaining days — so an RRN-matched settlement of yesterday never eats a
    terminal-less receipt of an earlier day."""
    days = {day: amount for day, amount in sorted(inflows) if amount > 0}
    spill = ZERO
    for start, end, amount in sorted(holds):
        left = amount
        for day in sorted(days):
            if left <= 0:
                break
            if start <= day <= end:
                take = min(days[day], left)
                days[day] -= take
                left -= take
        spill += left
    return fifo_remaining([(d, a) for d, a in days.items() if a > 0], spill)


def oldest_unsettled(inflows: Sequence[tuple[date, Decimal]], balance: Decimal) -> date | None:
    """The oldest day still holding part of ``balance`` (FIFO: settlements and refunds close the oldest
    days first) — BO-24 ``oldest_unsettled_date``."""
    if balance <= 0:
        return None
    total = sum((amount for _, amount in inflows if amount > 0), ZERO)
    remaining = fifo_remaining(inflows, total - balance)
    return remaining[0][0] if remaining else None


@dataclass(frozen=True, slots=True)
class DayMatch:
    gross: Decimal
    settled_from: date
    settled_to: date
    taken: tuple[tuple[date, Decimal], ...]


def match_days(remaining: Sequence[tuple[date, Decimal]], credit: Decimal) -> DayMatch | None:
    """55g step (3): the smallest prefix of remaining days (oldest first) with ``Σ ≥ credit`` and
    ``(Σ − credit) / Σ ≤ 5%``; ``None`` when no prefix fits."""
    total = ZERO
    taken: list[tuple[date, Decimal]] = []
    for day, amount in sorted(remaining):
        total += amount
        taken.append((day, amount))
        if total >= credit:
            if (total - credit) / total <= MATCH_TOLERANCE:
                return DayMatch(total, taken[0][0], taken[-1][0], tuple(taken))
            return None
    return None
