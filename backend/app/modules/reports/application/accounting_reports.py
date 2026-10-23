"""M11 accounting reports — ``GET /reports/trial-balance`` (20 #11), ``GET /reports/balance-sheet``
(20 #13) and the document-date stock report ``GET /reports/stock-as-of`` (20 #20a, ACC-09). Read only.

Branch scope (15 §2.4): an explicit ``branch_id`` must be one of the user's branches
(``403 BRANCH_SCOPE_DENIED``); without it a branch-restricted user gets their branches, an unrestricted
user the consolidation (13 §5.4 — 2970 is an inter-branch figure in a single branch's statement).

* Trial balance of a month: per account ``opening_balance`` (before the month), ``debit_turnover``,
  ``credit_turnover``, ``closing_balance`` — balances debit-positive (``Σ Dt − Σ Kt``; a liability is
  negative); 4410/6410 rows also carry ``by_tax_type[]`` (``analytics.tax_type``) — BO-07 «6410
  qoldig'i» reads the 6410 row. ``totals`` — Σ debit = Σ credit.
* Balance sheet on ``as_of``: :func:`app.modules.reports.domain.statements.balance_sheet`.
* Stock by document date (ACC-09): back-office documents move stock at ``posted_at`` but post the ledger
  at ``doc_date``; this report counts each move on its document's ``doc_date`` and compares the value
  with GL 2910/2920 on the same date (``ledger_value``, ``difference`` per inventory account).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import qty_str
from app.core.permissions import BranchScope
from app.modules.accounting.domain.calendar import business_today
from app.modules.accounting.domain.closing import parse_period, period_end
from app.modules.reports.domain.statements import ZERO, Turnover, account_name, account_type, balance_sheet

TAX_ACCOUNTS = ("4410", "6410")


@dataclass(frozen=True, slots=True)
class StockAsOfRow:
    warehouse_id: UUID
    branch_id: UUID
    inventory_account: str
    product_id: UUID
    name: str
    qty: Decimal
    value: Decimal


class AccountingReportsRepository(Protocol):
    async def turnovers(
        self, s: AsyncSession, start: date, end: date, branch_ids: tuple[UUID, ...] | None
    ) -> list[tuple[str, str | None, Decimal, Decimal, Decimal]]: ...
    async def balances(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> dict[str, Decimal]: ...
    async def stock_as_of(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None, warehouse_id: UUID | None
    ) -> list[StockAsOfRow]: ...
    async def stock_ledger(
        self, s: AsyncSession, as_of: date, branch_ids: tuple[UUID, ...] | None
    ) -> dict[str, Decimal]: ...


def _m(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _branches(scope: BranchScope, branch_id: UUID | None) -> tuple[UUID, ...] | None:
    if branch_id is not None:
        if not scope.unrestricted and branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return (branch_id,)
    return None if scope.unrestricted else scope.allowed


def _turnover_json(account: str, t: Turnover) -> dict[str, Any]:
    return {
        "opening_balance": _m(t.opening),
        "debit_turnover": _m(t.debit),
        "credit_turnover": _m(t.credit),
        "closing_balance": _m(t.closing),
    }


class AccountingReportsService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], repo: AccountingReportsRepository
    ) -> None:
        self._sf = session_factory
        self._repo = repo

    async def _read(self, s: AsyncSession) -> None:
        await s.execute(text("SET TRANSACTION READ ONLY"))

    # --- 20 #11 ---------------------------------------------------------------------------------------------
    async def trial_balance(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        period: str,
        branch_id: UUID | None,
        account: str | None,
    ) -> dict[str, Any]:
        start = parse_period(period)
        if start is None:
            raise _invalid("period", "validation.period_format")
        end = period_end(start)
        branches = _branches(scope, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            raw = await self._repo.turnovers(s, start, end, branches)
        per_account: dict[str, Turnover] = defaultdict(Turnover)
        per_tax: dict[str, dict[str, Turnover]] = defaultdict(lambda: defaultdict(Turnover))
        for code, tax_type, opening, debit, credit in raw:
            if account is not None and code != account:
                continue
            t = Turnover(opening, debit, credit)
            per_account[code] += t
            if code in TAX_ACCOUNTS:
                per_tax[code][tax_type or "other"] += t
        rows = []
        total_dt = total_kt = ZERO
        for code in sorted(per_account):
            t = per_account[code]
            if t.empty:
                continue
            total_dt += t.debit
            total_kt += t.credit
            row: dict[str, Any] = {
                "account": code,
                "name": account_name(code),
                "type": account_type(code),
                **_turnover_json(code, t),
                "by_tax_type": None,
            }
            if code in TAX_ACCOUNTS:
                row["by_tax_type"] = [
                    {"tax_type": k, **_turnover_json(code, v)}
                    for k, v in sorted(per_tax[code].items())
                    if not v.empty
                ]
            rows.append(row)
        return {
            "period": f"{start.year:04d}-{start.month:02d}",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "branch_id": None if branch_id is None else str(branch_id),
            "rows": rows,
            "totals": {"debit_turnover": _m(total_dt), "credit_turnover": _m(total_kt)},
        }

    # --- 20 #13 ---------------------------------------------------------------------------------------------
    async def balance_sheet(
        self, actor: Principal, scope: BranchScope, *, as_of: date | None, branch_id: UUID | None
    ) -> dict[str, Any]:
        day = as_of or business_today()
        branches = _branches(scope, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            balances = await self._repo.balances(s, day, branches)
        sheet = balance_sheet(balances)

        def lines(items: Sequence[tuple[str, Decimal]]) -> list[dict[str, Any]]:
            return [{"account": c, "name": account_name(c), "amount": _m(a)} for c, a in items]

        return {
            "as_of": day.isoformat(),
            "branch_id": None if branch_id is None else str(branch_id),
            "assets": lines(sheet.assets),
            "liabilities": lines(sheet.liabilities),
            "equity": lines(sheet.equity),
            "total_assets": _m(sheet.total_assets),
            "total_liabilities_and_equity": _m(sheet.total_liabilities_and_equity),
            "opening_balance_unresolved": sheet.opening_0000 != 0,
            "opening_0000_balance": _m(sheet.opening_0000),
            "warnings": sheet.warnings,
        }

    # --- ACC-09 ---------------------------------------------------------------------------------------------
    async def stock_as_of(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        as_of: date,
        branch_id: UUID | None,
        warehouse_id: UUID | None,
    ) -> dict[str, Any]:
        if as_of > business_today():
            raise _invalid("as_of", "validation.date_in_future")
        branches = _branches(scope, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            items = await self._repo.stock_as_of(s, as_of, branches, warehouse_id)
            ledger = await self._repo.stock_ledger(s, as_of, branches)
        by_account: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for r in items:
            by_account[r.inventory_account] += r.value
        accounts = sorted(set(by_account) | set(ledger))
        return {
            "as_of": as_of.isoformat(),
            "basis": "doc_date",
            "branch_id": None if branch_id is None else str(branch_id),
            "warehouse_id": None if warehouse_id is None else str(warehouse_id),
            "items": [
                {
                    "product_id": str(r.product_id),
                    "name": r.name,
                    "warehouse_id": str(r.warehouse_id),
                    "branch_id": str(r.branch_id),
                    "qty": qty_str(r.qty),
                    "value": _m(r.value),
                }
                for r in items
            ],
            "accounts": [
                {
                    "account": a,
                    "stock_value": _m(by_account.get(a, ZERO)),
                    "ledger_value": None if warehouse_id is not None else _m(ledger.get(a, ZERO)),
                    "difference": None
                    if warehouse_id is not None
                    else _m(ledger.get(a, ZERO) - by_account.get(a, ZERO)),
                }
                for a in accounts
            ],
        }
