/**
 * The single axios instance (24 §3, namuna `_base`) + the orval mutator `apiRequest`.
 *
 * - `withCredentials: true` — the HttpOnly `__Host-sid` BFF cookie authenticates (14 §2.1); there is
 *   no Authorization header and no token in JS.
 * - Writes carry `X-CSRF-Token` and `Idempotency-Key` (UUIDv7); every request carries
 *   `Accept-Language` and, when a branch is selected, `X-Branch-Id`. Tenant comes from the session.
 * - 403 CSRF_INVALID → refresh token once and retry; 409 IDEMPOTENCY_IN_PROGRESS → retry the same key
 *   after Retry-After (max 3); 401 / 403 SUBSCRIPTION_RESTRICTED / network → shell hooks; any server
 *   answer → `onOnline`. A canceled request (REQUEST_CANCELED) triggers no hook at all.
 */
import axios, { type AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";
import { v7 as uuidv7 } from "uuid";

import { getRuntimeConfig } from "@shared/lib/runtime-config";

import { CSRF_PATH, SKIP_INTERCEPTORS_HEADER, getCsrfToken, resetCsrfToken } from "./csrf.ts";
import { NETWORK_ERROR, toApiError } from "./errors.ts";
import { apiHooks } from "./hooks.ts";

const WRITE_METHODS = new Set(["post", "put", "patch", "delete"]);
/**
 * Every cookie-authenticated write carries X-CSRF-Token (15 §1.3); only the token endpoint itself is
 * exempt. Login is not an XHR any more: the browser navigates to /auth/login/start (14 §2.1).
 */
const CSRF_EXEMPT = new Set([CSRF_PATH]);
const MAX_IDEMPOTENCY_RETRIES = 3;

interface RetryState {
  _csrfRetried?: boolean;
  _idempotencyRetries?: number;
}
type RetriableConfig = InternalAxiosRequestConfig & RetryState;

export const http = axios.create({
  withCredentials: true,
  headers: { Accept: "application/json" },
});

function pathOf(config: InternalAxiosRequestConfig): string {
  const url = config.url ?? "";
  const q = url.indexOf("?");
  return q === -1 ? url : url.slice(0, q);
}

http.interceptors.request.use(async (config) => {
  config.baseURL ??= getRuntimeConfig().apiBaseUrl;
  if (config.headers.has(SKIP_INTERCEPTORS_HEADER)) {
    config.headers.delete(SKIP_INTERCEPTORS_HEADER);
    return config;
  }

  config.headers.set("Accept-Language", apiHooks.getLanguage());
  const branchId = apiHooks.getBranchId();
  if (branchId) config.headers.set("X-Branch-Id", branchId);

  const method = (config.method ?? "get").toLowerCase();
  if (WRITE_METHODS.has(method)) {
    if (!config.headers.has("Idempotency-Key")) config.headers.set("Idempotency-Key", uuidv7());
    if (!CSRF_EXEMPT.has(pathOf(config))) {
      config.headers.set("X-CSRF-Token", await getCsrfToken(http));
    }
  }
  return config;
});

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** `Retry-After` is whole seconds; integer parsing is not money (no Number()/parseInt — qaror #57). */
function retryAfterMs(error: AxiosError): number {
  const raw: unknown = error.response?.headers["retry-after"];
  if (typeof raw !== "string" || raw.length === 0 || raw.length > 3) return 1000;
  let seconds = 0;
  for (const ch of raw) {
    const digit = "0123456789".indexOf(ch);
    if (digit === -1) return 1000;
    seconds = seconds * 10 + digit;
  }
  return seconds > 0 ? seconds * 1000 : 1000;
}

http.interceptors.response.use(
  (response) => {
    apiHooks.onOnline();
    return response;
  },
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const apiError = toApiError(error);
    // Any HTTP answer (even 4xx/5xx) proves the server is reachable; canceled requests prove nothing.
    if (error.response) apiHooks.onOnline();

    if (config && apiError.status === 403 && apiError.code === "CSRF_INVALID" && !config._csrfRetried) {
      config._csrfRetried = true;
      resetCsrfToken();
      config.headers.delete("X-CSRF-Token");
      return http.request(config);
    }

    if (config && apiError.status === 409 && apiError.code === "IDEMPOTENCY_IN_PROGRESS") {
      const attempt = (config._idempotencyRetries ?? 0) + 1;
      if (attempt <= MAX_IDEMPOTENCY_RETRIES) {
        config._idempotencyRetries = attempt;
        await sleep(retryAfterMs(error));
        return http.request(config);
      }
    }

    if (apiError.code === NETWORK_ERROR) apiHooks.onNetworkError(apiError);
    else if (apiError.status === 401) apiHooks.onUnauthorized(apiError);
    else if (apiError.status === 403 && apiError.code === "SUBSCRIPTION_RESTRICTED") {
      apiHooks.onSubscriptionRestricted(apiError);
    }

    throw apiError;
  },
);

/** orval mutator: every generated function calls this. Returns the response body. */
export const apiRequest = async <T>(config: AxiosRequestConfig, options?: AxiosRequestConfig): Promise<T> => {
  const response = await http.request<T>({ ...config, ...options });
  return response.data;
};
