import type {
  StockBalanceOut,
  StockBalancePage,
  StockLotOut,
  StockLotPage,
  TransferOut,
} from "@shared/models";

export type Balance = StockBalanceOut;
export type Lot = StockLotOut;
export type { StockBalancePage, StockLotPage };

/** 07 BO-03 tabs. */
export type StockTab = "balances" | "transfers" | "counts";
export const STOCK_TABS: readonly StockTab[] = ["balances", "transfers", "counts"];

/** «Qoldiq» tab view: balances, or lots expiring within N days (`expiringWithinDays` filter). */
export type BalancesView = "balances" | "expiring";

export type LoadStatus = "idle" | "loading" | "error";

/** US-M04-06 default: 7 days (19 §7 `expiring_within_days=7`). */
export const EXPIRY_DAYS = 7;
export const BALANCE_PAGE_SIZE = 50;

export interface BalanceFilters {
  search: string;
  lowOnly: boolean;
}

export interface BalancesRequest {
  warehouseId: string;
  filters: BalanceFilters;
  cursor: string | null;
}

export interface LotsRequest {
  warehouseId: string;
  cursor: string | null;
}

/**
 * KPI cards of 07 BO-03. There is no aggregate endpoint in Bosqich 2 (`GET /reports/stock` is
 * Bosqich 4), so the figures are summed from every balance page of the warehouse (`capped` = the
 * page budget ran out — the figures are a lower bound).
 */
export interface StockSummary {
  /** Σ value at cost (2 dp). */
  value: string;
  positions: number;
  low: number;
  /** First names of low-stock products (banner «Choy ko'k 100 g, … va yana N ta»). */
  lowNames: string[];
  negative: number;
  capped: boolean;
}

export interface ExpiringSummary {
  lots: Lot[];
  capped: boolean;
}

export interface TransitSummary {
  inTransit: number;
  overdue: number;
  /** Posted vehicle transfers whose e-TTN is not registered yet. */
  waitingEttn: number;
}

/** «Ko'chirishlar va e-TTN» block under «Qoldiq» (07 BO-03): the last 7 days of the current branch. */
export const DIGEST_DAYS = 7;
export const DIGEST_ROWS = 5;

export interface DigestRequest {
  branchId: string;
  /** First day of the window `YYYY-MM-DD` (today − 6). */
  from: string;
}

export type DigestTransfer = TransferOut;

export interface StockMountParams {
  /** Local calendar date `YYYY-MM-DD` (expiry days are counted from it). */
  today: string;
  /** `settings.users` — the staff list for «Javobgar shaxs». */
  canListStaff: boolean;
}
