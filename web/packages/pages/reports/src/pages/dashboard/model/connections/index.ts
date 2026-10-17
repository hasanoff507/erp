/** BO-02 wiring — sample() only (24 §2). */
import { combine, sample } from "effector";

import { $activeBranchId } from "@shared/state/session";

import { loadDashboardFx, loadWeekFx } from "../effects/index.ts";
import { pageMounted, pageUnmounted, periodChanged, reloadRequested } from "../events/index.ts";
import { branchParam, sameDashboardRequest, sameWeekRequest, weekRange } from "../lib/index.ts";
import {
  $dashboard,
  $error,
  $loadedAt,
  $mounted,
  $period,
  $status,
  $today,
  $week,
  $weekError,
} from "../stores/index.ts";
import type { DashboardRequest } from "../types/index.ts";

/** The topbar branch as a report filter (`null` = «Barcha filiallar»). */
export const $branchId = $activeBranchId.map(branchParam);
const $request = combine($period, $branchId, (period, branchId): DashboardRequest => ({ period, branchId }));
const $weekRequest = combine($today, $branchId, (today, branchId) => weekRange(today, branchId));

$mounted.on(pageMounted, () => true).on(pageUnmounted, () => false);
$today.on(pageMounted, (_, { today }) => today);
$period.on(periodChanged, (_, p) => p).reset(pageMounted);

const branchChanged = sample({
  clock: $branchId.updates,
  source: $mounted,
  filter: (mounted) => mounted,
});

sample({
  clock: [pageMounted, periodChanged, reloadRequested, branchChanged],
  source: $request,
  target: loadDashboardFx,
});
sample({
  clock: [pageMounted, reloadRequested, branchChanged],
  source: $weekRequest,
  target: loadWeekFx,
});

// An answer for another period / branch is dropped.
const dashboardLoaded = sample({
  clock: loadDashboardFx.done,
  source: $request,
  filter: (current, { params }) => sameDashboardRequest(current, params),
  fn: (_, { result }) => result,
});
$dashboard.on(dashboardLoaded, (_, d) => d);
$loadedAt.on(dashboardLoaded, () => new Date().toISOString());
$status
  .on(loadDashboardFx, () => "loading")
  .on(dashboardLoaded, () => "idle")
  .on(
    sample({
      clock: loadDashboardFx.fail,
      source: $request,
      filter: (current, { params }) => sameDashboardRequest(current, params),
    }),
    () => "error",
  );
$error
  .on(
    sample({
      clock: loadDashboardFx.fail,
      source: $request,
      filter: (current, { params }) => sameDashboardRequest(current, params),
      fn: (_, { error }) => error,
    }),
    (_, e) => e,
  )
  .reset(loadDashboardFx);
// Another branch: the old figures are not shown under the new filter.
$dashboard.reset(branchChanged);

const weekLoaded = sample({
  clock: loadWeekFx.done,
  source: $weekRequest,
  filter: (current, { params }) => sameWeekRequest(current, params),
  fn: (_, { result }) => result,
});
$week.on(weekLoaded, (_, w) => w).reset(branchChanged);
$weekError.on(loadWeekFx.failData, (_, e) => e).reset(loadWeekFx);
