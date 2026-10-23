"""Ledger lines and VAT moves of a POS sale / return (13 §2.1–§2.5, §4.1, §4.3). Pure Python.

Revenue rows are split **by payment part** (13 §2.4: ``vat_p = ROUND_HALF_UP(vat_total × p / total, 2)``,
the last part takes the rest) and, inside a part, **by receipt line** (rest to the largest line), so every
9020 / 9040 / 9050 / 6410 row carries ``product_id`` analytics (13 §1; turnover tax by product, §4.3).
A single-line receipt gives exactly the 13 §2.1–§2.4 examples.

Sale (``gross_9050``, the default ``discount_posting``)::

    Dt acct(p) / Kt 9020 = net_pi + disc_pi       (list price without VAT)
    Dt 9050    / Kt acct(p) = disc_pi             (13 §2.1a row 1a; only with a discount)
    Dt acct(p) / Kt 6410 = vat_pi                 (VAT of the discounted amount)

``net`` posting: no 9050 row, 9020 = the discounted net. Return (13 §2.5)::

    Dt 9040 / Kt acct(p) = net_pi;   Dt 6410 / Kt acct(p) = vat_pi

``acct``: cash → 5010, card/uzqr/click/payme/uzum → 5710, debt / debt_adjustment → 4010. A turnover-regime
tenant (13 §4.3) writes no 6410 rows and no VAT moves: 9020/9040 take the whole amount.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

from app.core.money import money
from app.modules.accounting.domain.entries import LedgerLine, VatMove
from app.modules.sales.domain.calc import ZERO, allocate_largest, allocate_last

CASH_ACCOUNT: Final = "5010"
TRANSIT_ACCOUNT: Final = "5710"
RECEIVABLE_ACCOUNT: Final = "4010"
REVENUE: Final = "9020"
RETURNS: Final = "9040"
DISCOUNTS: Final = "9050"
VAT_PAYABLE: Final = "6410"
COGS: Final = "9120"
NON_CASH: Final = frozenset({"card", "uzqr", "click", "payme", "uzum"})

DiscountPosting = Literal["gross_9050", "net"]


def account_for(method: str) -> str:
    if method == "cash":
        return CASH_ACCOUNT
    if method in NON_CASH:
        return TRANSIT_ACCOUNT
    if method in ("debt", "debt_adjustment"):
        return RECEIVABLE_ACCOUNT
    raise ValueError(f"unknown payment method {method!r}")


@dataclass(frozen=True, slots=True)
class Part:
    """One money part of the document (a payment row; a return's debt part / money part)."""

    method: str
    amount: Decimal
    analytics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LineAmounts:
    product_id: UUID
    total: Decimal  # with VAT (after discount)
    vat: Decimal
    vat_rate: Decimal
    discount_net: Decimal = ZERO  # gross_9050 row 1a amount of the line (sales only)

    @property
    def net(self) -> Decimal:
        return money(self.total - self.vat)


def _split(parts: Sequence[Part], total: Decimal) -> list[Decimal]:
    return allocate_last(total, [p.amount for p in parts])


def document_ledger(
    *,
    kind: Literal["sale", "return"],
    entry_date: date,
    branch_id: UUID,
    parts: Sequence[Part],
    lines: Sequence[LineAmounts],
    vat_payer: bool,
    discount_posting: DiscountPosting = "gross_9050",
    analytics: Mapping[str, Any] | None = None,
) -> tuple[list[LedgerLine], list[VatMove]]:
    """Revenue/discount/VAT rows of a sale or a return (cost rows are written by the stock toolkit)."""
    base = dict(analytics or {})
    amount = money(sum((p.amount for p in parts), ZERO))
    if amount != money(sum((ln.total for ln in lines), ZERO)):
        raise ValueError("payment parts must add up to the line totals")
    vats = [ln.vat if vat_payer else ZERO for ln in lines]
    nets = [money(ln.total - v) for ln, v in zip(lines, vats, strict=True)]
    discs = [ln.discount_net if kind == "sale" and discount_posting == "gross_9050" else ZERO for ln in lines]
    vat_parts = _split(parts, sum(vats, ZERO))
    disc_parts = _split(parts, sum(discs, ZERO))
    out: list[LedgerLine] = []
    for part, vat_p, disc_p in zip(parts, vat_parts, disc_parts, strict=True):
        acct = account_for(part.method)
        net_p = money(part.amount - vat_p)
        net_lines = allocate_largest(net_p, nets)
        vat_lines = allocate_largest(vat_p, vats)
        disc_lines = allocate_largest(disc_p, discs) if disc_p else [ZERO for _ in lines]
        for ln, net_i, vat_i, disc_i in zip(lines, net_lines, vat_lines, disc_lines, strict=True):
            row = {**base, **dict(part.analytics), "product_id": str(ln.product_id)}
            if kind == "sale":
                out.append(LedgerLine(entry_date, branch_id, acct, REVENUE, money(net_i + disc_i), row))
                if disc_i:
                    out.append(LedgerLine(entry_date, branch_id, DISCOUNTS, acct, disc_i, row))
                if vat_i:
                    out.append(
                        LedgerLine(
                            entry_date, branch_id, acct, VAT_PAYABLE, vat_i, {**row, "tax_type": "vat"}
                        )
                    )
            else:
                out.append(LedgerLine(entry_date, branch_id, RETURNS, acct, net_i, row))
                if vat_i:
                    out.append(
                        LedgerLine(
                            entry_date, branch_id, VAT_PAYABLE, acct, vat_i, {**row, "tax_type": "vat"}
                        )
                    )
    vat_moves: list[VatMove] = []
    if vat_payer:
        sign = Decimal(1) if kind == "sale" else Decimal(-1)
        by_rate: dict[Decimal, tuple[Decimal, Decimal]] = {}
        for ln, net, vat in zip(lines, nets, vats, strict=True):
            b, v = by_rate.get(ln.vat_rate, (ZERO, ZERO))
            by_rate[ln.vat_rate] = (b + net, v + vat)
        for rate in sorted(by_rate):
            b, v = by_rate[rate]
            vat_moves.append(VatMove(entry_date, "output", money(sign * b), money(sign * v)))
    return out, vat_moves
