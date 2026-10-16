import { createEffect } from "effector";

import { api, ApiError, INTERNAL_ERROR, resetCsrfToken } from "@shared/api";

import { isSession, readStoredBranchId, writeStoredBranchId } from "../lib/index.ts";
import type { Session } from "../types/index.ts";

/** Effects call only @shared/api functions (24 §2). Failures are normalised ApiError instances. */

/** A non-JSON answer (e.g. an SPA fallback page) must never count as a session. */
function assertSession(value: unknown): Session {
  if (!isSession(value)) {
    throw new ApiError({ status: null, code: INTERNAL_ERROR, messageKey: "errors.internal_error" });
  }
  return value;
}

export const getSessionFx = createEffect<void, Session, ApiError>(async () =>
  assertSession(await api.auth.sessionGet()),
);

export const logoutFx = createEffect<void, void, ApiError>(async () => {
  try {
    await api.auth.logout();
  } finally {
    resetCsrfToken();
  }
});

export const revokeAllSessionsFx = createEffect<void, number, ApiError>(async () => {
  try {
    return (await api.auth.sessionsRevokeAll()).sessions_revoked;
  } finally {
    resetCsrfToken();
  }
});

export const readBranchFx = createEffect<void, string | null>(() => readStoredBranchId());
export const persistBranchFx = createEffect<string, void>((id) => writeStoredBranchId(id));
