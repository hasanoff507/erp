/** BO-03 wiring — sample() only (24 §2). */
import { combine, createEvent, sample } from "effector";

import { productsRequested, refsRequested } from "#/entities/refs/index.ts";
import {
  cancelCountFx,
  countsOpened,
  createCountFx,
  postCountFx,
  submitCountFx,
} from "#/features/stock-counts/index.ts";
import {
  cancelTransferFx,
  createTransferFx,
  postTransferFx,
  receiveTransferFx,
  sendTransferFx,
  transfersOpened,
} from "#/features/transfers/index.ts";
import { repostWriteOffFx, submitWriteOffFx } from "#/features/write-off/index.ts";

import {
  listBalancesFx,
  listExpiringLotsFx,
  loadDigestFx,
  loadExpiringFx,
  loadReviewCountFx,
  loadSummaryFx,
  loadTransitFx,
} from "../effects/index.ts";
import {
  lotsMoreRequested,
  lowOnlyToggled,
  moreRequested,
  pageMounted,
  reloadRequested,
  searchChanged,
  summaryRefreshRequested,
  tabChanged,
  viewChanged,
} from "../events/index.ts";
import { digestFrom, expiryByProduct, lastUpdated, pageTotal, sameFilters } from "../lib/index.ts";
import {
  $balances,
  $branchId,
  $cursor,
  $digest,
  $digestError,
  $error,
  $expiring,
  $filters,
  $loadedAt,
  $lots,
  $lotsCursor,
  $lotsError,
  $lotsStatus,
  $mounted,
  $refreshQueued,
  $reviewCount,
  $status,
  $summary,
  $summaryError,
  $tab,
  $today,
  $transit,
  $view,
  $warehouseId,
} from "../stores/index.ts";

export const $pageTotal = $balances.map(pageTotal);
export const $lastUpdated = combine($balances, $loadedAt, (rows, at) => lastUpdated(rows) ?? at);
export const $expiryDays = combine($expiring, $today, (e, today) =>
  e ? expiryByProduct(e.lots, today) : {},
);
export const $moreLoading = combine(listBalancesFx.pending, $status, (p, s) => p && s !== "loading");
export const $lotsMoreLoading = combine(
  listExpiringLotsFx.pending,
  $lotsStatus,
  (p, s) => p && s !== "loading",
);

// --- mount / warehouse -------------------------------------------------------------------------------
$mounted.on(pageMounted, () => true);
$today.on(pageMounted, (_, { today }) => today);
sample({
  clock: pageMounted,
  fn: ({ canListStaff }) => ({ canListStaff }),
  target: refsRequested,
});

/** The warehouse is known (mount with cached refs, or refs answered / branch changed after mount). */
const warehouseReady = sample({
  clock: [
    sample({ clock: pageMounted, source: $warehouseId }),
    sample({
      clock: $warehouseId.updates,
      source: $mounted,
      fn: (_, id) => id,
      filter: (mounted) => mounted,
    }),
  ],
  filter: (id): id is string => id !== null,
});

// --- balances ------------------------------------------------------------------------------------------
$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(lowOnlyToggled, (f, lowOnly) => ({ ...f, lowOnly }));

