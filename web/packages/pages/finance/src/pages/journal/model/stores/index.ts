import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import { defaultFilters } from "../lib/index.ts";
import type { JournalFilters, LedgerEntry, LoadStatus, RecostJob, RecostStatus } from "../types/index.ts";

// --- journal -------------------------------------------------------------------------------------
/** Local date of the visit (`pageMounted`) — the default period ends here. */
export const $today = createStore("1970-01-01");
export const $filters = createStore<JournalFilters>(defaultFilters("1970-01-01"));
export const $entries = createStore<LedgerEntry[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
/** First page state (a «load more» keeps `idle`; see `$moreLoading`). */
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
/** `true` once the first page answered (empty state vs. skeleton). */
export const $loaded = createStore(false);

// --- «Qayta hisoblash navbati» -------------------------------------------------------------------
export const $recostEnabled = createStore(false);
export const $recostFilter = createStore<RecostStatus | null>(null, { skipVoid: false });
export const $recostJobs = createStore<RecostJob[]>([]);
export const $recostCursor = createStore<string | null>(null, { skipVoid: false });
export const $recostStatus = createStore<LoadStatus>("idle");
export const $recostError = createStore<ApiError | null>(null, { skipVoid: false });
/** Jobs whose «Qayta urinish» is in flight. */
export const $retrying = createStore<readonly string[]>([]);
/** Last refused retry (409 DOC_INVALID_STATE / RECOST_REJECTED_PERIOD_CLOSED, network…) → banner. */
export const $retryError = createStore<ApiError | null>(null, { skipVoid: false });

/** product_id → name and warehouse_id → name for the queue (19 §18 answers ids only). */
export const $productNames = createStore<Record<string, string>>({});
export const $warehouseNames = createStore<Record<string, string>>({});
