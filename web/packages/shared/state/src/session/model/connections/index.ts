/**
 * Session flow — only sample() wiring here (24 §2).
 * Login itself is a full-page navigation to /auth/login/start (14 §2.1); this model learns the result
 * through GET /auth/session, then keeps polling it every ~30 s (14 §16.1.4 heartbeat): 401 → signed
 * out (ProtectedRoute sends the user to /login), 403 SUBSCRIPTION_RESTRICTED → the API hook redirects
 * to /login?reason=subscription_expired. A network failure / 5xx never signs out: during the heartbeat
 * the session is kept (back-office offline view, POS outbox — 24 §3); on the very first check the
 * status stays `unknown` and the check is retried with backoff (3 s doubling to 30 s).
 */
import { createStore, sample } from "effector";
import { delay, interval } from "patronum";

import {
  getSessionFx,
  logoutFx,
  persistBranchFx,
  readBranchFx,
  revokeAllSessionsFx,
  switchTenantFx,
} from "../effects/index.ts";
import {
  branchSelected,
  logoutFailed,
  logoutRequested,
  revokeAllSessionsRequested,
  sessionCheckRequested,
  sessionHeartbeatEnabled,
  subscriptionRestrictedReceived,
  tenantSwitchRequested,
  unauthorizedReceived,
} from "../events/index.ts";
import {
  HEARTBEAT_MS,
  isSessionRefusal,
  resolveActiveBranch,
  restrictionFromParams,
  sessionRetryDelay,
} from "../lib/index.ts";
import {
  $activeBranchId,
  $authStatus,
  $logoutError,
  $session,
  $sessionCheckError,
  $sessionError,
  $subscriptionRestriction,
  $tenantSwitchError,
} from "../stores/index.ts";

sample({ clock: sessionCheckRequested, target: getSessionFx });

sample({ clock: getSessionFx.doneData, target: $session });
sample({ clock: getSessionFx.done, fn: () => "authenticated" as const, target: $authStatus });
$subscriptionRestriction.reset(getSessionFx.done);
$sessionError.reset(getSessionFx.done);

// Signed out only by an answer from the server (401/403) — never by "could not ask".
const sessionRefused = sample({
  clock: getSessionFx.failData,
  filter: (error) => isSessionRefusal(error),
});
sample({
  clock: sessionRefused,
  filter: (error) => error.code === "PERMISSION_DENIED",
  target: $sessionError,
});

// First check failed without a verdict (network, 5xx, non-JSON answer): stay `unknown`, retry.
const sessionCheckFailed = sample({
  clock: getSessionFx.failData,
  source: $authStatus,
  filter: (status, error) => status === "unknown" && !isSessionRefusal(error),
  fn: (_, error) => error,
});
sample({ clock: sessionCheckFailed, target: $sessionCheckError });
$sessionCheckError.reset(getSessionFx.done, sessionRefused);

/** Number of retries scheduled so far; only the latest scheduled retry fires (no parallel chains). */
const $retryAttempt = createStore(0);
const retryScheduled = sample({
  clock: sessionCheckFailed,
  source: $retryAttempt,
  fn: (attempt) => ({ attempt: attempt + 1, ms: sessionRetryDelay(attempt) }),
});
$retryAttempt.on(retryScheduled, (_, { attempt }) => attempt).reset(getSessionFx.done, sessionRefused);
const retryDue = delay({ source: retryScheduled, timeout: ({ ms }) => ms });
sample({
  clock: retryDue,
  source: { status: $authStatus, attempt: $retryAttempt, pending: getSessionFx.pending },
  filter: ({ status, attempt, pending }, due) => status === "unknown" && attempt === due.attempt && !pending,
  fn: () => undefined,
  target: getSessionFx,
});

// 403 SUBSCRIPTION_RESTRICTED (session check or any API call) → banner data on /login.
sample({
  clock: subscriptionRestrictedReceived,
  fn: (error) => restrictionFromParams(error.params),
  target: $subscriptionRestriction,
});

// Re-resolve the branch after every session answer when none is chosen or the chosen one is no
// longer in session.branches (branch removed / access revoked); a valid choice is kept.
sample({
  clock: getSessionFx.doneData,
  source: $activeBranchId,
  filter: (id, session) => id === null || resolveActiveBranch(session.branches, id) !== id,
  fn: () => undefined,
  target: readBranchFx,
});
sample({
  clock: readBranchFx.doneData,
  source: $session,
  fn: (session, stored) => resolveActiveBranch(session?.branches ?? [], stored),
  target: $activeBranchId,
});
sample({ clock: branchSelected, target: [$activeBranchId, persistBranchFx] });

// Tenant switch (14 §9): the answer is the new session — permissions, branches and tenant follow
// from $session; the branch is resolved again (the old one belongs to the previous tenant).
sample({ clock: tenantSwitchRequested, target: switchTenantFx });
sample({ clock: switchTenantFx.doneData, target: $session });
sample({ clock: switchTenantFx.done, fn: () => null, target: $activeBranchId });
sample({ clock: switchTenantFx.done, fn: () => undefined, target: readBranchFx });
sample({
  clock: switchTenantFx.failData,
  filter: (error) => error.status !== 401, // 401: the session is gone → signed out by the API hook
  target: $tenantSwitchError,
});
$tenantSwitchError.reset(tenantSwitchRequested, switchTenantFx.done);

// Logout / lost session. Never automatic on network errors (POS keeps its outbox, 24 §3).
sample({ clock: logoutRequested, target: logoutFx });
sample({ clock: revokeAllSessionsRequested, target: revokeAllSessionsFx });

// A failed logout keeps the user signed in (the server session may still be alive) — except 401:
// the session is already gone, so signing out locally is the truth.
const sessionAlreadyGone = sample({
  clock: [logoutFx.failData, revokeAllSessionsFx.failData],
  filter: (error) => error.status === 401,
});
sample({ clock: logoutFx.failData, filter: (error) => error.status !== 401, target: logoutFailed });
sample({ clock: logoutFailed, target: $logoutError });

const signedOut = [
  logoutFx.done,
  revokeAllSessionsFx.done,
  sessionAlreadyGone,
  unauthorizedReceived,
  subscriptionRestrictedReceived,
  sessionRefused,
];
sample({ clock: signedOut, fn: () => null, target: [$session, $activeBranchId] });
sample({ clock: signedOut, fn: () => "anonymous" as const, target: $authStatus });
$logoutError.reset(logoutRequested, ...signedOut);
$tenantSwitchError.reset(signedOut);

// Heartbeat (14 §16.1.4): enabled by the shell, runs while authenticated.
const $heartbeatEnabled = createStore(false).on(sessionHeartbeatEnabled, () => true);
const heartbeat = interval({
  timeout: HEARTBEAT_MS,
  start: sample({ clock: getSessionFx.done, filter: $heartbeatEnabled }),
  stop: $authStatus.updates.filter({ fn: (status) => status !== "authenticated" }),
});
sample({ clock: heartbeat.tick, filter: getSessionFx.pending.map((p) => !p), target: getSessionFx });
