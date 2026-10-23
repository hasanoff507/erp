/**
 * e2e stub of the POS sync backend (16 §3, contracts/sync-push.md, sync-pull.md) for the web-POS
 * specs: `/api/v1/sync/push` (dedupe by client_event_id → `duplicate`), `/api/v1/sync/pull`,
 * `/api/v1/auth/csrf` and `/auth/session`, all via page.route(). Every pushed client_event_id is
 * recorded (each attempt), so a spec can assert "the sale synced exactly once"; the network can be
 * switched off/on (`context.setOffline` + aborted sync routes) and request-level failures scripted
 * (401 session lost, 403 DEVICE_REVOKED, 429, lost answer = server committed but the reply never came).
 *
 *   const sync = await installSyncStub(page, { pull: { catalog: [...] } });
 *   await sync.setOffline(true); … sell … await sync.setOffline(false);
 *   await expect.poll(() => sync.committed.length).toBe(1);
 *   sync.expectEachCommittedOnce();
 */
import { expect, type Page, type Request, type Route } from "@playwright/test";

export type Body = Record<string, unknown>;

export interface StubEvent {
  client_event_id: string;
  device_id: string;
  seq: number;
  type: string;
  created_at: string;
  actor_user_id: string;
  payload: Body;
}

export interface StubPushRequest {
  device_id: string;
  events: StubEvent[];
  outbox_state: { pending_count: number; oldest_pending_created_at: string | null };
}

export interface StubResult {
  client_event_id: string;
  status: "accepted" | "duplicate" | "rejected";
  server: Body | null;
  error_code: string | null;
  message: string | null;
  retryable: boolean;
  warnings: string[];
  params: Body;
  details: unknown[];
}

export type ScriptedFailure =
  | { status: 401; code?: "UNAUTHORIZED" }
  | { status: 403; code: "DEVICE_REVOKED" | "SUBSCRIPTION_RESTRICTED" | "CSRF_INVALID" }
  | { status: 429; retryAfterS?: number }
  | { status: 500 }
  | "lost-answer";

export const STUB_DEVICE = {
  id: "0190a000-0000-7000-8000-00000000d001",
  branch_id: "b-1",
  cash_register_id: "0190a000-0000-7000-8000-00000000c001",
};

export function posSession(permissions: string[] = ["sales.create", "shift.open", "shift.close"]): Body {
  return {
    user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
    tenant: { id: "t-1", name: "Baraka do'koni" },
    branches: [{ id: STUB_DEVICE.branch_id, name: "Chilonzor-3" }],
    roles: ["owner"],
    permissions,
    // token scope = the permission prefixes (14 §10) — the shell route guard checks prefix + code
    scope: [...new Set(["pos", "sync", ...permissions.map((code) => code.split(".")[0] ?? code)])],
    client_id: "web-bff",
    sub_status: "active",
    access_expires_at: 0,
    device: { ...STUB_DEVICE },
  };
}

export interface SyncStubOptions {
  /** `/auth/session` body (default: posSession()). */
  session?: Body;
  /** Delta arrays / snapshot objects returned by the first pull (`scope=all`, empty cursor). */
  pull?: Body;
  /** Per-event decision; return a rejected result to reject (default: accept). */
  onEvent?: (event: StubEvent) => Partial<StubResult> | null;
}

export interface SyncStub {
  /** Every pushed client_event_id, once per attempt (a re-sent event appears again). */
  readonly pushed: string[];
  /** client_event_ids the "server" committed, in commit order (each at most once by construction). */
  readonly committed: string[];
  readonly pushRequests: StubPushRequest[];
  readonly pullRequests: URLSearchParams[];
  /** `X-CSRF-Token` header of every push (cookie auth must send it, 15 §1.3). */
  readonly pushCsrfTokens: (string | null)[];
  readonly online: boolean;
  setOffline(offline: boolean): Promise<void>;
  /** The next push/pull answers with this failure (queue). */
  failNextPush(failure: ScriptedFailure): void;
  failNextPull(failure: ScriptedFailure): void;
  /** Every further push/pull answers 403 DEVICE_REVOKED. */
  revokeDevice(): void;
  /** Rows served by the next pull (then empty deltas). */
  setPullData(data: Body): void;
  /** Fails the test unless each id was committed exactly once (and, if given, exactly these ids). */
  expectEachCommittedOnce(expectedIds?: string[]): void;
}

const CSRF_TOKEN = "csrf-e2e-token";

function json(route: Route, status: number, body: unknown, headers: Record<string, string> = {}) {
  return route.fulfill({
    status,
    contentType: "application/json",
    headers: { date: new Date().toUTCString(), ...headers },
    body: JSON.stringify(body),
  });
}

