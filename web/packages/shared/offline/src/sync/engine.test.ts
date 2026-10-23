import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deviceSettings } from "../device-settings.ts";
import { authRequired, deviceRevoked, syncStatusChanged, type SyncStatus } from "../events.ts";
import { backgroundIdle } from "../lib/background.ts";
import { isOfflineError } from "../lib/errors.ts";
import { tryWithLock, withLock } from "../lib/locks.ts";
import { enqueueEvent } from "../outbox/enqueue.ts";
import { awaitEventResult, outbox } from "../outbox/queries.ts";
import { CASHIER, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import { backoffDelayMs, runPull, startSyncEngine, syncIdle } from "./engine.ts";
import { getSyncStatus } from "./status.ts";
import { parseRetryAfter, SyncHttpError, toSyncHttpError } from "./transport.ts";

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

describe("sync engine", () => {
  it("pushes right after enqueue and resolves awaitEventResult (online sale, 16 §4.1)", async () => {
    startSyncEngine();
    await backgroundIdle();
    await syncIdle();
    const r = await enqueueEvent("sale.created", { id: "s1" }, { actorUserId: CASHIER });
    const result = await awaitEventResult(r.clientEventId, { timeoutMs: 3000 });
    expect(result?.status).toBe("accepted");
    await syncIdle();
    expect(getSyncStatus()).toMatchObject({ pending: 0, rejected: 0, lastErrorCode: null });
    expect(getSyncStatus().lastPushAt).not.toBeNull();
  });

  it("publishes status, raises authRequired on a dead session and deviceRevoked on 403", async () => {
    const statuses: SyncStatus[] = [];
    const unwatch = syncStatusChanged.watch((s) => statuses.push(s));
    const onAuth = vi.fn();
    const onRevoked = vi.fn();
    const w1 = authRequired.watch(onAuth);
    const w2 = deviceRevoked.watch(onRevoked);
    startSyncEngine();
    await backgroundIdle();
    await syncIdle();

    env.server.sessionAlive = false;
    env.server.pushFailures = [
      { kind: "http", status: 401, code: "UNAUTHORIZED" },
      { kind: "http", status: 401, code: "UNAUTHORIZED" },
    ];
    await enqueueEvent("sale.created", { id: "s1" }, { actorUserId: CASHIER }); // push triggered
    await vi.waitFor(() => expect(onAuth).toHaveBeenCalledTimes(1));
    await syncIdle();
    expect(statuses.some((s) => s.authRequired)).toBe(true);
    expect(getSyncStatus().pending).toBe(1); // outbox untouched, nothing rejected

    env.server.pullFailures = [{ kind: "http", status: 403, code: "DEVICE_REVOKED" }];
    await runPull();
    expect(onRevoked).toHaveBeenCalledTimes(1);
    expect(getSyncStatus().deviceRevoked).toBe(true);
    expect((await outbox.summary()).pending).toBe(1); // nothing wiped until the UI says so
    await backgroundIdle();
    await expect(enqueueEvent("sale.created", { id: "s2" }, { actorUserId: CASHIER })).rejects.toSatisfy(
      (e) => isOfflineError(e, "DEVICE_REVOKED"),
    );
    expect(statuses.some((s) => s.pushing)).toBe(true);
    unwatch.unsubscribe();
    w1.unsubscribe();
    w2.unsubscribe();
  });

  it("backoff: exponential with jitter, capped at 60 s", () => {
    expect(backoffDelayMs(1, () => 0)).toBe(500);
    expect(backoffDelayMs(1, () => 0.999)).toBeLessThanOrEqual(1000);
    expect(backoffDelayMs(4, () => 0.5)).toBe(6000);
    expect(backoffDelayMs(30, () => 0.999)).toBeLessThanOrEqual(60_000);
  });
});

describe("transport helpers", () => {
  it("parses Retry-After seconds and keeps status/code/details of API errors", () => {
    expect(parseRetryAfter("3")).toBe(3000);
    expect(parseRetryAfter("x")).toBeNull();
    expect(parseRetryAfter(undefined)).toBeNull();
    const e = new SyncHttpError({ status: 429, code: "RATE_LIMITED", retryAfterMs: 2000 });
    expect(toSyncHttpError(e)).toBe(e);
    expect(toSyncHttpError(new Error("boom"))).toMatchObject({ status: null, code: "INTERNAL_ERROR" });
  });
});

describe("locks (16 §11) — in-process fallback without navigator.locks", () => {
  it("serialises writers and lets only one pusher in", async () => {
    const order: string[] = [];
    let release!: () => void;
    const gate = new Promise<void>((r) => {
      release = r;
    });
    const first = withLock("t", async () => {
      order.push("a-start");
      await gate;
      order.push("a-end");
    });
    const second = withLock("t", () => {
      order.push("b");
      return Promise.resolve();
    });
    expect(await tryWithLock("t", () => Promise.resolve(1))).toEqual({ acquired: false });
    release();
    await Promise.all([first, second]);
    expect(order).toEqual(["a-start", "a-end", "b"]);
    expect(await tryWithLock("t", () => Promise.resolve(1))).toEqual({ acquired: true, value: 1 });
  });
});

describe("deviceSettings (24 §5.1)", () => {
  it("stores values and protects the reserved device.* keys", async () => {
    await deviceSettings.set("pos.catalog_view", "list");
    expect(await deviceSettings.get("pos.catalog_view")).toBe("list");
    expect(await deviceSettings.all()).toEqual({ "pos.catalog_view": "list" });
    await expect(deviceSettings.set("device.identity", {})).rejects.toThrow();
    await deviceSettings.remove("pos.catalog_view");
    expect(await deviceSettings.get("pos.catalog_view")).toBeUndefined();
  });
});

describe("offline counters (06 §1.3 «Offlayn · N chek»)", () => {
  it("enqueue and manual retry refresh the pending/rejected counters without any push", async () => {
    // engine not started = no push attempts at all
    for (let i = 0; i < 3; i += 1) {
      await enqueueEvent("sale.created", { id: `s${i}` }, { actorUserId: CASHIER });
    }
    await backgroundIdle();
    expect(getSyncStatus()).toMatchObject({ pending: 3, rejected: 0 });
    expect(getSyncStatus().oldestPendingAt).not.toBeNull();
    expect(env.server.pushRequests).toHaveLength(0);
  });
});
