/** BO-08 wiring — sample() only (24 §2). */
import { combine, sample } from "effector";

import {
  listEntriesFx,
  listRecostFx,
  loadProductNamesFx,
  loadWarehousesFx,
  retryRecostFx,
} from "../effects/index.ts";
import {
  filtersApplied,
  filtersChanged,
  filtersReset,
  moreRequested,
  pageMounted,
  recostFilterChanged,
  recostMoreRequested,
  recostReloadRequested,
  recostRetryDismissed,
  recostRetryRequested,
  reloadRequested,
} from "../events/index.ts";
import {
  defaultFilters,
  isRangeValid,
  missingIds,
  replaceJob,
  sameFilters,
  turnoverOf,
} from "../lib/index.ts";
import {
  $cursor,
  $entries,
  $error,
  $filters,
  $loaded,
  $productNames,
  $recostCursor,
  $recostEnabled,
  $recostError,
  $recostFilter,
  $recostJobs,
  $recostStatus,
  $retryError,
  $retrying,
  $status,
  $today,
  $warehouseNames,
} from "../stores/index.ts";
import type { JournalFilters } from "../types/index.ts";

/** «Dt oboroti = Kt oboroti» of the loaded rows. */
export const $turnover = $entries.map(turnoverOf);
/** `dateFrom > dateTo` (or an empty end) — no request, the filter shows an error. */
export const $rangeInvalid = $filters.map((f) => !isRangeValid(f));
export const $moreLoading = combine(
  listEntriesFx.pending,
  $cursor,
  $status,
  (pending, cursor, status) => pending && cursor !== null && status !== "loading",
);
export const $recostMoreLoading = combine(
  listRecostFx.pending,
  $recostStatus,
  (pending, status) => pending && status !== "loading",
);

// --- filters ---------------------------------------------------------------------------------------
sample({ clock: pageMounted, fn: ({ today }) => defaultFilters(today), target: filtersApplied });
$today.on(pageMounted, (_, { today }) => today);
sample({ clock: filtersReset, source: $today, fn: defaultFilters, target: filtersApplied });
sample({
  clock: filtersChanged,
  source: $filters,
  fn: (f, patch): JournalFilters => ({ ...f, ...patch }),
  target: filtersApplied,
});
$filters.on(filtersApplied, (_, f) => f);

// --- journal list ----------------------------------------------------------------------------------
sample({
  clock: [filtersApplied, sample({ clock: reloadRequested, source: $filters })],
  filter: isRangeValid,
  fn: (filters) => ({ filters, cursor: null }),
  target: listEntriesFx,
});
sample({
  clock: moreRequested,
  source: { filters: $filters, cursor: $cursor, pending: listEntriesFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filters, cursor }) => ({ filters, cursor }),
  target: listEntriesFx,
});

// An answer for filters that are no longer current (changed while loading) is dropped.
const pageLoaded = sample({
  clock: listEntriesFx.done,
  source: $filters,
  filter: (current, { params }) => sameFilters(current, params.filters),
  fn: (_, payload) => payload,
});
$entries.on(pageLoaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$cursor.on(pageLoaded, (_, { result }) => result.next_cursor);
$loaded.on(pageLoaded, () => true);

$status
  .on(listEntriesFx, (status, { cursor }) => (cursor === null ? "loading" : status))
  .on(pageLoaded, () => "idle")
  .on(listEntriesFx.fail, (status, { params }) => (params.cursor === null ? "error" : status));
$error.on(listEntriesFx.failData, (_, e) => e).reset(listEntriesFx);
// An invalid range clears the table instead of showing rows of another period.
sample({
  clock: filtersApplied,
  filter: (f) => !isRangeValid(f),
  fn: () => [],
  target: $entries,
});
sample({ clock: filtersApplied, filter: (f) => !isRangeValid(f), fn: () => null, target: $cursor });
sample({
  clock: filtersApplied,
  filter: (f) => !isRangeValid(f),
  fn: () => "idle" as const,
  target: $status,
});

// --- «Qayta hisoblash navbati» (19 §18, qaror #56c) ----------------------------------------------
$recostEnabled.on(pageMounted, (_, { canViewRecost }) => canViewRecost);
$recostFilter.on(recostFilterChanged, (_, status) => status);

sample({
  clock: pageMounted,
  source: $recostFilter,
  filter: (_, { canViewRecost }) => canViewRecost,
  fn: (status) => ({ status, cursor: null }),
  target: listRecostFx,
});
sample({
  clock: [recostFilterChanged, recostReloadRequested],
  source: { status: $recostFilter, enabled: $recostEnabled },
  filter: ({ enabled }) => enabled,
  fn: ({ status }) => ({ status, cursor: null }),
  target: listRecostFx,
});
sample({
  clock: recostMoreRequested,
  source: { status: $recostFilter, cursor: $recostCursor, pending: listRecostFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ status, cursor }) => ({ status, cursor }),
  target: listRecostFx,
});

const recostLoaded = sample({
  clock: listRecostFx.done,
  source: $recostFilter,
  filter: (current, { params }) => current === params.status,
  fn: (_, payload) => payload,
});
$recostJobs.on(recostLoaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$recostCursor.on(recostLoaded, (_, { result }) => result.next_cursor);
$recostStatus
  .on(listRecostFx, (status, { cursor }) => (cursor === null ? "loading" : status))
  .on(recostLoaded, () => "idle")
  .on(listRecostFx.fail, (status, { params }) => (params.cursor === null ? "error" : status));
$recostError.on(listRecostFx.failData, (_, e) => e).reset(listRecostFx);

// Names for the ids of the loaded jobs.
sample({
  clock: recostLoaded,
  source: $productNames,
  fn: (known, { result }) =>
    missingIds(
      result.items.map((j) => j.product_id),
      known,
    ),
  filter: (known, { result }) =>
    missingIds(
      result.items.map((j) => j.product_id),
      known,
    ).length > 0,
  target: loadProductNamesFx,
});
$productNames.on(loadProductNamesFx.doneData, (names, loaded) => ({ ...names, ...loaded }));
sample({
  clock: pageMounted,
  source: $warehouseNames,
  filter: (names, { canViewRecost }) => canViewRecost && Object.keys(names).length === 0,
  fn: () => undefined,
  target: loadWarehousesFx,
});
$warehouseNames.on(loadWarehousesFx.doneData, (_, names) => names);

// Retry: only a failed job, one request per job at a time.
sample({
  clock: recostRetryRequested,
  source: { jobs: $recostJobs, retrying: $retrying },
  filter: ({ jobs, retrying }, id) =>
    !retrying.includes(id) && jobs.some((j) => j.id === id && j.status === "failed"),
  fn: (_, id) => id,
  target: retryRecostFx,
});
$retrying
  .on(retryRecostFx, (ids, id) => [...ids, id])
  .on(retryRecostFx.finally, (ids, { params }) => ids.filter((id) => id !== params));
$recostJobs.on(retryRecostFx.doneData, replaceJob);
$retryError.on(retryRecostFx.failData, (_, e) => e).reset(retryRecostFx, recostRetryDismissed);
// The job changed meanwhile (409 DOC_INVALID_STATE / RECOST_REJECTED_PERIOD_CLOSED / 404): show the truth.
sample({
  clock: retryRecostFx.failData,
  filter: (e) => e.status === 404 || e.status === 409,
  fn: () => undefined,
  target: recostReloadRequested,
});
