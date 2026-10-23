import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import {
  DEFAULT_COUNT_FILTER,
  type Count,
  type CountStatus,
  type CountSummary,
  type ExtraLine,
  type LineFilter,
  type LoadStatus,
} from "../types/index.ts";

/** The list was opened at least once (a warehouse change then re-reads it). */
export const $opened = createStore(false);
export const $filter = createStore<CountStatus | null>(DEFAULT_COUNT_FILTER, { skipVoid: false });
export const $counts = createStore<CountSummary[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });

export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<Count | null>(null, { skipVoid: false });
export const $detailStatus = createStore<LoadStatus>("idle");
export const $detailError = createStore<ApiError | null>(null, { skipVoid: false });

/** product_id → typed counted value (unsaved). */
export const $drafts = createStore<Record<string, string>>({});
export const $extras = createStore<ExtraLine[]>([]);
export const $lineFilter = createStore<LineFilter>("all");
export const $lineSearch = createStore("");

/** Last refused write (lines / submit / cancel); the post dialog shows its own error. */
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });
