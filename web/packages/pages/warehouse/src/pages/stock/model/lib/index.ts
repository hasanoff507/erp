import { dayjs } from "@shared/lib/date";
import type { TransferOut } from "@shared/models";

import { isNegative, isZero, sumMoney } from "#/shared/lib/decimal.ts";
import { daysUntil } from "#/shared/lib/effect.ts";

import {
  ALL_STOCK,
  DIGEST_DAYS,
  DIGEST_ROWS,
  STOCK_TABS,
  type Balance,
  type BalanceFilters,
  type Lot,
  type StockReport,
  type StockSummary,
  type StockTab,
} from "../types/index.ts";

/**
 * The «Qoldiq» scope: a branch → its warehouse id (`null` while unknown); «Barcha filiallar» (no branch)
 * → {@link ALL_STOCK} (consolidated, US-M04-03).
 */
export function stockScope(branchId: string | null, warehouseId: string | null): string | null {
  return branchId === null ? ALL_STOCK : warehouseId;
}

/** Client filters of the report rows: name (uz/ru) contains / exact barcode; «Faqat kam qoldiq». */
export function filterItems(items: readonly Balance[], filters: BalanceFilters): Balance[] {
  const q = filters.search.trim().toLowerCase();
  return items.filter((r) => {
    if (filters.lowOnly && !r.below_min) return false;
    if (!q) return true;
    return (
      r.name.toLowerCase().includes(q) ||
      (r.name_ru ?? "").toLowerCase().includes(q) ||
      r.barcode === filters.search.trim()
    );
  });
}

/** product_id → unit code (quantities of the lots view are formatted with it). */
export function unitsOf(report: StockReport | null): Record<string, string> {
  return Object.fromEntries((report?.items ?? []).map((r) => [r.product_id, r.unit_code]));
}

export function sameFilters(a: BalanceFilters, b: BalanceFilters): boolean {
  return a.search === b.search && a.lowOnly === b.lowOnly;
}

/** KPI from the report totals (07 BO-03: value at cost, positions, below-min, negative rows). */
export function summarize(report: StockReport, nameLimit = 3): StockSummary {
  const low = report.items.filter((r) => r.below_min);
  return {
    value: report.total.value,
    positions: report.total.positions,
    low: report.total.below_min_count,
    lowNames: low.slice(0, nameLimit).map((r) => r.name),
    negative: report.items.filter((r) => isNegative(r.qty)).length,
  };
}

/** Σ value of the rows shown («Sahifadagi jami»). */
export function pageTotal(rows: readonly Balance[]): string {
  return sumMoney(rows.map((r) => r.value));
}

/** product_id → days to the nearest expiry among its lots (negative = already expired). */
export function expiryByProduct(lots: readonly Lot[], today: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const lot of lots) {
    if (!lot.expiry_date || isZero(lot.qty_left)) continue;
    const days = daysUntil(lot.expiry_date, today);
    const known = out[lot.product_id];
    if (known === undefined || days < known) out[lot.product_id] = days;
  }
  return out;
}

export function isStockTab(value: string | null): value is StockTab {
  return value !== null && (STOCK_TABS as readonly string[]).includes(value);
}

/** Transfers the branch sends or receives (WEB-04: `GET /transfers` has no branch filter). */
export function ofBranch<T extends Pick<TransferOut, "from_branch_id" | "to_branch_id">>(
  list: readonly T[],
  branchId: string,
): T[] {
  return list.filter((t) => t.from_branch_id === branchId || t.to_branch_id === branchId);
}

/** First day of the digest window: today − (DIGEST_DAYS − 1), `YYYY-MM-DD`. */
export function digestFrom(today: string): string {
  return dayjs(today)
    .subtract(DIGEST_DAYS - 1, "day")
    .format("YYYY-MM-DD");
}

/** The branch's transfers, newest first (doc date, then creation), at most {@link DIGEST_ROWS}. */
export function digestOf<
  T extends Pick<TransferOut, "from_branch_id" | "to_branch_id" | "doc_date" | "created_at">,
>(list: readonly T[], branchId: string): T[] {
  return ofBranch(list, branchId)
    .sort((a, b) =>
      a.doc_date === b.doc_date
        ? (b.created_at ?? "").localeCompare(a.created_at ?? "")
        : b.doc_date.localeCompare(a.doc_date),
    )
    .slice(0, DIGEST_ROWS);
}
