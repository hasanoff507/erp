"""Manual ledger adjustments — ``ledger_adjustments`` (13 §2.23, §2.14, §2.15a, §5.5; 20 #10). Pure Python.

One-step document: ``POST`` writes ONE ledger line ``Dt account_dt / Kt account_kt = amount`` dated
``doc_date`` and returns ``status='posted'``; ``cancel`` = storno (13 §5.2). Rules checked here (the
stateful ones — closed period, balances — in the application service):

* both accounts are in the chart and in use (13 §1), ``account_dt ≠ account_kt``;
* register-managed inventory accounts (2910/2920/2970) are refused — their value lives in
  ``stock_balances`` and only stock documents move it (a manual line would break the ACC-09 check);
* ``amount > 0`` (tiyin); ``comment`` is mandatory;
* ``analytics`` keys — only the 13 §1 dimensions (string values); ``correction_of_period`` is a field;
* 4010 / 6010 / 6310 need ``analytics.counterparty_id`` — 4010/6010 also move ``debt_moves``
  (13 §2.14), 6310 is the customer advance account (balance checked per counterparty);
* an opening-balance line (``0000`` on either side, 13 §5.5) is dated ``go_live_date − 1``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Final, Literal
from uuid import UUID

from app.core.money import money, to_decimal
from app.modules.accounting.domain.chart_of_accounts import ACCOUNTS_BY_CODE

OPENING_ACCOUNT: Final = "0000"
REGISTER_MANAGED: Final = frozenset({"2910", "2920", "2970"})
COUNTERPARTY_ACCOUNTS: Final = frozenset({"4010", "6010", "6310"})
ANALYTICS_KEYS: Final = frozenset(
    {
        "product_id", "counterparty_id", "cash_register_id", "payment_method", "warehouse_id",
        "expense_category_id", "tax_type", "vat_credit", "employee_id", "doc_id",
    }
)  # fmt: skip
UUID_KEYS: Final = frozenset(
    {
        "product_id", "counterparty_id", "cash_register_id", "warehouse_id", "expense_category_id",
        "employee_id", "doc_id",
    }
)  # fmt: skip
MAX_VALUE_LEN: Final = 100

Side = Literal["dt", "kt"]


@dataclass(frozen=True, slots=True)
class Problem:
    """A validation failure: ``field`` + ``message_key`` (+ params) → ``422 VALIDATION_ERROR``."""

    field: str
    key: str
    params: Mapping[str, Any] | None = None


class AdjustmentInvalidError(ValueError):
    def __init__(self, problems: list[Problem]) -> None:
        super().__init__(", ".join(f"{p.field}:{p.key}" for p in problems))
        self.problems = problems


@dataclass(frozen=True, slots=True)
class AdjustmentDraft:
    branch_id: UUID
    doc_date: date
    account_dt: str
    account_kt: str
    amount: Decimal
    comment: str
    analytics: dict[str, str]
    correction_of_period: date | None


def is_opening(account_dt: str, account_kt: str) -> bool:
    return OPENING_ACCOUNT in (account_dt, account_kt)


def opening_date(go_live_date: date) -> date:
    """13 §2.13/§2.21/§5.5: opening balances are dated the day before go-live."""
    return go_live_date - timedelta(days=1)


def _account(code: str, field: str, problems: list[Problem]) -> None:
    account = ACCOUNTS_BY_CODE.get(code)
    if account is None or not account.in_use:
        problems.append(Problem(field, "validation.account_not_allowed", {"account": code}))
    elif code in REGISTER_MANAGED:
        problems.append(Problem(field, "validation.account_register_managed", {"account": code}))


def _analytics(raw: Mapping[str, Any] | None, problems: list[Problem]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (raw or {}).items():
        field = f"analytics.{key}"
        if key not in ANALYTICS_KEYS:
            problems.append(Problem(field, "validation.not_allowed"))
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_VALUE_LEN:
            problems.append(Problem(field, "validation.string"))
            continue
        if key in UUID_KEYS:
            try:
                value = str(UUID(value))
            except ValueError:
                problems.append(Problem(field, "validation.uuid"))
                continue
        out[key] = value.strip()
    return out


def checked_adjustment(
    *,
    branch_id: UUID,
    doc_date: date,
    account_dt: str,
    account_kt: str,
    amount: Any,
    comment: str | None,
    analytics: Mapping[str, Any] | None,
    correction_of_period: date | None,
    today: date,
    go_live_date: date | None,
) -> AdjustmentDraft:
    """Stateless checks of a ``POST /ledger-adjustments`` body (raises :class:`AdjustmentInvalidError`)."""
    problems: list[Problem] = []
    _account(account_dt, "account_dt", problems)
    _account(account_kt, "account_kt", problems)
    if account_dt == account_kt:
        problems.append(Problem("account_kt", "validation.same_account"))
    value = money(to_decimal(amount))
    if value <= 0:
        problems.append(Problem("amount", "validation.positive"))
    text = (comment or "").strip()
    if not text:
        problems.append(Problem("comment", "validation.required"))
    if doc_date > today:
        problems.append(Problem("doc_date", "validation.doc_date_in_future"))
    data = _analytics(analytics, problems)
    needs_cp = COUNTERPARTY_ACCOUNTS & {account_dt, account_kt} and "counterparty_id" not in data
    if needs_cp and not any(p.field == "analytics.counterparty_id" for p in problems):
        problems.append(Problem("analytics.counterparty_id", "validation.required"))
    if is_opening(account_dt, account_kt):
        if go_live_date is None:
            problems.append(Problem("doc_date", "validation.go_live_date_missing"))
        elif doc_date != opening_date(go_live_date):
            expected = opening_date(go_live_date).isoformat()
            problems.append(Problem("doc_date", "validation.opening_entry_date", {"expected": expected}))
        if correction_of_period is not None:
            problems.append(Problem("correction_of_period", "validation.must_be_null"))
    if problems:
        raise AdjustmentInvalidError(problems)
    return AdjustmentDraft(
        branch_id=branch_id,
        doc_date=doc_date,
        account_dt=account_dt,
        account_kt=account_kt,
        amount=value,
        comment=text,
        analytics=data,
        correction_of_period=correction_of_period,
    )


@dataclass(frozen=True, slots=True)
class DebtEffect:
    """``debt_moves`` a ledger line implies (13 §2.14): 4010 → receivable, 6010 → payable."""

    direction: Literal["receivable", "payable"]
    amount: Decimal  # signed: + increases the debt


def debt_effects(account_dt: str, account_kt: str, amount: Decimal) -> list[DebtEffect]:
    out: list[DebtEffect] = []
    if account_dt == "4010":
        out.append(DebtEffect("receivable", amount))
    if account_kt == "4010":
        out.append(DebtEffect("receivable", -amount))
    if account_kt == "6010":
        out.append(DebtEffect("payable", amount))
    if account_dt == "6010":
        out.append(DebtEffect("payable", -amount))
    return out


@dataclass(frozen=True, slots=True)
class BalanceNeed:
    """A balance a line consumes: ``amount`` must be ≤ ``available`` (13 §2.14 offset, §2.15a, §2.16)."""

    what: Literal["receivable", "payable", "advance_6310"]
    amount: Decimal


def balance_needs(account_dt: str, account_kt: str, amount: Decimal) -> list[BalanceNeed]:
    """Conservative guards: a manual line never drives a counterparty's receivable (Kt 4010), payable
    (Dt 6010) or customer advance (Dt 6310) below zero — a negative 4010 is an advance and belongs on 6310,
    a negative 6010 without 4310 breaks 13 §2.16, a debit 6310 balance does not exist."""
    out: list[BalanceNeed] = []
    if account_kt == "4010":
        out.append(BalanceNeed("receivable", amount))
    if account_dt == "6010":
        out.append(BalanceNeed("payable", amount))
    if account_dt == "6310":
        out.append(BalanceNeed("advance_6310", amount))
    return out
