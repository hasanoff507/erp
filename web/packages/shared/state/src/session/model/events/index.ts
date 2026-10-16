import { createEvent } from "effector";

import type { ApiError } from "@shared/api";

/** Shell start / heartbeat: ask the BFF whether the session cookie is valid (GET /auth/session). */
export const sessionCheckRequested = createEvent();
/** Turns on the ~30 s GET /auth/session heartbeat (14 §16.1.4); the shell enables it once. */
export const sessionHeartbeatEnabled = createEvent();
export const logoutRequested = createEvent();
/** End all of my sessions (POST /auth/sessions/revoke-all). */
export const revokeAllSessionsRequested = createEvent();
/** Branch picked on the BO-01 step or in the topbar (ALL_BRANCHES = all branches). */
export const branchSelected = createEvent<string>();

/** Raised by the API layer hooks (configured in the shell). */
export const unauthorizedReceived = createEvent<ApiError>();
export const subscriptionRestrictedReceived = createEvent<ApiError>();

/** Logout failed for a reason other than 401 (network, 5xx…): still signed in — show a toast. */
export const logoutFailed = createEvent<ApiError>();
