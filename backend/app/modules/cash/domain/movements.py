"""Cash movement rules and postings (18 §13.1, 20 #53, 13 §2.18, US-M16-01). Pure Python.

* ``reason ↔ direction``: ``collection``/``owner_withdrawal`` → only ``out``; ``deposit`` → only ``in``;
  ``other`` → both;
* ``account`` only for ``other`` — ``9430``/``9390``/``6310``/``4010``/``4730``; default ``out`` → ``9430``,
  ``in`` → ``9390``; ``6310``/``4010`` need ``counterparty_id``, ``4730`` needs ``employee_id``; ``4010`` is
  ``out`` only (money back from the customer's credit — the service caps it by that credit, ACC-02);
* ``owner_withdrawal`` — ``counterparty_id`` (a founder) is mandatory unless ``legal_form =
  sole_proprietor``; debit = ``tenants.settings.owner_withdrawal_account`` (default from ``legal_form``:
  ``4890``, YaTT ``8720``);
* ``comment`` mandatory for ``other``.

Ledger (one line): ``collection`` Dt 5710 / Kt 5010 (``payment_method='collection'``); ``deposit``
Dt 5010 / Kt 5110; ``owner_withdrawal`` Dt 4890|8720 / Kt 5010 (``counterparty_id``); ``other`` out
Dt account / Kt 5010, in Dt 5010 / Kt account. ``cash_moves``: ``+amount`` (in) / ``−amount`` (out),
``method='cash'``. Not a fiscal document (nothing goes to the OFD).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

Direction = Literal["in", "out"]
Reason = Literal["collection", "deposit", "owner_withdrawal", "other"]

OTHER_ACCOUNTS: Final[frozenset[str]] = frozenset({"9430", "9390", "6310", "4010", "4730"})
OWNER_ACCOUNTS: Final[frozenset[str]] = frozenset({"4890", "8720"})
DEFAULT_OTHER_ACCOUNT: Final[dict[str, str]] = {"out": "9430", "in": "9390"}
ALLOWED_DIRECTIONS: Final[dict[str, frozenset[str]]] = {
    "collection": frozenset({"out"}),
    "owner_withdrawal": frozenset({"out"}),
    "deposit": frozenset({"in"}),
    "other": frozenset({"in", "out"}),
}


@dataclass(frozen=True, slots=True)
class MovementInput:
    cash_register_id: UUID
    shift_id: UUID
    direction: str
    reason: str
    amount: Decimal
    account: str | None
    counterparty_id: UUID | None
    employee_id: UUID | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class Violation:
    field: str
    message_key: str


def validate(m: MovementInput, *, sole_proprietor: bool) -> list[Violation]:
    """Field rules independent of the database (references are checked by the service)."""
    out: list[Violation] = []
    if m.amount <= 0:
        out.append(Violation("amount", "validation.must_be_positive"))
    allowed = ALLOWED_DIRECTIONS.get(m.reason)
    if allowed is None:
        out.append(Violation("reason", "validation.enum"))
        return out
    if m.direction not in allowed:
        out.append(Violation("direction", "validation.cash_reason_direction"))
    if m.reason != "other":
        if m.account is not None:
            out.append(Violation("account", "validation.cash_account_reason_only"))
        if m.employee_id is not None:
            out.append(Violation("employee_id", "validation.not_allowed"))
        if m.reason == "owner_withdrawal":
            if m.counterparty_id is None and not sole_proprietor:
                out.append(Violation("counterparty_id", "validation.required"))
        elif m.counterparty_id is not None:
            out.append(Violation("counterparty_id", "validation.not_allowed"))
        return out
    account = m.account or DEFAULT_OTHER_ACCOUNT.get(m.direction, "9430")
    if account not in OTHER_ACCOUNTS:
        out.append(Violation("account", "validation.enum"))
    if not (m.comment or "").strip():
        out.append(Violation("comment", "validation.required"))
    if account == "4010" and m.direction == "in":
        # ACC-02 (13 §2.18, qaror #45/#67): a customer repays debt only through debt_payments (POS
        # debt_settlement receipt or bank) — never a cash movement on 4010
        out.append(Violation("account", "validation.cash_movement_debt_repayment"))
    if account in ("6310", "4010"):
        if m.counterparty_id is None:
            out.append(Violation("counterparty_id", "validation.required"))
    elif m.counterparty_id is not None:
        out.append(Violation("counterparty_id", "validation.not_allowed"))
    if account == "4730":
        if m.employee_id is None:
            out.append(Violation("employee_id", "validation.required"))
    elif m.employee_id is not None:
        out.append(Violation("employee_id", "validation.not_allowed"))
    return out


def effective_account(m: MovementInput) -> str | None:
    """The stored ``cash_movements.account`` (only ``other``; default by direction)."""
    if m.reason != "other":
        return None
    return m.account or DEFAULT_OTHER_ACCOUNT[m.direction]


def owner_account(legal_form: str, configured: str | None) -> str:
    if configured in OWNER_ACCOUNTS:
        assert configured is not None
        return configured
    return "8720" if legal_form == "sole_proprietor" else "4890"


@dataclass(frozen=True, slots=True)
class Entry:
    account_dt: str
    account_kt: str
    analytics: dict[str, Any]


def ledger_entry(m: MovementInput, *, owner_acct: str, branch_id: UUID) -> Entry:
    """The single 13 §2.18 line (amount = ``m.amount``)."""
    cash = {
        "cash_register_id": str(m.cash_register_id),
        "shift_id": str(m.shift_id),
        "branch_id": str(branch_id),
    }
    if m.reason == "collection":
        return Entry("5710", "5010", {**cash, "payment_method": "collection"})
    if m.reason == "deposit":
        return Entry("5010", "5110", cash)
    if m.reason == "owner_withdrawal":
        extra = {} if m.counterparty_id is None else {"counterparty_id": str(m.counterparty_id)}
        return Entry(owner_acct, "5010", {**cash, **extra})
    account = effective_account(m)
    assert account is not None
    extra = {}
    if m.counterparty_id is not None:
        extra["counterparty_id"] = str(m.counterparty_id)
    if m.employee_id is not None:
        extra["employee_id"] = str(m.employee_id)
    if m.direction == "out":
        return Entry(account, "5010", {**cash, **extra})
    return Entry("5010", account, {**cash, **extra})


def signed(direction: str, amount: Decimal) -> Decimal:
    """``cash_moves.amount`` — positive into the drawer, negative out of it."""
    return amount if direction == "in" else -amount
