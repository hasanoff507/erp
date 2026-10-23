"""Branch figures of a day/range — the shared building block of ``GET /reports/dashboard`` (20 #17) and the
Telegram daily report (21 §11, US-M18-02; contract ``.claude-scratch/b4/contracts/daily-summary.md``).

:meth:`SummaryService.for_day` is the public entry point for b4-telegram (``reports.wiring.daily_summary()``);
:meth:`SummaryService.for_range` feeds the dashboard. Both only read, inside the caller's tenant transaction.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.application.ports import Branches, ReportsRepository, branch_tuple
from app.modules.reports.domain.daily_summary import (
    ZERO,
    BranchDaySummary,
    CashRegisterCash,
    DailySummary,
    DebtorDue,
    branch_summary,
    m2,
    total_of,
)
from app.modules.reports.domain.debts import DebtDoc, OpenDebt, due_on_total, overdue_total, reconcile
from app.modules.reports.domain.periods import DateRange, day_bounds

DEBTORS_LIMIT = 20


class SummaryService:
    def __init__(self, repo: ReportsRepository) -> None:
        self._repo = repo

    async def for_day(
        self, s: AsyncSession, tenant_id: UUID, day: date, branch_ids: Sequence[UUID] | None
    ) -> DailySummary:
        """The evening report of ``day`` (Asia/Tashkent): branch rows + total, drawer cash, tomorrow's
        debtors,
        the unsynced-devices flag (QT-M12-04)."""
        return await self.for_range(s, tenant_id, DateRange(day, day), branch_tuple(branch_ids))

    async def for_range(
        self, s: AsyncSession, tenant_id: UUID, rng: DateRange, branch_ids: Branches
    ) -> DailySummary:
        branches = await self._repo.branches(s, branch_ids)
        scope: Branches = tuple(b.id for b in branches) if branch_ids is not None else None
        sales = {UUID(a.group_key): a for a in await self._repo.sales(s, rng, scope, "branch")}
        ledger = {t.branch_id: t for t in await self._repo.ledger_totals(s, rng, scope)}
        expenses: dict[UUID | None, Decimal] = defaultdict(lambda: ZERO)
        for line in await self._repo.expense_lines(s, rng, scope):
            expenses[line.branch_id] += line.amount
        _, end = day_bounds(rng)
        registers = await self._repo.register_cash(s, scope, end)
        cash: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
        for reg in registers:
            cash[reg.branch_id] += reg.cash_on_hand
        new_debts = await self._repo.new_debts(s, rng, scope)
        paid = await self._repo.debt_payments(s, rng, scope)
        open_docs, debtors = await self.open_debts(s, scope, rng.date_to)
        overdue: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
        for doc in open_docs:
            if doc.effective_due < rng.date_to:
                overdue[doc.branch_id] += doc.open_amount
        low = await self._repo.low_stock(s, scope)
        unsynced = await self._repo.unsynced_devices(s, scope)

        rows: list[BranchDaySummary] = []
        for b in branches:
            sale = sales.get(b.id)
            led = ledger.get(b.id)
            rows.append(
                branch_summary(
                    b.id,
                    b.name,
                    gross_sales=sale.gross_sales if sale else ZERO,
                    receipts_count=sale.receipts_count if sale else 0,
                    returns_total=sale.returns_total if sale else ZERO,
                    revenue=(led.revenue_9020 - led.returns_9040 - led.discounts_9050) if led else ZERO,
                    cogs=led.cogs_9120 if led else ZERO,
                    expenses=expenses.get(b.id, ZERO),
                    other_income=led.other_income_9390 if led else ZERO,
                    cash_on_hand=cash.get(b.id, ZERO),
                    new_debts=new_debts.get(b.id, ZERO),
                    debt_payments=paid.get(b.id, ZERO),
                    overdue_debt_total=overdue.get(b.id, ZERO),
                    low_stock_count=len(low.get(b.id, set())),
                )
            )
        low_products: set[UUID] = set()
        for products in low.values():
            low_products |= products
        parts = list(rows)
        unassigned = ledger.get(None)
        if scope is None and (unassigned is not None or expenses.get(None)):
            # ledger lines without a branch (tenant-level postings) count in the consolidated total only
            parts.append(
                branch_summary(
                    tenant_id, "", gross_sales=ZERO, receipts_count=0, returns_total=ZERO,
                    revenue=(unassigned.revenue_9020 - unassigned.returns_9040 - unassigned.discounts_9050)
                    if unassigned else ZERO,
                    cogs=unassigned.cogs_9120 if unassigned else ZERO, expenses=expenses.get(None, ZERO),
                    other_income=unassigned.other_income_9390 if unassigned else ZERO, cash_on_hand=ZERO,
                    new_debts=ZERO, debt_payments=ZERO, overdue_debt_total=ZERO, low_stock_count=0,
                )
            )  # fmt: skip
        total = total_of(parts, tenant_id, len(low_products))
        names = {b.id: b.name for b in branches}
        return DailySummary(
            tenant_id=tenant_id,
            day=rng.date_to,
            branches=tuple(rows),
            total=total,
            cash_registers=tuple(
                CashRegisterCash(r.cash_register_id, r.name, r.branch_id, m2(r.cash_on_hand))
                for r in sorted(
                    registers, key=lambda r: (names.get(r.branch_id, ""), r.name, str(r.cash_register_id))
                )
            ),
            debtors_due_tomorrow=tuple(debtors),
            unsynced_devices=unsynced.count > 0,
            unsynced_device_count=unsynced.count,
        )

    async def open_debts(
        self, s: AsyncSession, scope: Branches, as_of: date
    ) -> tuple[list[OpenDebt], list[DebtorDue]]:
        """Open receivable documents of the scope's branches and the customers due on ``as_of + 1``."""
        counterparties, docs = await self._repo.receivables(s)
        by_cp: dict[UUID, list[DebtDoc]] = defaultdict(list)
        for doc in docs:
            by_cp[doc.counterparty_id].append(doc)
        tomorrow = as_of + timedelta(days=1)
        allowed = None if scope is None else set(scope)
        out: list[OpenDebt] = []
        due: list[DebtorDue] = []
        for cp in counterparties:
            opened = reconcile(by_cp.get(cp.id, []), cp.balance)
            if allowed is not None:
                opened = [d for d in opened if d.branch_id in allowed]
            out.extend(opened)
            amount = due_on_total(opened, tomorrow)
            if amount > 0:
                due.append(DebtorDue(cp.id, cp.name, cp.phone, m2(amount), tomorrow))
        due.sort(key=lambda d: (-d.amount_due, d.name, str(d.counterparty_id)))
        return out, due[:DEBTORS_LIMIT]

    @staticmethod
    def overdue(open_docs: Sequence[OpenDebt], as_of: date) -> tuple[int, Decimal]:
        """(customers with an overdue document, overdue amount) on ``as_of``."""
        late = [d for d in open_docs if d.effective_due < as_of]
        return len({d.counterparty_id for d in late}), m2(overdue_total(late, as_of))
