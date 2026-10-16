import { allSettled, fork } from "effector";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ApiError, http, NETWORK_ERROR, resetCsrfToken } from "@shared/api";
import { createAuthHandlers, createAuthState, mockSession } from "@shared/api/mocks";

import {
  $activeBranch,
  $activeBranchId,
  $authStatus,
  $branchChoiceRequired,
  $logoutError,
  $permissions,
  $session,
  $sessionCheckError,
  $sessionError,
  $sessionUnavailable,
  $tenant,
  $user,
  ALL_BRANCHES,
  branchSelected,
  getSessionFx,
  logoutFx,
  logoutRequested,
  resolveActiveBranch,
  revokeAllSessionsRequested,
  sessionCheckRequested,
  sessionRetryDelay,
} from "./index.ts";

const BASE = "http://state.test";
const state = createAuthState();
const server = setupServer(...createAuthHandlers(BASE, state));

beforeAll(() => {
  http.defaults.baseURL = BASE;
  server.listen({ onUnhandledFrame: "error" });
});
afterEach(() => {
  Object.assign(state, createAuthState());
  resetCsrfToken();
});
afterAll(() => server.close());

describe("session model — BFF session (14 §2.1, §20)", () => {
  it("no cookie → anonymous", async () => {
    const scope = fork();
    await allSettled(sessionCheckRequested, { scope });
    expect(scope.getState($authStatus)).toBe("anonymous");
  });

  it("valid cookie → user, tenant, permissions; two branches → BO-01 branch step", async () => {
    state.session = "active";
    const scope = fork();
    await allSettled(sessionCheckRequested, { scope });
    expect(scope.getState($authStatus)).toBe("authenticated");
    expect(scope.getState($user)?.full_name).toBe("Akmal Karimov");
    expect(scope.getState($tenant)?.name).toBe("Baraka do'koni");
    expect(scope.getState($permissions)).toContain("reports.sales.view");
    expect(scope.getState($branchChoiceRequired)).toBe(true);

    await allSettled(branchSelected, { scope, params: "0192a0f0-0000-7000-8000-0000000000b1" });
    expect(scope.getState($branchChoiceRequired)).toBe(false);
    expect(scope.getState($activeBranch)?.name).toBe("Chilonzor-3");

    await allSettled(logoutRequested, { scope });
    expect(scope.getState($authStatus)).toBe("anonymous");
    expect(scope.getState($activeBranchId)).toBeNull();
  });

  it("revoke-all ends the session", async () => {
    state.session = "active";
    const scope = fork();
    await allSettled(sessionCheckRequested, { scope });
    await allSettled(revokeAllSessionsRequested, { scope });
    expect(scope.getState($authStatus)).toBe("anonymous");
  });

  it("no active membership (403 PERMISSION_DENIED) → anonymous with the reason kept", async () => {
    state.session = "no_membership";
    const scope = fork();
    await allSettled(sessionCheckRequested, { scope });
    expect(scope.getState($authStatus)).toBe("anonymous");
    expect(scope.getState($sessionError)?.code).toBe("PERMISSION_DENIED");
  });

  it("heartbeat: a network failure keeps the session, a 401 ends it (14 §16.1.4)", async () => {
    state.session = "active";
    const network = new ApiError({ status: null, code: NETWORK_ERROR, messageKey: "errors.network" });
    const unauthorized = new ApiError({
      status: 401,
      code: "UNAUTHORIZED",
      messageKey: "errors.unauthorized",
    });
    const scope = fork();
    await allSettled(sessionCheckRequested, { scope });

    const offline = fork({
      values: [[$authStatus, "authenticated"]],
      handlers: [[getSessionFx, () => Promise.reject(network)]],
    });
    await allSettled(sessionCheckRequested, { scope: offline });
    expect(offline.getState($authStatus)).toBe("authenticated");

    const expired = fork({
      values: [[$authStatus, "authenticated"]],
      handlers: [[getSessionFx, () => Promise.reject(unauthorized)]],
    });
    await allSettled(sessionCheckRequested, { scope: expired });
    expect(expired.getState($authStatus)).toBe("anonymous");
  });
});

const networkError = () => new ApiError({ status: null, code: NETWORK_ERROR, messageKey: "errors.network" });
const serverError = () =>
  new ApiError({ status: 500, code: "INTERNAL_ERROR", messageKey: "errors.internal_error" });
const unauthorizedError = () =>
  new ApiError({ status: 401, code: "UNAUTHORIZED", messageKey: "errors.unauthorized" });

