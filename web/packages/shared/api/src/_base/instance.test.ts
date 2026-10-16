import { http as mswHttp, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import {
  api,
  ApiError,
  configureApi,
  http,
  loginStartUrl,
  NETWORK_ERROR,
  REQUEST_CANCELED,
  resetCsrfToken,
} from "../index.ts";
import { createAuthHandlers, createAuthState, mockSession } from "../mocks/index.ts";

const BASE = "http://api.test";
const state = createAuthState();
const server = setupServer(...createAuthHandlers(BASE, state));

beforeAll(() => {
  http.defaults.baseURL = BASE;
  server.listen({ onUnhandledFrame: "error" });
});
afterEach(() => {
  server.resetHandlers();
  Object.assign(state, createAuthState());
  resetCsrfToken();
});
afterAll(() => server.close());

describe("@shared/api instance — 24 §3", () => {
  it("generated functions return the response body", async () => {
    await expect(api.health.get()).resolves.toEqual({ status: "ok", checks: {} });
    state.session = "active";
    await expect(api.auth.sessionGet()).resolves.toEqual(mockSession);
  });

  it("cookie writes carry X-CSRF-Token, Idempotency-Key, Accept-Language and X-Branch-Id", async () => {
    configureApi({ getLanguage: () => "ru", getBranchId: () => "branch-1" });
    state.session = "active";
    await api.auth.logout();
    const headers = state.lastWriteHeaders;
    expect(headers?.get("x-csrf-token")).toBe("csrf-test-token");
    expect(headers?.get("idempotency-key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(headers?.get("accept-language")).toBe("ru");
    expect(headers?.get("x-branch-id")).toBe("branch-1");
  });

  it("403 CSRF_INVALID → fetches a fresh token and retries once (15 §1.3)", async () => {
    state.session = "active";
    state.rejectCsrfOnce = true;
    await expect(api.auth.sessionsRevokeAll()).resolves.toEqual({ sessions_revoked: 3 });
  });

  it("401 → normalised ApiError + unauthorized hook", async () => {
    const onUnauthorized = vi.fn();
    configureApi({ onUnauthorized });
    const error: unknown = await api.auth.sessionGet().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, code: "UNAUTHORIZED" });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("403 SUBSCRIPTION_RESTRICTED keeps pay_url / amount_due and calls the hook", async () => {
    const onSubscriptionRestricted = vi.fn();
    configureApi({ onSubscriptionRestricted });
    state.session = "restricted";
    const error = (await api.auth.sessionGet().catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("SUBSCRIPTION_RESTRICTED");
    expect(error.params).toMatchObject({ amount_due: "99000.00" });
    expect(onSubscriptionRestricted).toHaveBeenCalledOnce();
  });
});

describe("online / offline hooks — WEB-3", () => {
  const hooks = () => {
    const onOnline = vi.fn();
    const onNetworkError = vi.fn();
    configureApi({ onOnline, onNetworkError });
    return { onOnline, onNetworkError };
  };

  it("a successful response reports the server reachable", async () => {
    const { onOnline, onNetworkError } = hooks();
    await api.health.get();
    expect(onOnline).toHaveBeenCalled();
    expect(onNetworkError).not.toHaveBeenCalled();
  });

  it("an error WITH a response (5xx) still means online", async () => {
    server.use(mswHttp.get(`${BASE}/health`, () => HttpResponse.json({}, { status: 503 })));
    const { onOnline, onNetworkError } = hooks();
    const error = (await api.health.get().catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(503);
    expect(onOnline).toHaveBeenCalled();
    expect(onNetworkError).not.toHaveBeenCalled();
  });

  it("no response at all → NETWORK_ERROR + onNetworkError, not onOnline", async () => {
    server.use(mswHttp.get(`${BASE}/health`, () => HttpResponse.error()));
    const { onOnline, onNetworkError } = hooks();
    const error = (await api.health.get().catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe(NETWORK_ERROR);
    expect(onNetworkError).toHaveBeenCalledOnce();
    expect(onOnline).not.toHaveBeenCalled();
  });

  it("a canceled request is REQUEST_CANCELED and never goes offline", async () => {
    const { onOnline, onNetworkError } = hooks();
    const controller = new AbortController();
    controller.abort();
    const error: unknown = await http.get("/health", { signal: controller.signal }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: null, code: REQUEST_CANCELED });
    expect(onNetworkError).not.toHaveBeenCalled();
    expect(onOnline).not.toHaveBeenCalled();
  });
});

describe("loginStartUrl — 14 §2.1 (browser navigation, not XHR)", () => {
  it("encodes return_to and tenant_id", () => {
    expect(loginStartUrl()).toBe("/auth/login/start");
    expect(loginStartUrl({ returnTo: "/app/debts?x=1" })).toBe(
      "/auth/login/start?return_to=%2Fapp%2Fdebts%3Fx%3D1",
    );
    expect(loginStartUrl({ returnTo: "/app", tenantId: "t-1" })).toBe(
      "/auth/login/start?return_to=%2Fapp&tenant_id=t-1",
    );
  });
});
