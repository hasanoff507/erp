import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { enqueueEvent } from "../outbox/enqueue.ts";
import { awaitEventResult, outbox } from "../outbox/queries.ts";
import { posDb } from "../runtime.ts";
import { rejected } from "../testing/fake-sync-server.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import { pushNow, rejectedRetryDelayMs } from "./push.ts";

const REGISTER = DEVICE.cashRegisterId ?? "";
const MINUTE = 60_000;

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

async function sell(n: number) {
  return enqueueEvent(
    "sale.created",
    { id: `sale-${n}`, shift_id: SHIFT_ID, lines: [{ product_id: "p1", qty: "1.000", price: "1000.00" }] },
    { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID } },
  );
}

describe("push (16 §3.1, 18 §2.6)", () => {
  it("sends events in seq order with outbox_state of the part not in the request", async () => {
    env.server.handler = () => null;
    for (let i = 1; i <= 3; i += 1) await sell(i);
    const outcome = await pushNow();
    expect(outcome).toEqual({ kind: "done", sent: 3 });
    const [request] = env.server.pushRequests;
    expect(request?.device_id).toBe(DEVICE.deviceId);
    expect(request?.events.map((e) => e.seq)).toEqual([1, 2, 3]);
    expect(Object.keys(request?.events[0] ?? {}).sort()).toEqual(
      ["actor_user_id", "client_event_id", "created_at", "device_id", "payload", "seq", "type"].sort(),
    );
    expect(request?.outbox_state).toEqual({ pending_count: 0, oldest_pending_created_at: null });
    const rows = await outbox.list();
    expect(rows.every((r) => r.status === "accepted" && r.unsynced === 0)).toBe(true);
    expect(rows[0]?.server).toEqual({ id: "srv-1", number: "K-1" });
  });

  it("splits into batches of ≤ 100 and reports the rest in outbox_state", async () => {
    for (let i = 1; i <= 230; i += 1) await sell(i);
    await pushNow();
    const sizes = env.server.pushRequests.map((r) => r.events.length);
    expect(sizes).toEqual([100, 100, 30]);
    expect(env.server.pushRequests[0]?.outbox_state.pending_count).toBe(130);
    expect(env.server.pushRequests[0]?.outbox_state.oldest_pending_created_at).toBe(
      env.server.pushRequests[1]?.events[0]?.created_at,
    );
    expect(env.server.pushRequests[2]?.outbox_state).toEqual({
      pending_count: 0,
      oldest_pending_created_at: null,
    });
  }, 30_000);

  it("keeps rejected events visible; a retryable one does not block later events and is retried after backoff", async () => {
    const a = await sell(1);
    const b = await sell(2);
    const c = await sell(3);
    env.server.handler = (event) => {
      if (event.client_event_id === a.clientEventId) return rejected(event, "SALE_NOT_FOUND", true);
      if (event.client_event_id === b.clientEventId) return rejected(event, "RECEIPT_SEQ_CONFLICT", false);
      return null;
    };
    await pushNow();
    expect(await outbox.get(a.clientEventId)).toMatchObject({
      status: "rejected",
      error_code: "SALE_NOT_FOUND",
      retryable: true,
      message: "errors.sale_not_found",
      unsynced: 1,
    });
    expect(await outbox.get(b.clientEventId)).toMatchObject({ status: "rejected", retryable: false });
    expect((await outbox.get(c.clientEventId))?.status).toBe("accepted");

    // next push before the backoff: nothing due → no request
    env.server.handler = () => null;
    const before = env.server.pushRequests.length;
    await pushNow();
    expect(env.server.pushRequests.length).toBe(before);

    // after the backoff: only the retryable one goes; the non-retryable waits for a manual retry
    env.clock.advance(rejectedRetryDelayMs(1) + 1);
    await pushNow();
    const last = env.server.pushRequests.at(-1);
    expect(last?.events.map((e) => e.client_event_id)).toEqual([a.clientEventId]);
    expect(last?.outbox_state.pending_count).toBe(1); // b is still not synced
    expect((await outbox.get(a.clientEventId))?.status).toBe("accepted");

    await outbox.retry(b.clientEventId);
    await pushNow();
    expect((await outbox.get(b.clientEventId))?.status).toBe("accepted");
  });

  it("treats a duplicate answer as done (same server result)", async () => {
    const a = await sell(1);
    env.server.pushFailures = [{ kind: "lost-answer" }];
    expect((await pushNow()).kind).toBe("retry");
    expect((await outbox.get(a.clientEventId))?.status).toBe("pending");
    await pushNow();
    expect(await outbox.get(a.clientEventId)).toMatchObject({ status: "duplicate", server: { id: "srv-1" } });
    expect(env.server.committed).toEqual([a.clientEventId]);
  });

  it("401 → one silent session probe then retry; failing probe → AUTH_REQUIRED with the outbox untouched", async () => {
    const a = await sell(1);
    env.server.pushFailures = [{ kind: "http", status: 401, code: "UNAUTHORIZED" }];
    expect(await pushNow()).toEqual({ kind: "done", sent: 1 });
    expect(env.server.refreshCalls).toBe(1);
    expect((await outbox.get(a.clientEventId))?.status).toBe("accepted");

    const b = await sell(2);
    env.server.sessionAlive = false;
    env.server.pushFailures = [{ kind: "http", status: 401, code: "UNAUTHORIZED" }];
    expect(await pushNow()).toEqual({ kind: "stopped", code: "AUTH_REQUIRED" });
    expect(await outbox.get(b.clientEventId)).toMatchObject({ status: "pending", attempts: 0 });
  });

  it("403 DEVICE_REVOKED stops; 429 returns Retry-After; network error retries; nothing is lost", async () => {
    const a = await sell(1);
    env.server.pushFailures = [{ kind: "http", status: 429, code: "RATE_LIMITED", retryAfterMs: 3000 }];
    expect(await pushNow()).toMatchObject({ kind: "retry", code: "RATE_LIMITED", retryAfterMs: 3000 });
    env.server.pushFailures = [{ kind: "network" }];
    expect(await pushNow()).toMatchObject({ kind: "retry", code: "NETWORK_ERROR" });
    env.server.pushFailures = [
      { kind: "http", status: 409, code: "IDEMPOTENCY_IN_PROGRESS", retryAfterMs: 1000 },
    ];
    expect(await pushNow()).toMatchObject({ kind: "retry", retryAfterMs: 1000 });
    env.server.pushFailures = [{ kind: "http", status: 403, code: "DEVICE_REVOKED" }];
    expect(await pushNow()).toEqual({ kind: "stopped", code: "DEVICE_REVOKED" });
    expect((await outbox.get(a.clientEventId))?.status).toBe("pending");
  });

  it("sends an empty heartbeat push with outbox_state when nothing is due", async () => {
    await pushNow({ heartbeat: true });
    expect(env.server.pushRequests).toEqual([
      {
        device_id: DEVICE.deviceId,
        events: [],
        outbox_state: { pending_count: 0, oldest_pending_created_at: null },
      },
    ]);
  });

  it("marks the fiscal ack carried in server.fiscal", async () => {
    const a = await sell(1);
    env.server.handler = (event) => ({
      client_event_id: event.client_event_id,
      status: "accepted",
      server: { id: "s", fiscal: { status: "fiscalized", ofd_acked_at: "2026-10-14T04:00:01Z" } },
      warnings: [],
    });
    await pushNow();
    expect(await outbox.get(a.clientEventId)).toMatchObject({
      fiscal_unacked: 0,
      ofd_acked_at: "2026-10-14T04:00:01Z",
    });
  });

  it("awaitEventResult resolves on the push result and times out with null while pending", async () => {
    const a = await sell(1);
    expect(await awaitEventResult(a.clientEventId, { timeoutMs: 10 })).toBeNull();
    const waiting = awaitEventResult(a.clientEventId, { timeoutMs: 5000 });
    await pushNow();
    expect(await waiting).toMatchObject({ client_event_id: a.clientEventId, status: "accepted" });
    expect(await awaitEventResult(a.clientEventId, { timeoutMs: 10 })).toMatchObject({ status: "accepted" });
  });
});

