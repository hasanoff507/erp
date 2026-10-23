/**
 * POS-14 «Xarajat» (07 POS-14; 18 §13.2; 20 #42 offline payload; US-M15-01; QT-M15-01): a cash expense
 * paid from the till → `expense.created` in the outbox (works offline). The cashier has no
 * `expenses.create`: the event is checked against `cash.withdraw` (limit; default 50 000 so'm) — above the
 * actor's own limit an ApprovalDialog (`cash_withdrawal_over_limit`, the approver's `cash.withdraw` limit
 * must cover the amount; local PIN offline too). The server posts it at once (`Dt <category account> /
 * Kt 5010` + `cash_moves`). Categories come from `GET /expense-categories` while online and are cached on
 * the device (`deviceSettings` "pos.expense_categories") for offline use.
 */
import { api } from "@shared/api";
import { compareMoney, money, type Money } from "@shared/lib/money";
import { deviceSettings, enqueueEvent, limits } from "@shared/offline";

import { isOwner, limitCovers, uuidv7, type PosCashier } from "#/entities/pos-session/index.ts";

/** 18 §2.4 ApprovalRef as produced by the manager-approval feature (kept opaque here — FSD: no feature → feature import). */
export type ExpenseApprovalRef = object;

export const CATEGORIES_KEY = "pos.expense_categories";
export const COMMENT_MAX = 1000;
/** `taxType` of a 6410 category: VAT / turnover tax only (`validation.tax_type_not_accrued` otherwise). */
export const TAX_TYPES = ["vat", "turnover"] as const;
export type TaxType = (typeof TAX_TYPES)[number];

export interface PosExpenseCategory {
  id: string;
  name: string;
  default_account: string;
}

export interface CachedCategories {
  items: PosExpenseCategory[];
  savedAt: string;
}

export interface ExpenseForm {
  /** Whole so'm keypad digits ("150000"). */
  digits: string;
  categoryId: string | null;
  taxType: TaxType | null;
  comment: string;
}

export type ExpenseError = "amount" | "category" | "taxType" | "comment";

export const isTaxCategory = (c: PosExpenseCategory | null | undefined): boolean =>
  c?.default_account === "6410";

export function digitsToMoney(digits: string): Money | null {
  return /^\d+$/.test(digits) ? money(digits) : null;
}

export function validateExpense(form: ExpenseForm, category: PosExpenseCategory | null): ExpenseError[] {
  const errors: ExpenseError[] = [];
  const amount = digitsToMoney(form.digits);
  if (!amount || compareMoney(amount, "0.00" as Money) <= 0) errors.push("amount");
  if (!category) errors.push("category");
  if (isTaxCategory(category) && !form.taxType) errors.push("taxType");
  if (form.comment.length > COMMENT_MAX) errors.push("comment");
  return errors;
}

/** Over the actor's own `cash.withdraw` limit → approval (the Owner is unlimited). */
export function expenseNeedsApproval(
  cashier: Pick<PosCashier, "roleCodes">,
  ownLimit: string | null | undefined,
  amount: string,
): boolean {
  if (isOwner(cashier.roleCodes)) return false;
  return !limitCovers(ownLimit, amount);
}

/** 18 §13.2 payload — exactly the documented fields (extra fields are refused by the server). */
export function expensePayload(input: {
  id: string;
  docDate: string;
  branchId: string;
  cashRegisterId: string;
  shiftId: string;
  category: PosExpenseCategory;
  amount: Money;
  comment: string;
  taxType: TaxType | null;
  approval: ExpenseApprovalRef | null;
}) {
  return {
    id: input.id,
    doc_date: input.docDate,
    branch_id: input.branchId,
    cash_register_id: input.cashRegisterId,
    shift_id: input.shiftId,
    category_id: input.category.id,
    amount: input.amount,
    comment: input.comment.trim() || null,
    tax_type: isTaxCategory(input.category) ? input.taxType : null,
    approval: input.approval,
  };
}

/** Active categories of the `GET /expense-categories` answer, in the served (name) order. */
export function toCached(
  items: readonly { id: string; name: string; default_account: string; archived_at: string | null }[],
  savedAt: string,
): CachedCategories {
  return {
    items: items
      .filter((c) => c.archived_at === null)
      .map((c) => ({ id: c.id, name: c.name, default_account: c.default_account })),
    savedAt,
  };
}

export interface PosExpenseDeps {
  isOnline(): boolean;
  fetchCategories(): Promise<CachedCategories>;
  readCache(): Promise<CachedCategories | undefined>;
  writeCache(value: CachedCategories): Promise<void>;
  ownLimit(userId: string): Promise<string | null | undefined>;
  enqueue(
    payload: ReturnType<typeof expensePayload>,
    actorUserId: string,
  ): Promise<{ clientEventId: string }>;
}

/** Online: refresh the cache from the server; offline or on failure: the cached list (or none). */
export async function loadCategories(
  deps: Pick<PosExpenseDeps, "isOnline" | "fetchCategories" | "readCache" | "writeCache">,
): Promise<{ categories: CachedCategories | null; fromCache: boolean }> {
  if (deps.isOnline()) {
    try {
      const fresh = await deps.fetchCategories();
      await deps.writeCache(fresh);
      return { categories: fresh, fromCache: false };
    } catch {
      // fall back to the cache below
    }
  }
  return { categories: (await deps.readCache()) ?? null, fromCache: true };
}

export const defaultPosExpenseDeps = (isOnline: () => boolean): PosExpenseDeps => ({
  isOnline,
  fetchCategories: async () => {
    const { items } = await api.expenses.listCategories();
    return toCached(items, new Date().toISOString());
  },
  readCache: () => deviceSettings.get<CachedCategories>(CATEGORIES_KEY),
  writeCache: (value) => deviceSettings.set(CATEGORIES_KEY, value),
  ownLimit: (userId) => limits.value(userId, "cash.withdraw"),
  enqueue: async (payload, actorUserId) => {
    const r = await enqueueEvent("expense.created", payload, { actorUserId });
    return { clientEventId: r.clientEventId };
  },
});

export const newExpenseId = (): string => uuidv7();
