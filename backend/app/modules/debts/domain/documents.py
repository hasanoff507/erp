"""Debt book documents — posting lines and rules (13 §2.13–§2.15a, 18 §12, 20 #21). Pure Python.

* :func:`payment_ledger` — 13 §2.14: ``Dt 5010/5710/5110 / Kt 4010`` (sales + openings allocations, one line
  per
  target), ``Kt 9390`` (written-off debt that came back), ``Kt 6310`` (offline overpayment, qaror #67);
* :func:`opening_ledger` — 13 §2.13: receivable ``Dt 4010 / Kt 0000``, payable ``Dt 0000 / Kt 6010``;
* :func:`writeoff_ledger` — 13 §2.15: ``Dt 9430 | 4910 / Kt 4010`` (one line per written-off target);
* aging buckets (20 #21), debt row status (11 §8), the US-M08-03/09 reminder template.

A doubtful flag (13 §2.15a, 18 §12.6) is a mark only — it never posts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

from app.modules.accounting.domain.entries import LedgerLine
from app.shared.debt_allocation import AllocationResult

ZERO: Final = Decimal("0.00")
RECEIVABLE: Final = "4010"
PAYABLE: Final = "6010"
OPENING: Final = "0000"
ADVANCE_RECEIVED: Final = "6310"
OTHER_INCOME: Final = "9390"
CASH: Final = "5010"
TRANSIT: Final = "5710"
BANK: Final = "5110"
WRITEOFF_ACCOUNTS: Final = ("9430", "4910")

PaymentMethod = Literal["cash", "card", "uzqr", "click", "payme", "uzum", "bank"]
POS_METHODS: Final = frozenset({"cash", "card", "uzqr", "click", "payme", "uzum"})
CHECKOUT_METHODS: Final = frozenset({"click", "payme", "uzum"})
BUCKETS: Final = ("0-30", "31-60", "60+")


def debit_account(method: str) -> str:
    """13 §2.14 row 1: cash → 5010, cashless POS methods → 5710 (qaror #42), bank → 5110."""
    if method == "cash":
        return CASH
    if method == "bank":
        return BANK
    if method in POS_METHODS:
        return TRANSIT
    raise ValueError(f"unknown debt payment method {method!r}")


@dataclass(frozen=True, slots=True)
class PaymentPosting:
    entry_date: date
    branch_id: UUID
    method: str
    counterparty_id: UUID
    payment_id: UUID
    money_analytics: Mapping[
        str, Any
    ]  # 5010: cash_register_id/shift_id; 5710: payment_method (+rrn); 5110: {}
    extra: Mapping[str, Any]  # e.g. correction_of_period


def payment_ledger(p: PaymentPosting, result: AllocationResult) -> list[LedgerLine]:
    debit = debit_account(p.method)
    base = {
        **p.money_analytics,
        **p.extra,
        "counterparty_id": str(p.counterparty_id),
        "debt_payment_id": str(p.payment_id),
    }
    lines: list[LedgerLine] = []
    for a in result.allocations:
        credit = OTHER_INCOME if a.target_doc_type == "debt_writeoffs" else RECEIVABLE
        analytics = {**base, "target_doc_type": a.target_doc_type, "target_doc_id": a.target_doc_id}
        lines.append(LedgerLine(p.entry_date, p.branch_id, debit, credit, a.amount, analytics))
    if result.unallocated_amount > 0:
        lines.append(
            LedgerLine(
                p.entry_date, p.branch_id, debit, ADVANCE_RECEIVED, result.unallocated_amount, dict(base)
            )
        )
    return lines


def opening_ledger(
    entry_date: date,
    branch_id: UUID,
    direction: str,
    amount: Decimal,
    counterparty_id: UUID,
    opening_id: UUID,
) -> list[LedgerLine]:
    analytics = {"counterparty_id": str(counterparty_id), "debt_opening_id": str(opening_id)}
    if direction == "receivable":
        return [LedgerLine(entry_date, branch_id, RECEIVABLE, OPENING, amount, analytics)]
    if direction == "payable":
        return [LedgerLine(entry_date, branch_id, OPENING, PAYABLE, amount, analytics)]
    raise ValueError(f"unknown direction {direction!r}")


def writeoff_ledger(
    entry_date: date,
    branch_id: UUID,
    account_choice: str,
    counterparty_id: UUID,
    writeoff_id: UUID,
    targets: Sequence[tuple[str, UUID, Decimal]],
) -> list[LedgerLine]:
    if account_choice not in WRITEOFF_ACCOUNTS:
        raise ValueError(f"unknown write-off account {account_choice!r}")
    return [
        LedgerLine(
            entry_date,
            branch_id,
            account_choice,
            RECEIVABLE,
            amount,
            {
                "counterparty_id": str(counterparty_id),
                "debt_writeoff_id": str(writeoff_id),
                "target_doc_type": doc_type,
                "target_doc_id": str(doc_id),
            },
        )
        for doc_type, doc_id, amount in targets
    ]


def aging_bucket(days_overdue: int) -> str:
    """20 #21: 0–30 / 31–60 / 60+ days (``days_overdue = max(0, as_of − overdue_since)``)."""
    if days_overdue <= 30:
        return "0-30"
    if days_overdue <= 60:
        return "31-60"
    return "60+"


def doc_status(original: Decimal, open_amount: Decimal, written_off: Decimal = ZERO) -> str:
    """11 §8 debt row state: open → partially_paid → paid; closed by a write-off → written_off."""
    if open_amount <= 0:
        return "written_off" if written_off > 0 else "paid"
    if open_amount >= original:
        return "open"
    return "partially_paid"


def reminder_text(name: str, amount: str, due: date | None, shop: str) -> str:
    """US-M08-03/09 reminder draft — the deterministic template (AI-06 is Bosqich 6); a person confirms it
    before anything is sent to the customer."""
    when = f" ({due.strftime('%d.%m.%Y')} gacha to'lash va'da qilingan)" if due else ""
    return (
        f"Assalomu alaykum, {name}! {shop} do'konidan eslatma: qarzingiz {amount} so'm{when}. "
        "Iltimos, imkoniyat bo'yicha to'lab qo'ying. Rahmat!"
    )
