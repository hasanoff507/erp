import { combine, createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { AuthStatus, Branch, Session, SubscriptionRestriction } from "../types/index.ts";

/** Global session state (24 §2: $user, $tenant, $activeBranch, $permissions). */
export const $session = createStore<Session | null>(null);
export const $authStatus = createStore<AuthStatus>("unknown");

export const $user = $session.map((s) => s?.user ?? null);
export const $tenant = $session.map((s) => s?.tenant ?? null);
export const $roleCodes = $session.map<readonly string[]>((s) => s?.roles ?? []);
/** Effective permission codes (15 §2.1) — what `useCan` / `<Can>` check, per exact code. */
export const $permissions = $session.map<readonly string[]>((s) => s?.permissions ?? []);
/** Token `scope`: permission-code prefixes (14 §10) — only the coarse first filter. */
export const $scopes = $session.map<readonly string[]>((s) => s?.scope ?? []);
export const $branches = $session.map<readonly Branch[]>((s) => s?.branches ?? []);

/** Selected branch id (`X-Branch-Id`), ALL_BRANCHES for the consolidated view, `null` = not chosen. */
export const $activeBranchId = createStore<string | null>(null);
export const $activeBranch = combine(
  $branches,
  $activeBranchId,
  (branches, id) => branches.find((b) => b.id === id) ?? null,
);
/** Several branches and none chosen yet → the BO-01 branch step (07 `branchId`). */
export const $branchChoiceRequired = combine(
  $authStatus,
  $branches,
  $activeBranchId,
  (status, branches, id) => status === "authenticated" && branches.length > 1 && id === null,
);

export const $subscriptionRestriction = createStore<SubscriptionRestriction | null>(null);
/** Last session refusal (e.g. 403 PERMISSION_DENIED — no active membership) for the login page. */
export const $sessionError = createStore<ApiError | null>(null);

/**
 * The first GET /auth/session could not be answered (network error, 5xx): `$authStatus` stays
 * `unknown` and the check is retried with backoff (3 s → 30 s). The splash can show this + a retry.
 */
export const $sessionCheckError = createStore<ApiError | null>(null);
/** `true` while the first session check keeps failing for reasons other than 401/403. */
export const $sessionUnavailable = $sessionCheckError.map((e) => e !== null);

/**
 * Last failed logout (network, 5xx…): the user stays signed in; UI shows
 * `t("common:session.logoutFailed")`. Cleared on the next attempt or once signed out.
 */
export const $logoutError = createStore<ApiError | null>(null);

/**
 * Last refused tenant switch (403 PERMISSION_DENIED `membership_inactive`, 403
 * SUBSCRIPTION_RESTRICTED with `pay_url`/`amount_due`, …): the current session is unchanged.
 * Cleared on the next attempt or a successful switch.
 */
export const $tenantSwitchError = createStore<ApiError | null>(null);
