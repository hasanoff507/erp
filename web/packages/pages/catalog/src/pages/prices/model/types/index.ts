import type { PriceChangeOut, PriceHistoryItem, ProductOut } from "@shared/models";

export interface PriceFilters {
  search: string;
  categoryId: string | null;
}

/** "all" = global price (all branches, `branch_id=null`), otherwise a branch id (branch override). */
export type PriceScope = string;
export const ALL_BRANCHES_SCOPE = "all";

export interface ProductPrice {
  /** Price in force now (branch override first, then global) — decimal string or null (never set). */
  current: string | null;
  /** A posted price with a later valid_from, if any. */
  scheduled: { price: string; validFrom: string } | null;
}

export type ListStatus = "idle" | "loading" | "error";

/** Row state in the «Chakana narxlar» table (07 BO-05: o'zgarmagan / o'zgaradi / tasdiq kerak). */
export type RowState = "unchanged" | "changed" | "approval" | "approvalMaybe" | "invalid";

/**
 * One edited row, kept across pages/filters until saved or reset (07 BO-05: the document holds every
 * edit, not just the visible page). The product and its price at edit time are snapshotted so the
 * footer, the limit banner and the save payload do not depend on the current page.
 */
export interface PriceDraft {
  product: ProductOut;
  /** Current price when the row was first edited (fallback when `$prices` no longer has the row). */
  oldPrice: string | null;
  /** `newPrice` decimal string from MoneyInput ("" = no change). */
  value: string;
}

/**
 * The approval threshold used for the row status prediction (19 §4: the server compares |pct| with the
 * poster's `prices.approve` limit; without a grant the default 10%). `exact` = the server will use this
 * very limit; otherwise the label is advisory ("may need approval").
 */
export interface ApprovalLimit {
  /** Percent as a decimal string; `null` = unlimited (never needs approval). */
  pct: string | null;
  exact: boolean;
}

export interface PriceChange {
  product: ProductOut;
  oldPrice: string | null;
  newPrice: string;
  /** Signed percent, 1 place, or null without an old price. */
  pct: string | null;
  overLimit: boolean;
}

export interface SavePricesParams {
  docDate: string;
  validFrom: string | null;
  branchId: string | null;
  lines: { productId: string; newPrice: string }[];
}

export const PRICES_PAGE_SIZE = 20;
export const HISTORY_PAGE_SIZE = 20;

export type { PriceChangeOut, PriceHistoryItem, ProductOut };
