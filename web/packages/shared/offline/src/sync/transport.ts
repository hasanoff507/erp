/**
 * SyncTransport — the only network boundary of the engine (16 §3). The default HTTP transport goes
 * through the shared axios instance of @shared/api (BFF cookie, X-CSRF-Token on POST, CSRF retry,
 * X-Branch-Id, Accept-Language). When `pnpm api:gen` has produced `api.sync.*`, a transport built on
 * those generated functions can be passed to `configureOffline({ transport })` instead.
 * Tests and the e2e stub use their own transports / page.route().
 */
import { api, http, toApiError } from "@shared/api";

import type { SyncPullParams, SyncPullResponse, SyncPushRequest, SyncPushResponse } from "../types.ts";

export const SYNC_PUSH_PATH = "/api/v1/sync/push";
export const SYNC_PULL_PATH = "/api/v1/sync/pull";

export interface TransportResult<T> {
  data: T;
  /** Server clock from the HTTP `Date` header (ms), for the trusted clock (16 §8). */
  serverDate: number | null;
}

export interface SyncTransport {
  push(body: SyncPushRequest): Promise<TransportResult<SyncPushResponse>>;
  pull(params: SyncPullParams): Promise<TransportResult<SyncPullResponse>>;
  /** Silent session probe after a 401 (the BFF refreshes server-side, 14 §7–8). true = session alive. */
  refreshSession(): Promise<boolean>;
}

/** Request-level failure: `status` null = no answer (network). */
export class SyncHttpError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly retryAfterMs: number | null;
  readonly params: Readonly<Record<string, unknown>>;
  readonly details: readonly { field: string; messageKey: string }[];

  constructor(init: {
    status: number | null;
    code: string;
    retryAfterMs?: number | null;
    params?: Record<string, unknown>;
    details?: { field: string; messageKey: string }[];
  }) {
    super(init.code);
    this.name = "SyncHttpError";
    this.status = init.status;
    this.code = init.code;
    this.retryAfterMs = init.retryAfterMs ?? null;
    this.params = init.params ?? {};
    this.details = init.details ?? [];
  }
}

/** `Retry-After` whole seconds → ms; digit loop (no Number()/parseInt — qaror #57 lint rule). */
export function parseRetryAfter(raw: unknown): number | null {
  if (typeof raw !== "string" || raw.length === 0 || raw.length > 5) return null;
  let seconds = 0;
  for (const ch of raw.trim()) {
    const digit = "0123456789".indexOf(ch);
    if (digit === -1) return null;
    seconds = seconds * 10 + digit;
  }
  return seconds * 1000;
}

function headerOf(headers: unknown, name: string): unknown {
  if (typeof headers !== "object" || headers === null) return undefined;
  const h = headers as { get?: (n: string) => unknown } & Record<string, unknown>;
  if (typeof h.get === "function") {
    const value = h.get(name);
    if (value !== undefined && value !== null) return value;
  }
  return h[name];
}

function serverDateOf(headers: unknown): number | null {
  const raw = headerOf(headers, "date");
  if (typeof raw !== "string") return null;
  const ms = Date.parse(raw);
  return Number.isNaN(ms) ? null : ms;
}

export function toSyncHttpError(error: unknown): SyncHttpError {
  if (error instanceof SyncHttpError) return error;
  const apiError = toApiError(error);
  const cause = apiError.cause as { response?: { headers?: unknown } } | undefined;
  return new SyncHttpError({
    status: apiError.status,
    code: apiError.code,
    retryAfterMs: parseRetryAfter(headerOf(cause?.response?.headers, "retry-after")),
    params: { ...apiError.params },
    details: [...apiError.details],
  });
}

export function createHttpSyncTransport(): SyncTransport {
  return {
    async push(body) {
      try {
        const response = await http.post<SyncPushResponse>(SYNC_PUSH_PATH, body);
        return { data: response.data, serverDate: serverDateOf(response.headers) };
      } catch (error) {
        throw toSyncHttpError(error);
      }
    },
    async pull(params) {
      try {
        const response = await http.get<SyncPullResponse>(SYNC_PULL_PATH, { params });
        return { data: response.data, serverDate: serverDateOf(response.headers) };
      } catch (error) {
        throw toSyncHttpError(error);
      }
    },
    async refreshSession() {
      try {
        await api.auth.sessionGet();
        return true;
      } catch {
        return false;
      }
    },
  };
}
