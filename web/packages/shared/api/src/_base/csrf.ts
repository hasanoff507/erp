/**
 * CSRF synchronizer token — 15-xavfsizlik-va-audit.md §1.3, 17 §5.
 * `GET /api/v1/auth/csrf` once, cached in memory (never in storage), sent as `X-CSRF-Token` on writes.
 */
import type { AxiosInstance } from "axios";

export const CSRF_PATH = "/api/v1/auth/csrf";
export const SKIP_INTERCEPTORS_HEADER = "X-Erp-Skip-Interceptors";

let cached: Promise<string> | null = null;

export function getCsrfToken(http: AxiosInstance): Promise<string> {
  cached ??= http
    .get<{ csrf_token: string }>(CSRF_PATH, { headers: { [SKIP_INTERCEPTORS_HEADER]: "1" } })
    .then((r) => r.data.csrf_token)
    .catch((e: unknown) => {
      cached = null;
      throw e;
    });
  return cached;
}

/** Called on logout, session change and after 403 CSRF_INVALID. */
export function resetCsrfToken(): void {
  cached = null;
}
