/** BO-17 wiring — sample() only (24 §2). */
import { combine, merge, sample } from "effector";

import {
  cancelExpenseFx,
  confirmRuleFx,
  createCategoryFx,
  createExpenseFx,
  listCategoriesFx,
  listExpensesFx,
  listRulesFx,
  postExpenseFx,
  updateCategoryFx,
  updateRuleFx,
} from "../effects/index.ts";
import {
  actionErrorDismissed,
  categoriesReloadRequested,
  filtersChanged,
  moreRequested,
  noticeDismissed,
  noticeShown,
  pageMounted,
  reloadRequested,
  ruleSnoozed,
  rulesReloadRequested,
  tabChanged,
} from "../events/index.ts";
import { activeCategories, categoryShares, dueRules, patchFilters, visibleRows } from "../lib/index.ts";
import {
  $actionError,
  $categories,
  $categoriesStatus,
  $cursor,
  $defaultBranchId,
  $error,
  $expenses,
  $filters,
  $notice,
  $rules,
  $rulesStatus,
  $snoozed,
  $status,
  $tab,
  $today,
  $totals,
} from "../stores/index.ts";
import type { ExpenseFilters, ListRequest, Notice } from "../types/index.ts";

export const $rows = combine($expenses, $filters, (list, f) => visibleRows(list, f.status));
export const $shares = $expenses.map(categoryShares);
export const $activeCategories = $categories.map(activeCategories);
export const $dueRules = combine($rules, $snoozed, dueRules);
export const $activeRulesCount = $rules.map((rules) => rules.filter((r) => r.is_active).length);
export const $hasMore = $cursor.map((c) => c !== null);
export const $moreLoading = combine(listExpensesFx.pending, $status, (p, s) => p && s !== "loading");
export const $saving = combine(createExpenseFx.pending, postExpenseFx.pending, (a, b) => a || b);

const sameFilters = (a: ExpenseFilters, b: ExpenseFilters) =>
  a.from === b.from &&
  a.to === b.to &&
  a.categoryId === b.categoryId &&
  a.source === b.source &&
  a.status === b.status;

// --- mount ---------------------------------------------------------------------------------------------
$today.on(pageMounted, (_, { today }) => today);
$defaultBranchId.on(pageMounted, (_, { branchId }) => branchId);
$filters.on(pageMounted, (f, { today }) => ({ ...f, from: `${today.slice(0, 7)}-01`, to: today }));
$snoozed.reset(pageMounted);
$notice.reset(pageMounted);
$tab.on(tabChanged, (_, tab) => tab);

// --- list ----------------------------------------------------------------------------------------------
$filters.on(filtersChanged, patchFilters);
sample({
  clock: [pageMounted, filtersChanged, reloadRequested],
  source: $filters,
  fn: (filters): ListRequest => ({ filters, cursor: null }),
  target: listExpensesFx,
});
sample({
  clock: moreRequested,
  source: { filters: $filters, cursor: $cursor, pending: listExpensesFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filters, cursor }): ListRequest => ({ filters, cursor }),
  target: listExpensesFx,
});
// An answer for older filters is dropped.
const listed = sample({
  clock: listExpensesFx.done,
  source: $filters,
  filter: (filters, { params }) => sameFilters(filters, params.filters),
  fn: (_, payload) => payload,
});
$expenses.on(listed, (list, { params, result }) =>
  params.cursor === null ? result.items : [...list, ...result.items],
);
$cursor.on(listed, (_, { result }) => result.next_cursor);
$totals.on(listed, (_, { result }) => result.totals);
$status
  .on(listExpensesFx, (s, p) => (p.cursor === null ? "loading" : s))
  .on(listed, () => "idle")
  .on(listExpensesFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listExpensesFx.failData, (_, e) => e).reset(listExpensesFx);

// --- categories / rules --------------------------------------------------------------------------------
sample({
  clock: [pageMounted, categoriesReloadRequested, createCategoryFx.done, updateCategoryFx.done],
  fn: () => undefined,
  target: listCategoriesFx,
});
$categories.on(listCategoriesFx.doneData, (_, items) => items);
$categoriesStatus
  .on(listCategoriesFx, () => "loading")
  .on(listCategoriesFx.done, () => "idle")
  .on(listCategoriesFx.fail, () => "error");

const ruleCreated = sample({ clock: createExpenseFx.doneData, filter: ({ rule }) => rule !== null });
sample({
  clock: [pageMounted, rulesReloadRequested, confirmRuleFx.finally, updateRuleFx.done, ruleCreated],
  fn: () => undefined,
  target: listRulesFx,
});
$rules.on(listRulesFx.doneData, (_, page) => page.items);
$rulesStatus
  .on(listRulesFx, () => "loading")
  .on(listRulesFx.done, () => "idle")
  .on(listRulesFx.fail, () => "error");
$snoozed.on(ruleSnoozed, (list, id) => (list.includes(id) ? list : [...list, id]));

// --- writes --------------------------------------------------------------------------------------------
sample({
  clock: createExpenseFx.done,
  filter: ({ params }) => params.post,
  fn: ({ result }) => result.expense.id,
  target: postExpenseFx,
});
const savedAsDraft = sample({ clock: createExpenseFx.done, filter: ({ params }) => !params.post });

sample({
  clock: [
    postExpenseFx.doneData.map((r): Notice =>
      r.status === "posted" ? { kind: "posted", number: r.number ?? null } : { kind: "approval" },
    ),
    confirmRuleFx.doneData.map((r): Notice =>
      r.status === "posted" ? { kind: "posted", number: null } : { kind: "approval" },
    ),
    savedAsDraft.map((): Notice => ({ kind: "draft" })),
    cancelExpenseFx.done.map((): Notice => ({ kind: "cancelled" })),
  ],
  target: noticeShown,
});
$notice.on(noticeShown, (_, n) => n).reset(noticeDismissed);

sample({
  clock: merge([createExpenseFx.done, postExpenseFx.finally, cancelExpenseFx.done, confirmRuleFx.done]),
  fn: () => undefined,
  target: reloadRequested,
});

$actionError
  .on(merge([postExpenseFx.failData, confirmRuleFx.failData, updateRuleFx.failData]), (_, e) => e)
  .reset(actionErrorDismissed, postExpenseFx, confirmRuleFx, updateRuleFx, pageMounted);
