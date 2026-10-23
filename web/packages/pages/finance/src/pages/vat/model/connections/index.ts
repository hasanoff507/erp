/** BO-07 wiring — sample() only (24 §2). */
import { combine, sample } from "effector";

import { listMovesFx, loadSummaryFx } from "../effects/index.ts";
import {
  movesDocTypeChanged,
  movesKindChanged,
  movesMoreRequested,
  movesReloadRequested,
  pageMounted,
  periodChanged,
  summaryReloadRequested,
} from "../events/index.ts";
import { isPeriodKey, movesTotals, periodMonths, summarize } from "../lib/index.ts";
import {
  $moves,
  $movesCursor,
  $movesError,
  $movesFilters,
  $movesMonthIndex,
  $movesStatus,
  $period,
  $summary,
  $summaryError,
  $summaryStatus,
  $today,
} from "../stores/index.ts";
import type { MovesRequest } from "../types/index.ts";

export const $periodMonths = $period.map(periodMonths);
export const $movesTotals = $moves.map(movesTotals);
/** More rows: a cursor in this month, or further months of the quarter. */
export const $movesHasMore = combine(
  $movesCursor,
  $movesMonthIndex,
  $periodMonths,
  (cursor, index, months) => cursor !== null || index < months.length - 1,
);
export const $movesMoreLoading = combine(
  listMovesFx.pending,
  $movesStatus,
  (pending, status) => pending && status !== "loading",
);

// --- period ------------------------------------------------------------------------------------------
$today.on(pageMounted, (_, { today }) => today);
sample({ clock: pageMounted, fn: ({ today }) => today.slice(0, 7), target: periodChanged });
/** A valid period choice (re-choosing the same period reloads too). */
const periodApplied = sample({ clock: periodChanged, filter: isPeriodKey });
$period.on(periodApplied, (_, next) => next);

// --- summary -----------------------------------------------------------------------------------------
sample({
  clock: [periodApplied, sample({ clock: summaryReloadRequested, source: $period })],
  fn: (period) => ({ period, months: periodMonths(period) }),
  target: loadSummaryFx,
});
const summaryLoaded = sample({
  clock: loadSummaryFx.done,
  source: $period,
  filter: (period, { params }) => period === params.period,
  fn: (period, { result }) => summarize(period, result),
});
$summary.on(summaryLoaded, (_, view) => view);
const summaryFailed = sample({
  clock: loadSummaryFx.fail,
  source: $period,
  filter: (period, { params }) => period === params.period,
});
$summaryStatus
  .on(loadSummaryFx, () => "loading")
  .on(summaryLoaded, () => "idle")
  .on(summaryFailed, () => "error");
$summaryError.on(loadSummaryFx.failData, (_, e) => e).reset(loadSummaryFx);

// --- QQS registri (vat_moves) ------------------------------------------------------------------------
$movesFilters
  .on(movesKindChanged, (f, kind) => ({ ...f, kind }))
  .on(movesDocTypeChanged, (f, docType) => ({ ...f, docType }));

sample({
  clock: periodApplied,
  source: $movesFilters,
  fn: (filters, period): MovesRequest => ({
    months: periodMonths(period),
    monthIndex: 0,
    filters,
    cursor: null,
  }),
  target: listMovesFx,
});
sample({
  clock: [$movesFilters.updates, movesReloadRequested],
  source: { months: $periodMonths, filters: $movesFilters },
  filter: ({ months }) => months.length > 0,
  fn: ({ months, filters }): MovesRequest => ({ months, monthIndex: 0, filters, cursor: null }),
  target: listMovesFx,
});
sample({
  clock: movesMoreRequested,
  source: {
    months: $periodMonths,
    filters: $movesFilters,
    index: $movesMonthIndex,
    cursor: $movesCursor,
    pending: listMovesFx.pending,
  },
  filter: ({ months, index, cursor, pending }) => !pending && (cursor !== null || index < months.length - 1),
  fn: ({ months, filters, index, cursor }): MovesRequest =>
    cursor !== null
      ? { months, monthIndex: index, filters, cursor }
      : { months, monthIndex: index + 1, filters, cursor: null },
  target: listMovesFx,
});

// Answers for another period / filter set are dropped.
const movesLoaded = sample({
  clock: listMovesFx.done,
  source: { months: $periodMonths, filters: $movesFilters },
  filter: ({ months, filters }, { params }) =>
    months.join() === params.months.join() &&
    filters.kind === params.filters.kind &&
    filters.docType === params.filters.docType,
  fn: (_, payload) => payload,
});
const firstPage = (p: MovesRequest) => p.monthIndex === 0 && p.cursor === null;
$moves.on(movesLoaded, (list, { params, result }) =>
  firstPage(params) ? result.items : [...list, ...result.items],
);
$movesMonthIndex.on(movesLoaded, (_, { params }) => params.monthIndex);
$movesCursor.on(movesLoaded, (_, { result }) => result.next_cursor);
$movesStatus
  .on(listMovesFx, (status, params) => (firstPage(params) ? "loading" : status))
  .on(movesLoaded, () => "idle")
  .on(listMovesFx.fail, (status, { params }) => (firstPage(params) ? "error" : status));
$movesError.on(listMovesFx.failData, (_, e) => e).reset(listMovesFx);
