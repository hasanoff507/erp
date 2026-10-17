import type {
  ExpenseCategoryCreateIn,
  ExpenseCategoryItem,
  ExpenseCategoryUpdateIn,
  ExpenseCreate,
  ExpenseOut,
  ExpensePage,
  ExpensePosted,
  RuleConfirmed,
  RuleCreate,
  RuleOut,
  RulePage,
  RuleUpdate,
} from "@shared/models";

import type { Attachment } from "#/shared/lib/attachments.ts";

export type Expense = ExpenseOut;
export type Category = ExpenseCategoryItem;
export type CategoryCreate = ExpenseCategoryCreateIn;
export type CategoryUpdate = ExpenseCategoryUpdateIn;
export type Rule = RuleOut;
export type { ExpenseCreate, ExpensePage, ExpensePosted, RuleConfirmed, RuleCreate, RulePage, RuleUpdate };

/** 12 expense_categories.default_account (13 §2.17). */
export const EXPENSE_ACCOUNTS = ["9410", "9420", "9430", "6410"] as const;
export type ExpenseAccount = (typeof EXPENSE_ACCOUNTS)[number];
/**
 * `taxType` of a 6410 category (QT-M15-06): only taxes accrued on 6410 by a tax settlement (ST) — VAT and
 * turnover tax; anything else is refused (`validation.tax_type_not_accrued`, contracts/expenses.md).
 */
export const TAX_TYPES = ["vat", "turnover"] as const;
export type TaxType = (typeof TAX_TYPES)[number];
/** BO-17 records bank / corporate card only — cash expenses are POS-14 «Xarajat» (`expense.created`). */
export const FORM_SOURCES = ["bank", "card"] as const;
export type FormSource = (typeof FORM_SOURCES)[number];
export const SOURCES = ["bank", "card", "cash"] as const;
export type Source = (typeof SOURCES)[number];
export const PERIODS = ["none", "month", "quarter", "year"] as const;
export type RecurrencePeriod = (typeof PERIODS)[number];
/**
 * List status filter: the server statuses plus «Tasdiq kutmoqda» = a draft whose `expense_over_limit`
 * request is pending (07 BO-17).
 */
export const STATUS_FILTERS = ["posted", "draft", "awaiting", "cancelled"] as const;
export type StatusFilter = (typeof STATUS_FILTERS)[number];
/** Display status of a row. */
export type RowStatus = "posted" | "draft" | "awaiting" | "cancelled";

export type ExpensesTab = "expenses" | "recurring" | "categories";
export const EXPENSES_TABS: readonly ExpensesTab[] = ["expenses", "recurring", "categories"];

export interface ExpenseFilters {
  from: string;
  to: string;
  categoryId: string | null;
  source: Source | null;
  status: StatusFilter | null;
}

export interface ListRequest {
  filters: ExpenseFilters;
  cursor: string | null;
}

/** The «Yangi xarajat» form (strings as typed; amount = MoneyInput value). */
export interface ExpenseForm {
  amount: string;
  categoryId: string;
  taxType: TaxType | null;
  docDate: string;
  branchId: string;
  source: FormSource;
  comment: string;
  attachment: Attachment | null;
  period: RecurrencePeriod;
  dayOfMonth: string;
}

export type ExpenseFormField =
  "amount" | "categoryId" | "taxType" | "docDate" | "branchId" | "comment" | "dayOfMonth";
export type ExpenseFormErrors = Partial<Record<ExpenseFormField, string>>;

export interface SaveRequest {
  body: ExpenseCreate;
  /** «Saqlash va o'tkazish» (else «Qoralama»). */
  post: boolean;
  /** Takrorlanish davri ≠ «Takrorlanmaydi» → a recurring rule too (20 #49). */
  rule: RuleCreate | null;
}

/** What the last action told the user (banner above the list). */
export type Notice =
  | { kind: "posted"; number: string | null }
  | { kind: "approval" }
  | { kind: "draft" }
  | { kind: "cancelled" }
  | { kind: "ruleCreated" };

export interface CategoryShare {
  categoryId: string;
  name: string;
  amount: string;
  /** Share of the posted total, percent with one decimal ("37.5"). */
  pct: string;
}

export const COMMENT_MAX = 1000;
export const CANCEL_MIN = 3;
export const CANCEL_MAX = 500;
export const CATEGORY_NAME_MAX = 50;
export const PAGE_SIZE = 50;
export const RULES_PAGE_SIZE = 100;

export interface ExpensesMountParams {
  today: string;
  /** Topbar branch (`X-Branch-Id`) or the user's only branch — the form default. */
  branchId: string | null;
}
