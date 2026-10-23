import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { LoadStatus } from "#/shared/lib/effect.ts";

import type { Category, Expense, ExpenseFilters, ExpensesTab, Notice, Rule } from "../types/index.ts";

export const $today = createStore("1970-01-01");
/** Form default branch (topbar / the user's only branch). */
export const $defaultBranchId = createStore<string | null>(null, { skipVoid: false });
export const $tab = createStore<ExpensesTab>("expenses");

export const $filters = createStore<ExpenseFilters>({
  from: "1970-01-01",
  to: "1970-01-01",
  categoryId: null,
  source: null,
  status: null,
});
export const $expenses = createStore<Expense[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $totals = createStore<{ posted: string; draft: string }>({ posted: "0.00", draft: "0.00" });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });

export const $categories = createStore<Category[]>([]);
export const $categoriesStatus = createStore<LoadStatus>("idle");

export const $rules = createStore<Rule[]>([]);
export const $rulesStatus = createStore<LoadStatus>("idle");
export const $snoozed = createStore<string[]>([]);

export const $notice = createStore<Notice | null>(null, { skipVoid: false });
/** Post / confirm / rule-toggle failures shown above the list. */
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });
