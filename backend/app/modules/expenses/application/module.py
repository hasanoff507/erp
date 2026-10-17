"""REST services of the expenses module published on ``app.state.expenses``."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.expenses.application.categories import CategoryService
from app.modules.expenses.application.expenses import ExpenseService
from app.modules.expenses.application.recurring import RecurringService


@dataclass(frozen=True, slots=True)
class ExpensesModule:
    expenses: ExpenseService
    categories: CategoryService
    recurring: RecurringService
