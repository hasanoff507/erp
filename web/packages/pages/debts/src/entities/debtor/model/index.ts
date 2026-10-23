/**
 * Debtor rows of BO-06 — `GET /reports/debts-aging` rows (20 #21, contracts b4/debts-aging.md) and the pure
 * rules the screen applies to them: the tabs (07 BO-06: «Bugun/o'tgan va'da» = promise/due date ≤ today,
 * US-M08-09; «60+ kun» = bucket 60+, a reminder list only — nothing is flagged automatically, US-M08-10;
 * «Limitdan oshgan» = `limit_exceeded_offline`; «Barchasi»), the search, the promise chip and the aging
 * card shares. Money stays decimal strings.
 */
import { addMoney, compareMoney, toDecimal, type Money } from "@shared/lib/money";
import type { AgingRow, AgingSummary } from "@shared/models";

export type Direction = "receivable" | "payable";
export type DebtorTab = "due" | "aged" | "over_limit" | "all";
export const DEBTOR_TABS: readonly DebtorTab[] = ["due", "aged", "over_limit", "all"];
export const AGING_BUCKETS = ["0-30", "31-60", "60+"] as const;
export type AgingBucketKey = (typeof AGING_BUCKETS)[number];

export function isDebtorTab(value: unknown): value is DebtorTab {
  return typeof value === "string" && (DEBTOR_TABS as readonly string[]).includes(value);
}

/** The date the customer promised to pay: the current promise, else the earliest due date. */
export function promiseOf(row: Pick<AgingRow, "promise_date" | "due_date">): string | null {
  return row.promise_date ?? row.due_date ?? null;
}

export type PromiseState = "today" | "overdue" | "future" | "none";

export function promiseState(row: Pick<AgingRow, "promise_date" | "due_date">, today: string): PromiseState {
  const date = promiseOf(row);
  if (!date) return "none";
  if (date === today) return "today";
  return date < today ? "overdue" : "future";
}

export function matchesTab(row: AgingRow, tab: DebtorTab, today: string): boolean {
  switch (tab) {
    case "due": {
      const s = promiseState(row, today);
      return s === "today" || s === "overdue";
    }
    case "aged":
      return row.bucket === "60+";
    case "over_limit":
      return row.limit_exceeded_offline;
    default:
      return true;
  }
}

/** Name words / phone digits (the last 9 digits too), case-insensitive. */
export function matchesSearch(row: Pick<AgingRow, "name" | "phone">, search: string): boolean {
  const q = search.trim().toLocaleLowerCase();
  if (!q) return true;
  const digits = q.replace(/\D+/g, "");
  const phone = (row.phone ?? "").replace(/\D+/g, "");
  if (digits.length >= 3 && digits.length === q.replace(/[\s+()-]/g, "").length)
    return phone.includes(digits);
  const name = row.name.toLocaleLowerCase();
  return q.split(/\s+/).every((w) => name.includes(w));
}

export function filterRows(
  rows: readonly AgingRow[],
  tab: DebtorTab,
  search: string,
  today: string,
): AgingRow[] {
  return rows.filter((r) => matchesTab(r, tab, today) && matchesSearch(r, search));
}

export function tabCounts(rows: readonly AgingRow[], today: string): Record<DebtorTab, number> {
  return {
    due: rows.filter((r) => matchesTab(r, "due", today)).length,
    aged: rows.filter((r) => matchesTab(r, "aged", today)).length,
    over_limit: rows.filter((r) => r.limit_exceeded_offline).length,
    all: rows.length,
  };
}

export function totalOf(rows: readonly Pick<AgingRow, "balance">[]): Money {
  return addMoney("0.00" as Money, ...rows.map((r) => r.balance as Money));
}

export interface BucketCard {
  bucket: AgingBucketKey;
  count: number;
  amount: Money;
  /** Share of the total in percent, one decimal ("37.5"); "0.0" without debt. */
  share: string;
}

export function bucketCards(summary: AgingSummary | null): BucketCard[] {
  const total = (summary?.total ?? "0.00") as Money;
  return AGING_BUCKETS.map((bucket) => {
    const b = summary?.buckets.find((x) => x.bucket === bucket);
    const amount = (b?.amount ?? "0.00") as Money;
    const share =
      compareMoney(total, "0.00" as Money) > 0
        ? toDecimal(amount).times(100).div(toDecimal(total)).toDecimalPlaces(1).toFixed(1)
        : "0.0";
    return { bucket, count: b?.count ?? 0, amount, share };
  });
}

/** The credit limit is passed by the current debt (shown as «oshgan»). */
export function overLimit(row: Pick<AgingRow, "balance" | "credit_limit">): boolean {
  if (row.credit_limit === null) return false;
  return compareMoney(row.balance as Money, row.credit_limit as Money) > 0;
}

export const PAGE_SIZE = 20;

export function pageOf<T>(rows: readonly T[], page: number, size = PAGE_SIZE): T[] {
  const start = (Math.max(1, page) - 1) * size;
  return rows.slice(start, start + size);
}
