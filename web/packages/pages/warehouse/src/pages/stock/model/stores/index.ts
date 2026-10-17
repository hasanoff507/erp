import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import { $currentBranchId, $currentWarehouse } from "#/entities/refs/index.ts";

import type {
  Balance,
  BalanceFilters,
  BalancesView,
  DigestTransfer,
  ExpiringSummary,
  LoadStatus,
  Lot,
  StockSummary,
  StockTab,
  TransitSummary,
} from "../types/index.ts";

export const $mounted = createStore(false);
export const $today = createStore("1970-01-01");
export const $tab = createStore<StockTab>("balances");

/** The topbar branch (`null` = «Barcha filiallar» / none) and its warehouse (qaror #54). */
export const $branchId = $currentBranchId;
export const $warehouse = $currentWarehouse;
export const $warehouseId = $warehouse.map((w) => w?.id ?? null);

// --- «Qoldiq» ----------------------------------------------------------------------------------------
export const $filters = createStore<BalanceFilters>({ search: "", lowOnly: false });
export const $view = createStore<BalancesView>("balances");
export const $balances = createStore<Balance[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
/** When the list was last read (07 «Oxirgi yangilanish»). */
export const $loadedAt = createStore<string | null>(null, { skipVoid: false });

export const $lots = createStore<Lot[]>([]);
export const $lotsCursor = createStore<string | null>(null, { skipVoid: false });
export const $lotsStatus = createStore<LoadStatus>("idle");
export const $lotsError = createStore<ApiError | null>(null, { skipVoid: false });

// --- KPI / badges --------------------------------------------------------------------------------------
export const $summary = createStore<StockSummary | null>(null, { skipVoid: false });
export const $expiring = createStore<ExpiringSummary | null>(null, { skipVoid: false });
export const $transit = createStore<TransitSummary | null>(null, { skipVoid: false });
export const $reviewCount = createStore<number | null>(null, { skipVoid: false });
/** The KPI summary could not be read (WEB-06) — the cards show it with «Qayta urinish». */
export const $summaryError = createStore<ApiError | null>(null, { skipVoid: false });
/** «Ko'chirishlar va e-TTN» block rows (`null` = not read yet). */
export const $digest = createStore<DigestTransfer[] | null>(null, { skipVoid: false });
export const $digestError = createStore<ApiError | null>(null, { skipVoid: false });
/** A KPI refresh asked for while one is running — run once more when it ends (WEB-10). */
export const $refreshQueued = createStore(false);
