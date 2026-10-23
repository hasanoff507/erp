/** BO-24 wiring — sample() only (24 §2). */
import { combine, merge, sample } from "effector";

import {
  cancelSettlementFx,
  createSettlementFx,
  getSettlementFx,
  importStatementFx,
  listSettlementsFx,
  loadTransitFx,
  postSettlementFx,
  updateSettlementFx,
} from "../effects/index.ts";
import {
  detailReloadRequested,
  filtersChanged,
  importResultDismissed,
  importedDraftsShown,
  moreRequested,
  pageMounted,
  reloadRequested,
  settlementOpened,
  transitReloadRequested,
} from "../events/index.ts";
import { postedTotals, transitRows } from "../lib/index.ts";
import {
  $cursor,
  $defaultBranchId,
  $detail,
  $detailError,
  $detailStatus,
  $error,
  $filters,
  $importResult,
  $openedId,
  $settlements,
  $status,
  $today,
  $transit,
  $transitStatus,
} from "../stores/index.ts";
import type { ListRequest, SettlementFilters } from "../types/index.ts";

export const $hasMore = $cursor.map((c) => c !== null);
export const $moreLoading = combine(listSettlementsFx.pending, $status, (p, s) => p && s !== "loading");
export const $postedTotals = $settlements.map(postedTotals);
export const $transitView = $transit.map((t) => transitRows(t?.items ?? []));
export const $busy = combine(
  [
    createSettlementFx.pending,
    updateSettlementFx.pending,
    postSettlementFx.pending,
    cancelSettlementFx.pending,
  ],
  (flags) => flags.some(Boolean),
);

const same = (a: SettlementFilters, b: SettlementFilters) =>
  a.branchId === b.branchId &&
  a.method === b.method &&
  a.status === b.status &&
  a.source === b.source &&
  a.from === b.from &&
  a.to === b.to;

$today.on(pageMounted, (_, { today }) => today);
$defaultBranchId.on(pageMounted, (_, { branchId }) => branchId);
$filters.on(pageMounted, (f, { branchId }) => ({ ...f, branchId }));
$importResult.reset(pageMounted, importResultDismissed);

// --- list ----------------------------------------------------------------------------------------------
$filters.on(filtersChanged, (f, patch) => ({ ...f, ...patch }));
$filters.on(importedDraftsShown, (f) => ({ ...f, status: "draft", source: "statement_import" }));
sample({
  clock: [pageMounted, filtersChanged, reloadRequested, importedDraftsShown],
  source: $filters,
  fn: (filters): ListRequest => ({ filters, cursor: null }),
  target: listSettlementsFx,
});
sample({
  clock: moreRequested,
  source: { filters: $filters, cursor: $cursor, pending: listSettlementsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filters, cursor }): ListRequest => ({ filters, cursor }),
  target: listSettlementsFx,
});
const listed = sample({
  clock: listSettlementsFx.done,
  source: $filters,
  filter: (f, { params }) => same(f, params.filters),
  fn: (_, payload) => payload,
});
$settlements.on(listed, (list, { params, result }) =>
  params.cursor === null ? result.items : [...list, ...result.items],
);
$cursor.on(listed, (_, { result }) => result.next_cursor);
$status
  .on(listSettlementsFx, (s, p) => (p.cursor === null ? "loading" : s))
  .on(listed, () => "idle")
  .on(listSettlementsFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listSettlementsFx.failData, (_, e) => e).reset(listSettlementsFx);

// --- transit balances (5710 by branch × method) --------------------------------------------------------
sample({
  clock: [
    pageMounted,
    transitReloadRequested,
    sample({ clock: filtersChanged, filter: (p) => "branchId" in p }),
  ],
  source: $filters,
  fn: (f) => ({ branchId: f.branchId }),
  target: loadTransitFx,
});
$transit.on(loadTransitFx.doneData, (_, t) => t);
$transitStatus
  .on(loadTransitFx, () => "loading")
  .on(loadTransitFx.done, () => "idle")
  .on(loadTransitFx.fail, () => "error");

// --- the open document ---------------------------------------------------------------------------------
$openedId.on(settlementOpened, (_, id) => id);
$detail.on(settlementOpened, (d, id) => (d && d.id === id ? d : null));
const isDocId = (id: string | null): id is string => id !== null && id !== "new";
sample({ clock: settlementOpened, filter: isDocId, target: getSettlementFx });
sample({ clock: detailReloadRequested, source: $openedId, filter: isDocId, target: getSettlementFx });
const detailLoaded = sample({
  clock: getSettlementFx.done,
  source: $openedId,
  filter: (id, { params }) => id === params,
  fn: (_, { result }) => result,
});
$detail.on(detailLoaded, (_, d) => d);
$detailStatus
  .on(getSettlementFx, () => "loading")
  .on(detailLoaded, () => "idle")
  .on(getSettlementFx.fail, () => "error");
$detailError.on(getSettlementFx.failData, (_, e) => e).reset(getSettlementFx, settlementOpened);

// --- writes --------------------------------------------------------------------------------------------
const changed = merge([
  createSettlementFx.done,
  updateSettlementFx.done,
  postSettlementFx.done,
  cancelSettlementFx.done,
  importStatementFx.done,
]);
sample({ clock: changed, fn: () => undefined, target: reloadRequested });
sample({
  clock: merge([postSettlementFx.done, cancelSettlementFx.done, importStatementFx.done]),
  fn: () => undefined,
  target: transitReloadRequested,
});
sample({
  clock: merge([updateSettlementFx.done, postSettlementFx.done, cancelSettlementFx.done]),
  fn: () => undefined,
  target: detailReloadRequested,
});
$importResult.on(importStatementFx.doneData, (_, r) => r);
