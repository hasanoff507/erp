import { dayjs } from "@shared/lib/date";
import type { ListStockBalancesParams, TransferOut } from "@shared/models";

import { isNegative, isZero, sumMoney } from "#/shared/lib/decimal.ts";
import { daysUntil } from "#/shared/lib/effect.ts";

import {
  BALANCE_PAGE_SIZE,
  DIGEST_DAYS,
  DIGEST_ROWS,
  STOCK_TABS,
  type Balance,
  type BalanceFilters,
  type Lot,
  type StockSummary,
  type StockTab,
} from "../types/index.ts";

export function toBalancesQuery(
  warehouseId: string,
  filters: BalanceFilters,
  cursor: string | null,
): ListStockBalancesParams {
  const search = filters.search.trim();
  return {
    warehouse_id: warehouseId,
    ...(search ? { search } : {}),
    ...(filters.lowOnly ? { low_stock: true } : {}),
    ...(cursor ? { cursor } : {}),
    limit: BALANCE_PAGE_SIZE,
  };
}

export function sameFilters(a: BalanceFilters, b: BalanceFilters): boolean {
  return a.search === b.search && a.lowOnly === b.lowOnly;
}

/** Positions = balance rows with a non-zero quantity (a zero row is history, not stock). */
export function summarize(rows: readonly Balance[], capped: boolean, nameLimit = 3): StockSummary {
  const live = rows.filter((r) => !isZero(r.qty));
  const low = live.filter((r) => r.is_low);
  return {
    value: sumMoney(rows.map((r) => r.value)),
    positions: live.length,
    low: low.length,
    lowNames: low.slice(0, nameLimit).map((r) => r.product_name),
    negative: rows.filter((r) => r.is_negative || isNegative(r.qty)).length,
    capped,
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

/** Latest `updated_at` of the rows (07 «oxirgi yangilanish»), `null` without one. */
export function lastUpdated(rows: readonly Balance[]): string | null {
  let best: string | null = null;
  for (const r of rows) if (r.updated_at && (best === null || r.updated_at > best)) best = r.updated_at;
  return best;
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
