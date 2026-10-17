/** BO-03 wiring — sample() only (24 §2). */
import { combine, createEvent, sample } from "effector";

import { refsRequested } from "#/entities/refs/index.ts";
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
  listExpiringLotsFx,
  loadDigestFx,
  loadExpiringFx,
  loadReviewCountFx,
  loadStockFx,
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
import {
  digestFrom,
  expiryByProduct,
  filterItems,
  pageTotal,
  stockScope,
  summarize,
  unitsOf,
} from "../lib/index.ts";
import {
  $branchId,
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
  $shown,
  $status,
  $stock,
  $tab,
  $today,
  $transit,
  $view,
  $warehouseId,
} from "../stores/index.ts";
import { BALANCE_PAGE_SIZE } from "../types/index.ts";

/** The report scope: the branch's warehouse, or «Barcha filiallar» (consolidated). */
export const $scope = combine($branchId, $warehouseId, stockScope);
/** Rows after the search / «Faqat kam qoldiq» filters (client side — the report is complete). */
export const $filtered = combine($stock, $filters, (stock, filters) =>
  stock ? filterItems(stock.items, filters) : [],
);
/** Rows shown («Yana yuklash» adds a page). */
export const $balances = combine($filtered, $shown, (rows, shown) => rows.slice(0, shown));
export const $hasMore = combine($filtered, $shown, (rows, shown) => rows.length > shown);
export const $summary = $stock.map((s) => (s ? summarize(s) : null));
/** The KPI could not be read (WEB-06) — the cards show it with «Qayta urinish». */
export const $summaryError = combine($stock, $error, (s, e) => (s ? null : e));
export const $consolidated = $stock.map((s) => s?.consolidated ?? false);
export const $units = $stock.map(unitsOf);
export const $pageTotal = $balances.map(pageTotal);
export const $lastUpdated = $loadedAt;
export const $expiryDays = combine($expiring, $today, (e, today) =>
  e ? expiryByProduct(e.lots, today) : {},
);
export const $lotsMoreLoading = combine(
  listExpiringLotsFx.pending,
  $lotsStatus,
  (p, s) => p && s !== "loading",
);

// --- mount / scope ---------------------------------------------------------------------------------------
$mounted.on(pageMounted, () => true);
$today.on(pageMounted, (_, { today }) => today);
sample({
  clock: pageMounted,
  fn: ({ canListStaff }) => ({ canListStaff }),
  target: refsRequested,
});

/** The scope is known (mount, or refs answered / branch changed after mount). */
const scopeReady = sample({
  clock: [
    sample({ clock: pageMounted, source: $scope }),
    sample({
      clock: $scope.updates,
      source: $mounted,
      fn: (_, scope) => scope,
      filter: (mounted) => mounted,
    }),
  ],
  filter: (scope): scope is string => scope !== null,
});
/** A branch's warehouse is known — lots, badges and the digest are per warehouse / branch. */
const warehouseReady = sample({
  clock: scopeReady,
  source: $warehouseId,
  filter: (id): id is string => id !== null,
});

// --- the stock report (rows + KPI), one run at a time (WEB-10) -----------------------------------------
$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(lowOnlyToggled, (f, lowOnly) => ({ ...f, lowOnly }));
$shown.on(moreRequested, (n) => n + BALANCE_PAGE_SIZE).reset(searchChanged, lowOnlyToggled, $scope.updates);

/** A write changed the stock, or «Yangilash» / «Qayta urinish» — re-read the report. */
const refreshWanted = sample({
  clock: [
    summaryRefreshRequested,
    reloadRequested,
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
// A new scope is read at once; other refreshes wait for the running read, then run once.
sample({ clock: scopeReady, fn: () => undefined, target: refreshRun });
sample({
  clock: refreshWanted,
  source: loadStockFx.pending,
  filter: (pending) => !pending,
  fn: () => undefined,
  target: refreshRun,
});
$refreshQueued
  .on(sample({ clock: refreshWanted, source: loadStockFx.pending, filter: (pending) => pending }), () => true)
  .reset(refreshRun);
sample({
  clock: loadStockFx.finally,
  source: $refreshQueued,
  filter: (queued) => queued,
  fn: () => undefined,
  target: refreshRun,
});

const refresh = sample({
  clock: refreshRun,
  source: { scope: $scope, warehouseId: $warehouseId, branchId: $branchId, today: $today },
});
sample({
  clock: refresh,
  filter: ({ scope }) => scope !== null,
  fn: ({ scope }) => scope ?? "",
  target: loadStockFx,
});

// Answers for a scope that is no longer current are dropped (WEB-05).
const stockLoaded = sample({
  clock: loadStockFx.done,
  source: $scope,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
});
const stockFailed = sample({
  clock: loadStockFx.fail,
  source: $scope,
  filter: (current, { params }) => current === params,
  fn: (_, { error }) => error,
});
$stock.on(stockLoaded, (_, s) => s);
$loadedAt.on(stockLoaded, () => new Date().toISOString());
$status
  .on(sample({ clock: loadStockFx, source: $stock, filter: (s) => s === null }), () => "loading")
  .on(stockLoaded, () => "idle")
  .on(stockFailed, () => "error");
$error.on(stockFailed, (_, e) => e).reset(stockLoaded);

// --- expiring lots view (one warehouse) ------------------------------------------------------------------
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

// --- per-warehouse KPI / badges -----------------------------------------------------------------------------
const warehouseRefresh = sample({
  clock: refresh,
  filter: (s): s is { scope: string; warehouseId: string; branchId: string | null; today: string } =>
    s.warehouseId !== null && s.branchId !== null,
});
sample({ clock: warehouseRefresh, fn: ({ warehouseId }) => warehouseId, target: loadExpiringFx });
sample({ clock: warehouseRefresh, fn: ({ warehouseId }) => warehouseId, target: loadReviewCountFx });
sample({ clock: warehouseRefresh, fn: ({ branchId }) => branchId ?? "", target: loadTransitFx });
sample({
  clock: warehouseRefresh,
  fn: ({ branchId, today }) => ({ branchId: branchId ?? "", from: digestFrom(today) }),
  target: loadDigestFx,
});

// Answers for a warehouse / branch that is no longer current are dropped (WEB-05).
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
$digestError.reset(loadDigestFx);
for (const store of [$stock, $expiring, $transit, $reviewCount, $digest, $digestError]) {
  store.reset($scope.updates);
}
$error.reset($scope.updates);
$refreshQueued.reset($scope.updates);

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
