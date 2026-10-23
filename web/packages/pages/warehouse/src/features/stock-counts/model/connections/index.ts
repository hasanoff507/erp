/** Inventarizatsiyalar wiring — sample() only (24 §2). */
import { combine, merge, sample } from "effector";

import { $currentWarehouse } from "#/entities/refs/index.ts";

import {
  cancelCountFx,
  createCountFx,
  getCountFx,
  listCountsFx,
  postCountFx,
  recordLinesFx,
  submitCountFx,
} from "../effects/index.ts";
import {
  actionErrorDismissed,
  countSelected,
  countedChanged,
  countsOpened,
  detailReloadRequested,
  draftsReset,
  extraLineAdded,
  filterChanged,
  lineFilterChanged,
  lineSearchChanged,
  moreRequested,
  reloadRequested,
} from "../events/index.ts";
import { changedLines, countTotals, draftsAfterSave, filterLines } from "../lib/index.ts";
import {
  $actionError,
  $counts,
  $cursor,
  $detail,
  $detailError,
  $detailStatus,
  $drafts,
  $error,
  $extras,
  $filter,
  $lineFilter,
  $lineSearch,
  $opened,
  $selectedId,
  $status,
} from "../stores/index.ts";

/** The current branch's warehouse — the list shows its counts only (WEB-04). */
export const $warehouseId = $currentWarehouse.map((w) => w?.id ?? null);

export const $moreLoading = combine(listCountsFx.pending, $status, (p, s) => p && s !== "loading");
export const $totals = $detail.map((d) => (d ? countTotals(d.lines) : null));
export const $visibleLines = combine($detail, $lineFilter, $lineSearch, (d, f, q) =>
  d ? filterLines(d.lines, f, q) : [],
);
/** Unsaved counted values → `POST /lines` body. */
export const $pendingLines = combine($detail, $extras, $drafts, (d, extras, drafts) =>
  d ? changedLines(d.lines, extras, drafts) : [],
);
export const $acting = combine(
  [recordLinesFx.pending, submitCountFx.pending, postCountFx.pending, cancelCountFx.pending],
  (flags) => flags.some(Boolean),
);

// --- list ------------------------------------------------------------------------------------------
$filter.on(filterChanged, (_, s) => s);
$opened.on(countsOpened, () => true);
sample({
  clock: [countsOpened, filterChanged, reloadRequested],
  source: { status: $filter, warehouseId: $warehouseId },
  fn: ({ status, warehouseId }) => ({ warehouseId, status, cursor: null }),
  target: listCountsFx,
});
sample({
  clock: moreRequested,
  source: { status: $filter, warehouseId: $warehouseId, cursor: $cursor, pending: listCountsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ status, warehouseId, cursor }) => ({ warehouseId, status, cursor }),
  target: listCountsFx,
});
// Opened before the warehouses were known (or the branch changed): read the right warehouse's counts.
sample({
  clock: $warehouseId.updates,
  source: $opened,
  filter: (opened) => opened,
  fn: () => undefined,
  target: reloadRequested,
});
const pageLoaded = sample({
  clock: listCountsFx.done,
  source: { status: $filter, warehouseId: $warehouseId },
  filter: (current, { params }) =>
    current.status === params.status && current.warehouseId === params.warehouseId,
  fn: (_, payload) => payload,
});
$counts.on(pageLoaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$cursor.on(pageLoaded, (_, { result }) => result.next_cursor);
$status
  .on(listCountsFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(pageLoaded, () => "idle")
  .on(listCountsFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listCountsFx.failData, (_, e) => e).reset(listCountsFx);

// --- detail ----------------------------------------------------------------------------------------
$selectedId.on(countSelected, (_, id) => id).on(createCountFx.doneData, (_, c) => c.id);
sample({ clock: countSelected, filter: (id): id is string => id !== null, target: getCountFx });
sample({
  clock: detailReloadRequested,
  source: $selectedId,
  filter: (id): id is string => id !== null,
  target: getCountFx,
});
const detailLoaded = sample({
  clock: getCountFx.done,
  source: $selectedId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
});
const written = merge([
  createCountFx.doneData,
  recordLinesFx.doneData,
  submitCountFx.doneData,
  cancelCountFx.doneData,
]);
$detail.on([detailLoaded, written], (_, c) => c).reset(countSelected);
$detailStatus
  .on(getCountFx, () => "loading")
  .on(getCountFx.done, () => "idle")
  .on(getCountFx.fail, () => "error")
  .reset(countSelected);
$detailError.on(getCountFx.failData, (_, e) => e).reset(getCountFx, countSelected);

// The post answer has no lines — the document is re-read.
sample({ clock: postCountFx.done, fn: ({ params }) => params.id, target: getCountFx });

// The list changes with every status change.
sample({
  clock: [createCountFx.done, submitCountFx.done, postCountFx.done, cancelCountFx.done],
  fn: () => undefined,
  target: reloadRequested,
});

// --- line entry ------------------------------------------------------------------------------------
$drafts
  .on(countedChanged, (d, { productId, value }) => ({ ...d, [productId]: value }))
  .on(extraLineAdded, (d, { productId }) => (productId in d ? d : { ...d, [productId]: "" }))
  // Only what was saved is dropped — a value typed during the request survives (WEB-12).
  .on(recordLinesFx.done, (d, { params, result }) => draftsAfterSave(d, params.lines, result.lines))
  .reset(draftsReset, countSelected);
$extras
  .on(extraLineAdded, (list, line) =>
    list.some((l) => l.productId === line.productId) ? list : [...list, line],
  )
  // A saved extra is a count line now.
  .on(recordLinesFx.done, (list, { params }) =>
    list.filter((e) => !params.lines.some((l) => l.product_id === e.productId)),
  )
  .reset(draftsReset, countSelected);
$lineFilter.on(lineFilterChanged, (_, f) => f).reset(countSelected);
$lineSearch.on(lineSearchChanged, (_, q) => q).reset(countSelected);

$actionError
  .on([recordLinesFx.failData, submitCountFx.failData, cancelCountFx.failData], (_, e) => e)
  .reset(actionErrorDismissed, countSelected, recordLinesFx, submitCountFx, cancelCountFx);
