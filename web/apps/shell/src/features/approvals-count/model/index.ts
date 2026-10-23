/**
 * WEB-12 (Bosqich 3 part) — pending approvals badge of the «Tasdiqlash navbati» sidebar item (06 §1.9):
 * `GET /api/v1/approval-requests?status=pending` (18 §9.3 — the server returns only the kinds the user
 * may decide), refreshed every 30 s while a sidebar is mounted and online, and on navigation. A failed
 * read keeps the last count (the badge is a hint; BO-16 is the truth).
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";
import { interval } from "patronum";

import { api, toApiError, type ApiError } from "@shared/api";
import { $isOnline } from "@shared/state/network";

export const APPROVALS_POLL_MS = 30_000;
/** One page is enough for the badge: more than this shows «99+». */
export const APPROVALS_BADGE_LIMIT = 100;

/** A sidebar that shows the item mounted / unmounted (the rail and the drawer may both be mounted). */
export const approvalsBadgeMounted = createEvent();
export const approvalsBadgeUnmounted = createEvent();
/** Refresh now (navigation, a decision in BO-16). */
export const approvalsCountRequested = createEvent();

export const fetchPendingCountFx = createEffect<void, number, ApiError>(async () => {
  try {
    const page = await api.approvals.listRequests({ status: "pending", limit: APPROVALS_BADGE_LIMIT });
    return page.items.length;
  } catch (e) {
    throw toApiError(e);
  }
});

const $subscribers = createStore(0)
  .on(approvalsBadgeMounted, (n) => n + 1)
  .on(approvalsBadgeUnmounted, (n) => Math.max(0, n - 1));
export const $approvalsPending = createStore<number | null>(null, { skipVoid: false });
$approvalsPending.on(fetchPendingCountFx.doneData, (_, n) => n);

const started = sample({ clock: approvalsBadgeMounted, source: $subscribers, filter: (n) => n === 1 });
const stopped = sample({ clock: approvalsBadgeUnmounted, source: $subscribers, filter: (n) => n === 0 });
const poll = interval({ timeout: APPROVALS_POLL_MS, start: started, stop: stopped });

sample({
  clock: [started, poll.tick, approvalsCountRequested],
  source: combine({ online: $isOnline, pending: fetchPendingCountFx.pending, subscribers: $subscribers }),
  filter: ({ online, pending, subscribers }) => online && !pending && subscribers > 0,
  fn: () => undefined,
  target: fetchPendingCountFx,
});
$approvalsPending.reset(stopped);

/** Badge text: nothing for 0 / unknown, «99+» above 99. */
export function badgeText(count: number | null): string | null {
  if (count === null || count <= 0) return null;
  return count > 99 ? "99+" : String(count);
}