function failureResponse(route: Route, failure: Exclude<ScriptedFailure, "lost-answer">) {
  if (failure.status === 401) {
    return json(route, 401, {
      error: {
        code: failure.code ?? "UNAUTHORIZED",
        message_key: "errors.unauthorized",
        params: {},
        details: [],
      },
    });
  }
  if (failure.status === 403) {
    return json(route, 403, {
      error: {
        code: failure.code,
        message_key: `errors.${failure.code.toLowerCase()}`,
        params: {},
        details: [],
      },
    });
  }
  if (failure.status === 429) {
    return json(
      route,
      429,
      { error: { code: "RATE_LIMITED", message_key: "errors.rate_limited", params: {}, details: [] } },
      { "retry-after": String(failure.retryAfterS ?? 1) },
    );
  }
  return json(route, 500, {
    error: { code: "INTERNAL_ERROR", message_key: "errors.internal_error", params: {}, details: [] },
  });
}

export async function installSyncStub(page: Page, options: SyncStubOptions = {}): Promise<SyncStub> {
  const pushed: string[] = [];
  const committed: string[] = [];
  const pushRequests: StubPushRequest[] = [];
  const pullRequests: URLSearchParams[] = [];
  const pushCsrfTokens: (string | null)[] = [];
  const stored = new Map<string, StubResult>();
  const pushFailures: ScriptedFailure[] = [];
  const pullFailures: ScriptedFailure[] = [];
  let offline = false;
  let revoked = false;
  let pullData: Body | null = options.pull ?? null;
  let cursorSerial = 0;
  let serial = 0;

  const decide = (event: StubEvent): StubResult => {
    const previous = stored.get(event.client_event_id);
    if (previous) return { ...previous, status: "duplicate" };
    const custom = options.onEvent?.(event) ?? null;
    if (custom?.status === "rejected") {
      return {
        client_event_id: event.client_event_id,
        status: "rejected",
        server: null,
        error_code: custom.error_code ?? "VALIDATION_ERROR",
        message: custom.message ?? `errors.${(custom.error_code ?? "VALIDATION_ERROR").toLowerCase()}`,
        retryable: custom.retryable ?? false,
        warnings: custom.warnings ?? [],
        params: custom.params ?? {},
        details: custom.details ?? [],
      };
    }
    serial += 1;
    const result: StubResult = {
      client_event_id: event.client_event_id,
      status: "accepted",
      server: custom?.server ?? {
        id: `srv-${serial}`,
        number: `K-01-2026-${String(serial).padStart(6, "0")}`,
      },
      error_code: null,
      message: null,
      retryable: false,
      warnings: custom?.warnings ?? [],
      params: {},
      details: [],
    };
    stored.set(event.client_event_id, result);
    committed.push(event.client_event_id);
    return result;
  };

  await page.route("**/api/v1/auth/csrf", (route) =>
    offline ? route.abort("internetdisconnected") : json(route, 200, { csrf_token: CSRF_TOKEN }),
  );
  await page.route("**/auth/session", (route) =>
    offline ? route.abort("internetdisconnected") : json(route, 200, options.session ?? posSession()),
  );

  await page.route("**/api/v1/sync/push", async (route: Route, request: Request) => {
    if (offline) return route.abort("internetdisconnected");
    const body = request.postDataJSON() as StubPushRequest;
    pushRequests.push(body);
    pushCsrfTokens.push(request.headers()["x-csrf-token"] ?? null);
    for (const event of body.events) pushed.push(event.client_event_id);
    if (revoked) return failureResponse(route, { status: 403, code: "DEVICE_REVOKED" });
    const failure = pushFailures.shift();
    if (failure && failure !== "lost-answer") return failureResponse(route, failure);
    const results = body.events.map(decide);
    if (failure === "lost-answer") return route.abort("connectionreset");
    return json(route, 200, { results });
  });

  await page.route("**/api/v1/sync/pull**", (route: Route, request: Request) => {
    if (offline) return route.abort("internetdisconnected");
    const params = new URL(request.url()).searchParams;
    pullRequests.push(params);
    if (revoked) return failureResponse(route, { status: 403, code: "DEVICE_REVOKED" });
    const failure = pullFailures.shift();
    if (failure === "lost-answer") return route.abort("connectionreset");
    if (failure) return failureResponse(route, failure);
    cursorSerial += 1;
    const data = pullData ?? {};
    pullData = null;
    return json(route, 200, {
      cursor: `e2e-cursor-${cursorSerial}`,
      has_more: false,
      server_time: new Date().toISOString(),
      device: { ...STUB_DEVICE },
      ...data,
    });
  });

  return {
    pushed,
    committed,
    pushRequests,
    pullRequests,
    pushCsrfTokens,
    get online() {
      return !offline;
    },
    async setOffline(value: boolean) {
      offline = value;
      await page.context().setOffline(value);
    },
    failNextPush(failure) {
      pushFailures.push(failure);
    },
    failNextPull(failure) {
      pullFailures.push(failure);
    },
    revokeDevice() {
      revoked = true;
    },
    setPullData(data) {
      pullData = data;
    },
    expectEachCommittedOnce(expectedIds) {
      const counts = new Map<string, number>();
      for (const id of committed) counts.set(id, (counts.get(id) ?? 0) + 1);
      for (const [id, count] of counts) expect(count, `client_event_id ${id} committed ${count}×`).toBe(1);
      if (expectedIds) expect([...committed].sort()).toEqual([...expectedIds].sort());
    },
  };
}
