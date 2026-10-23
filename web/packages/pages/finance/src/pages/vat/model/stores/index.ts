import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { LoadStatus, MovesFilters, PeriodKey, SummaryView, VatMove } from "../types/index.ts";

export const $today = createStore("1970-01-01");
export const $period = createStore<PeriodKey>("1970-01");

export const $summary = createStore<SummaryView | null>(null, { skipVoid: false });
export const $summaryStatus = createStore<LoadStatus>("idle");
export const $summaryError = createStore<ApiError | null>(null, { skipVoid: false });

export const $movesFilters = createStore<MovesFilters>({ kind: null, docType: null });
export const $moves = createStore<VatMove[]>([]);
/** Month of the period being paged (quarter → 0..2) and its cursor. */
export const $movesMonthIndex = createStore(0);
export const $movesCursor = createStore<string | null>(null, { skipVoid: false });
export const $movesStatus = createStore<LoadStatus>("idle");
export const $movesError = createStore<ApiError | null>(null, { skipVoid: false });
