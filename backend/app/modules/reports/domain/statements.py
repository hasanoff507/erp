"""M11 statements — trial balance and balance sheet (20 #11, #13; 13 §1, §5.1, §5.4, §5.5). Pure Python.

Sign convention: a *balance* is ``Σ Dt − Σ Kt`` of the account ("debit-positive"); the trial balance shows
it as is (a liability is negative), the balance sheet shows every line as an amount on its own side.

Balance sheet (MEF №181 1-ilova shape, MVP chart of 13 §1):

* **assets** — active (``A``) and contra-active (``KA``, 4910 — a negative line): ``amount = balance``;
* **liabilities** — passive 6xxx accounts: ``amount = −balance``;
* **equity** — passive 8xxx accounts (``−balance``) + ``9910`` "current result" = ``−Σ balance`` of every
  transit 9xxx account (monthly closing does not zero them, 13 §5.1) + ``0000`` while it is not zero
  (unresolved opening balances, 13 §5.5 — the statement still balances,
  ``warnings = ["opening_0000_nonzero"]``).

``Σ assets = Σ liabilities + Σ equity`` holds because every ledger line is double-entry (``Σ balance = 0``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from app.modules.accounting.domain.chart_of_accounts import ACCOUNTS_BY_CODE, AccountType

ZERO: Final = Decimal("0.00")
RESULT_ACCOUNT: Final = "9910"
OPENING_ACCOUNT: Final = "0000"


@dataclass(frozen=True, slots=True)
class Turnover:
    opening: Decimal = ZERO
    debit: Decimal = ZERO
    credit: Decimal = ZERO

    @property
    def closing(self) -> Decimal:
        return self.opening + self.debit - self.credit

    def __add__(self, other: Turnover) -> Turnover:
        return Turnover(self.opening + other.opening, self.debit + other.debit, self.credit + other.credit)

    @property
    def empty(self) -> bool:
        return self.opening == 0 and self.debit == 0 and self.credit == 0


def account_name(code: str) -> str:
    account = ACCOUNTS_BY_CODE.get(code)
    return account.name if account is not None else code


def account_type(code: str) -> str:
    account = ACCOUNTS_BY_CODE.get(code)
    return account.type.value if account is not None else "?"


@dataclass(slots=True)
class BalanceSheet:
    assets: list[tuple[str, Decimal]] = field(default_factory=list)
    liabilities: list[tuple[str, Decimal]] = field(default_factory=list)
    equity: list[tuple[str, Decimal]] = field(default_factory=list)
    opening_0000: Decimal = ZERO

    @property
    def total_assets(self) -> Decimal:
        return sum((a for _, a in self.assets), ZERO)

    @property
    def total_liabilities_and_equity(self) -> Decimal:
        return sum((a for _, a in self.liabilities), ZERO) + sum((a for _, a in self.equity), ZERO)

    @property
    def warnings(self) -> list[str]:
        return ["opening_0000_nonzero"] if self.opening_0000 != 0 else []


def balance_sheet(balances: Mapping[str, Decimal]) -> BalanceSheet:
    """``balances`` = account → ``Σ Dt − Σ Kt`` up to the date."""
    sheet = BalanceSheet()
    result = ZERO
    for code in sorted(balances):
        bal = balances[code]
        account = ACCOUNTS_BY_CODE.get(code)
        kind = account.type if account is not None else None
        if code == OPENING_ACCOUNT:
            sheet.opening_0000 = bal
            continue
        if kind == AccountType.TRANSIT or code.startswith("9"):
            result -= bal
            continue
        if bal == 0:
            continue
        if kind in (AccountType.ACTIVE, AccountType.CONTRA_ACTIVE):
            sheet.assets.append((code, bal))
        elif code.startswith("8"):
            sheet.equity.append((code, -bal))
        else:
            sheet.liabilities.append((code, -bal))
    if result != 0:
        sheet.equity.append((RESULT_ACCOUNT, result))
    if sheet.opening_0000 != 0:
        sheet.equity.append((OPENING_ACCOUNT, -sheet.opening_0000))
    return sheet
