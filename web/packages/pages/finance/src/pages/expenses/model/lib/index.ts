import { addMoney, compareMoney, money, toDecimal } from "@shared/lib/money";
import type { ListExpensesParams } from "@shared/models";

import { isPositiveMoney, typedMoney, ZERO } from "#/shared/lib/money.ts";

import {
  CANCEL_MAX,
  CANCEL_MIN,
  COMMENT_MAX,
  EXPENSES_TABS,
  PAGE_SIZE,
  PERIODS,
  SOURCES,
  STATUS_FILTERS,
  TAX_TYPES,
  type Category,
  type CategoryShare,
  type Expense,
  type ExpenseFilters,
  type ExpenseForm,
  type ExpenseFormErrors,
  type ExpensesTab,
  type ListRequest,
  type RecurrencePeriod,
  type RowStatus,
  type Rule,
  type SaveRequest,
  type Source,
  type StatusFilter,
  type TaxType,
} from "../types/index.ts";

const oneOf =
  <T extends string>(values: readonly T[]) =>
  (value: string | null): value is T =>
    value !== null && (values as readonly string[]).includes(value);

export const isExpensesTab = oneOf<ExpensesTab>(EXPENSES_TABS);
export const isSource = oneOf<Source>(SOURCES);
export const isStatusFilter = oneOf<StatusFilter>(STATUS_FILTERS);
export const isTaxType = oneOf<TaxType>(TAX_TYPES);
export const isPeriod = oneOf<RecurrencePeriod>(PERIODS);

/** A category paid to the budget (6410) needs `tax_type` (20 #42, QT-M15-06); recurring rules refuse it. */
export const isTaxCategory = (c: Pick<Category, "default_account"> | null | undefined): boolean =>
  c?.default_account === "6410";

/** Display status: a draft with a pending `expense_over_limit` request is «Tasdiq kutmoqda». */
export function rowStatus(e: Pick<Expense, "status" | "approval_status">): RowStatus {
  if (e.status === "draft" && e.approval_status === "pending") return "awaiting";
  return e.status;
}

/** Server filter: «Qoralama» and «Tasdiq kutmoqda» are both `status=draft` (split on the client). */
export function toListParams(req: ListRequest): ListExpensesParams {
  const f = req.filters;
  const status = f.status === "awaiting" ? "draft" : f.status;
  return {
    doc_date__gte: f.from,
    doc_date__lte: f.to,
    ...(f.categoryId ? { category_id: f.categoryId } : {}),
    ...(f.source ? { source: f.source } : {}),
    ...(status ? { status } : {}),
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: PAGE_SIZE,
  };
}

export function visibleRows(list: readonly Expense[], status: StatusFilter | null): Expense[] {
  if (status !== "draft" && status !== "awaiting") return [...list];
  return list.filter((e) => rowStatus(e) === status);
}

/** «toifalar bo'yicha o'tkazilgan» — posted rows of the loaded list grouped by category, biggest first. */
export function categoryShares(list: readonly Expense[]): { items: CategoryShare[]; total: string } {
  const sums = new Map<string, { name: string; amount: string }>();
  for (const e of list) {
    if (e.status !== "posted") continue;
    const prev = sums.get(e.category_id);
    sums.set(e.category_id, {
      name: e.category_name,
      amount: addMoney(money(prev?.amount ?? "0"), money(e.amount)),
    });
  }
  const total = addMoney(ZERO, ...[...sums.values()].map((s) => money(s.amount)));
  const items = [...sums.entries()]
    .map(([categoryId, s]) => ({
      categoryId,
      name: s.name,
      amount: s.amount,
      pct:
        compareMoney(total, ZERO) === 0
          ? "0.0"
          : toDecimal(s.amount).times(100).dividedBy(toDecimal(total)).toFixed(1),
    }))
    .sort((a, b) => compareMoney(money(b.amount), money(a.amount)) || a.name.localeCompare(b.name));
  return { items, total };
}

/** Active categories for the form (name order as served). */
export const activeCategories = (list: readonly Category[]): Category[] =>
  list.filter((c) => c.archived_at === null);

export function emptyForm(today: string, branchId: string | null): ExpenseForm {
  return {
    amount: "",
    categoryId: "",
    taxType: null,
    docDate: today,
    branchId: branchId ?? "",
    source: "bank",
    comment: "",
    attachment: null,
    period: "none",
    dayOfMonth: "",
  };
}

/** Day of month 1..28 typed as digits (no Number()). */
export function parseDay(value: string): number | null {
  if (!/^\d{1,2}$/.test(value.trim())) return null;
  let n = 0;
  for (const c of value.trim()) n = n * 10 + (c.charCodeAt(0) - 48);
  return n >= 1 && n <= 28 ? n : null;
}

/** 07 BO-17 field checks; keys are `common` validation keys. */
export function validateExpenseForm(
  form: ExpenseForm,
  category: Category | null,
  today: string,
): ExpenseFormErrors {
  const errors: ExpenseFormErrors = {};
  if (form.amount.trim() === "") errors.amount = "validation.required";
  else if (!isPositiveMoney(form.amount)) errors.amount = "validation.must_be_positive";
  if (!category) errors.categoryId = "validation.required";
  else if (category.archived_at !== null) errors.categoryId = "validation.archived";
  if (isTaxCategory(category) && !form.taxType) errors.taxType = "validation.required";
  if (form.docDate === "") errors.docDate = "validation.required";
  else if (form.docDate > today) errors.docDate = "validation.doc_date_in_future";
  if (form.branchId === "") errors.branchId = "validation.required";
  if (form.comment.length > COMMENT_MAX) errors.comment = "validation.max_length";
  if (form.period !== "none" && !isTaxCategory(category) && parseDay(form.dayOfMonth) === null)
    errors.dayOfMonth = "validation.range";
  return errors;
}

export function toSaveRequest(form: ExpenseForm, category: Category, post: boolean): SaveRequest {
  const amount = typedMoney(form.amount) ?? ZERO;
  const tax = isTaxCategory(category);
  const day = parseDay(form.dayOfMonth);
  return {
    post,
    body: {
      doc_date: form.docDate,
      branch_id: form.branchId,
      category_id: category.id,
      amount,
      source: form.source,
      attachment_id: form.attachment?.id ?? null,
      comment: form.comment.trim() || null,
      tax_type: tax ? form.taxType : null,
    },
    rule:
      form.period !== "none" && !tax && day !== null
        ? {
            name: form.comment.trim() || null,
            category_id: category.id,
            amount,
            day_of_month: day,
            period: form.period,
            source: form.source,
            branch_id: form.branchId,
          }
        : null,
  };
}

export const isCancelReasonValid = (reason: string): boolean => {
  const v = reason.trim();
  return v.length >= CANCEL_MIN && v.length <= CANCEL_MAX;
};

/** Reminder banners: due active rules minus the ones put off with «Keyinroq» in this visit. */
export function dueRules(rules: readonly Rule[], snoozed: readonly string[]): Rule[] {
  return rules.filter((r) => r.is_active && r.is_due && !snoozed.includes(r.id));
}

/** Rule title: its name, else the category name. */
export function ruleTitle(rule: Rule, categories: readonly Category[]): string {
  return rule.name ?? categories.find((c) => c.id === rule.category_id)?.name ?? "—";
}

/** Next filters after a patch (an inverted period is swapped). */
export function patchFilters(f: ExpenseFilters, patch: Partial<ExpenseFilters>): ExpenseFilters {
  const next = { ...f, ...patch };
  return next.from > next.to ? { ...next, from: next.to, to: next.from } : next;
}
