/**
 * WEB-12 (Bosqich 4) — topbar bell (06 §1.9): the same alerts as BO-02 «Diqqat talab qiladi»
 * (`GET /api/v1/reports/dashboard` → `alerts[]`, 20 §17) for the topbar branch («Barcha filiallar» =
 * every branch of the user). Read when the bell mounts, every 60 s while it is mounted and online, when
 * the panel opens and when the branch changes. A failed read keeps the last list (the bell is a hint).
 * The bell itself is shown only with `reports.sales.view` (the endpoint's permission).
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";
import { interval } from "patronum";

import { api, toApiError, type ApiError } from "@shared/api";
import type { AlertOut } from "@shared/models";
import { $isOnline } from "@shared/state/network";
import { $activeBranchId, ALL_BRANCHES } from "@shared/state/session";

export const ALERTS_POLL_MS = 60_000;

export const bellMounted = createEvent();
export const bellUnmounted = createEvent();
/** The panel opened — read again. */
export const bellOpened = createEvent();

/** Topbar branch → `branch_id` (`null` = «Barcha filiallar» / not chosen). */
export function branchParam(active: string | null): string | null {
  return active && active !== ALL_BRANCHES ? active : null;
}

export const fetchAlertsFx = createEffect<string | null, AlertOut[], ApiError>(async (branchId) => {
  try {
    const dashboard = await api.reports.getDashboard({
      period: "today",
      ...(branchId ? { branch_id: branchId } : {}),
    });
    // A partial / older answer without `alerts` counts as none.
    return Array.isArray(dashboard.alerts) ? dashboard.alerts : [];
  } catch (e) {
    throw toApiError(e);
  }
});

const $branchId = $activeBranchId.map(branchParam);
const $mounted = createStore(0)
  .on(bellMounted, (n) => n + 1)
  .on(bellUnmounted, (n) => Math.max(0, n - 1));
export const $alerts = createStore<AlertOut[] | null>(null, { skipVoid: false });
export const $alertsError = createStore<ApiError | null>(null, { skipVoid: false });

const started = sample({ clock: bellMounted, source: $mounted, filter: (n) => n === 1 });
const stopped = sample({ clock: bellUnmounted, source: $mounted, filter: (n) => n === 0 });
const poll = interval({ timeout: ALERTS_POLL_MS, start: started, stop: stopped });
const branchChanged = sample({ clock: $branchId.updates, source: $mounted, filter: (n) => n > 0 });

sample({
  clock: [started, poll.tick, bellOpened, branchChanged],
  source: combine({
    online: $isOnline,
    pending: fetchAlertsFx.pending,
    mounted: $mounted,
    branchId: $branchId,
  }),
  filter: ({ online, pending, mounted }) => online && !pending && mounted > 0,
  fn: ({ branchId }) => branchId,
  target: fetchAlertsFx,
});
// An answer for another branch is dropped.
sample({
  clock: fetchAlertsFx.done,
  source: $branchId,
  filter: (current, { params }) => current === params,
  // Never undefined in the store (a malformed answer must not break the layout).
  fn: (_, { result }): AlertOut[] => (Array.isArray(result) ? result : []),
  target: $alerts,
});
$alertsError.on(fetchAlertsFx.failData, (_, e) => e).reset(fetchAlertsFx.done);
$alerts.reset(stopped, branchChanged);

/** Badge text: nothing for 0 / unknown, «9+» above 9. */
export function bellBadge(alerts: readonly AlertOut[] | null): string | null {
  if (!alerts || alerts.length === 0) return null;
  return alerts.length > 9 ? "9+" : String(alerts.length);
}

/** The most urgent severity (badge colour). */
export function bellTone(alerts: readonly AlertOut[] | null): "destructive" | "warning" | "info" | null {
  if (!alerts || alerts.length === 0) return null;
  if (alerts.some((a) => a.severity === "critical")) return "destructive";
  if (alerts.some((a) => a.severity === "warning")) return "warning";
  return "info";
}
