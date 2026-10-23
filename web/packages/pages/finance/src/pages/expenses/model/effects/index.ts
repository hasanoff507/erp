/** BO-17 effects — generated `api.expenses.*` (20 #41–#51; tag `expenses`). */
import { api } from "@shared/api";

import { apiFx } from "#/shared/lib/effect.ts";

import { toListParams } from "../lib/index.ts";
import {
  RULES_PAGE_SIZE,
  type Category,
  type CategoryCreate,
  type CategoryUpdate,
  type Expense,
  type ExpensePage,
  type ExpensePosted,
  type ListRequest,
  type Rule,
  type RuleConfirmed,
  type RulePage,
  type RuleUpdate,
  type SaveRequest,
} from "../types/index.ts";

export const listExpensesFx = apiFx<ListRequest, ExpensePage>((req) =>
  api.expenses.listExpenses(toListParams(req)),
);
export const listCategoriesFx = apiFx<void, Category[]>(async () => {
  const { items } = await api.expenses.listCategories({ include_archived: true });
  return items;
});
export const listRulesFx = apiFx<void, RulePage>(() =>
  api.expenses.listRecurring({ page: 1, size: RULES_PAGE_SIZE }),
);

/** «Qoralama» / «Saqlash va o'tkazish»: the draft (20 #42), then the recurring rule when asked (20 #49). */
export const createExpenseFx = apiFx<SaveRequest, { expense: Expense; rule: Rule | null }>(async (req) => {
  const expense = await api.expenses.createExpense(req.body);
  const rule = req.rule ? await api.expenses.createRecurring(req.rule) : null;
  return { expense, rule };
});
/** 20 #43: `200 posted` or `202 {status:"draft", approval_request_id}` (`expense_over_limit`, BO-16). */
export const postExpenseFx = apiFx<string, ExpensePosted>((id) => api.expenses.postExpense(id));
export const cancelExpenseFx = apiFx<{ id: string; reason: string }, unknown>(({ id, reason }) =>
  api.expenses.cancelExpense(id, { reason }),
);
/** 20 #51 one-click confirm of a due reminder: `201 posted` or `202` approval. */
export const confirmRuleFx = apiFx<string, RuleConfirmed>((id) => api.expenses.confirmRecurring(id, {}));
export const updateRuleFx = apiFx<{ id: string; body: RuleUpdate }, Rule>(({ id, body }) =>
  api.expenses.updateRecurring(id, body),
);
export const createCategoryFx = apiFx<CategoryCreate, Category>((body) => api.expenses.createCategory(body));
export const updateCategoryFx = apiFx<{ id: string; body: CategoryUpdate }, Category>(({ id, body }) =>
  api.expenses.updateCategory(id, body),
);
