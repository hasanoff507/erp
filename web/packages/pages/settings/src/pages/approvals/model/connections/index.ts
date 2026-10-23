/** BO-16 wiring — sample() only (24 §2) + the poll clock (patronum `interval`). */
import { combine, sample } from "effector";
import { interval } from "patronum";

import { $isOnline } from "@shared/state/network";

import { approveFx, listRequestsFx, listResolvedFx, readClockFx, rejectFx } from "../effects/index.ts";
import {
  approveSubmitted,
  clockTicked,
  kindChanged,
  moreRequested,
  pageMounted,
  pageUnmounted,
  pinErrorCleared,
  pollingStarted,
  rejectSubmitted,
  reloadRequested,
  tabChanged,
} from "../events/index.ts";
import {
  dropDecided,
  filterByKind,
  isPinValid,
  isReasonValid,
  isStaleDecision,
  kindCounts,
  resolvedOn,
  without,
} from "../lib/index.ts";
import {
  $approveErrors,
  $busy,
  $cursor,
  $error,
  $kind,
  $loaded,
  $mounted,
  $now,
  $pendingIds,
  $rejectErrors,
  $requests,
  $resolvedToday,
  $status,
  $tab,
  $today,
} from "../stores/index.ts";
import { POLL_MS } from "../types/index.ts";

/** Requests of the active kind chip. */
export const $visible = combine($requests, $kind, filterByKind);
/** Chip counters of the loaded list. */
export const $kindCounts = $requests.map(kindCounts);
/** «Kutilmoqda (N)» on every tab; `null` until the pending queue was loaded once. */
export const $pendingCount = $pendingIds.map((ids) => (ids === null ? null : ids.length));
export const $moreLoading = combine(
  listRequestsFx.pending,
  $status,
  (pending, status) => pending && status !== "loading",
);

// --- mount / clock ---------------------------------------------------------------------------------
$today.on(pageMounted, (_, { today }) => today);
$now.on(pageMounted, (_, { now }) => now).on(clockTicked, (_, now) => now);
$mounted.on(pageMounted, () => true).on(pageUnmounted, () => false);

const poll = interval({ timeout: POLL_MS, start: pollingStarted, stop: pageUnmounted });
sample({ clock: poll.tick, target: readClockFx });
sample({ clock: readClockFx.doneData, target: clockTicked });

// --- list ------------------------------------------------------------------------------------------
$tab.on(tabChanged, (_, tab) => tab);
$kind.on(kindChanged, (_, kind) => kind).reset(tabChanged);

sample({
  clock: [pageMounted, reloadRequested],
  source: $tab,
  fn: (tab) => ({ tab, cursor: null, silent: false }),
  target: listRequestsFx,
});
sample({
  clock: tabChanged,
  fn: (tab) => ({ tab, cursor: null, silent: false }),
  target: listRequestsFx,
});
sample({
  clock: moreRequested,
  source: { tab: $tab, cursor: $cursor, pending: listRequestsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ tab, cursor }) => ({ tab, cursor, silent: false }),
  target: listRequestsFx,
});
// Quiet refresh of the pending queue on every tick (online, nothing in flight, first page only).
sample({
  clock: clockTicked,
  source: {
    tab: $tab,
    online: $isOnline,
    pending: listRequestsFx.pending,
    cursor: $cursor,
    mounted: $mounted,
  },
  filter: ({ tab, online, pending, cursor, mounted }) =>
    mounted && online && !pending && tab === "pending" && cursor === null,
  fn: ({ tab }) => ({ tab, cursor: null, silent: true }),
  target: listRequestsFx,
});

// An answer for a tab that is no longer active is dropped.
const pageLoaded = sample({
  clock: listRequestsFx.done,
  source: $tab,
  filter: (tab, { params }) => tab === params.tab,
  fn: (_, payload) => payload,
});
$requests
  .on(pageLoaded, (list, { params, result }) => (params.cursor ? [...list, ...result.items] : result.items))
  .reset(tabChanged);
$cursor.on(pageLoaded, (_, { result }) => result.next_cursor).reset(tabChanged);
$pendingIds
  .on(pageLoaded.filter({ fn: ({ params }) => params.tab === "pending" }), (ids, { params, result }) => [
    ...(params.cursor ? (ids ?? []) : []),
    ...result.items.filter((r) => r.status === "pending").map((r) => r.id),
  ])
  .on(approveFx.done, (ids, { params }) => ids?.filter((id) => id !== params.id) ?? null)
  .on(rejectFx.done, (ids, { params }) => ids?.filter((id) => id !== params.id) ?? null);
$loaded.on(pageLoaded, () => true).reset(tabChanged);
$status
  .on(listRequestsFx, (status, { cursor, silent }) => (cursor === null && !silent ? "loading" : status))
  .on(pageLoaded, () => "idle")
  .on(listRequestsFx.fail, (status, { params }) =>
    params.cursor === null && !params.silent ? "error" : status,
  );
$error
  .on(listRequestsFx.fail, (current, { params, error }) => (params.silent ? current : error))
  .on(pageLoaded, () => null);

// --- «Bugun hal qilinganlar» -------------------------------------------------------------------------
sample({ clock: [pageMounted, approveFx.done, rejectFx.done], target: listResolvedFx });
sample({
  clock: listResolvedFx.doneData,
  source: $today,
  fn: (today, list) => resolvedOn(list, today),
  target: $resolvedToday,
});

// --- decisions -------------------------------------------------------------------------------------
sample({
  clock: approveSubmitted,
  source: $busy,
  filter: (busy, { id, pin }) => !busy.includes(id) && isPinValid(pin),
  fn: (_, req) => req,
  target: approveFx,
});
sample({
  clock: rejectSubmitted,
  source: $busy,
  filter: (busy, { id, reason }) => !busy.includes(id) && isReasonValid(reason),
  fn: (_, { id, reason }) => ({ id, reason: reason.trim() }),
  target: rejectFx,
});
$busy
  .on(approveFx, (ids, { id }) => [...ids, id])
  .on(rejectFx, (ids, { id }) => [...ids, id])
  .on(approveFx.finally, (ids, { params }) => ids.filter((id) => id !== params.id))
  .on(rejectFx.finally, (ids, { params }) => ids.filter((id) => id !== params.id));

$approveErrors
  .on(approveFx.fail, (errs, { params, error }) => ({ ...errs, [params.id]: error }))
  .on(approveFx.done, (errs, { params }) => without(errs, params.id))
  .on(pinErrorCleared, without);
$rejectErrors
  .on(rejectFx.fail, (errs, { params, error }) => ({ ...errs, [params.id]: error }))
  .on(rejectFx.done, (errs, { params }) => without(errs, params.id));

// A decided request leaves the pending list at once (the queue refresh confirms it).
$requests
  .on(approveFx.done, (list, { params }) => dropDecided(list, params.id))
  .on(rejectFx.done, (list, { params }) => dropDecided(list, params.id));

// Decided / expired elsewhere (409 ALREADY_RESOLVED / EXPIRED, 404): show the truth.
sample({
  clock: [approveFx.failData, rejectFx.failData],
  filter: isStaleDecision,
  fn: () => undefined,
  target: reloadRequested,
});