sample({
  clock: [
    warehouseReady,
    searchChanged,
    lowOnlyToggled,
    reloadRequested,
    // a write changed the stock
    createTransferFx.done,
    sendTransferFx.done,
    receiveTransferFx.done,
    cancelTransferFx.done,
    postCountFx.done,
    cancelCountFx.done,
    submitWriteOffFx.done,
    repostWriteOffFx.done,
  ],
  source: { warehouseId: $warehouseId, filters: $filters },
  filter: ({ warehouseId }) => warehouseId !== null,
  fn: ({ warehouseId, filters }) => ({ warehouseId: warehouseId ?? "", filters, cursor: null }),
  target: listBalancesFx,
});
sample({
  clock: moreRequested,
  source: { warehouseId: $warehouseId, filters: $filters, cursor: $cursor, pending: listBalancesFx.pending },
  filter: ({ warehouseId, cursor, pending }) => warehouseId !== null && cursor !== null && !pending,
  fn: ({ warehouseId, filters, cursor }) => ({ warehouseId: warehouseId ?? "", filters, cursor }),
  target: listBalancesFx,
});
// An answer for filters / a warehouse that are no longer current is dropped.
const balancesLoaded = sample({
  clock: listBalancesFx.done,
  source: { filters: $filters, warehouseId: $warehouseId },
  filter: (current, { params }) =>
    current.warehouseId === params.warehouseId && sameFilters(current.filters, params.filters),
  fn: (_, payload) => payload,
});
$balances.on(balancesLoaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$cursor.on(balancesLoaded, (_, { result }) => result.next_cursor);
$loadedAt.on(balancesLoaded, () => new Date().toISOString());
$status
  .on(listBalancesFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(balancesLoaded, () => "idle")
  .on(listBalancesFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listBalancesFx.failData, (_, e) => e).reset(listBalancesFx);

// --- expiring lots view ----------------------------------------------------------------------------------
$view.on(viewChanged, (_, v) => v);
sample({
  clock: [
    sample({ clock: viewChanged, filter: (v) => v === "expiring" }),
    sample({
      clock: [warehouseReady, reloadRequested, submitWriteOffFx.done],
      source: $view,
      filter: (v) => v === "expiring",
    }),
  ],
  source: $warehouseId,
  filter: (id): id is string => id !== null,
  fn: (warehouseId) => ({ warehouseId: warehouseId ?? "", cursor: null }),
  target: listExpiringLotsFx,
});
sample({
  clock: lotsMoreRequested,
  source: { warehouseId: $warehouseId, cursor: $lotsCursor, pending: listExpiringLotsFx.pending },
  filter: ({ warehouseId, cursor, pending }) => warehouseId !== null && cursor !== null && !pending,
  fn: ({ warehouseId, cursor }) => ({ warehouseId: warehouseId ?? "", cursor }),
  target: listExpiringLotsFx,
});
// An answer for another warehouse is dropped (WEB-05).
const lotsLoaded = sample({
  clock: listExpiringLotsFx.done,
  source: $warehouseId,
  filter: (current, { params }) => current === params.warehouseId,
  fn: (_, payload) => payload,
});
$lots
  .on(lotsLoaded, (list, { params, result }) => (params.cursor ? [...list, ...result.items] : result.items))
  .reset($warehouseId.updates);
$lotsCursor.on(lotsLoaded, (_, { result }) => result.next_cursor).reset($warehouseId.updates);
$lotsStatus
  .on(listExpiringLotsFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(lotsLoaded, () => "idle")
  .on(listExpiringLotsFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$lotsError.on(listExpiringLotsFx.failData, (_, e) => e).reset(listExpiringLotsFx);

// Product cards (barcode, unit, category, marking) of the rows shown.
sample({
  clock: [listBalancesFx.doneData, listExpiringLotsFx.doneData],
  fn: (page) => page.items.map((r) => r.product_id),
  target: productsRequested,
});

// --- KPI / badges ----------------------------------------------------------------------------------------
/** A write changed the stock, or «Yangilash» — re-read the KPI (one at a time, WEB-10). */
const refreshWanted = sample({
  clock: [
    summaryRefreshRequested,
    createTransferFx.done,
    postTransferFx.done,
    sendTransferFx.done,
    receiveTransferFx.done,
    cancelTransferFx.done,
    createCountFx.done,
    submitCountFx.done,
    postCountFx.done,
    cancelCountFx.done,
    submitWriteOffFx.done,
    repostWriteOffFx.done,
  ],
  fn: () => undefined,
});
const refreshRun = createEvent();
// A new warehouse is read at once; other refreshes wait for the running summary, then run once.
sample({ clock: warehouseReady, fn: () => undefined, target: refreshRun });
sample({
  clock: refreshWanted,
  source: loadSummaryFx.pending,
  filter: (pending) => !pending,
  fn: () => undefined,
  target: refreshRun,
});
$refreshQueued
  .on(
    sample({ clock: refreshWanted, source: loadSummaryFx.pending, filter: (pending) => pending }),
    () => true,
  )
  .reset(refreshRun);
sample({
  clock: loadSummaryFx.finally,
  source: $refreshQueued,
  filter: (queued) => queued,
  fn: () => undefined,
  target: refreshRun,
});

const refreshSummary = sample({
  clock: refreshRun,
  source: { warehouseId: $warehouseId, branchId: $branchId, today: $today },
  filter: (s): s is { warehouseId: string; branchId: string | null; today: string } => s.warehouseId !== null,
});
sample({ clock: refreshSummary, fn: ({ warehouseId }) => warehouseId, target: loadSummaryFx });
sample({ clock: refreshSummary, fn: ({ warehouseId }) => warehouseId, target: loadExpiringFx });
sample({ clock: refreshSummary, fn: ({ warehouseId }) => warehouseId, target: loadReviewCountFx });
const branchRefresh = sample({
  clock: refreshSummary,
  filter: (s): s is { warehouseId: string; branchId: string; today: string } => s.branchId !== null,
});
sample({ clock: branchRefresh, fn: ({ branchId }) => branchId, target: loadTransitFx });
sample({
  clock: branchRefresh,
  fn: ({ branchId, today }) => ({ branchId, from: digestFrom(today) }),
  target: loadDigestFx,
});

// Answers for a warehouse / branch that is no longer current are dropped (WEB-05).
sample({
  clock: loadSummaryFx.done,
  source: $warehouseId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
  target: $summary,
});
sample({
  clock: loadSummaryFx.fail,
  source: $warehouseId,
  filter: (current, { params }) => current === params,
  fn: (_, { error }) => error,
  target: $summaryError,
});
sample({
  clock: loadExpiringFx.done,
  source: $warehouseId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
  target: $expiring,
});
sample({
  clock: loadReviewCountFx.done,
  source: $warehouseId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
  target: $reviewCount,
});
sample({
  clock: loadTransitFx.done,
  source: $branchId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
  target: $transit,
});
sample({
  clock: loadDigestFx.done,
  source: $branchId,
  filter: (current, { params }) => current === params.branchId,
  fn: (_, { result }) => result,
  target: $digest,
});
sample({
  clock: loadDigestFx.fail,
  source: $branchId,
  filter: (current, { params }) => current === params.branchId,
  fn: (_, { error }) => error,
  target: $digestError,
});
$summaryError.reset(loadSummaryFx);
$digestError.reset(loadDigestFx);
for (const store of [$summary, $expiring, $transit, $reviewCount, $digest, $summaryError, $digestError]) {
  store.reset($warehouseId.updates);
}
$refreshQueued.reset($warehouseId.updates);

// --- tabs ----------------------------------------------------------------------------------------------
$tab.on(tabChanged, (_, tab) => tab).on(createCountFx.done, () => "counts");
sample({
  clock: tabChanged,
  filter: (tab) => tab === "transfers",
  fn: () => undefined,
  target: transfersOpened,
});
sample({
  clock: [sample({ clock: tabChanged, filter: (tab) => tab === "counts" }), createCountFx.done],
  fn: () => undefined,
  target: countsOpened,
});
// A new transfer is listed in its tab.
sample({ clock: createTransferFx.done, fn: () => "transfers" as const, target: tabChanged });
