import { dayjs } from "@shared/lib/date";
import { addMoney, money } from "@shared/lib/money";
import type { ListVatMovesParams } from "@shared/models";

import {
  QUICK_RANGES,
  REPORT_KEYS,
  VAT_PAGE_SIZE,
  type DateRange,
  type HistoryTotals,
  type QuickRange,
  type ReportKey,
  type ShiftRow,
  type VatReturnsRequest,
} from "../types/index.ts";

export function isReportKey(value: string | null): value is ReportKey {
  return value !== null && (REPORT_KEYS as readonly string[]).includes(value);
}

export function isQuickRange(value: string): value is QuickRange {
  return (QUICK_RANGES as readonly string[]).includes(value);
}

/** «Bugun» — today; «Hafta» — the last 7 days; «Oy» — from the 1st of the month (all up to today). */
export function quickRange(kind: QuickRange, today: string): DateRange {
  const day = dayjs(today);
  if (kind === "today") return { from: today, to: today };
  if (kind === "week") return { from: day.subtract(6, "day").format("YYYY-MM-DD"), to: today };
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