describe("logout — a failed request never fakes a sign-out (WEB-2)", () => {
  const signedInScope = (logout: () => Promise<void>) =>
    fork({
      values: [
        [$authStatus, "authenticated"],
        [$session, mockSession],
        [$activeBranchId, mockSession.branches[0]?.id ?? null],
      ],
      handlers: [[logoutFx, logout]],
    });

  it.each([
    ["network", networkError],
    ["500", serverError],
  ])("%s failure → still authenticated, $logoutError set", async (_, makeError) => {
    let calls = 0;
    const scope = signedInScope(() => {
      calls += 1;
      return calls === 1 ? Promise.reject(makeError()) : Promise.resolve();
    });
    await allSettled(logoutRequested, { scope });
    expect(scope.getState($authStatus)).toBe("authenticated");
    expect(scope.getState($session)).not.toBeNull();
    expect(scope.getState($logoutError)?.code).toBe(makeError().code);

    // The retry succeeds → signed out and the error is gone.
    await allSettled(logoutRequested, { scope });
    expect(scope.getState($authStatus)).toBe("anonymous");
    expect(scope.getState($logoutError)).toBeNull();
  });

  it("401 (session already dead) → signed out locally", async () => {
    const scope = signedInScope(() => Promise.reject(unauthorizedError()));
    await allSettled(logoutRequested, { scope });
    expect(scope.getState($authStatus)).toBe("anonymous");
    expect(scope.getState($session)).toBeNull();
    expect(scope.getState($activeBranchId)).toBeNull();
    expect(scope.getState($logoutError)).toBeNull();
  });
});

describe("first session check — only 401/403 mean anonymous (WEB-4)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it.each([
    ["network", networkError],
    ["500", serverError],
  ])("%s → stays unknown, exposes the error, retries after 3 s", async (_, makeError) => {
    vi.useFakeTimers();
    let calls = 0;
    const scope = fork({
      handlers: [
        [
          getSessionFx,
          () => {
            calls += 1;
            return calls === 1 ? Promise.reject(makeError()) : Promise.resolve(mockSession);
          },
        ],
      ],
    });
    const settled = allSettled(sessionCheckRequested, { scope });
    await vi.advanceTimersByTimeAsync(0);
    expect(scope.getState($authStatus)).toBe("unknown");
    expect(scope.getState($sessionCheckError)?.code).toBe(makeError().code);
    expect(scope.getState($sessionUnavailable)).toBe(true);

    await vi.advanceTimersByTimeAsync(2_999);
    expect(calls).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    await settled;
    expect(calls).toBe(2);
    expect(scope.getState($authStatus)).toBe("authenticated");
    expect(scope.getState($sessionCheckError)).toBeNull();
  });

  it("backoff doubles 3 s → 6 s → 12 s … capped at 30 s; a 401 ends the retries", async () => {
    expect([0, 1, 2, 3, 4, 10].map(sessionRetryDelay)).toEqual([
      3_000, 6_000, 12_000, 24_000, 30_000, 30_000,
    ]);

    vi.useFakeTimers();
    const times: number[] = [];
    const start = Date.now();
    const scope = fork({
      handlers: [
        [
          getSessionFx,
          () => {
            times.push(Date.now() - start);
            return Promise.reject(times.length < 4 ? networkError() : unauthorizedError());
          },
        ],
      ],
    });
    const settled = allSettled(sessionCheckRequested, { scope });
    await vi.advanceTimersByTimeAsync(3_000 + 6_000 + 12_000);
    await settled;
    expect(times).toEqual([0, 3_000, 9_000, 21_000]);
    expect(scope.getState($authStatus)).toBe("anonymous");
    expect(scope.getState($sessionCheckError)).toBeNull();
  });
});

describe("active branch re-resolved on every session answer (WEB-6)", () => {
  it("a branch no longer in session.branches is dropped; a valid one is kept", async () => {
    state.session = "active";
    const stale = fork({ values: [[$activeBranchId, "0192a0f0-0000-7000-8000-0000000000ff"]] });
    await allSettled(sessionCheckRequested, { scope: stale });
    expect(stale.getState($activeBranchId)).toBeNull();
    expect(stale.getState($branchChoiceRequired)).toBe(true);

    const valid = "0192a0f0-0000-7000-8000-0000000000b2";
    const kept = fork({ values: [[$activeBranchId, valid]] });
    await allSettled(sessionCheckRequested, { scope: kept });
    expect(kept.getState($activeBranchId)).toBe(valid);
  });

  it("a single remaining branch replaces a removed choice", async () => {
    const only = { ...mockSession, branches: [{ id: "only", name: "Only" }] };
    const scope = fork({
      values: [[$activeBranchId, "0192a0f0-0000-7000-8000-0000000000b1"]],
      handlers: [[getSessionFx, () => Promise.resolve(only)]],
    });
    await allSettled(sessionCheckRequested, { scope });
    expect(scope.getState($activeBranchId)).toBe("only");
  });
});

describe("resolveActiveBranch", () => {
  const branches = mockSession.branches;
  it("keeps a valid choice, auto-picks a single branch, otherwise asks (null)", () => {
    expect(resolveActiveBranch(branches, "0192a0f0-0000-7000-8000-0000000000b2")).toBe(
      "0192a0f0-0000-7000-8000-0000000000b2",
    );
    expect(resolveActiveBranch(branches, ALL_BRANCHES)).toBe(ALL_BRANCHES);
    expect(resolveActiveBranch(branches, "zzz")).toBeNull();
    expect(resolveActiveBranch([{ id: "only", name: "Only" }], null)).toBe("only");
  });
});
