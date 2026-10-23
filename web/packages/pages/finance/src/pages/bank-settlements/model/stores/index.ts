import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { LoadStatus } from "#/shared/lib/effect.ts";

import type {
  BankImportResult,
  Settlement,
  SettlementDetail,
  SettlementFilters,
  TransitBalances,
} from "../types/index.ts";

export const $today = createStore("1970-01-01");
export const $defaultBranchId = createStore<string | null>(null, { skipVoid: false });

export const $filters = createStore<SettlementFilters>({
  branchId: null,
  method: null,
  status: null,
  source: null,
  from: null,
  to: null,
});
export const $settlements = createStore<Settlement[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });

export const $transit = createStore<TransitBalances | null>(null, { skipVoid: false });
export const $transitStatus = createStore<LoadStatus>("idle");

/** `null` — no document open; `"new"` — the create form; else a document id. */
export const $openedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<SettlementDetail | null>(null, { skipVoid: false });
export const $detailStatus = createStore<LoadStatus>("idle");
export const $detailError = createStore<ApiError | null>(null, { skipVoid: false });

export const $importResult = createStore<BankImportResult | null>(null, { skipVoid: false });
