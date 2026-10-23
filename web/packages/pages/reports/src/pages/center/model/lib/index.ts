import { dayjs } from "@shared/lib/date";
import { addMoney, money, subtractMoney } from "@shared/lib/money";
import type { ListVatMovesParams } from "@shared/models";

import {
  QUICK_RANGES,
  REPORT_KEYS,
  VAT_PAGE_SIZE,
  type DataReportKey,
  type DateRange,
  type HistoryTotals,
  type QuickRange,
  type ReportKey,
  type ReportOptions,
  type ReportRequest,
  type ShiftRow,
  type VatReturnsRequest,
} from "../types/index.ts";

export function isReportKey(value: string | null): value is ReportKey {
  return value !== null && (REPORT_KEYS as readonly string[]).includes(value);
}

export function isQuickRange(value: string): value is QuickRange {
  return (QUICK_RANGES as readonly string[]).includes(value);
}

/**
 * «Bugun» — today; «Hafta» — the last 7 days; «Oy» — from the 1st of the month; «Chorak» — from the
 * first day of the calendar quarter (all up to today).
 */
export function quickRange(kind: QuickRange, today: string): DateRange {
  const day = dayjs(today);
  if (kind === "today") return { from: today, to: today };
  if (kind === "week") return { from: day.subtract(6, "day").format("YYYY-MM-DD"), to: today };
  if (kind === "quarter") {
    const first = day.startOf("month").subtract(day.month() % 3, "month");
    return { from: first.format("YYYY-MM-DD"), to: today };
  }
  return { from: day.startOf("month").format("YYYY-MM-DD"), to: today };
}

export function sameRange(a: DateRange, b: DateRange): boolean {
  return a.from === b.from && a.to === b.to;
}

/** Which quick button matches the range (or none — «Boshqa»). */
export function matchQuickRange(range: DateRange, today: string): QuickRange | null {
  return QUICK_RANGES.find((k) => sameRange(quickRange(k, today), range)) ?? null;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Both ends are dates and `from ≤ to`. */
export function isRangeValid(r: DateRange): boolean {
  return ISO_DATE.test(r.from) && ISO_DATE.test(r.to) && r.from <= r.to;
}

/** Footer totals of the cash-history table (QT-M16-04: opening / sales / in / out / variance). */
export function historyTotals(rows: readonly ShiftRow[]): HistoryTotals {
  const sum = (pick: (r: ShiftRow) => string | null) =>
    addMoney(
      ...rows
        .map(pick)
        .filter((v): v is string => v !== null)
        .map((v) => money(v)),
    );
  return {
    openingCash: sum((r) => r.opening_cash),
    cashSales: sum((r) => r.cash_sales),
    cashIn: sum((r) => r.cash_in),
    cashOut: sum((r) => r.cash_out),
    variance: sum((r) => r.variance),
  };
}

export function toVatReturnsParams(req: VatReturnsRequest): ListVatMovesParams {
  return {
    doc_type: "returns",
    period: req.period,
    ...(req.cursor ? { cursor: req.cursor } : {}),
    limit: VAT_PAGE_SIZE,
  };
}

/** The last `count` months `YYYY-MM`, newest first. */
export function lastMonths(today: string, count = 12): string[] {
  const start = dayjs(today).startOf("month");
  return Array.from({ length: count }, (_, i) => start.subtract(i, "month").format("YYYY-MM"));
}

const DATA_REPORTS: readonly DataReportKey[] = [
  "daily-sales",
  "top-products",
  "cashier-sales",
  "stock",
  "low-stock",
  "profit-and-loss",
  "discounts",
  "debts-aging",
  "trial-balance",
  "balance-sheet",
  "stock-as-of",
];

export function isDataReport(key: ReportKey | null): key is DataReportKey {
  return key !== null && (DATA_REPORTS as readonly string[]).includes(key);
}

/**
 * The request of the open report from the filters (`null` — no data report open, or an invalid
 * period). «Qarzdorlik muddati» is «as of» the end of the period.
 */
export function reportRequest(
  report: ReportKey | null,
  range: DateRange,
  branchId: string | null,
  options: ReportOptions,
): ReportRequest | null {
  if (!isDataReport(report)) return null;
  if (report === "stock" || report === "low-stock") {
    return {
      kind: "stock",
      branchId,
      belowMinOnly: report === "low-stock",
      search: options.stockSearch.trim(),
    };
  }
  if (!isRangeValid(range)) return null;
  switch (report) {
    case "daily-sales":
    case "cashier-sales":
      return { kind: "sales", report, range, branchId };
    case "top-products":
      return { kind: "top-products", range, branchId, order: options.topOrder };
    case "profit-and-loss":
      return { kind: "profit-and-loss", range, branchId };
    case "discounts":
      return { kind: "discounts", range, branchId, groupBy: options.discountsGroupBy };
    case "debts-aging":
      return { kind: "debts-aging", asOf: range.to, branchId, direction: options.agingDirection };
    case "trial-balance":
      return { kind: "trial-balance", period: range.to.slice(0, 7), branchId };
    case "balance-sheet":
      return { kind: "balance-sheet", asOf: range.to, branchId };
    case "stock-as-of":
      return { kind: "stock-as-of", asOf: range.to, branchId };
  }
}

/**
 * «Sinov balansi» is monthly (20 #11 `?period=YYYY-MM`): choosing a month sets the range to that month (up to
 * today for the current month).
 */
export function monthRange(month: string, today: string): DateRange {
  const last = dayjs(`${month}-01`).endOf("month").format("YYYY-MM-DD");
  return { from: `${month}-01`, to: last < today ? last : today };
}

/** Stable identity of a request (answers to an older request are dropped). */
export function requestKey(req: ReportRequest | null): string {
  return req === null ? "" : JSON.stringify(req);
}

/** «Chegirmalar va marja»: margin lost because of discounts (margin without discounts − margin). */
export function lostMargin(r: { margin: string; margin_without_discounts: string }): string {
  return subtractMoney(money(r.margin_without_discounts), money(r.margin));
}