describe("B3-DoD-01 / B3-QT-M01-03: 2 h offline, then every sale reaches the server once and in order", () => {
  it("survives a long outage, lost answers and a crash between push and ack", async () => {
    const created: string[] = [];
    // 2 hours of selling while the network is down: one sale every 30 s, push attempts all fail
    for (let i = 1; i <= 240; i += 1) {
      const r = await sell(i);
      created.push(r.clientEventId);
      env.clock.advance(30_000);
      if (i % 20 === 0) {
        env.server.pushFailures = [{ kind: "network" }];
        expect((await pushNow()).kind).toBe("retry");
      }
    }
    expect(env.server.committed).toEqual([]);
    const local = await outbox.list();
    expect(local).toHaveLength(240);
    expect(
      local.every((r) => r.status === "pending" && r.created_at <= new Date(env.clock.now).toISOString()),
    ).toBe(true);

    // network back: first answer lost (server committed batch 1), then the tab "crashes" — rows untouched
    env.server.pushFailures = [{ kind: "lost-answer" }];
    expect((await pushNow()).kind).toBe("retry");
    expect(env.server.committed).toHaveLength(100);
    expect((await outbox.summary()).pending).toBe(240);

    // reload: the engine resumes from the outbox; batch 1 comes back as duplicates
    env.clock.advance(MINUTE);
    expect(await pushNow()).toEqual({ kind: "done", sent: 240 });

    expect(env.server.committed).toEqual(created); // exactly once, in seq order
    const rows = await outbox.list();
    expect(rows.filter((r) => r.status === "duplicate")).toHaveLength(100);
    expect(rows.filter((r) => r.status === "accepted")).toHaveLength(140);
    expect(await outbox.summary()).toEqual({
      pending: 0,
      rejected: 0,
      rejectedRetryable: 0,
      escalated: 0,
      oldestPendingAt: null,
    });
    // every request carried events in strictly increasing seq order
    for (const request of env.server.pushRequests) {
      const seqs = request.events.map((e) => e.seq);
      expect(seqs).toEqual([...seqs].sort((x, y) => x - y));
    }
    // receipt_seq stayed gap-free across the outage
    const receiptSeqs = (await posDb().outbox.orderBy("seq").toArray()).map((r) => r.receipt_seq);
    expect(receiptSeqs).toEqual(Array.from({ length: 240 }, (_, i) => i + 1));
  }, 30_000);
});
