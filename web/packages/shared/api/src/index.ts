/**
 * @shared/api — 24-frontend-arxitekturasi.md §3.
 *
 * Generated domain modules are re-exported as ESM namespaces only (no hand-written wrappers):
 *   import { api } from "@shared/api";  api.auth.sessionGet()
 * Regenerate after any backend schema change: `pnpm api:export` (no running backend needed),
 * `pnpm api:fetch` (running backend) or `pnpm api:gen` (committed schema).
 */
import * as auth from "./generated/auth/auth.ts";
import * as health from "./generated/health/health.ts";

export const api = { auth, health } as const;

export { apiRequest, http } from "./_base/instance.ts";
export {
  ApiError,
  INTERNAL_ERROR,
  NETWORK_ERROR,
  REQUEST_CANCELED,
  toApiError,
  type ApiErrorDetail,
} from "./_base/errors.ts";
export { configureApi, type ApiHooks } from "./_base/hooks.ts";
export { resetCsrfToken } from "./_base/csrf.ts";
export { LOGIN_START_PATH, loginStartUrl, type LoginStartOptions } from "./_base/navigation.ts";
