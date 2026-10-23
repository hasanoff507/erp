import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import { todayIso } from "../lib/index.ts";
import {
  ALL_BRANCHES_SCOPE,
  type ListStatus,
  type PriceChangeOut,
  type PriceDraft,
  type PriceFilters,
  type PriceHistoryItem,
  type PriceProduct,
  type PriceScope,
  type ProductPrice,
} from "../types/index.ts";

export const $filters = createStore<PriceFilters>({ search: "", categoryId: null });
export const $page = createStore(1);
export const $products = createStore<PriceProduct[]>([]);
export const $total = createStore(0);
export const $listStatus = createStore<ListStatus>("idle");
export const $listError = createStore<ApiError | null>(null, { skipVoid: false });

export const $prices = createStore<Record<string, ProductPrice>>({});
export const $drafts = createStore<Record<string, PriceDraft>>({});
export const $effectiveFrom = createStore<string>(todayIso());
export const $scope = createStore<PriceScope>(ALL_BRANCHES_SCOPE);

export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $history = createStore<PriceHistoryItem[]>([]);
export const $historyCursor = createStore<string | null>(null, { skipVoid: false });
export const $historyError = createStore<ApiError | null>(null, { skipVoid: false });

/** Last saved document: `posted` or `pending_approval` (banner), until dismissed or the next save. */
export const $saveResult = createStore<PriceChangeOut | null>(null, { skipVoid: false });
export const $saveError = createStore<ApiError | null>(null, { skipVoid: false });
